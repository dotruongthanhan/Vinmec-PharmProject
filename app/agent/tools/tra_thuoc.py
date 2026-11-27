"""Công cụ tra thuốc: định danh, quy tắc theo hoạt chất và chế phẩm Cục QLD (chỉ đọc)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu
from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.rules.renal_dose import RenalDrugRule, derive_draw_bounds, select_renal_tier

if TYPE_CHECKING:
    from app.api import schemas as s

_TEN = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
PhanTraThuoc = Literal["dinh_danh", "quy_tac", "che_pham"]
NhomQuyTac = Literal[
    "lieu_than",
    "lieu_gan",
    "nguong_xet_nghiem",
    "duong_dung",
    "lieu_toi_da",
    "doc_tinh",
    "khang_sinh_quan_ly",
    "di_ung_cheo",
    "nhom_trung_dieu_tri",
]

_MAX_CAN_CU = 20
_MAX_DONG = _MAX_CAN_CU
_MAX_KY_TU_NOI_DUNG = 6500
_MAX_KY_TU_TRUONG = 220
_MAX_KHOA = 120
_MAX_UNG_VIEN = 5
_MAX_CHE_PHAM = 5
_MAX_HOAT_CHAT = 3
_SUGGEST_LIMIT = 15
_BAD_KEY_RE = re.compile(r"[\s\x00-\x1f\x7f\[\]|]+")
_LOW_PRIORITY_SECTIONS = frozenset({"khong_co_nguong", "khong_ghi_toi_da", "khong_co_nguon"})
_EXTRA_TEXT_KEYS = (
    "mo_ta",
    "noi_dung",
    "text",
    "thong_bao",
    "ly_do",
    "khuyen_cao",
    "dieu_kien",
    "ghi_chu",
    "hanh_dong_nhan",
)
_SKIP_FALLBACK_KEYS = frozenset(
    {
        "hoat_chat_id",
        "hoat_chat_ids",
        "ten_quoc_te",
        "trang_thai",
        "nguoi_duyet",
        "nguon",
        "nguon_chi_tiet",
        "url",
        "url_api",
        "set_id",
        "ma_dong",
        "phien_ban",
        "quy_doi_don_vi",
    }
)
_NHAN_DINH_DANH = "Danh mục hoạt chất (tri_thuc.tra_cuu_hoat_chat)"
_NHAN_BANG: dict[str, str] = {
    "quy_tac_lieu_than": "Bảng liều theo chức năng thận",
    "quy_tac_gan": "Bảng liều theo chức năng gan",
    "nguong_xet_nghiem": "Bảng ngưỡng xét nghiệm",
    "duong_dung_hop_le": "Bảng đường dùng hợp lệ",
    "lieu_toi_da": "Bảng liều tối đa theo nhãn",
    "doc_tinh": "Bảng cảnh báo độc tính",
    "khang_sinh_quan_ly": "Danh mục kháng sinh quản lý (QĐ 5631/QĐ-BYT)",
    "di_ung_cheo": "Bảng dị ứng chéo theo nhóm",
    "nhom_dieu_tri_trung": "Bảng nhóm trùng điều trị theo ATC",
}
_KHOP_VI: dict[str, str] = {
    "chinh_xac": "chính xác",
    "tien_to": "tiền tố",
    "gan_dung": "gần đúng",
}
_TRANG_THAI_VI: dict[str, str] = {
    "cho_duoc_si_duyet": "chờ dược sĩ duyệt",
    "chua_duoc_si_duyet": "chưa dược sĩ duyệt",
    "da_duyet": "đã duyệt",
    "da_duoc_si_duyet": "đã dược sĩ duyệt",
}
_KHONG_NGUONG_VI: dict[str, str] = {
    "khong_can_chinh": "nhãn không nêu chỉnh liều",
    "chi_noi_chung": "chỉ nêu chung, không có ngưỡng số",
    "bang_hoac_cong_thuc": "theo bảng/công thức, chưa cài ngưỡng cắt",
    "co_nguong_o_tep_khac": "ngưỡng ở bảng xét nghiệm",
    "chua_co_nhan": "chưa có nhãn trong kho",
}
_GAN_LOAI_VI: dict[str, str] = {
    "child_pugh_A": "Child-Pugh A",
    "child_pugh_B": "Child-Pugh B",
    "child_pugh_C": "Child-Pugh C",
    "nhe_vua": "nhẹ–vừa",
    "nang": "nặng",
    "khong_phan_loai": "suy gan chung",
}
_GAN_HANH_DONG_VI: dict[str, str] = {
    "chong_chi_dinh": "chống chỉ định",
    "tranh_khong_khuyen_cao": "tránh / không khuyến cáo",
    "giam_lieu": "giảm liều",
    "theo_doi": "theo dõi",
    "khong_chinh_lieu": "không chỉnh liều",
    "khong_co_khuyen_cao_cu_the": "không có khuyến cáo cụ thể",
}
_GIOI_HAN_VI: dict[str, str] = {
    "toi_da_ro": "tối đa rõ",
    "tran_up_to": "trần mềm (up to)",
    "gioi_han_thiet_bi": "giới hạn thiết bị",
}
_KS_NHOM_VI: dict[str, str] = {
    "phe_duyet_truoc": "Nhóm 1 – cần ưu tiên quản lý, phê duyệt trước",
    "theo_doi_giam_sat": "Nhóm 2 – theo dõi, giám sát sử dụng",
}
_HUONG_VI: dict[str, str] = {
    "hai_chieu": "hai chiều",
    "mot_chieu": "một chiều",
}
_MUC_TRUNG_VI: dict[str, str] = {
    "nghiem_trong": "nghiêm trọng",
    "can_luu_y": "cần lưu ý",
}
_CHAN_LUU_Y = (
    "Lưu ý: ngưỡng bảng chỉ để tham khảo, không phải kết luận cho ca bệnh; "
    "dược sĩ lâm sàng là người quyết định."
)


class ThamSoTraThuoc(BaseModel):
    """Tham số của công cụ tra_thuoc; không có mã ca và không nhận trường lạ."""

    model_config = ConfigDict(extra="forbid")

    ten: _TEN
    phan: list[PhanTraThuoc] = Field(
        default_factory=lambda: ["dinh_danh", "quy_tac"],
        min_length=1,
        max_length=3,
    )
    nhom_quy_tac: list[NhomQuyTac] = Field(default_factory=list, max_length=10)

    @field_validator("phan")
    @classmethod
    def _khong_trung_phan(cls, value: list[PhanTraThuoc]) -> list[PhanTraThuoc]:
        """Từ chối danh sách phan chứa phần tử lặp lại."""
        if len(set(value)) != len(value):
            raise ValueError("phan không được chứa giá trị trùng lặp")
        return value


class _Dong:
    """Một dòng bảng có thể trích dẫn bằng mã bang:<bang_luat>:<khoa>."""

    __slots__ = ("ma", "nhan", "noi_dung", "bo_du_lieu")

    def __init__(self, ma: str, nhan: str, noi_dung: str) -> None:
        self.ma = ma
        self.nhan = nhan
        self.noi_dung = noi_dung
        self.bo_du_lieu: BoDuLieu | None = None


def _renal_dataset(data: Mapping[str, Any], ma: str) -> BoDuLieu | None:
    """Dựng bảng mức đã duyệt cùng biên theo hàm chọn mức hiện hành."""
    try:
        rule = RenalDrugRule.model_validate(data)
        rows: list[dict[str, str | float | bool | None]] = []
        for tier, low, high in derive_draw_bounds(rule):
            rows.append(
                {
                    "crcl_tu": tier.crcl_tu,
                    "crcl_den": tier.crcl_den,
                    "bien_ve_tu": low,
                    "bien_ve_den": high,
                    "bao_gom_tu": low is not None and select_renal_tier(low, rule) == tier,
                    "bao_gom_den": high is not None and select_renal_tier(high, rule) == tier,
                    "can_chinh": tier.can_chinh,
                    "khuyen_cao": tier.khuyen_cao,
                }
            )
        columns = [
            CotDuLieu(
                ten=name,
                kieu=kind,
                don_vi=unit,
                nhan_dung="Cần chỉnh liều" if name == "can_chinh" else None,
                nhan_sai="Không cần chỉnh" if name == "can_chinh" else None,
            )
            for name, kind, unit in (
                ("crcl_tu", "dinh_luong", "mL/min"),
                ("crcl_den", "dinh_luong", "mL/min"),
                ("bien_ve_tu", "dinh_luong", "mL/min"),
                ("bien_ve_den", "dinh_luong", "mL/min"),
                ("bao_gom_tu", "logic", None),
                ("bao_gom_den", "logic", None),
                ("can_chinh", "logic", None),
                ("khuyen_cao", "danh_muc", None),
            )
        ]
        return BoDuLieu(ma="", cot=columns, dong=rows, can_cu=[ma])
    except (ValueError, TypeError):
        return None


def _cat(text: str | None, limit: int = _MAX_KY_TU_TRUONG) -> str:
    """Gộp khoảng trắng và cắt gọn ở ranh giới từ để dòng bảng không dài."""
    clean = " ".join((text or "").split())
    if not clean:
        return "thiếu"
    if len(clean) <= limit:
        return clean
    head = clean[: max(1, limit - 2)]
    cut = head.rsplit(" ", 1)[0].rstrip(",;:")
    return (cut or head) + " …"


def _fmt_num(value: Any) -> str:
    """Hiển thị số gọn không thêm số 0 thừa sau dấu chấm."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:g}"
    return str(value)


