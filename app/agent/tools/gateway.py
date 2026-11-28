"""Chốt an toàn duy nhất giữa LLM và công cụ: quyền, ngân sách, PII, chèn lệnh và kiểm toán."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextvars import copy_context
from datetime import datetime
from threading import Lock
from typing import Any

from pydantic import ValidationError

from app.agent.minh_hoa.kiem import LoiDacTa
from app.agent.minh_hoa.models import BoDuLieu, KhoiMinhHoa
from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.agent.tools.ve_bieu_do import ThamSoVeBieuDo, VeBieuDo
from app.core.progress import ghi_buoc
from app.core.types import Chunk
from app.deid.scrubber import TOKEN_PATTERN, DeidError
from app.deid.session import DeidSession
from app.orchestration.ask import _has_injection_directive
from app.tracing import bam_du_lieu, ghi_su_kien_bao_mat, span, vet_hien_tai

_AUDIT_LOGGER = logging.getLogger("app.agent.audit")
_DEID_TOKEN_RE = re.compile(TOKEN_PATTERN)
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_MAX_TOOL_OUTPUT_CHARS = 8000
_SCRUB_FALLBACK = "[không đưa được kết quả vào vì lỗi che định danh]"
_INJECTION_BLOCKED_MESSAGE = "Kết quả công cụ có câu giống chỉ thị nên bị loại."
_BLOCK_MARKERS = (
    "<<<DU_LIEU_BENH_AN",
    "DU_LIEU_BENH_AN>>>",
    "<<<DOAN_NGUON",
    "DOAN_NGUON>>>",
    "<<<LICH_SU",
    "LICH_SU>>>",
    "<<<CAU_HOI",
    "CAU_HOI>>>",
    "<<<KET_QUA_CONG_CU",
    "KET_QUA_CONG_CU>>>",
)
_SAFE_STEP_REASONS: dict[str, str] = {
    "khong_co_cong_cu": "Công cụ không tồn tại",
    "khong_co_quyen": "Không có quyền gọi công cụ",
    "het_ngan_sach": "Đã hết lượt gọi công cụ",
    "het_gio": "Hết thời gian xử lý công cụ",
    "sai_tham_so": "Tham số công cụ không hợp lệ",
    "tham_so_co_dinh_danh": "Tham số chứa định danh người bệnh",
    "nghi_chen_lenh": "Kết quả công cụ bị nghi chèn lệnh",
    "loi_cong_cu": "Công cụ gặp lỗi khi thực thi",
}


def _normalize_illustration(spec: dict[str, Any], datasets: Mapping[str, BoDuLieu]) -> str | None:
    """So đặc tả và nội dung bộ dữ liệu, không phụ thuộc mã ds."""

    def replace_ids(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    datasets[item].model_dump(exclude={"ma"}, mode="json")
                    if key in {"ds", "du_lieu"} and isinstance(item, str) and item in datasets
                    else replace_ids(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [replace_ids(item) for item in value]
        return value

    try:
        return json.dumps(
            replace_ids(spec),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError):
        return None


def _sanitize_markers(text: str) -> str:
    """Loại bỏ các chuỗi phân tách khối dữ liệu khỏi văn bản kết quả công cụ."""
    cleaned = text
    for marker in _BLOCK_MARKERS:
        while marker in cleaned:
            cleaned = cleaned.replace(marker, "[đã bỏ ký hiệu]")
    return cleaned


def _scrub_dataset_cell(text: str, session: DeidSession, can_cu: Sequence[CanCu]) -> str:
    """Che cả định danh mới khi ô đã có mã tạm; giữ nguyên mã căn cứ."""
    protected, placeholders = _protect_evidence_codes(text, can_cu)
    parts = _DEID_TOKEN_RE.split(protected)
    tokens = _DEID_TOKEN_RE.findall(protected)
    masked: list[str] = []
    for index, part in enumerate(parts):
        masked.append(session.scrub(part))
        if index < len(tokens):
            masked.append(tokens[index])
    return _sanitize_markers(_restore_evidence_codes("".join(masked), placeholders))


def _is_iso_time(value: str) -> bool:
    """Chỉ chấp nhận ngày hoặc thời điểm ISO đầy đủ trong cột thời gian."""
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?)?",
        value,
    ):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _alpha_index(index: int) -> str:
    """Đổi số nguyên không âm sang chuỗi chỉ gồm chữ cái thường (a, b, ..., z, aa, ...)."""
    chars: list[str] = []
    num = index
    while True:
        chars.append(chr(ord("a") + (num % 26)))
        num = num // 26 - 1
        if num < 0:
            break
    return "".join(reversed(chars))


def _protect_evidence_codes(text: str, can_cu: Sequence[CanCu]) -> tuple[str, dict[str, str]]:
    """Thay mã căn cứ còn giữ bằng ký hiệu giữ chỗ không chữ số trước khi che PII."""
    codes = sorted(
        {cc.ma for cc in can_cu if cc.ma and cc.ma in text},
        key=lambda ma: (-len(ma), ma),
    )
    if not codes:
        return text, {}
    code_to_placeholder: dict[str, str] = {}
    placeholder_to_code: dict[str, str] = {}
    counter = 0
    for code in codes:
        while True:
            placeholder = f"⟦macancu{_alpha_index(counter)}⟧"
            counter += 1
            if placeholder not in text and placeholder not in placeholder_to_code:
                break
        code_to_placeholder[code] = placeholder
        placeholder_to_code[placeholder] = code
    pattern = re.compile("|".join(re.escape(code) for code in codes))
    protected = pattern.sub(lambda match: code_to_placeholder[match.group(0)], text)
    return protected, placeholder_to_code


def _restore_evidence_codes(text: str, placeholder_to_code: Mapping[str, str]) -> str:
    """Trả lại mã căn cứ gốc từ ký hiệu giữ chỗ sau khi che PII."""
    if not placeholder_to_code:
        return text
    pattern = re.compile("|".join(re.escape(ph) for ph in placeholder_to_code))
    return pattern.sub(lambda match: placeholder_to_code[match.group(0)], text)


def _iter_strings(value: Any) -> Iterator[str]:
    """Duyệt mọi chuỗi nằm trong giá trị tham số kể cả lồng trong list/dict."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_strings(item)


