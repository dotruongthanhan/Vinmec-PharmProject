"""Luồng cũ cứng (RAG cố định) bọc thành công cụ.

Đây là luồng hỏi đáp trước plan 1.9, giữ lại làm công cụ chuyển tiếp và đường lui
(plan 1.9 mục 6.6). Không thêm tính năng mới vào đây. Sẽ thôi gọi khi các công cụ
chuyên biệt đạt đánh giá; khi đó tắt bằng `cong_cu.luong_cu_cung.bat: false` trong
`config/tool_policy.yaml`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict

from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.domain.models import CaBenh
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskResult
from app.pipeline import KetQuaThamDinh

_SOURCE_LABELS: dict[str, str] = {
    "openfda": "Nhãn FDA",
    "openfda_drug_label": "Nhãn FDA",
    "byt": "Hướng dẫn Bộ Y tế",
    "van_ban_byt": "Văn bản Bộ Y tế",
    "duoc_thu": "Dược thư Quốc gia",
}


def _source_label(nguon: str) -> str:
    """Đổi mã nguồn đoạn trích sang nhãn công khai tiếng Việt."""
    return _SOURCE_LABELS.get(nguon, nguon.replace("_", " "))


class _AskerProtocol(Protocol):
    """Giao diện tối thiểu khớp với CaseAsker cho cả chế độ ca và chế độ chung."""

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult: ...

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult: ...


class _LuongCuCungThamSo(BaseModel):
    """Lược đồ tham số rỗng; toàn bộ ngữ cảnh lấy từ ToolContext."""

    model_config = ConfigDict(extra="forbid")


class LuongCuCung(Tool):
    """Công cụ bọc nguyên vẹn CaseAsker làm bước chuyển tiếp và đường lui an toàn."""

    ten: ClassVar[str] = "luong_cu_cung"
    ten_hien_thi: ClassVar[str] = "Luồng cũ cứng (RAG cố định)"
    mo_ta: ClassVar[str] = (
        "Chạy toàn bộ luồng hỏi đáp cố định: truy xuất nhãn thuốc theo hoạt chất của ca, "
        "gọi mô hình một lần và kiểm chứng trích dẫn/số liệu, trả về câu trả lời đã "
        "kiểm chứng kèm các đoạn nguồn. Không nhận tham số."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = _LuongCuCungThamSo
    thoi_gian_toi_da: ClassVar[float] = 45.0
    so_can_cu_toi_da: ClassVar[int] = 8

    def __init__(self, asker: _AskerProtocol) -> None:
        self._asker = asker

    def chay_truc_tiep(self, ctx: ToolContext) -> AskResult:
        """Gọi thẳng CaseAsker theo chế độ ca hoặc chế độ chung; dùng cho nút đường lui."""
        if ctx.che_do == "ca":
            if ctx.ca is None:
                raise ValueError("Chế độ ca yêu cầu ToolContext.ca khác None")
            return self._asker.ask(
                ctx.ca,
                ctx.cau_hoi_goc,
                list(ctx.lich_su_goc),
                ket_qua=ctx.ket_qua_luat,
                ai_result=ctx.ai_result,
                nhan_dinh_id=ctx.nhan_dinh_id,
            )
        return self._asker.ask_global(
            list(ctx.cac_ca),
            dict(ctx.cac_ket_qua),
            ctx.cau_hoi_goc,
            list(ctx.lich_su_goc),
        )

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        """Chạy luồng cũ cứng và quy đổi AskResult sang KetQuaCongCu."""
        del tham_so
        result = self.chay_truc_tiep(ctx)

        if result.trang_thai == "ok":
            trang_thai = "ok"
            ma_loi = None
        elif result.trang_thai in ("khong_co_nguon", "ngoai_pham_vi"):
            trang_thai = "khong_co"
            ma_loi = None
        else:
            trang_thai = "loi"
            ma_loi = "loi_cong_cu"

        parts = [result.noi_dung] if result.noi_dung else []
        if result.trich_dan:
            citation_lines = [
                (
                    f"[{td.so}] {td.nhan}: {td.trich_nguyen_van}"
                    if td.trich_nguyen_van
                    else f"[{td.so}] {td.nhan}"
                )
                for td in result.trich_dan
            ]
            parts.append("\n".join(citation_lines))
        noi_dung = "\n\n".join(parts)

        can_cu = [
            CanCu(
                ma=f"doan:{chunk.doan_trich_id}",
                loai="doan",
                nhan=_source_label(chunk.nguon),
                doan=chunk,
            )
            for chunk in result.doan
        ]

        return KetQuaCongCu(
            trang_thai=trang_thai,
            noi_dung=noi_dung,
            can_cu=can_cu,
            chi_tiet_tien_trinh=f"{len(result.doan)} đoạn nguồn",
            ma_loi=ma_loi,
        )