def _https_url(value: Any) -> str | None:
    """Chỉ giữ liên kết dùng giao thức https."""
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.startswith("https://"):
            return cleaned
    return None


def _clean_key_part(value: str) -> str:
    """Làm sạch một phần khoá dòng bảng: một dòng, chữ thường, không khoảng trắng hay ngoặc."""
    cleaned = _BAD_KEY_RE.sub("_", value.strip().lower()).strip("_")
    return cleaned or "dong"


def _make_ma(bang_luat: str, raw_khoa: str, used: set[str]) -> str:
    """Tạo mã căn cứ bang:<bang_luat>:<khoa> duy nhất, ổn định, tối đa 120 ký tự."""
    prefix = f"bang:{_clean_key_part(bang_luat)}:"
    max_tail = max(1, _MAX_KHOA - len(prefix))
    tail = _clean_key_part(raw_khoa)[:max_tail]
    candidate = f"{prefix}{tail}"
    if candidate not in used:
        used.add(candidate)
        return candidate
    suffix_no = 2
    while True:
        suffix = f":{suffix_no}"
        trimmed = tail[: max(1, max_tail - len(suffix))]
        candidate = f"{prefix}{trimmed}{suffix}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix_no += 1


def _row_key(hid: str, rule: s.QuyTacDong, index: int) -> str:
    """Lấy định danh dòng nếu bảng có; không thì <hoat_chat>:<phan>:<chỉ số>."""
    ma_dong = rule.du_lieu.get("ma_dong")
    if isinstance(ma_dong, str) and ma_dong.strip():
        return ma_dong
    ma_nhom = rule.du_lieu.get("ma_nhom")
    if (
        rule.bang_luat in {"di_ung_cheo", "nhom_dieu_tri_trung"}
        and isinstance(ma_nhom, str)
        and ma_nhom.strip()
    ):
        return ma_nhom
    return f"{hid}:{rule.phan}:{index}"


