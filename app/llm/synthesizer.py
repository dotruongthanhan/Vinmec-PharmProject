"""Điều phối bước LLM tổng hợp kèm vòng thử lại kiểm chứng và ghép phát hiện luật."""

from pathlib import Path

from pydantic import ValidationError

from app.config.settings import CaseContextSettings
from app.core.errors import ProviderError
from app.core.interfaces import LLMClient
from app.core.types import ChatMessage, Chunk
from app.domain.models import CaBenh
from app.llm.case_context import build_case_context
from app.llm.prompt_loader import load_prompt, render_prompt
from app.llm.schema import (
    KetQuaLLM,
    KetQuaTongHop,
    NhanDinhCuoi,
    NhanDinhDaKiem,
    json_schema_for_llm,
)
from app.pipeline import KetQuaThamDinh
from app.rules.types import PhatHien
from app.verify.merge import merge
from app.verify.pipeline import verify_all

_DATA_SPLIT_MARKER = "\n## DỮ LIỆU ĐẦU VÀO\n"
_FALLBACK_SYSTEM_PROMPT = "Bạn là trợ lý cho dược sĩ lâm sàng thẩm định y lệnh."


def _rule_only_findings(phat_hien: list[PhatHien]) -> list[NhanDinhCuoi]:
    """Bọc nguyên vẹn các phát hiện của bộ luật thành NhanDinhCuoi."""
    return [NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in phat_hien]


def _select_evidence(doan: list[Chunk], evidence_max_chars: int) -> tuple[list[Chunk], str]:
    """Chọn tuần tự các đoạn nguồn tới khi chạm trần evidence_max_chars và định dạng văn bản."""
    selected: list[Chunk] = []
    blocks: list[str] = []
    total_chars = 0
    for chunk in doan:
        chunk_len = len(chunk.noi_dung_goc)
        if total_chars + chunk_len > evidence_max_chars:
            break
        selected.append(chunk)
        total_chars += chunk_len
        blocks.append(
            f"[{chunk.doan_trich_id}] (tầng {chunk.tang_tin_cay}, {chunk.duong_dan_muc})\n"
            f"{chunk.noi_dung_goc}"
        )
    text = "\n\n".join(blocks) if blocks else "(không có đoạn nguồn)"
    return selected, text


def _build_messages(
    template: str,
    van_ban_ca: str,
    doan_nguon: str,
    loi_lan_truoc: str,
) -> list[ChatMessage]:
    """Tách phần chỉ thị hệ thống và dữ liệu ca bệnh để gửi cho mô hình."""
    if _DATA_SPLIT_MARKER in template:
        sys_part, user_template = template.split(_DATA_SPLIT_MARKER, maxsplit=1)
        user_content = render_prompt(
            user_template,
            van_ban_ca=van_ban_ca,
            doan_nguon=doan_nguon,
            loi_lan_truoc=loi_lan_truoc,
        ).strip()
        return [
            ChatMessage(role="system", content=sys_part.strip()),
            ChatMessage(role="user", content=user_content),
        ]

    rendered = render_prompt(
        template,
        van_ban_ca=van_ban_ca,
        doan_nguon=doan_nguon,
        loi_lan_truoc=loi_lan_truoc,
    )
    return [
        ChatMessage(role="system", content=_FALLBACK_SYSTEM_PROMPT),
        ChatMessage(role="user", content=rendered),
    ]


