"""Công cụ tra tương tác thuốc–thuốc, thuốc–thức ăn, thuốc–bệnh từ dữ liệu DDInter (chỉ đọc)."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.exceptions import HTTPException

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu
from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.kb.interactions.models import SEVERITIES, PairRecord
from app.kb.names import normalize_key
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d4_config import try_load_default_drug_disease_config
from app.rules.drug_disease import icd_matches
from app.rules.types import normalize_text

if TYPE_CHECKING:
    from app.rules.registry import RuleContext

_TEN = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
_MAX_DONG = 20
_MAX_KY_TU_NOI_DUNG = 6500
_MAX_KY_TU_TOI_DA = 8000
_MAX_KY_TU_TRUONG = 220
_MAX_KHOA = 120
_ICD_RE = re.compile(r"^[A-Za-z]\d{2}(?:\.\d{1,4})?(?:-[A-Za-z]\d{2}(?:\.\d{1,4})?)?$")
_BAD_KEY_RE = re.compile(r"[\s\x00-\x1f\x7f\[\]]+")
_MUC_VI: dict[str, str] = {
    "Major": "nặng",
    "Moderate": "trung bình",
    "Minor": "nhẹ",
    "Unknown": "chưa rõ",
}
_NHAN_THUOC = "DDInter 2.0 – tương tác thuốc–thuốc (sàng lọc)"
_NHAN_THUC_AN = "DDInter 2.0 – tương tác thuốc–thức ăn (sàng lọc)"
_NHAN_BENH = "DDInter 2.0 – tương tác thuốc–bệnh (sàng lọc)"


class ThamSoTraTuongTac(BaseModel):
    """Tham số của công cụ; không có mã ca và không nhận trường lạ."""

    model_config = ConfigDict(extra="forbid")

    loai: Literal["thuoc_thuoc", "thuoc_thuc_an", "thuoc_benh"] = "thuoc_thuoc"
    ten_thuoc: list[_TEN] = Field(min_length=1, max_length=10)
    benh: list[_TEN] = Field(default_factory=list, max_length=5)


def _cat(text: str | None, limit: int = _MAX_KY_TU_TRUONG) -> str:
    """Gộp khoảng trắng và cắt gọn ở ranh giới từ để dòng bảng không dài."""
    clean = " ".join((text or "").split())
    if not clean:
        return "thiếu"
    if len(clean) <= limit:
        return clean
    return clean[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " …"


def _khoa(*phan: str) -> str:
    """Khoá dòng bảng ổn định: một dòng, không khoảng trắng, tối đa 120 ký tự."""
    joined = ":".join(_BAD_KEY_RE.sub("_", item.strip().lower()) for item in phan)
    return joined[:_MAX_KHOA]


def _goi_y_gan_dung(ten: str) -> str:
    """Gợi ý tên gần đúng (chỉ mục T105, có sửa lỗi gõ); lỗi bất kỳ thì bỏ qua lặng lẽ."""
    try:
        from app.api.lookup import suggest_drugs

        ket_qua = suggest_drugs(ten, limit=3)
        nhan: list[str] = []
        if ket_qua.goi_y_sua:
            nhan.append(" ".join(str(ket_qua.goi_y_sua).split())[:80])
        nhan.extend(" ".join(str(item.nhan).split())[:80] for item in ket_qua.ket_qua)
        nhan = list(dict.fromkeys(item for item in nhan if item))[:3]
    except Exception:
        return ""
    if not nhan:
        return ""
    return f"; có thể là: {', '.join(nhan)} (gợi ý gần đúng, cần xác nhận)"


def _loi(ma_loi: str, thong_bao: str) -> KetQuaCongCu:
    return KetQuaCongCu(trang_thai="loi", ma_loi=ma_loi, noi_dung=thong_bao)


class _KhongCoDuLieu(Exception):
    """Chưa nạp được chỉ mục tra cứu hoặc bảng luật."""


class _Dong:
    """Một dòng bảng có thể trích dẫn, kèm mức để sắp xếp."""

    __slots__ = ("khoa", "nhan", "noi_dung", "thu_tu", "du_lieu")

    def __init__(
        self,
        khoa: str,
        nhan: str,
        noi_dung: str,
        thu_tu: int,
        du_lieu: dict[str, str] | None = None,
    ) -> None:
        self.khoa = khoa
        self.nhan = nhan
        self.noi_dung = noi_dung
        self.thu_tu = thu_tu
        self.du_lieu = du_lieu


class TraTuongTac(Tool):
    """Tra tương tác trong DDInter; phân biệt rõ thiếu dữ liệu với không phát hiện."""

    ten: ClassVar[str] = "tra_tuong_tac"
    ten_hien_thi: ClassVar[str] = "Tra tương tác"
    mo_ta: ClassVar[str] = (
        "Tra tương tác trong DDInter (sàng lọc, cần đối chiếu nhãn) từ tên thuốc dược sĩ nêu. "
        "loai=thuoc_thuoc: cần từ 2 tên thuốc trở lên; loai=thuoc_thuc_an: tương tác thuốc với "
        "thức ăn, đồ uống; loai=thuoc_benh: tương tác thuốc với bệnh, nêu tên bệnh hoặc mã "
        "ICD-10 trong benh (ở chế độ ca có thể bỏ trống để dùng chẩn đoán của ca). Mỗi dòng kết "
        "quả mở đầu bằng mã trong ngoặc vuông; khi trích phải dùng loai=bang với đúng mã đó. "
        "Dòng ghi không có dữ liệu nghĩa là chưa đủ dữ liệu, không phải đã loại trừ tương tác."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoTraTuongTac
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca", "chung"})
    so_can_cu_toi_da: ClassVar[int] = _MAX_DONG

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        """Chạy theo loại tra cứu; mọi lỗi dữ liệu đầu vào trả `loi` kèm giải thích ngắn."""
        assert isinstance(tham_so, ThamSoTraTuongTac)
        try:
            if tham_so.loai == "thuoc_thuoc":
                return self._thuoc_thuoc(tham_so)
            if tham_so.loai == "thuoc_thuc_an":
                return self._thuoc_thuc_an(tham_so)
            return self._thuoc_benh(tham_so, ctx)
        except _KhongCoDuLieu as exc:
            return _loi("thieu_du_lieu_nguon", str(exc))

    # ------------------------------------------------------------------ dùng chung

    @staticmethod
    def _ngu_canh() -> RuleContext:
        """Chỉ mục phân giải và kho DDInter dùng chung với trang Tra tương tác."""
        from app import container as container_mod

        context = container_mod.get_rule_context()
        if context.resolver is None or context.interactions is None:
            raise _KhongCoDuLieu("Chưa nạp được chỉ mục tra cứu hoặc dữ liệu DDInter.")
        return context

    @staticmethod
    def _tach_trung(ten_thuoc: list[str]) -> list[str]:
        """Bỏ tên nhập trùng (so theo khoá chuẩn hoá), giữ thứ tự."""
        seen: set[str] = set()
        out: list[str] = []
        for name in ten_thuoc:
            key = normalize_key(name)
            if key and key not in seen:
                seen.add(key)
                out.append(name)
        return out

    @staticmethod
    def _ket_qua(
        dong: list[_Dong],
        ghi_chu: list[str],
        *,
        tom_tat: str,
        nhan_chung: str,
    ) -> KetQuaCongCu:
        """Ghép nội dung: dòng bảng (cắt theo số dòng và độ dài), rồi các dòng ghi chú."""
        duy_nhat = {item.khoa: item for item in reversed(dong)}
        dong = sorted(reversed(list(duy_nhat.values())), key=lambda item: item.thu_tu)
        giu: list[_Dong] = []
        tong = 0
        for item in dong:
            do_dai = len(item.khoa) + len(item.noi_dung) + 4
            if len(giu) >= _MAX_DONG or tong + do_dai > _MAX_KY_TU_NOI_DUNG:
                break
            giu.append(item)
            tong += do_dai
        lines = [f"[bang:{item.khoa}] {item.noi_dung}" for item in giu]
        con_lai = len(dong) - len(giu)
        if con_lai > 0:
            lines.append(f"(còn {con_lai} dòng nữa chưa hiển thị)")
        chan = f"Nguồn: {nhan_chung}. Chỉ sàng lọc, cần đối chiếu nhãn và quyết định của dược sĩ."
        # Ghi chú thiếu dữ liệu cũng có trần để tổng nội dung không vượt giới hạn của Gateway.
        con_cho = _MAX_KY_TU_TOI_DA - len("\n".join(lines)) - len(chan) - 80
        for index, note in enumerate(ghi_chu):
            if len(note) + 1 > con_cho:
                lines.append(f"(còn {len(ghi_chu) - index} ghi chú nữa chưa hiển thị)")
                break
            lines.append(note)
            con_cho -= len(note) + 1
        lines.append(chan)
        can_cu = [
            CanCu(ma=f"bang:{item.khoa}", loai="bang", nhan=item.nhan, noi_dung=item.noi_dung)
            for item in giu
        ]
        rows = [item.du_lieu for item in giu if item.du_lieu is not None]
        datasets = []
        if rows:
            datasets.append(
                BoDuLieu(
                    ma="",
                    cot=[
                        CotDuLieu(ten=name, kieu="danh_muc")
                        for name in ("thuoc_a", "thuoc_b", "muc_do", "co_che", "ma_can_cu")
                    ],
                    dong=rows,
                    can_cu=[cc.ma for cc in can_cu],
                )
            )
        return KetQuaCongCu(
            trang_thai="ok" if giu else "khong_co",
            noi_dung="\n".join(lines),
            can_cu=can_cu,
            bo_du_lieu=datasets,
            chi_tiet_tien_trinh=tom_tat,
        )

    @staticmethod
    def _thieu(ten: str, ket_qua: KetQuaPhanGiai) -> str | None:
        """Dòng ghi chú khi thuốc không phân giải được hoặc có hoạt chất chưa có mã DDInter."""
        if ket_qua.trang_thai == "khong_ap_dung":
            return f"{ten}: không áp dụng tra DDInter ({ket_qua.ly_do or 'không phải thuốc'})."
        if not ket_qua.thanh_phan:
            base = f"không có dữ liệu DDInter cho {ten}: {ket_qua.ly_do or 'không phân giải được'}"
            return f"{base}{_goi_y_gan_dung(ten)}."
        thieu_ma = [row.ten_inn for row in ket_qua.thanh_phan if row.ddinter_id is None]
        if thieu_ma:
            return (
                f"không có dữ liệu DDInter cho {ten}: hoạt chất {', '.join(thieu_ma)} "
                "chưa có mã DDInter."
            )
        if ket_qua.trang_thai == "mot_phan":
            return (
                f"không có dữ liệu DDInter đầy đủ cho {ten}: chỉ phân giải được một phần hoạt chất "
                f"({ket_qua.ly_do or 'chưa rõ lý do'})."
            )
        return None

    # ------------------------------------------------------------------ thuốc–thuốc

    def _thuoc_thuoc(self, tham_so: ThamSoTraTuongTac) -> KetQuaCongCu:
        from app.api.lookup import lookup_interactions

        ten = tham_so.ten_thuoc
        if len(ten) < 2:
            return _loi("sai_tham_so", "Tra thuốc–thuốc cần ít nhất 2 tên thuốc trong ten_thuoc.")
        try:
            ket_qua = lookup_interactions(ten)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            if exc.status_code == 422:
                return _loi("sai_tham_so", str(detail.get("thong_bao") or "Danh sách thuốc sai."))
            raise _KhongCoDuLieu(
                str(detail.get("thong_bao") or "Chưa chạy được tra tương tác.")
            ) from None
        context = self._ngu_canh()
        phan_giai = {row.chi_tiet_y_lenh_id: row for row in ket_qua.phan_giai}
        resolved = {
            line_id: context.resolver.resolve_name(row.ten_nhap)
            for line_id, row in phan_giai.items()
        }
        dong: list[_Dong] = []
        ghi_chu: list[str] = []
        da_ghi: set[str] = set()
        for line_id, row in phan_giai.items():
            note = self._thieu(row.ten_nhap, resolved[line_id])
            if note is not None and note not in da_ghi:
                da_ghi.add(note)
                ghi_chu.append(note)
        so_cap_co = 0
        for cap in ket_qua.ma_tran.cap:
            ten_a, ten_b = phan_giai[cap.a].ten_nhap, phan_giai[cap.b].ten_nhap
            records = self._ban_ghi_cap(context, resolved[cap.a], resolved[cap.b])
            for label, record in records:
                pair_key = _khoa("ddinter_cap", f"{record.ddinter_id_a}-{record.ddinter_id_b}")
                dong.append(
                    _Dong(
                        pair_key,
                        _NHAN_THUOC,
                        (
                            f"{label} · mức: {_MUC_VI[record.muc_do]} (DDInter: {record.muc_do}) · "
                            f"cơ chế: {', '.join(record.co_che) or 'thiếu'} · "
                            f"hậu quả: {_cat(record.hau_qua)} · xử trí: {_cat(record.xu_tri)}"
                        ),
                        SEVERITIES.index(record.muc_do),
                        {
                            "thuoc_a": label.split(" – ", 1)[0],
                            "thuoc_b": label.split(" – ", 1)[1],
                            "muc_do": _MUC_VI[record.muc_do],
                            "co_che": _cat(", ".join(record.co_che), 200),
                            "ma_can_cu": f"bang:{pair_key}",
                        },
                    )
                )
            if records:
                so_cap_co += 1
            if cap.muc == "khong_phat_hien":
                ghi_chu.append(
                    f"{ten_a} – {ten_b}: không phát hiện cặp tương tác trong DDInter "
                    "(cả hai hoạt chất đã có danh sách tương tác đầy đủ)."
                )
            elif cap.muc == "thieu_du_lieu":
                ghi_chu.append(
                    f"{ten_a} – {ten_b}: chưa đủ dữ liệu DDInter để kết luận ({cap.ly_do})."
                )
            elif cap.muc == "khong_ap_dung":
                ghi_chu.append(
                    f"{ten_a} – {ten_b}: không áp dụng ({cap.ly_do or 'không rõ lý do'})."
                )
        so_hoat_chat = len(
            {hc for row in resolved.values() for hc in (t.hoat_chat_id for t in row.thanh_phan)}
        )
        return self._ket_qua(
            dong,
            ghi_chu,
            tom_tat=f"{so_hoat_chat} hoạt chất, {so_cap_co} cặp có tương tác",
            nhan_chung=_NHAN_THUOC,
        )

    @staticmethod
    def _ban_ghi_cap(
        context: RuleContext, a: KetQuaPhanGiai, b: KetQuaPhanGiai
    ) -> list[tuple[str, PairRecord]]:
        """Bản ghi DDInter của mọi cặp hoạt chất giữa hai thuốc (nhãn: tên INN hai phía)."""
        out: list[tuple[str, PairRecord]] = []
        for ia in a.thanh_phan:
            for ib in b.thanh_phan:
                if ia.hoat_chat_id == ib.hoat_chat_id or not ia.ddinter_id or not ib.ddinter_id:
                    continue
                record = context.interactions.pair(ia.ddinter_id, ib.ddinter_id)
                if record is not None:
                    out.append((f"{ia.ten_inn} – {ib.ten_inn}", record))
        return out

    # ------------------------------------------------------------------ thuốc–thức ăn

    def _thanh_phan(
        self, tham_so: ThamSoTraTuongTac
    ) -> tuple[list[tuple[str, ThanhPhanPhanGiai]], list[str]]:
        """Hoạt chất có mã DDInter của từng tên (không trùng) và các dòng ghi chú thiếu dữ liệu."""
        context = self._ngu_canh()
        parts: dict[str, ThanhPhanPhanGiai] = {}
        ghi_chu: list[str] = []
        for name in self._tach_trung(tham_so.ten_thuoc):
            result = context.resolver.resolve_name(name)
            note = self._thieu(name, result)
            if note is not None:
                ghi_chu.append(note)
            for row in result.thanh_phan:
                if row.ddinter_id and row.hoat_chat_id not in parts:
                    parts[row.hoat_chat_id] = row
        return [(hid, row) for hid, row in parts.items()], ghi_chu

    def _thuoc_thuc_an(self, tham_so: ThamSoTraTuongTac) -> KetQuaCongCu:
        context = self._ngu_canh()
        thanh_phan, ghi_chu = self._thanh_phan(tham_so)
        dong: list[_Dong] = []
        for _, row in thanh_phan:
            foods = context.interactions.foods(row.ddinter_id)
            if not foods:
                ghi_chu.append(
                    f"{row.ten_inn}: DDInter không có dòng tương tác thức ăn nào "
                    "(nguồn sàng lọc, không đủ để loại trừ)."
                )
            for food in foods:
                dong.append(
                    _Dong(
                        _khoa("ddinter_thuc_an", row.ddinter_id, food.thuc_an),
                        _NHAN_THUC_AN,
                        (
                            f"{row.ten_inn} – {food.thuc_an} · mức: {_MUC_VI[food.muc_do]} "
                            f"(DDInter: {food.muc_do}) · mô tả: {_cat(food.mo_ta)} · "
                            f"xử trí: {_cat(food.xu_tri)}"
                        ),
                        SEVERITIES.index(food.muc_do),
                    )
                )
        return self._ket_qua(
            dong,
            ghi_chu,
            tom_tat=f"{len(thanh_phan)} hoạt chất, {len(dong)} dòng thức ăn",
            nhan_chung=_NHAN_THUC_AN,
        )

    # ------------------------------------------------------------------ thuốc–bệnh

    def _thuoc_benh(self, tham_so: ThamSoTraTuongTac, ctx: ToolContext) -> KetQuaCongCu:
        config = try_load_default_drug_disease_config()
        if config is None or not config.cap_thuoc_benh:
            raise _KhongCoDuLieu("Chưa nạp được bảng tương tác thuốc–bệnh.")
        ma_icd: list[str] = []
        ten_benh: list[str] = []
        ghi_chu: list[str] = []
        for item in tham_so.benh:
            (ma_icd if _ICD_RE.match(item) else ten_benh).append(item)
        if not tham_so.benh:
            if ctx.che_do != "ca" or ctx.ca is None:
                return _loi("sai_tham_so", "Tra thuốc–bệnh ở chế độ chung cần nêu benh.")
            ma_icd = [cd.ma_icd10 for cd in ctx.ca.chan_doan if cd.ma_icd10]
            thieu_ma = sum(1 for cd in ctx.ca.chan_doan if not cd.ma_icd10)
            if thieu_ma:
                ghi_chu.append(f"{thieu_ma} chẩn đoán của ca chưa có mã ICD-10 nên chưa đối chiếu.")
            if not ma_icd:
                return _loi("sai_tham_so", "Ca chưa có chẩn đoán kèm mã ICD-10; hãy nêu benh.")
        thanh_phan, ghi_chu_thuoc = self._thanh_phan(tham_so)
        ghi_chu = [*ghi_chu_thuoc, *ghi_chu]
        khoa_ten = [normalize_text(item) for item in ten_benh]
        dong: list[_Dong] = []
        for hid, row in thanh_phan:
            cac_dong = [
                p
                for p in config.cap_thuoc_benh
                if normalize_text(p.hoat_chat_id) == normalize_text(hid)
            ]
            if not cac_dong:
                ghi_chu.append(
                    f"không có dữ liệu thuốc–bệnh DDInter cho hoạt chất {row.ten_inn}, "
                    "không đủ để loại trừ."
                )
                continue
            khop = 0
            for pair in cac_dong:
                theo_ma = any(icd_matches(code, pat) for code in ma_icd for pat in pair.ma_icd10)
                ten_pair = normalize_text(pair.ten_benh)
                theo_ten = any(key and key in ten_pair for key in khoa_ten)
                if not (theo_ma or theo_ten):
                    continue
                khop += 1
                ma_text = ", ".join(pair.ma_icd10) or "chưa ánh xạ ICD-10"
                dong.append(
                    _Dong(
                        _khoa("thuoc_benh_icd", hid, pair.ten_benh),
                        _NHAN_BENH,
                        (
                            f"{row.ten_inn} – bệnh: {pair.ten_benh} (ICD-10: {ma_text}) · "
                            f"mức: {_MUC_VI[pair.muc_do]} (DDInter: {pair.muc_do}) · "
                            f"nội dung: {_cat(pair.noi_dung)}"
                        ),
                        SEVERITIES.index(pair.muc_do),
                    )
                )
            if not khop:
                ghi_chu.append(
                    f"{row.ten_inn}: không khớp dòng thuốc–bệnh DDInter nào với bệnh đã nêu "
                    f"(bảng trong kho chỉ có {len(cac_dong)} dòng cho hoạt chất này, không đủ để "
                    "loại trừ; tên bệnh trong DDInter bằng tiếng Anh)."
                )
        return self._ket_qua(
            dong,
            ghi_chu,
            tom_tat=f"{len(thanh_phan)} hoạt chất, {len(dong)} dòng thuốc–bệnh khớp",
            nhan_chung=_NHAN_BENH,
        )


__all__ = ["ThamSoTraTuongTac", "TraTuongTac"]