def _string_has_pii(text: str, session: DeidSession) -> bool:
    """Kiểm tra chuỗi tham số có chứa định danh thật ngoài mã tạm hợp lệ hay không."""
    try:
        if session.mask_known(text) != text:
            return True
        if _DEID_TOKEN_RE.search(text) is None and session.scrub(text) != text:
            return True
    except DeidError:
        return True
    return False


def _params_contain_pii(data: Any, session: DeidSession) -> bool:
    """Quét PII trên toàn bộ chuỗi trong tham số đã xác thực."""
    return any(_string_has_pii(text, session) for text in _iter_strings(data))


def _hash_case_id(ctx: ToolContext) -> str:
    """Băm mã ca sang 12 ký tự hex để ghi nhật ký kiểm toán."""
    if ctx.ca is not None and ctx.ca.ca_id:
        return hashlib.sha256(ctx.ca.ca_id.encode("utf-8")).hexdigest()[:12]
    return "-"


def _run_tool_with_timeout(
    tool: Tool,
    tham_so: Any,
    ctx: ToolContext,
    timeout: float,
    doan_goc: Chunk | None = None,
) -> KetQuaCongCu:
    """Chạy công cụ trong luồng phụ với giới hạn thời gian như CaseAsker._run_with_deadline."""
    if timeout <= 0:
        raise TimeoutError("Hết thời gian xử lý công cụ")
    executor = ThreadPoolExecutor(max_workers=1)
    ctx_copy = copy_context()
    if tool.chi_doan_da_tra:
        future = executor.submit(ctx_copy.run, tool.chay, tham_so, ctx, doan_goc=doan_goc)
    else:
        future = executor.submit(ctx_copy.run, tool.chay, tham_so, ctx)
    try:
        result = future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError("Công cụ chạy quá thời gian cho phép") from exc
    else:
        executor.shutdown(wait=False)
        return result


def _run_illustration_with_timeout(
    tool: VeBieuDo,
    params: ThamSoVeBieuDo,
    datasets: Mapping[str, BoDuLieu],
    evidence: set[str],
    timeout: float,
) -> KhoiMinhHoa | LoiDacTa:
    """Kiểm đặc tả trong thời gian còn lại, không sửa trạng thái trong luồng phụ."""
    if timeout <= 0:
        raise TimeoutError
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(copy_context().run, tool.tao, params, datasets, evidence)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        raise TimeoutError from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


