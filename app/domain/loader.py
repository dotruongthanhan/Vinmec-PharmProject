"""Bộ nạp dữ liệu ca bệnh từ JSON và các hàm truy xuất bối cảnh cơ bản."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    DapAn,
    HoatChat,
    KetQuaXetNghiem,
    SinhHieu,
)


def load_case(path: Path) -> CaBenh:
    """Nạp một ca bệnh từ tệp JSON mã hoá UTF-8."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise ValidationError.from_exception_data(
            "CaBenh",
            [
                {
                    "type": "json_invalid",
                    "loc": (),
                    "input": None,
                    "ctx": {"error": "JSON không hợp lệ"},
                }
            ],
        ) from None
    if not isinstance(raw, dict):
        return CaBenh.model_validate(raw)
    # Hai phần mở rộng chỉ dành cho giao diện, không đi vào pipeline AI.
    raw.pop("hanh_chinh", None)
    if isinstance(raw.get("dot_dieu_tri"), dict):
        raw["dot_dieu_tri"].pop("quan_ly", None)
    return CaBenh.model_validate(raw)


def load_all_cases(folder: Path) -> list[CaBenh]:
    """Nạp mọi tệp *.json trong thư mục và sắp xếp tăng dần theo ca_id."""
    cases = [load_case(file_path) for file_path in sorted(Path(folder).glob("*.json"))]
    return sorted(cases, key=lambda ca: ca.ca_id)


def load_answer(path: Path) -> DapAn:
    """Nạp đáp án chuẩn của ca bệnh từ tệp JSON mã hoá UTF-8."""
    raw = Path(path).read_text(encoding="utf-8")
    return DapAn.model_validate_json(raw)


def latest_lab(ca: CaBenh, ma_xet_nghiem: str) -> KetQuaXetNghiem | None:
    """Trả về kết quả xét nghiệm mới nhất theo ma_xet_nghiem, hoặc None nếu không có."""
    matches = [xn for xn in ca.xet_nghiem if xn.ma_xet_nghiem == ma_xet_nghiem]
    if not matches:
        return None
    return max(matches, key=lambda xn: xn.thoi_diem_ket_qua)


def latest_vital(ca: CaBenh, loai: str) -> SinhHieu | None:
    """Trả về sinh hiệu mới nhất theo loai, hoặc None nếu không có."""
    matches = [sh for sh in ca.sinh_hieu if sh.loai == loai]
    if not matches:
        return None
    return max(matches, key=lambda sh: sh.thoi_diem_do)


def ingredients_of(ca: CaBenh, chi_tiet: ChiTietYLenh) -> list[HoatChat]:
    """Trả về danh sách hoạt chất của một dòng thuốc; dòng không có thuoc_id trả rỗng."""
    if chi_tiet.thuoc_id is None:
        return []
    thuoc = next((item for item in ca.danh_muc_thuoc if item.thuoc_id == chi_tiet.thuoc_id), None)
    if thuoc is None:
        return []
    hoat_chat_by_id = {hc.hoat_chat_id: hc for hc in ca.danh_muc_hoat_chat}
    result: list[HoatChat] = []
    seen: set[str] = set()
    for tp in thuoc.thanh_phan:
        if tp.hoat_chat_id not in seen and tp.hoat_chat_id in hoat_chat_by_id:
            seen.add(tp.hoat_chat_id)
            result.append(hoat_chat_by_id[tp.hoat_chat_id])
    return result