class Synthesizer:
    """Chạy bước LLM tổng hợp có kiểm chứng bằng code và giữ nguyên phát hiện luật."""

    def __init__(
        self,
        llm: LLMClient | None,
        prompt_path: Path,
        case_settings: CaseContextSettings,
        evidence_max_chars: int,
        max_synthesis_attempts: int,
        model_name: str | None,
    ) -> None:
        self.llm = llm
        self.prompt_path = Path(prompt_path)
        self.case_settings = case_settings
        self.evidence_max_chars = evidence_max_chars
        self.max_synthesis_attempts = max_synthesis_attempts
        self.model_name = model_name

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh, doan: list[Chunk]) -> KetQuaLLM:
        """Tổng hợp, kiểm chứng và ghép với phát hiện luật; không bao giờ ném ngoại lệ."""
        phien_ban_prompt = self.prompt_path.stem
        try:
            phien_ban_prompt, template = load_prompt(self.prompt_path)
        except Exception as exc:
            return KetQuaLLM(
                trang_thai="loi_llm",
                nhan_dinh=_rule_only_findings(ket_qua.phat_hien),
                so_lan_goi=0,
                canh_bao=[f"Không đọc được prompt: {type(exc).__name__}"],
                phien_ban_prompt=phien_ban_prompt,
                mo_hinh=self.model_name,
            )

        if self.llm is None:
            return KetQuaLLM(
                trang_thai="khong_co_llm",
                nhan_dinh=_rule_only_findings(ket_qua.phat_hien),
                so_lan_goi=0,
                canh_bao=[],
                phien_ban_prompt=phien_ban_prompt,
                mo_hinh=None,
            )

        try:
            return self._run_with_llm(ca, ket_qua, doan, phien_ban_prompt, template)
        except Exception as exc:
            return KetQuaLLM(
                trang_thai="loi_llm",
                nhan_dinh=_rule_only_findings(ket_qua.phat_hien),
                so_lan_goi=0,
                canh_bao=[f"Lỗi tổng hợp LLM: {type(exc).__name__}"],
                phien_ban_prompt=phien_ban_prompt,
                mo_hinh=self.model_name,
            )

    def _run_with_llm(
        self,
        ca: CaBenh,
        ket_qua: KetQuaThamDinh,
        doan: list[Chunk],
        phien_ban_prompt: str,
        template: str,
    ) -> KetQuaLLM:
        """Thực thi vòng gọi LLM, kiểm chứng và ghép kết quả."""
        assert self.llm is not None
        goi, warnings = build_case_context(ca, ket_qua, self.case_settings)
        selected_chunks, doan_nguon_text = _select_evidence(doan, self.evidence_max_chars)
        goi = goi.model_copy(update={"doan": selected_chunks})

        schema = json_schema_for_llm()
        attempts = max(1, self.max_synthesis_attempts)
        kept_passed: list[NhanDinhDaKiem] = []
        kept_signatures: set[str] = set()
        last_failed: list[NhanDinhDaKiem] = []
        previous_errors = "Không có."
        so_lan_goi = 0
        schema_failed_last = False

        for _attempt in range(attempts):
            messages = _build_messages(template, goi.van_ban_ca, doan_nguon_text, previous_errors)
            so_lan_goi += 1
            try:
                raw = self.llm.complete_json(messages, schema)
            except ProviderError as exc:
                code = str(exc)
                if code == "het_han_muc_token":
                    warnings.append(
                        "Bước AI bị cắt vì vượt hạn mức độ dài; đang hiển thị kết quả của bộ luật."
                    )
                else:
                    safe_code = (
                        code if code.isascii() and code.isidentifier() else "loi_nha_cung_cap"
                    )
                    warnings.append(
                        f"Bước AI gặp lỗi ({safe_code}); đang hiển thị kết quả của bộ luật."
                    )
                merged, merge_warnings = merge(ket_qua.phat_hien, kept_passed)
                warnings.extend(merge_warnings)
                return KetQuaLLM(
                    trang_thai="loi_llm",
                    nhan_dinh=merged,
                    so_lan_goi=so_lan_goi,
                    canh_bao=warnings,
                    phien_ban_prompt=phien_ban_prompt,
                    mo_hinh=self.model_name,
                )
            except Exception as exc:
                warnings.append(f"Lỗi LLM không mong muốn: {type(exc).__name__}")
                merged, merge_warnings = merge(ket_qua.phat_hien, kept_passed)
                warnings.extend(merge_warnings)
                return KetQuaLLM(
                    trang_thai="loi_llm",
                    nhan_dinh=merged,
                    so_lan_goi=so_lan_goi,
                    canh_bao=warnings,
                    phien_ban_prompt=phien_ban_prompt,
                    mo_hinh=self.model_name,
                )

            try:
                tong_hop = KetQuaTongHop.model_validate(raw)
            except ValidationError:
                schema_failed_last = True
                previous_errors = "Lần trước: sai_luoc_do"
                continue

            schema_failed_last = False
            checked = verify_all(tong_hop, goi)
            current_failed: list[NhanDinhDaKiem] = []
            error_lines: list[str] = []
            for idx, item in enumerate(checked):
                if item.dat:
                    signature = item.de_xuat.model_dump_json()
                    if signature not in kept_signatures:
                        kept_signatures.add(signature)
                        kept_passed.append(item)
                else:
                    current_failed.append(item)
                    error_lines.append(f"Dòng {idx}: {', '.join(item.loi)}")

            last_failed = current_failed
            if not current_failed:
                break
            previous_errors = (
                "Các dòng đã đạt ở lần trước đã được giữ; chỉ cần sửa các dòng lỗi sau:\n"
                + "\n".join(error_lines)
            )

        if schema_failed_last and not kept_passed and not last_failed:
            warnings.append("sai_luoc_do")
            return KetQuaLLM(
                trang_thai="dau_ra_khong_hop_le",
                nhan_dinh=_rule_only_findings(ket_qua.phat_hien),
                so_lan_goi=so_lan_goi,
                canh_bao=warnings,
                phien_ban_prompt=phien_ban_prompt,
                mo_hinh=self.model_name,
            )

        if schema_failed_last:
            warnings.append("sai_luoc_do")

        merged, merge_warnings = merge(ket_qua.phat_hien, [*kept_passed, *last_failed])
        warnings.extend(merge_warnings)
        return KetQuaLLM(
            trang_thai="ok",
            nhan_dinh=merged,
            so_lan_goi=so_lan_goi,
            canh_bao=warnings,
            phien_ban_prompt=phien_ban_prompt,
            mo_hinh=self.model_name,
        )