class ToolGateway:
    """Chốt kiểm soát duy nhất cho mọi lần gọi công cụ trong một lượt hỏi đáp."""

    def __init__(
        self,
        danh_muc: DanhMucCongCu,
        chinh_sach: ChinhSachCongCu,
        so_lan_goi_toi_da: int,
    ) -> None:
        self._danh_muc = danh_muc
        self._chinh_sach = chinh_sach
        self._so_lan_goi_toi_da = max(0, so_lan_goi_toi_da)
        self._so_lan_da_goi = 0
        self._so_lan_ve_bi_tu_choi = 0
        self._so_lan_trung_hinh = 0
        self._so_thu_tu_buoc = 0
        self._lock = Lock()
        self._doan_da_tra: set[str] = set()
        self._doan_goc: dict[str, Chunk] = {}
        self._bo_du_lieu: dict[str, BoDuLieu] = {}
        self._minh_hoa: list[KhoiMinhHoa] = []
        self._ma_can_cu: set[str] = set()
        self._ket_qua_da_goi: dict[tuple[Any, ...], KetQuaCongCu] = {}

    @property
    def bo_du_lieu(self) -> dict[str, BoDuLieu]:
        """Các bộ dữ liệu đã che trong lượt hiện tại."""
        with self._lock:
            return dict(self._bo_du_lieu)

    @property
    def minh_hoa(self) -> list[KhoiMinhHoa]:
        """Các khối đã kiểm trong lượt hiện tại."""
        with self._lock:
            return list(self._minh_hoa)

    def xoa_minh_hoa(self) -> None:
        """Bỏ hình của lần trả lời không đạt kiểm chứng."""
        with self._lock:
            self._minh_hoa.clear()

    def _audit(
        self,
        ten: str,
        ctx: ToolContext,
        ket_qua_nhan: str,
        so_can_cu: int,
        elapsed_ms: int,
    ) -> None:
        """Ghi đúng một dòng nhật ký kiểm toán mức INFO, không chứa nội dung hay tham số."""
        _AUDIT_LOGGER.info(
            "tool=%s vai_tro=%s che_do=%s ca=%s ket_qua=%s can_cu=%d thoi_gian_ms=%d",
            ten,
            ctx.vai_tro,
            ctx.che_do,
            _hash_case_id(ctx),
            ket_qua_nhan,
            so_can_cu,
            elapsed_ms,
        )

    def goi(
        self,
        ten: str,
        tham_so_tho: dict[str, Any],
        ctx: ToolContext,
    ) -> KetQuaCongCu:
        """Kiểm tra quyền, ngân sách, lược đồ, PII; chạy tool; hậu xử lý và ghi kiểm toán."""
        perf_start = time.perf_counter()
        with self._lock:
            self._so_thu_tu_buoc += 1
            step_no = self._so_thu_tu_buoc
        ma_buoc = f"cong_cu_{step_no}"
        tool = self._danh_muc.lay(ten)
        span_ten = ten if tool is not None else "khong_co_cong_cu"
        vet = vet_hien_tai.get()
        if vet is not None:
            vet.tang_so_tool()

        def _elapsed_ms() -> int:
            return int((time.perf_counter() - perf_start) * 1000.0)

        with span(
            "tool",
            span_ten,
            ten_cong_cu=span_ten,
            bam_tham_so=bam_du_lieu(tham_so_tho),
            vai_tro=ctx.vai_tro,
            che_do=ctx.che_do,
        ) as tool_span:

            def _reject(
                ma_loi: str,
                message: str,
                *,
                khoa_tham_so: list[str] | None = None,
            ) -> KetQuaCongCu:
                if isinstance(tool, VeBieuDo) and ma_loi not in ("het_luot_ve", "trung_hinh"):
                    with self._lock:
                        self._so_lan_ve_bi_tu_choi += 1
                ghi_buoc("bat_dau", ma_buoc, ten="Gọi công cụ bị từ chối")
                ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS.get(ma_loi, "Bị từ chối"))
                tool_span.dat_trang_thai("tu_choi")
                attrs: dict[str, Any] = {
                    "trang_thai_cong_cu": "tu_choi",
                    "ma_loi": ma_loi,
                    "kich_thuoc_ket_qua": 0,
                    "bi_cat": False,
                    "ma_can_cu": [],
                    "so_can_cu": 0,
                }
                if khoa_tham_so is not None:
                    attrs["khoa_tham_so"] = khoa_tham_so
                tool_span.dat_thuoc_tinh(**attrs)
                if ma_loi == "tham_so_co_dinh_danh":
                    ghi_su_kien_bao_mat(
                        "pii_trong_tham_so_cong_cu",
                        nguon="tool_gateway",
                        ten_cong_cu=span_ten,
                        ma_loi=ma_loi,
                    )
                    if vet is not None:
                        vet.tang_so_bi_chan()
                elif ma_loi == "khong_co_quyen":
                    ghi_su_kien_bao_mat(
                        "vuot_quyen_cong_cu",
                        nguon="tool_gateway",
                        ten_cong_cu=span_ten,
                        ma_loi=ma_loi,
                    )
                    if vet is not None:
                        vet.tang_so_bi_chan()
                res = KetQuaCongCu(trang_thai="tu_choi", ma_loi=ma_loi, noi_dung=message)
                self._audit(ten, ctx, f"tu_choi:{ma_loi}", 0, _elapsed_ms())
                return res

            # 1. Kiểm tra công cụ có trong danh mục.
            if tool is None:
                return _reject("khong_co_cong_cu", "Công cụ không tồn tại trong danh mục.")

            # 2. Kiểm tra quyền theo vai trò và chế độ.
            if (
                not self._chinh_sach.cho_phep(ctx.vai_tro, ctx.che_do, ten)
                or ctx.che_do not in tool.che_do_cho_phep
            ):
                return _reject(
                    "khong_co_quyen",
                    "Vai trò hoặc chế độ hiện tại không được phép gọi công cụ này.",
                )

            # 3. Kiểm tra ngân sách lượt gọi và hạn chót thời gian.
            if isinstance(tool, VeBieuDo):
                with self._lock:
                    het_luot_ve = self._so_lan_ve_bi_tu_choi >= 2
                if het_luot_ve:
                    return _reject(
                        "het_luot_ve", "het_luot_ve: không vẽ thêm, hãy trả lời bằng chữ"
                    )
            with self._lock:
                if (
                    not isinstance(tool, VeBieuDo)
                    and self._so_lan_da_goi >= self._so_lan_goi_toi_da
                ):
                    return _reject(
                        "het_ngan_sach",
                        "Đã hết số lần gọi công cụ cho phép trong lượt này.",
                    )
            if time.monotonic() >= ctx.han_chot:
                return _reject("het_gio", "Đã hết thời gian xử lý của lượt hỏi.")

            # 4. Xác thực tham số theo LuocDoThamSo; không lặp lại giá trị đầu vào.
            if not isinstance(tham_so_tho, Mapping):
                return _reject("sai_tham_so", "Tham số công cụ không hợp lệ ở trường: tham_so.")
            try:
                tham_so = tool.LuocDoThamSo.model_validate(tham_so_tho)
            except ValidationError as exc:
                fields = sorted(
                    {
                        ".".join(str(part) for part in err["loc"]) or "tham_so"
                        for err in exc.errors(include_input=False, include_context=False)
                    }
                )
                return _reject(
                    "sai_tham_so",
                    f"Tham số công cụ không hợp lệ ở trường: {', '.join(fields)}.",
                )

            doan_goc = None
            if tool.chi_doan_da_tra:
                ma = getattr(tham_so, "doan_trich_id", None)
                with self._lock:
                    if ma in self._doan_da_tra:
                        doan_goc = self._doan_goc.get(ma)
                if doan_goc is None:
                    return _reject("sai_tham_so", "Chỉ mở được đoạn đã trả trong lượt này.")

            # 5. Quét PII trong toàn bộ chuỗi tham số (bỏ qua doan_trich_id đã chốt ở bước 4).
            session = ctx.deid_session if ctx.deid_session is not None else DeidSession()
            params_for_pii = tham_so.model_dump()
            khoa_tham_so = sorted(params_for_pii.keys())
            if tool.chi_doan_da_tra and doan_goc is not None:
                params_for_pii = {k: v for k, v in params_for_pii.items() if k != "doan_trich_id"}
            if _params_contain_pii(params_for_pii, session):
                return _reject(
                    "tham_so_co_dinh_danh",
                    "Tham số công cụ có chứa định danh người bệnh nên bị từ chối.",
                    khoa_tham_so=khoa_tham_so,
                )

            tool_span.dat_thuoc_tinh(khoa_tham_so=khoa_tham_so)
            if not isinstance(tool, VeBieuDo):
                tool_span.dat_noi_dung({"tham_so_da_che": tham_so.model_dump(mode="json")})

            # Chiếm một lượt ngân sách và bắt đầu bước tiến trình chạy công cụ.
            with self._lock:
                if (
                    not isinstance(tool, VeBieuDo)
                    and self._so_lan_da_goi >= self._so_lan_goi_toi_da
                ):
                    return _reject(
                        "het_ngan_sach",
                        "Đã hết số lần gọi công cụ cho phép trong lượt này.",
                        khoa_tham_so=khoa_tham_so,
                    )
                if not isinstance(tool, VeBieuDo):
                    self._so_lan_da_goi += 1

            ghi_buoc("bat_dau", ma_buoc, ten=tool.ten_hien_thi)

            cache_key = None
            if not isinstance(tool, VeBieuDo):
                try:
                    params_key = json.dumps(
                        tham_so.model_dump(mode="json"),
                        sort_keys=True,
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                    cache_key = (
                        ten,
                        params_key,
                        ctx.vai_tro,
                        ctx.che_do,
                        id(ctx.ca),
                        id(ctx.ket_qua_luat),
                        id(ctx.ai_result),
                        id(ctx.deid_session),
                        ctx.nhan_dinh_id,
                        ctx.cau_hoi_goc,
                        ctx.lich_su_goc,
                        tuple(id(case) for case in ctx.cac_ca),
                        tuple(sorted((key, id(value)) for key, value in ctx.cac_ket_qua.items())),
                    )
                except (TypeError, ValueError):
                    pass
                with self._lock:
                    cached = self._ket_qua_da_goi.get(cache_key) if cache_key else None
                if cached is not None:
                    ghi_buoc("xong", ma_buoc, chi_tiet="Dùng kết quả đã có")
                    tool_span.dat_trang_thai("ok")
                    self._audit(ten, ctx, "cho_phep", len(cached.can_cu), _elapsed_ms())
                    return cached.model_copy(
                        deep=True,
                        update={"noi_dung": cached.noi_dung + "\nKết quả đã có ở lần gọi trước."},
                    )

            if isinstance(tool, VeBieuDo) and isinstance(tham_so, ThamSoVeBieuDo):
                with self._lock:
                    full = len(self._minh_hoa) >= 3
                    datasets_snapshot = dict(self._bo_du_lieu)
                    evidence_snapshot = set(self._ma_can_cu)
                    normalized = _normalize_illustration(tham_so.dac_ta, datasets_snapshot)
                    duplicate = next(
                        (
                            block.ma
                            for block in self._minh_hoa
                            if normalized is not None
                            and _normalize_illustration(block.dac_ta, datasets_snapshot)
                            == normalized
                        ),
                        None,
                    )
                    if duplicate is not None:
                        self._so_lan_trung_hinh += 1
                        duplicate_count = self._so_lan_trung_hinh
                if duplicate is not None:
                    tool_span.dat_thuoc_tinh(so_lan_trung_hinh=duplicate_count)
                    ghi_buoc("xong", ma_buoc, chi_tiet="Hình đã có")
                    tool_span.dat_trang_thai("ok")
                    self._audit(ten, ctx, "cho_phep", 0, _elapsed_ms())
                    return KetQuaCongCu(
                        trang_thai="ok", noi_dung=f"Đã vẽ ở {duplicate}, không vẽ lại."
                    )
                try:
                    outcome: KhoiMinhHoa | LoiDacTa = (
                        LoiDacTa(ly_do="qua_3_khoi")
                        if full
                        else _run_illustration_with_timeout(
                            tool,
                            tham_so,
                            datasets_snapshot,
                            evidence_snapshot,
                            min(tool.thoi_gian_toi_da, ctx.han_chot - time.monotonic()),
                        )
                    )
                except TimeoutError:
                    return _reject("het_gio", "Công cụ xử lý quá thời gian cho phép.")
                except Exception:
                    return _reject("loi_cong_cu", "Công cụ gặp lỗi khi thực thi.")
                if isinstance(outcome, KhoiMinhHoa):
                    with self._lock:
                        duplicate = next(
                            (
                                block.ma
                                for block in self._minh_hoa
                                if normalized is not None
                                and _normalize_illustration(block.dac_ta, datasets_snapshot)
                                == normalized
                            ),
                            None,
                        )
                        if duplicate is not None:
                            self._so_lan_trung_hinh += 1
                            duplicate_count = self._so_lan_trung_hinh
                        elif len(self._minh_hoa) >= 3:
                            outcome = LoiDacTa(ly_do="qua_3_khoi")
                        else:
                            outcome.ma = f"mh-{len(self._minh_hoa) + 1}"
                            self._minh_hoa.append(outcome)
                    if duplicate is not None:
                        tool_span.dat_thuoc_tinh(so_lan_trung_hinh=duplicate_count)
                        ghi_buoc("xong", ma_buoc, chi_tiet="Hình đã có")
                        tool_span.dat_trang_thai("ok")
                        self._audit(ten, ctx, "cho_phep", 0, _elapsed_ms())
                        return KetQuaCongCu(
                            trang_thai="ok", noi_dung=f"Đã vẽ ở {duplicate}, không vẽ lại."
                        )
                if isinstance(outcome, LoiDacTa):
                    reason = outcome.ly_do
                    with self._lock:
                        self._so_lan_ve_bi_tu_choi += 1
                    if reason == "nguon_khong_hop_le":
                        reason += "; mã căn cứ hợp lệ: " + ", ".join(sorted(evidence_snapshot)[:10])
                    elif reason.startswith(("ds_khong_ton_tai:", "cot_khong_ton_tai:")):
                        available = [
                            f"{ma}: {', '.join(c.ten for c in ds.cot)}"
                            for ma, ds in datasets_snapshot.items()
                        ]
                        reason += "; bộ dữ liệu và cột hiện có: " + "; ".join(available)
                    elif reason.startswith("so_tu_do:"):
                        reason += "; dùng tham chiếu `o` hoặc `o_theo_khoang`"
                    tool_span.dat_trang_thai("tu_choi")
                    tool_span.dat_thuoc_tinh(ly_do_tu_choi=outcome.ly_do.split(":", 1)[0])
                    ghi_buoc("loi", ma_buoc, ly_do="Đặc tả không hợp lệ")
                    self._audit(ten, ctx, "tu_choi:dac_ta_khong_hop_le", 0, _elapsed_ms())
                    return KetQuaCongCu(
                        trang_thai="tu_choi", ma_loi="dac_ta_khong_hop_le", noi_dung=reason
                    )
                layers = outcome.dac_ta["lop"]
                points = sum(len(self._bo_du_lieu[item["du_lieu"]].dong) for item in layers)
                size = len(json.dumps(outcome.model_dump(mode="json")).encode("utf-8"))
                tool_span.dat_thuoc_tinh(
                    kieu_dau=[item["dau"] for item in layers],
                    so_lop=len(layers),
                    so_phan_tu=points,
                    kich_thuoc_byte=size,
                )
                tool_span.dat_trang_thai("ok")
                ghi_buoc("xong", ma_buoc, chi_tiet="Đã tạo minh hoạ")
                self._audit(ten, ctx, "cho_phep", 0, _elapsed_ms())
                controls = len(outcome.dac_ta.get("tham_so", []))
                message = (
                    f"{outcome.ma}: {len(layers)} lớp, {controls} điều khiển, {points} dòng. "
                    f"Đã có hình {outcome.ma}. Không cần vẽ lại; hãy trả lời bằng chữ."
                )
                return KetQuaCongCu(trang_thai="ok", noi_dung=message)

            # 6. Chạy công cụ trong luồng phụ có giới hạn thời gian.
            timeout = min(tool.thoi_gian_toi_da, ctx.han_chot - time.monotonic())
            try:
                raw_result = _run_tool_with_timeout(tool, tham_so, ctx, timeout, doan_goc)
            except TimeoutError:
                ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS["het_gio"])
                tool_span.dat_trang_thai("loi")
                tool_span.dat_thuoc_tinh(
                    trang_thai_cong_cu="loi",
                    ma_loi="het_gio",
                    loai_ngoai_le="TimeoutError",
                    kich_thuoc_ket_qua=0,
                    bi_cat=False,
                    ma_can_cu=[],
                    so_can_cu=0,
                )
                self._audit(ten, ctx, "loi:het_gio", 0, _elapsed_ms())
                return KetQuaCongCu(
                    trang_thai="loi",
                    ma_loi="het_gio",
                    noi_dung="Công cụ xử lý quá thời gian cho phép.",
                )
            except Exception as exc:
                ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS["loi_cong_cu"])
                tool_span.dat_trang_thai("loi")
                tool_span.dat_thuoc_tinh(
                    trang_thai_cong_cu="loi",
                    ma_loi="loi_cong_cu",
                    loai_ngoai_le=type(exc).__name__,
                    kich_thuoc_ket_qua=0,
                    bi_cat=False,
                    ma_can_cu=[],
                    so_can_cu=0,
                )
                self._audit(ten, ctx, "loi:loi_cong_cu", 0, _elapsed_ms())
                return KetQuaCongCu(
                    trang_thai="loi",
                    ma_loi="loi_cong_cu",
                    noi_dung="Công cụ gặp lỗi khi thực thi.",
                )

            # 7. Hậu xử lý kết quả.
            trang_thai = raw_result.trang_thai
            ma_loi = raw_result.ma_loi
            can_cu = list(raw_result.can_cu[: tool.so_can_cu_toi_da])

            # 7.1 Che PII trong noi_dung (bảo vệ đúng mã căn cứ còn giữ).
            protected_text, code_placeholders = _protect_evidence_codes(raw_result.noi_dung, can_cu)
            try:
                if _DEID_TOKEN_RE.search(protected_text):
                    cleaned = session.mask_known(protected_text)
                else:
                    cleaned = session.scrub(protected_text)
                cleaned = _restore_evidence_codes(cleaned, code_placeholders)
            except DeidError:
                cleaned = _SCRUB_FALLBACK
                trang_thai = "loi"
                ma_loi = ma_loi or "loi_cong_cu"
                can_cu = []

            # 7.2 Loại bỏ chuỗi phân tách khối.
            cleaned = _sanitize_markers(cleaned)

            # 7.3 Quét chèn lệnh.
            cleaned_no_zw = _ZERO_WIDTH_RE.sub("", cleaned)
            if _has_injection_directive(cleaned) or _has_injection_directive(cleaned_no_zw):
                cleaned = _INJECTION_BLOCKED_MESSAGE
                trang_thai = "loi"
                ma_loi = "nghi_chen_lenh"
                can_cu = []
                ghi_su_kien_bao_mat(
                    "chen_lenh_ket_qua_cong_cu",
                    nguon="tool_gateway",
                    ten_cong_cu=span_ten,
                    ma_loi="nghi_chen_lenh",
                )
                if vet is not None:
                    vet.tang_so_bi_chan()

            # 7.4 Cắt độ dài tối đa 8000 ký tự (can_cu đã cắt ở trên).
            bi_cat = len(cleaned) > _MAX_TOOL_OUTPUT_CHARS
            cleaned = cleaned[:_MAX_TOOL_OUTPUT_CHARS]

            if trang_thai == "ok":
                with self._lock:
                    self._ma_can_cu.update(cc.ma for cc in can_cu)
                    for cc in can_cu:
                        if cc.loai == "doan" and cc.doan is not None:
                            self._doan_da_tra.add(cc.ma)
                            self._doan_goc[cc.ma] = cc.doan

            datasets: list[BoDuLieu] = []
            ly_do_bo: list[str] = []
            summaries: list[str] = []
            if trang_thai == "ok":
                for dataset in raw_result.bo_du_lieu:
                    try:
                        if len(dataset.cot) > 20:
                            raise ValueError("qua_20_cot")
                        if len(dataset.dong) > 2000:
                            raise ValueError("qua_2000_dong")
                        cols = []
                        names: set[str] = set()
                        for col in dataset.cot:
                            if not re.fullmatch(r"[a-z][a-z0-9_]{0,119}", col.ten):
                                raise ValueError("ten_cot_khong_hop_le")
                            if col.ten in names:
                                raise ValueError("trung_cot")
                            names.add(col.ten)
                            metadata = {}
                            for field in ("don_vi", "nhan", "nhan_dung", "nhan_sai"):
                                value = getattr(col, field)
                                if value is not None:
                                    if len(value) > 200:
                                        raise ValueError("chuoi_qua_dai")
                                    value = _scrub_dataset_cell(value, session, can_cu)
                                    if _has_injection_directive(value):
                                        raise ValueError("nghi_chen_lenh")
                                metadata[field] = value
                            cols.append(col.model_copy(update=metadata))
                        rows: list[dict[str, str | float | bool | None]] = []
                        masked_rows: list[dict[str, str | float | bool | None]] = []
                        time_columns = {col.ten for col in cols if col.kieu == "thoi_gian"}
                        for row in dataset.dong:
                            if not set(row).issubset(names):
                                raise ValueError("cot_khong_ton_tai")
                            clean_row: dict[str, str | float | bool | None] = {}
                            masked_row: dict[str, str | float | bool | None] = {}
                            for key, value in row.items():
                                if isinstance(value, str):
                                    if len(value) > 200:
                                        raise ValueError("chuoi_qua_dai")
                                    raw_value = value
                                    value = _scrub_dataset_cell(raw_value, session, can_cu)
                                    if _has_injection_directive(value) or _has_injection_directive(
                                        _ZERO_WIDTH_RE.sub("", value)
                                    ):
                                        raise ValueError("nghi_chen_lenh")
                                    if len(value) > 200:
                                        raise ValueError("chuoi_qua_dai")
                                    masked_row[key] = value
                                    if key in time_columns:
                                        if not _is_iso_time(raw_value):
                                            raise ValueError("thoi_gian_khong_hop_le")
                                        value = raw_value
                                else:
                                    masked_row[key] = value
                                clean_row[key] = value
                            rows.append(clean_row)
                            masked_rows.append(masked_row)
                        with self._lock:
                            ma = f"ds-{len(self._bo_du_lieu) + 1}"
                            codes = {cc.ma for cc in can_cu}
                            safe = dataset.model_copy(
                                update={
                                    "ma": ma,
                                    "cot": cols,
                                    "dong": rows,
                                    "can_cu": [c for c in dataset.can_cu if c in codes],
                                }
                            )
                            self._bo_du_lieu[ma] = safe
                        datasets.append(safe)
                        columns = ", ".join(
                            f"{c.ten} ({c.kieu}, {c.don_vi or 'không đơn vị'})" for c in safe.cot
                        )

                        def display_cell(value: str | float | bool | None) -> str:
                            if isinstance(value, float):
                                number = str(int(value)) if value.is_integer() else str(value)
                                return number.replace(".", ",")
                            return json.dumps(value, ensure_ascii=False)

                        sample = " | ".join(
                            "; ".join(f"{key}: {display_cell(value)}" for key, value in row.items())
                            for row in masked_rows[:5]
                        )
                        summaries.append(
                            f"{ma}: {columns}; căn cứ cho nguon: {', '.join(safe.can_cu)}; "
                            f"{len(rows)} dòng; mẫu: {sample}"
                        )
                    except (ValueError, DeidError) as exc:
                        ly_do_bo.append(str(exc) if isinstance(exc, ValueError) else "loi_che_pii")
            if ly_do_bo:
                tool_span.dat_thuoc_tinh(ly_do_bo_bo_du_lieu=ly_do_bo)
            if summaries:
                summary_text = "\n".join(summaries)
                remaining = max(0, _MAX_TOOL_OUTPUT_CHARS - len(summary_text) - 1)
                cleaned = f"{cleaned[:remaining]}\n{summary_text}".strip()
            cleaned = cleaned[:_MAX_TOOL_OUTPUT_CHARS]

            # 7.5 Bọc kết quả trong khối dữ liệu riêng của công cụ.
            wrapped = f"<<<KET_QUA_CONG_CU ten={tool.ten}>>>\n{cleaned}\nKET_QUA_CONG_CU>>>"

            # 8. Cập nhật tiến trình và span tool.
            if trang_thai in ("ok", "khong_co"):
                ghi_buoc("xong", ma_buoc, chi_tiet=raw_result.chi_tiet_tien_trinh or "Xong")
                audit_status = "cho_phep"
                tool_span.dat_trang_thai("ok")
                tool_span.dat_noi_dung({"ket_qua_da_che": cleaned})
            elif trang_thai == "tu_choi":
                code = ma_loi or "khong_co_quyen"
                ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS.get(code, "Bị từ chối"))
                audit_status = f"tu_choi:{code}"
                tool_span.dat_trang_thai("tu_choi")
            else:
                code = ma_loi or "loi_cong_cu"
                ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS.get(code, "Công cụ gặp lỗi"))
                audit_status = f"loi:{code}"
                tool_span.dat_trang_thai("loi")

            tool_span.dat_thuoc_tinh(
                trang_thai_cong_cu=trang_thai,
                ma_loi=ma_loi,
                kich_thuoc_ket_qua=len(cleaned),
                bi_cat=bi_cat,
                ma_can_cu=[cc.ma for cc in can_cu],
                so_can_cu=len(can_cu),
            )

            # 9. Ghi nhật ký kiểm toán.
            self._audit(ten, ctx, audit_status, len(can_cu), _elapsed_ms())

            result = KetQuaCongCu(
                trang_thai=trang_thai,
                noi_dung=wrapped,
                can_cu=can_cu,
                bo_du_lieu=datasets,
                chi_tiet_tien_trinh=raw_result.chi_tiet_tien_trinh,
                ma_loi=ma_loi,
            )
            if cache_key is not None and trang_thai in ("ok", "khong_co"):
                with self._lock:
                    self._ket_qua_da_goi[cache_key] = result.model_copy(deep=True)
            return result