def _nhan_trang_thai(rule: s.QuyTacDong) -> str:
    """Chuẩn hoá nhãn trạng thái duyệt luôn hiển thị trên từng dòng quy tắc."""
    if rule.trang_thai:
        return _TRANG_THAI_VI.get(rule.trang_thai, _cat(rule.trang_thai, 80))
    if rule.phan == "quy_tac_cho_duyet":
        return "chờ dược sĩ duyệt"
    if "nguoi_duyet" in rule.du_lieu and rule.du_lieu.get("nguoi_duyet") is None:
        return "chưa dược sĩ duyệt"
    return "chưa ghi trạng thái"


def _source_from_dict(item: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Rút tên nguồn ngắn và URL https từ một mục nguồn dạng dict."""
    url = _https_url(item.get("url")) or _https_url(item.get("doi_url"))
    loai = str(item.get("loai") or "").strip()
    ten_nhan = str(item.get("ten_nhan") or item.get("tieu_de") or "").strip()
    if loai == "nhan_fda" and ten_nhan:
        return f"Nhãn FDA: {_cat(ten_nhan, 80)}", url
    if loai == "livertox":
        return f"LiverTox: {_cat(ten_nhan, 80)}" if ten_nhan else "LiverTox", url
    if loai == "tong_quan" and ten_nhan:
        return f"Tổng quan: {_cat(ten_nhan, 80)}", url
    if loai == "dav_dang_bao_che":
        return "DAV", url
    if loai == "ndc_openfda":
        return "openFDA NDC", url
    if ten_nhan:
        return _cat(ten_nhan, 100), url
    fallback = _cat(loai, 60) if loai else None
    return fallback, url


def _extract_source(du_lieu: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Lấy mô tả nguồn và liên kết https đầu tiên nếu dòng bảng luật có."""
    url = _https_url(du_lieu.get("url"))
    nguon = du_lieu.get("nguon")
    nguon_text: str | None = None
    if isinstance(nguon, str) and nguon.strip():
        nguon_text = _cat(nguon, 120)
    elif isinstance(nguon, Mapping):
        nguon_text, found_url = _source_from_dict(nguon)
        url = url or found_url
    elif isinstance(nguon, list):
        labels: list[str] = []
        for entry in nguon:
            if not isinstance(entry, Mapping):
                continue
            label, found_url = _source_from_dict(entry)
            if label and label not in labels:
                labels.append(label)
            if url is None and found_url is not None:
                url = found_url
        if labels:
            nguon_text = ", ".join(labels[:2])

    details = du_lieu.get("nguon_chi_tiet")
    if isinstance(details, list):
        for entry in details:
            if not isinstance(entry, Mapping):
                continue
            label, found_url = _source_from_dict(entry)
            if nguon_text is None and label:
                nguon_text = label
            if url is None and found_url is not None:
                url = found_url
            if nguon_text is not None and url is not None:
                break
    return nguon_text, url


def _fmt_crcl_range(tier: Mapping[str, Any]) -> str:
    """Định dạng khoảng CrCl từ cận dưới và cận trên của một mức chỉnh liều thận."""
    lo = tier.get("crcl_tu")
    hi = tier.get("crcl_den")
    inc_lo = bool(tier.get("bao_gom_can_duoi", True))
    inc_hi = tier.get("bao_gom_can_tren")
    if lo is not None and hi is not None:
        left = "" if inc_lo else ">"
        right = "<" if inc_hi is False else ""
        return f"{left}{_fmt_num(lo)}–{right}{_fmt_num(hi)}"
    if lo is not None:
        return f"{'>=' if inc_lo else '>'}{_fmt_num(lo)}"
    if hi is not None:
        op = "<" if inc_hi is False or not inc_lo else "<="
        return f"{op}{_fmt_num(hi)}"
    nhan = tier.get("nhan_ghi")
    return _cat(str(nhan), 40) if nhan else "không ghi khoảng"


def _fmt_dose(value: Any) -> str | None:
    """Định dạng một đối tượng {gia_tri, don_vi} thành chuỗi ngắn."""
    if not isinstance(value, Mapping):
        return None
    gia_tri = value.get("gia_tri")
    if gia_tri is None:
        return None
    don_vi = str(value.get("don_vi") or "").strip()
    return f"{_fmt_num(gia_tri)} {don_vi}".strip()


def _fmt_lieu_than(hid: str, phan: str, d: Mapping[str, Any]) -> str:
    if phan == "khong_co_nguong":
        loai = str(d.get("loai") or "").strip()
        loai_vi = _KHONG_NGUONG_VI.get(loai, _cat(loai, 80)) if loai else "chưa phân loại"
        ly_do = d.get("ly_do")
        parts = [f"{hid} · Liều thận: nhãn không ghi ngưỡng ({loai_vi})"]
        if ly_do:
            parts.append(f"lý do: {_cat(str(ly_do))}")
        return " · ".join(parts)

    chi_so = _cat(str(d.get("chi_so") or "CrCl"), 60)
    tiers = []
    for tier in d.get("muc") or []:
        if not isinstance(tier, Mapping):
            continue
        khoang = _fmt_crcl_range(tier)
        khuyen_cao = _cat(str(tier.get("khuyen_cao") or ""), _MAX_KY_TU_TRUONG)
        tiers.append(f"{khoang}: {khuyen_cao}")
    parts = [f"{hid} · Liều thận ({chi_so}): {'; '.join(tiers) if tiers else 'thiếu mức'}"]
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_lieu_gan(hid: str, d: Mapping[str, Any]) -> str:
    raw_cls = d.get("phan_loai_gan")
    if isinstance(raw_cls, list):
        cls_items = raw_cls
    elif raw_cls:
        cls_items = [raw_cls]
    else:
        cls_items = []
    cls_text = ", ".join(_GAN_LOAI_VI.get(str(x), _cat(str(x), 40)) for x in cls_items) or "chung"
    action_raw = str(d.get("hanh_dong_nhan") or "").strip()
    action = _GAN_HANH_DONG_VI.get(action_raw, _cat(action_raw, 80)) if action_raw else "thiếu"
    parts = [
        f"{hid} · Liều gan ({cls_text})",
        f"hành động: {action}",
        f"khuyến cáo: {_cat(str(d.get('khuyen_cao') or ''))}",
    ]
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_nguong_xet_nghiem(hid: str, d: Mapping[str, Any]) -> str:
    xn = _cat(str(d.get("xet_nghiem") or "xét nghiệm"), 60)
    conds: list[str] = []
    for item in d.get("dieu_kien") or []:
        if not isinstance(item, Mapping):
            continue
        ma = str(item.get("ma_xet_nghiem") or xn)
        op = str(item.get("toan_tu") or "")
        unit = str(item.get("don_vi_nhan") or "").strip()
        val = item.get("gia_tri")
        val_to = item.get("gia_tri_den")
        if op == "khoang" and val is not None and val_to is not None:
            cond = f"{ma} {_fmt_num(val)}–{_fmt_num(val_to)} {unit}".strip()
        elif val is not None:
            cond = f"{ma} {op} {_fmt_num(val)} {unit}".strip()
        else:
            cond = ma
        conds.append(cond)
    parts = [f"{hid} · Ngưỡng xét nghiệm ({xn}): {'; '.join(conds) or 'thiếu điều kiện'}"]
    if d.get("hanh_dong_nhan"):
        parts.append(f"khuyến cáo: {_cat(str(d['hanh_dong_nhan']))}")
    if d.get("dieu_kien_khac"):
        parts.append(f"điều kiện khác: {_cat(str(d['dieu_kien_khac']))}")
    if d.get("quy_doi"):
        parts.append(f"quy đổi: {_cat(str(d['quy_doi']), 140)}")
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_duong_dung(hid: str, d: Mapping[str, Any]) -> str:
    ten_dang = _cat(str(d.get("ten_nhom_dang") or d.get("nhom_dang_bao_che") or "dạng chung"), 100)
    raw_routes = d.get("duong_dung_hop_le")
    routes = ", ".join(str(x) for x in raw_routes) if isinstance(raw_routes, list) else ""
    parts = [f"{hid} · Đường dùng hợp lệ ({ten_dang}): {routes or 'thiếu'}"]
    if d.get("muc_chac_chan"):
        parts.append(f"mức chắc chắn: {_cat(str(d['muc_chac_chan']), 60)}")
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_lieu_toi_da(hid: str, phan: str, d: Mapping[str, Any]) -> str:
    if phan == "khong_ghi_toi_da":
        head = f"{hid} · Liều tối đa: nhãn không ghi ngưỡng"
        special = d.get("co_dong_theo_nhom_dac_biet")
        if isinstance(special, list) and special:
            head += f" chung (có dòng riêng cho: {', '.join(str(x) for x in special[:4])})"
        parts = [head]
        if d.get("ly_do"):
            parts.append(f"lý do: {_cat(str(d['ly_do']))}")
        return " · ".join(parts)

    doi_tuong = _cat(str(d.get("doi_tuong") or "chung"), 80)
    raw_routes = d.get("duong_dung")
    routes = ", ".join(str(x) for x in raw_routes) if isinstance(raw_routes, list) else ""
    doses: list[str] = []
    for key, label in (
        ("lieu_toi_da_lan", "tối đa/lần"),
        ("lieu_toi_da_ngay", "tối đa/ngày"),
        ("lieu_toi_da_tuan", "tối đa/tuần"),
    ):
        formatted = _fmt_dose(d.get(key))
        if formatted:
            doses.append(f"{label}: {formatted}")
    theo_kg = d.get("theo_kg")
    if isinstance(theo_kg, Mapping):
        if theo_kg.get("lan_mg_kg") is not None:
            doses.append(f"theo kg/lần: {_fmt_num(theo_kg['lan_mg_kg'])} mg/kg")
        if theo_kg.get("ngay_mg_kg") is not None:
            doses.append(f"theo kg/ngày: {_fmt_num(theo_kg['ngay_mg_kg'])} mg/kg")
    parts = [
        f"{hid} · Liều tối đa ({doi_tuong}; đường dùng: {routes or 'thiếu'}): "
        f"{'; '.join(doses) or 'thiếu số'}"
    ]
    loai = str(d.get("loai_gioi_han") or "").strip()
    if loai:
        parts.append(f"loại: {_GIOI_HAN_VI.get(loai, _cat(loai, 60))}")
    if d.get("dieu_kien"):
        parts.append(f"điều kiện: {_cat(str(d['dieu_kien']))}")
    concomitant = d.get("thuoc_dung_cung_hoat_chat_ids")
    if isinstance(concomitant, list) and concomitant:
        parts.append(f"dùng cùng: {', '.join(str(x) for x in concomitant[:6])}")
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _first_quote(d: Mapping[str, Any]) -> str | None:
    nguon = d.get("nguon")
    if isinstance(nguon, list):
        for item in nguon:
            if isinstance(item, Mapping) and item.get("trich_nguyen_van"):
                return _cat(str(item["trich_nguyen_van"]), 180)
    return None


def _fmt_doc_tinh(hid: str, phan: str, d: Mapping[str, Any]) -> str:
    if phan == "doc_than":
        nhom = _cat(str(d.get("nhom") or "thiếu"), 60)
        parts = [f"{hid} · Độc tính (độc thận; nhóm: {nhom})"]
    elif phan == "keo_dai_qt":
        muc = _cat(str(d.get("muc_nhan") or "thiếu"), 60)
        parts = [f"{hid} · Độc tính (kéo dài QT; mục nhãn: {muc})"]
    elif phan == "khoang_dieu_tri_hep":
        raw_xn = d.get("ma_xet_nghiem_nong_do")
        xn = ", ".join(str(x) for x in raw_xn) if isinstance(raw_xn, list) else "thiếu"
        parts = [f"{hid} · Độc tính (khoảng điều trị hẹp; theo dõi nồng độ: {xn})"]
    elif phan == "doc_gan_livertox":
        score = _cat(str(d.get("likelihood_score") or "thiếu"), 20)
        parts = [f"{hid} · Độc tính (độc gan LiverTox; điểm khả năng: {score})"]
    elif phan == "khong_co_nguon":
        ds = _cat(str(d.get("danh_sach") or "thiếu"), 60)
        ly_do = _cat(str(d.get("ly_do") or ""))
        return f"{hid} · Độc tính (chưa có nguồn/loại trừ cho {ds}): {ly_do}"
    else:
        parts = [f"{hid} · Độc tính ({phan})"]
    quote = _first_quote(d)
    if quote:
        parts.append(f"trích nguồn: {quote}")
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_khang_sinh(hid: str, d: Mapping[str, Any]) -> str:
    ten_vb = _cat(str(d.get("ten_trong_van_ban") or hid), 80)
    ma_nhom = str(d.get("ma_nhom") or "").strip()
    nhom_vi = _KS_NHOM_VI.get(ma_nhom, _cat(ma_nhom, 80)) if ma_nhom else "thiếu nhóm"
    parts = [f"{hid} · Kháng sinh quản lý ({ten_vb}): {nhom_vi}"]
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_di_ung_cheo(hid: str, d: Mapping[str, Any]) -> str:
    ma_nhom = _cat(str(d.get("ma_nhom") or ""), 60)
    ten_nhom = _cat(str(d.get("ten_nhom") or ""), 120)
    huong = _HUONG_VI.get(str(d.get("huong") or ""), _cat(str(d.get("huong") or ""), 40))
    rel_parts: list[str] = []
    for item in d.get("hoat_chat_lien_quan") or []:
        if not isinstance(item, Mapping):
            continue
        muc = str(item.get("muc_cheo") or "thiếu")
        nhan = str(item.get("muc_canh_bao_nhan") or "thiếu")
        ids = item.get("hoat_chat_ids")
        if isinstance(ids, list) and ids:
            shown = ", ".join(str(x) for x in ids[:5])
            if len(ids) > 5:
                shown += f" (+{len(ids) - 5} chất)"
        else:
            shown = "thiếu"
        ly_do = f" – {_cat(str(item['ly_do']), 140)}" if item.get("ly_do") else ""
        rel_parts.append(f"mức chéo {muc}, nhãn {nhan} với {shown}{ly_do}")
    header = f"{ma_nhom} – {ten_nhom}" if ma_nhom != "thiếu" else ten_nhom
    parts = [f"{hid} · Dị ứng chéo ({header}; hướng: {huong})"]
    if rel_parts:
        parts.append("; ".join(rel_parts[:2]))
    if d.get("co_so"):
        parts.append(f"cơ sở: {_cat(str(d['co_so']), 160)}")
    if d.get("ghi_chu"):
        parts.append(f"ghi chú: {_cat(str(d['ghi_chu']))}")
    return " · ".join(parts)


def _fmt_nhom_trung(hid: str, d: Mapping[str, Any]) -> str:
    ten = _cat(str(d.get("ten") or d.get("ma_nhom") or "nhóm"), 80)
    raw_atc = d.get("tien_to_atc")
    atc = ", ".join(str(x) for x in raw_atc) if isinstance(raw_atc, list) else "thiếu"
    muc = str(d.get("muc_do") or "")
    muc_vi = _MUC_TRUNG_VI.get(muc, _cat(muc, 40)) if muc else "thiếu"
    parts = [f"{hid} · Nhóm trùng điều trị ({ten}; ATC: {atc}): mức {muc_vi}"]
    raw_exc = d.get("tien_to_atc_loai_tru")
    if isinstance(raw_exc, list) and raw_exc:
        parts.append(f"loại trừ ATC: {', '.join(str(x) for x in raw_exc)}")
    if d.get("ly_do"):
        parts.append(_cat(str(d["ly_do"])))
    return " · ".join(parts)


def _fmt_fallback(hid: str, rule: s.QuyTacDong) -> str:
    """Tóm tắt gọn các trường vô hướng khi gặp bảng luật chưa có mẫu riêng."""
    items: list[str] = []
    for key, val in rule.du_lieu.items():
        if key in _SKIP_FALLBACK_KEYS or val is None or isinstance(val, (dict, list)):
            continue
        items.append(f"{key}: {_cat(str(val))}")
        if len(items) >= 4:
            break
    body = "; ".join(items) or "thiếu chi tiết"
    return f"{hid} · {rule.nhom}: {body}"


def _tom_tat_quy_tac(hid: str, rule: s.QuyTacDong) -> str:
    """Tóm tắt một dòng QuyTacDong thành một dòng văn bản có trạng thái và nguồn."""
    d = rule.du_lieu
    bang = rule.bang_luat
    if bang == "quy_tac_lieu_than":
        body = _fmt_lieu_than(hid, rule.phan, d)
    elif bang == "quy_tac_gan":
        body = _fmt_lieu_gan(hid, d)
    elif bang == "nguong_xet_nghiem":
        body = _fmt_nguong_xet_nghiem(hid, d)
    elif bang == "duong_dung_hop_le":
        body = _fmt_duong_dung(hid, d)
    elif bang == "lieu_toi_da":
        body = _fmt_lieu_toi_da(hid, rule.phan, d)
    elif bang == "doc_tinh":
        body = _fmt_doc_tinh(hid, rule.phan, d)
    elif bang == "khang_sinh_quan_ly":
        body = _fmt_khang_sinh(hid, d)
    elif bang == "di_ung_cheo":
        body = _fmt_di_ung_cheo(hid, d)
    elif bang == "nhom_dieu_tri_trung":
        body = _fmt_nhom_trung(hid, d)
    else:
        body = _fmt_fallback(hid, rule)

    extras: list[str] = []
    for key in _EXTRA_TEXT_KEYS:
        raw_val = d.get(key)
        if isinstance(raw_val, str) and raw_val.strip():
            snippet = _cat(raw_val)
            if snippet not in body and snippet not in extras:
                extras.append(snippet)
    segments = [body, *extras, f"trạng thái: {_nhan_trang_thai(rule)}"]

    nguon_text, url = _extract_source(d)
    if bang == "khang_sinh_quan_ly" and nguon_text is None:
        trang = d.get("trang_pdf")
        nguon_text = f"QĐ 5631/QĐ-BYT, tr.{trang}" if trang is not None else "QĐ 5631/QĐ-BYT"
    if nguon_text and url:
        segments.append(f"nguồn: {nguon_text} ({url})")
    elif nguon_text:
        segments.append(f"nguồn: {nguon_text}")
    elif url:
        segments.append(f"nguồn: {url}")
    return " · ".join(segments)


def _chon_ung_vien(items: Sequence[s.GoiYThuoc]) -> list[s.GoiYThuoc]:
    """Chọn tối đa 5 ứng viên, ưu tiên mỗi tập hoạt chất một đại diện trước."""
    out: list[s.GoiYThuoc] = []
    seen_sets: set[frozenset[str]] = set()
    seen_sigs: set[tuple[str, frozenset[str]]] = set()
    rest: list[s.GoiYThuoc] = []
    for item in items:
        ing_set = frozenset(item.hoat_chat_ids)
        sig = (item.nhan.strip().lower(), ing_set)
        if sig in seen_sigs:
            continue
        seen_sigs.add(sig)
        if ing_set and ing_set not in seen_sets:
            seen_sets.add(ing_set)
            out.append(item)
        else:
            rest.append(item)
    for item in rest:
        if len(out) >= _MAX_UNG_VIEN:
            break
        out.append(item)
    return out[:_MAX_UNG_VIEN]


def _phan_giai_ten(
    items: Sequence[s.GoiYThuoc],
) -> tuple[Literal["ok", "mo_ho", "khong_thay"], list[str], str | None, list[s.GoiYThuoc]]:
    """Phân giải tên theo mức khớp: chỉ nhận chính xác hoặc tiền tố về đúng một tập hoạt chất."""
    if not items:
        return "khong_thay", [], None, []
    for tier in ("chinh_xac", "tien_to"):
        matched = [item for item in items if item.khop == tier]
        if not matched:
            continue
        sets = {frozenset(item.hoat_chat_ids) for item in matched if item.hoat_chat_ids}
        if len(sets) == 1:
            ids = list(dict.fromkeys(matched[0].hoat_chat_ids))
            return "ok", ids, tier, []
        return "mo_ho", [], None, _chon_ung_vien(matched)
    fuzzy = [item for item in items if item.khop == "gan_dung"]
    if fuzzy:
        return "mo_ho", [], None, _chon_ung_vien(fuzzy)
    return "khong_thay", [], None, []


def _format_che_pham_block(info_ten: str, products: s.DanhSachChePham) -> list[str]:
    """Định dạng khối ≤ 5 chế phẩm đầu kèm tổng số cho một hoạt chất."""
    top = products.danh_sach[:_MAX_CHE_PHAM]
    if products.tong == 0 or not top:
        return [f"Chế phẩm ({info_ten}): 0 chế phẩm trong danh mục Cục QLD."]
    lines = [
        f"Chế phẩm ({info_ten}, tổng {products.tong} chế phẩm; hiển thị {len(top)} chế phẩm đầu):"
    ]
    for item in top:
        if item.ham_luong is not None:
            hl = f"{_fmt_num(item.ham_luong)} {item.don_vi or ''}".strip()
        else:
            hl = "chưa ghi hàm lượng"
        sdk = _cat(item.so_dang_ky, 40) if item.so_dang_ky else "thiếu"
        lines.append(f"- {_cat(item.ten_thuoc, 120)} · SĐK: {sdk} · hàm lượng: {hl}")
    return lines


class TraThuoc(Tool):
    """Tra định danh thuốc, bảng quy tắc theo hoạt chất và chế phẩm Cục QLD."""

    ten: ClassVar[str] = "tra_thuoc"
    ten_hien_thi: ClassVar[str] = "Tra thuốc"
    mo_ta: ClassVar[str] = (
        "Tra thông tin thuốc theo tên tự do, biệt dược hoặc tên hoạt chất: định danh "
        "(INN, tên Việt, ATC, DDInter), các bảng quy tắc theo hoạt chất (liều tối đa, liều thận, "
        "liều gan, ngưỡng xét nghiệm, đường dùng hợp lệ, độc tính, kháng sinh quản lý, dị ứng "
        "chéo, nhóm trùng điều trị; không gồm thuốc–bệnh đã có ở tra_tuong_tac) và chế phẩm Cục "
        "QLD. Dùng phan để chọn phần cần trả và nhom_quy_tac để lọc nhóm quy tắc. Mỗi dòng định "
        "danh/quy tắc mở đầu bằng [bang:...]; khi trích dùng loai=bang với đúng mã đó. Ngưỡng "
        "trả về chỉ để tham khảo, không phải kết luận cho ca bệnh."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoTraThuoc
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca", "chung"})
    goi_ra_ngoai: ClassVar[bool] = False
    so_can_cu_toi_da: ClassVar[int] = _MAX_CAN_CU

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        """Phân giải tên thuốc và gom đúng các phần được yêu cầu; lỗi lookup trả loi_cong_cu."""
        del ctx
        assert isinstance(tham_so, ThamSoTraThuoc)
        try:
            return self._thuc_thi(tham_so)
        except Exception:
            return KetQuaCongCu(
                trang_thai="loi",
                ma_loi="loi_cong_cu",
                noi_dung="Không tra cứu được thông tin thuốc từ danh mục.",
            )

    def _thuc_thi(self, tham_so: ThamSoTraThuoc) -> KetQuaCongCu:
        from app.api import lookup

        suggested = lookup.suggest_drugs(tham_so.ten, limit=_SUGGEST_LIMIT)
        trang_thai_pg, hoat_chat_ids, muc_khop, ung_vien = _phan_giai_ten(suggested.ket_qua)
        if trang_thai_pg == "khong_thay":
            return KetQuaCongCu(
                trang_thai="khong_co",
                noi_dung="Không tìm thấy trong danh mục.",
                chi_tiet_tien_trinh="0 hoạt chất",
            )
        if trang_thai_pg == "mo_ho":
            lines = [
                "Tên thuốc chưa xác định duy nhất một hoạt chất; "
                "cần hỏi lại dược sĩ thuốc nào trong các ứng viên sau:"
            ]
            for idx, item in enumerate(ung_vien, start=1):
                hc_text = ", ".join(item.ten_hoat_chat or item.hoat_chat_ids) or "thiếu"
                khop_vi = _KHOP_VI.get(item.khop, item.khop)
                lines.append(
                    f"{idx}. {_cat(item.nhan, 100)} · hoạt chất: {_cat(hc_text, 120)} · "
                    f"mức khớp: {khop_vi} ({item.khop})"
                )
            return KetQuaCongCu(
                trang_thai="khong_co",
                noi_dung="\n".join(lines),
                chi_tiet_tien_trinh=f"{len(ung_vien)} ứng viên, cần hỏi lại",
            )

        assert muc_khop is not None
        selected_ids = hoat_chat_ids[:_MAX_HOAT_CHAT]
        notes: list[str] = []
        if len(hoat_chat_ids) > _MAX_HOAT_CHAT:
            notes.append(
                f"(biệt dược có {len(hoat_chat_ids)} hoạt chất; "
                f"chỉ hiển thị {_MAX_HOAT_CHAT} hoạt chất đầu)"
            )

        phan_set = set(tham_so.phan)
        nhom_loc = set(tham_so.nhom_quy_tac)
        used_ma: set[str] = set()
        dinh_danh_rows: list[_Dong] = []
        quy_tac_rows: list[_Dong] = []
        seen_rules: set[tuple[str, str, str]] = set()
        che_pham_lines: list[str] = []
        total_products_shown = 0
        has_products = False
        found_ingredients = 0

        for hid in selected_ids:
            identity = lookup.drug_identity(hid)
            if identity is None:
                notes.append(f"Không tìm thấy hoạt chất {hid} trong danh mục.")
                continue
            found_ingredients += 1
            if "dinh_danh" in phan_set:
                ma = _make_ma("tra_cuu_hoat_chat", identity.hoat_chat_id, used_ma)
                khop_vi = _KHOP_VI.get(muc_khop, muc_khop)
                atc_text = ", ".join(identity.ma_atc) or "thiếu"
                body = (
                    f"{identity.ten_inn} (mã: {identity.hoat_chat_id}) · "
                    f"tên Việt: {identity.ten_viet or 'thiếu'} · "
                    f"ATC: {atc_text} · loại: {identity.loai} · "
                    f"DDInter: {identity.ddinter_id or 'chưa có'} · "
                    f"mức khớp: {khop_vi} ({muc_khop}) · nguồn: {identity.nguon}"
                )
                dinh_danh_rows.append(_Dong(ma, _NHAN_DINH_DANH, body))

            if "quy_tac" in phan_set:
                raw_rules = lookup.drug_rules(hid, identity.ma_atc)
                filtered = [
                    rule
                    for rule in raw_rules
                    if rule.nhom != "thuoc_benh" and (not nhom_loc or rule.nhom in nhom_loc)
                ]
                ordered = sorted(
                    filtered,
                    key=lambda item: 1 if item.phan in _LOW_PRIORITY_SECTIONS else 0,
                )
                if not ordered:
                    if nhom_loc:
                        notes.append(
                            f"{identity.ten_inn}: không có quy tắc thuộc nhóm "
                            f"{', '.join(tham_so.nhom_quy_tac)} trong kho."
                        )
                    else:
                        notes.append(f"{identity.ten_inn}: chưa có quy tắc nào trong kho.")
                per_section_idx: dict[tuple[str, str], int] = {}
                for rule in ordered:
                    sec_key = (rule.bang_luat, rule.phan)
                    per_section_idx[sec_key] = per_section_idx.get(sec_key, 0) + 1
                    body = _tom_tat_quy_tac(hid, rule)
                    dedup_sig = (rule.bang_luat, rule.phan, body)
                    if dedup_sig in seen_rules:
                        continue
                    seen_rules.add(dedup_sig)
                    raw_khoa = _row_key(hid, rule, per_section_idx[sec_key])
                    ma = _make_ma(rule.bang_luat, raw_khoa, used_ma)
                    nhan = _NHAN_BANG.get(rule.bang_luat, f"Bảng quy tắc ({rule.bang_luat})")
                    dong = _Dong(ma, nhan, body)
                    if rule.bang_luat == "quy_tac_lieu_than" and rule.phan == "quy_tac":
                        dong.bo_du_lieu = _renal_dataset(rule.du_lieu, ma)
                    quy_tac_rows.append(dong)

            if "che_pham" in phan_set:
                products = lookup.drug_products(hid, limit=_MAX_CHE_PHAM)
                if products is not None:
                    shown = min(len(products.danh_sach), _MAX_CHE_PHAM)
                    total_products_shown += shown
                    if products.tong > 0 and shown > 0:
                        has_products = True
                    che_pham_lines.extend(_format_che_pham_block(identity.ten_inn, products))

        return self._dong_goi(
            dinh_danh_rows=dinh_danh_rows,
            quy_tac_rows=quy_tac_rows,
            che_pham_lines=che_pham_lines,
            notes=notes,
            phan_set=phan_set,
            found_ingredients=found_ingredients,
            total_products_shown=total_products_shown,
            has_products=has_products,
        )

    @staticmethod
    def _dong_goi(
        *,
        dinh_danh_rows: list[_Dong],
        quy_tac_rows: list[_Dong],
        che_pham_lines: list[str],
        notes: list[str],
        phan_set: set[PhanTraThuoc],
        found_ingredients: int,
        total_products_shown: int,
        has_products: bool,
    ) -> KetQuaCongCu:
        """Cắt trần 20 dòng bảng và 6500 ký tự tổng; dựng căn cứ và tiến trình chỉ số đếm."""
        all_rows = [*dinh_danh_rows, *quy_tac_rows]
        has_footer = bool(all_rows or has_products)
        footer_len = len(_CHAN_LUU_Y) + 1 if has_footer else 0
        extra_budget = sum(len(line) + 1 for line in (*che_pham_lines, *notes))
        row_budget = _MAX_KY_TU_NOI_DUNG - footer_len - min(extra_budget, 2000) - 60

        kept: list[_Dong] = []
        used_chars = 0
        for row in all_rows:
            line_len = len(row.ma) + len(row.noi_dung) + 4
            if len(kept) >= _MAX_DONG or used_chars + line_len > row_budget:
                break
            kept.append(row)
            used_chars += line_len

        lines = [f"[{row.ma}] {row.noi_dung}" for row in kept]
        con_lai = len(all_rows) - len(kept)
        if con_lai > 0:
            lines.append(f"(còn {con_lai} dòng nữa chưa hiển thị)")

        current_len = len("\n".join(lines))
        max_body = _MAX_KY_TU_NOI_DUNG - footer_len
        for extra in (*che_pham_lines, *notes):
            sep = 1 if lines else 0
            if current_len + sep + len(extra) > max_body:
                break
            lines.append(extra)
            current_len += sep + len(extra)

        if has_footer:
            lines.append(_CHAN_LUU_Y)

        can_cu = [
            CanCu(ma=row.ma, loai="bang", nhan=row.nhan, noi_dung=row.noi_dung) for row in kept
        ]
        kept_rules = sum(1 for row in kept if not row.ma.startswith("bang:tra_cuu_hoat_chat:"))
        summary_parts = [f"{found_ingredients} hoạt chất"]
        if "quy_tac" in phan_set:
            summary_parts.append(f"{kept_rules} quy tắc")
        if "che_pham" in phan_set:
            summary_parts.append(f"{total_products_shown} chế phẩm")
        has_content = bool(kept or has_products)
        return KetQuaCongCu(
            trang_thai="ok" if has_content else "khong_co",
            noi_dung="\n".join(lines) if lines else "Không tìm thấy trong danh mục.",
            can_cu=can_cu,
            bo_du_lieu=[row.bo_du_lieu for row in kept if row.bo_du_lieu is not None],
            chi_tiet_tien_trinh=", ".join(summary_parts),
        )


__all__ = ["NhomQuyTac", "PhanTraThuoc", "ThamSoTraThuoc", "TraThuoc"]
