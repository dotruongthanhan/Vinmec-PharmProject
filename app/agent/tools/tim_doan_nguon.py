"""Công cụ tìm đoạn nguồn (nhãn thuốc) theo hoạt chất và mục: chính xác, ngữ nghĩa hoặc kết hợp."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Annotated, ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.core.errors import ProviderError, RetrievalError
from app.core.types import Chunk
from app.domain.loader import ingredients_of
from app.orchestration.ask import _source_label

_TEN = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
_MUC = Literal[
    "lieu",
    "lieu_than",
    "lieu_gan",
    "chong_chi_dinh",
    "canh_bao",
    "tuong_tac",
    "tac_dung_phu",
    "thai_ky_cho_bu",
    "nhi_cao_tuoi",
    "qua_lieu",
    "chi_dinh",
    "duoc_ly",
    "khac",
]
_MAX_KY_TU_DOAN = 1200
_MAX_KY_TU_NOI_DUNG = 7500
_MAX_KY_TU_GHI_CHU = 200
_MAX_GHI_CHU = 6
_CANH_BAO_NHUNG_LOI = "nhúng lỗi, trả theo thứ tự tài liệu"
_DAU_CAU = (". ", "; ", "? ", "! ", ".\n")

IngredientResolver = Callable[[str], Sequence[str] | str | None]


class NguonDoan(Protocol):
    """Nguồn đoạn: bộ nạp đoạn theo hoạt chất và bộ xếp hạng vector (LazyRetrieverFactory)."""

    def ingredient_items(self, ids: set[str]) -> list[tuple[Chunk, list[float] | None]]: ...

    def rank_by_vector(
        self, items: Sequence[tuple[Chunk, list[float] | None]], query: str, k: int
    ) -> list[Chunk]: ...


class ThamSoTimDoanNguon(BaseModel):
    """Tham số của công cụ; không có mã ca và không nhận trường lạ."""

    model_config = ConfigDict(extra="forbid")

    cau_hoi: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    hoat_chat: list[_TEN] = Field(default_factory=list, max_length=5)
    muc: list[_MUC] = Field(default_factory=list, max_length=4)
    so_doan: int = Field(default=4, ge=1, le=6)


def _loi(ma_loi: str, thong_bao: str) -> KetQuaCongCu:
    return KetQuaCongCu(trang_thai="loi", ma_loi=ma_loi, noi_dung=thong_bao)


def _cat_doan(text: str, limit: int = _MAX_KY_TU_DOAN) -> tuple[str, bool]:
    """Gộp khoảng trắng; cắt ở ranh giới câu (hoặc từ) khi vượt giới hạn. Trả (văn bản, bị cắt)."""
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean, False
    head = clean[:limit]
    cut = max(head.rfind(mark) for mark in _DAU_CAU)
    if cut >= limit // 2:
        return head[: cut + 1].rstrip(), True
    return head.rsplit(" ", 1)[0].rstrip(), True


def _chuan_hoa(raw: Sequence[str] | str | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    return list(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))


class TimDoanNguon(Tool):
    """Tìm đoạn nhãn thuốc theo hoạt chất, mục và câu hỏi; trả nguyên văn để trích dẫn."""

    ten: ClassVar[str] = "tim_doan_nguon"
    ten_hien_thi: ClassVar[str] = "Tìm đoạn nguồn"
    mo_ta: ClassVar[str] = (
        "Tìm đoạn nguyên văn trong nhãn thuốc (tiếng Anh, FDA) cho một hoạt chất: liều, chống chỉ "
        "định, cảnh báo, tương tác, thai kỳ... Nêu hoat_chat (tên hoặc mã; ở chế độ ca có thể bỏ "
        "trống để dùng thuốc của ca; chế độ chung bắt buộc nêu) và nên nêu muc khi đã rõ mục "
        "(lieu, lieu_than, lieu_gan, chong_chi_dinh, canh_bao, tuong_tac, tac_dung_phu, "
        "thai_ky_cho_bu, nhi_cao_tuoi, qua_lieu, chi_dinh, duoc_ly, khac). Mỗi đoạn mở đầu bằng "
        "dòng [doan_trich_id: ...]; khi trích dùng loai=tai_lieu, ma là đúng mã đó và "
        "trich_nguyen_van chép nguyên văn từ đoạn hiển thị."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoTimDoanNguon
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca", "chung"})
    thoi_gian_toi_da: ClassVar[float] = 20.0
    so_can_cu_toi_da: ClassVar[int] = 6

    def __init__(self, nguon: NguonDoan | None, resolve_name: IngredientResolver) -> None:
        self._nguon = nguon
        self._resolve_name = resolve_name

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        """Phân giải hoạt chất, lọc theo mục, chọn cách tra rồi dựng kết quả có thể trích dẫn."""
        assert isinstance(tham_so, ThamSoTimDoanNguon)
        if self._nguon is None:
            return _loi("thieu_du_lieu_nguon", "Chưa nạp được kho đoạn nguồn.")

        ten_theo_id, khong_phan_giai = self._phan_giai(tham_so, ctx)
        if ten_theo_id is None:
            return _loi("sai_tham_so", "Chế độ chung cần nêu thuốc trong hoat_chat.")
        ghi_chu = [f"không có nhãn trong kho cho {ten}." for ten in khong_phan_giai]
        if not ten_theo_id:
            return self._khong_co(ghi_chu or ["Ca chưa có thuốc để tra; hãy nêu hoat_chat."])

        try:
            items = self._nguon.ingredient_items(set(ten_theo_id))
        except RetrievalError:
            return _loi("thieu_du_lieu_nguon", "Không đọc được kho đoạn nguồn.")
        co_doan = {hid for chunk, _ in items for hid in chunk.hoat_chat_ids}
        ghi_chu.extend(
            f"không có nhãn trong kho cho {ten}."
            for hid, ten in ten_theo_id.items()
            if hid not in co_doan
        )
        # Thứ tự tài liệu: gom theo tài liệu, giữ thứ tự nạp trong từng tài liệu.
        items.sort(key=lambda item: item[0].tai_lieu_id)
        if tham_so.muc:
            tap_muc = set(tham_so.muc)
            items = [item for item in items if item[0].muc in tap_muc]
            if not items and co_doan:
                ghi_chu.append(f"không có đoạn nào thuộc mục {', '.join(tham_so.muc)}.")
        if not items:
            return self._khong_co(ghi_chu)

        cach, chon, canh_bao = self._chon(tham_so, items)
        return self._ket_qua(chon, cach, canh_bao, ghi_chu)

    # ------------------------------------------------------------------ phân giải

    def _phan_giai(
        self, tham_so: ThamSoTimDoanNguon, ctx: ToolContext
    ) -> tuple[dict[str, str] | None, list[str]]:
        """Trả ({mã hoạt chất: tên hiển thị}, tên không phân giải); None nếu thiếu tham số."""
        ten_vao: list[str] = list(tham_so.hoat_chat)
        if not ten_vao:
            if ctx.che_do != "ca" or ctx.ca is None:
                return None, []
            for line in ctx.ca.y_lenh_cho_duyet.chi_tiet:
                for hc in ingredients_of(ctx.ca, line):
                    ten = hc.ten_quoc_te.strip() if hc.ten_quoc_te else hc.ten_hoat_chat
                    if ten and ten not in ten_vao:
                        ten_vao.append(ten)
            ten_vao = ten_vao[:5]
        ten_theo_id: dict[str, str] = {}
        khong_phan_giai: list[str] = []
        for ten in ten_vao:
            ids = _chuan_hoa(self._resolve_name(ten))
            if not ids:
                khong_phan_giai.append(ten)
            for hid in ids:
                ten_theo_id.setdefault(hid, ten)
        return ten_theo_id, khong_phan_giai

    # ------------------------------------------------------------------ chọn đoạn

    def _chon(
        self,
        tham_so: ThamSoTimDoanNguon,
        items: list[tuple[Chunk, list[float] | None]],
    ) -> tuple[str, list[Chunk], str | None]:
        """Chọn cách tra: chính xác (không nhúng), kết hợp (lọc rồi vector) hoặc ngữ nghĩa."""
        assert self._nguon is not None
        k = tham_so.so_doan
        if tham_so.muc and len(items) <= k:
            return "chính xác", [chunk for chunk, _ in items], None
        cach = "kết hợp" if tham_so.muc else "ngữ nghĩa"
        try:
            return cach, self._nguon.rank_by_vector(items, tham_so.cau_hoi, k), None
        except (ProviderError, RetrievalError):
            return cach, [chunk for chunk, _ in items[:k]], _CANH_BAO_NHUNG_LOI

    # ------------------------------------------------------------------ kết quả

    @staticmethod
    def _khong_co(ghi_chu: list[str]) -> KetQuaCongCu:
        return KetQuaCongCu(
            trang_thai="khong_co",
            noi_dung="\n".join(ghi_chu[:_MAX_GHI_CHU]),
            chi_tiet_tien_trinh="Không có đoạn nguồn",
        )

    @staticmethod
    def _ket_qua(
        chon: list[Chunk], cach: str, canh_bao: str | None, ghi_chu: list[str]
    ) -> KetQuaCongCu:
        """Dựng các khối đoạn (cắt 1.200 ký tự mỗi đoạn, 7.500 tổng) và căn cứ tương ứng."""
        ghi_chu_giu = [item[:_MAX_KY_TU_GHI_CHU] for item in ghi_chu[:_MAX_GHI_CHU]]
        if canh_bao:
            ghi_chu_giu.append("Không xếp hạng được theo ngữ nghĩa; các đoạn theo thứ tự tài liệu.")
        con_cho = _MAX_KY_TU_NOI_DUNG - sum(len(item) + 1 for item in ghi_chu_giu)
        khoi: list[str] = []
        can_cu: list[CanCu] = []
        for chunk in chon:
            van_ban, bi_cat = _cat_doan(chunk.noi_dung_goc)
            nhan = f"{_source_label(chunk.nguon)} · {chunk.duong_dan_muc}"
            lines = [
                f"[doan_trich_id: {chunk.doan_trich_id}]",
                f"Nguồn: {nhan} · mục: {chunk.muc} · tầng tin cậy: {chunk.tang_tin_cay}",
                van_ban,
            ]
            if bi_cat:
                lines.append("(đã cắt bớt; chỉ trích phần hiển thị ở trên)")
            if bi_cat or chunk.loai_noi_dung in ("bang", "dong_bang"):
                lines.append("(có thể gọi doc_doan_mo_rong với mã này để xem cả mục)")
            block = "\n".join(lines)
            if len(block) + 2 > con_cho:
                break
            con_cho -= len(block) + 2
            khoi.append(block)
            can_cu.append(CanCu(ma=chunk.doan_trich_id, loai="doan", nhan=nhan, doan=chunk))
        so_bo = len(chon) - len(khoi)
        if so_bo > 0:
            ghi_chu_giu.append(f"(còn {so_bo} đoạn nữa chưa hiển thị)")
        nguon = " + ".join(dict.fromkeys(_source_label(c.doan.nguon) for c in can_cu if c.doan))
        tom_tat = f"{nguon or 'Nguồn'}, {len(can_cu)} đoạn ({cach})"
        if canh_bao:
            tom_tat += f"; {canh_bao}"
        noi_dung = "\n\n".join([*khoi, *ghi_chu_giu])
        return KetQuaCongCu(
            trang_thai="ok" if can_cu else "khong_co",
            noi_dung=noi_dung,
            can_cu=can_cu,
            chi_tiet_tien_trinh=tom_tat,
        )


__all__ = ["NguonDoan", "ThamSoTimDoanNguon", "TimDoanNguon"]
