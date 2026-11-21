"""Kiểm thông tin giả lập T45 và đối chiếu bất biến với 66 bản gốc."""

import copy
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.sinh_hanh_chinh import (
    DISCHARGE_TYPES,
    ETHNICITIES,
    PAYMENT_TYPES,
    REFERRAL_TYPES,
    ROOT,
    encounters,
    enrich_record,
    nearest_measurement,
    source_paths,
)


def check_record(record: dict[str, Any], original: dict[str, Any], number: int) -> list[str]:
    """Trả tên trường lỗi; không đưa dữ liệu hành chính vào thông báo."""
    errors: list[str] = []
    stripped = copy.deepcopy(record)
    stripped.pop("hanh_chinh", None)
    for encounter in encounters(stripped):
        encounter.pop("quan_ly", None)
    if stripped != original:
        errors.append("chỉ thêm hanh_chinh/quan_ly; nội dung gốc đã đổi")
    expected = enrich_record(original, number)
    admin = record.get("hanh_chinh")
    if not isinstance(admin, dict):
        return errors + ["thiếu hanh_chinh"]
    missing = set(expected["hanh_chinh"]) - set(admin)
    if missing:
        errors.append("thiếu hanh_chinh: " + ", ".join(sorted(missing)))
    if admin.get("ho_ten") != expected["hanh_chinh"]["ho_ten"]:
        errors.append("ho_ten không đúng quy tắc 1–66")
    if admin.get("dan_toc") not in ETHNICITIES:
        errors.append("dan_toc ngoài từ điển")
    if admin.get("doi_tuong") not in PAYMENT_TYPES:
        errors.append("doi_tuong ngoài từ điển")
    try:
        birth = date.fromisoformat(admin["ngay_sinh"])
        admission = min(
            datetime.fromisoformat(e["thoi_diem_bat_dau"]).date() for e in encounters(original)
        )
        age = (
            admission.year
            - birth.year
            - ((admission.month, admission.day) < (birth.month, birth.day))
        )
        if age != original["nguoi_benh"]["tuoi"]:
            errors.append("ngay_sinh không khớp tuoi lúc vào viện đầu")
    except (ValueError, TypeError, KeyError):
        errors.append("ngay_sinh thiếu hoặc sai định dạng")
    child = original["nguoi_benh"]["tuoi"] < 16
    parents = admin.get("bo_me")
    if child:
        if not isinstance(parents, dict) or any(
            not isinstance(parents.get(p), dict)
            or not {"ho_ten", "nghe_nghiep"} <= parents[p].keys()
            for p in ("bo", "me")
        ):
            errors.append("bo_me thiếu thông tin trẻ dưới 16 tuổi")
    elif parents is not None:
        errors.append("bo_me chỉ dành cho trẻ dưới 16 tuổi")
    contact = admin.get("nguoi_bao_tin")
    if not isinstance(contact, dict) or not {"ho_ten", "quan_he", "dien_thoai"} <= contact.keys():
        errors.append("nguoi_bao_tin thiếu trường")
    else:
        if (
            contact["ho_ten"] != f"Nguyễn Thị {number}"
            or contact["dien_thoai"] != f"0900 000 0{number:02d}"
        ):
            errors.append("nguoi_bao_tin không đúng tên/số điện thoại giả lập")
        if child and contact["quan_he"] not in ("Bố", "Mẹ"):
            errors.append("nguoi_bao_tin.quan_he phải là bố hoặc mẹ")
    address = admin.get("dia_chi")
    if (
        not isinstance(address, dict)
        or not {"so_nha", "thon_pho", "xa_phuong", "huyen", "tinh_thanh"} <= address.keys()
    ):
        errors.append("dia_chi thiếu trường")
    insurance = admin.get("bhyt")
    if admin.get("doi_tuong") == "bhyt":
        if (
            not isinstance(insurance, dict)
            or re.fullmatch(r"[A-Z]{2}\d{13}", str(insurance.get("so_the", ""))) is None
        ):
            errors.append("bhyt.so_the sai dạng 15 ký tự")
        else:
            try:
                expiry = date.fromisoformat(insurance["gia_tri_den"])
                last = max(
                    datetime.fromisoformat(
                        e.get("thoi_diem_ket_thuc") or e["thoi_diem_bat_dau"]
                    ).date()
                    for e in encounters(original)
                )
                if expiry < last:
                    errors.append("bhyt.gia_tri_den hết hạn")
            except (ValueError, TypeError, KeyError):
                errors.append("bhyt.gia_tri_den thiếu hoặc sai")
    elif insurance is not None:
        errors.append("bhyt phải null khi không có BHYT")
    for field, kind in (("can_nang_kg", "can_nang"), ("chieu_cao_cm", "chieu_cao")):
        measured = nearest_measurement(original, kind)
        if (measured is not None or kind == "can_nang") and admin.get(field) != measured:
            errors.append(f"{field} không khớp số đo gốc")
    for encounter, generated in zip(encounters(record), encounters(expected), strict=True):
        management = encounter.get("quan_ly")
        if not isinstance(management, dict):
            errors.append("thiếu quan_ly")
            continue
        missing = set(generated["quan_ly"]) - set(management)
        if missing:
            errors.append("thiếu quan_ly: " + ", ".join(sorted(missing)))
        if management.get("noi_gioi_thieu") not in REFERRAL_TYPES:
            errors.append("quan_ly.noi_gioi_thieu ngoài từ điển")
        if (
            encounter["loai_dieu_tri"] == "ngoai_tru"
            and management.get("noi_gioi_thieu") != "tu_den"
        ):
            errors.append("quan_ly.noi_gioi_thieu ngoại trú phải tu_den")
        if management.get("vao_khoa_luc") != generated["quan_ly"]["vao_khoa_luc"]:
            errors.append("quan_ly.vao_khoa_luc không khớp khoa đầu")
        if re.fullmatch(r"LT-2026-\d{5}", str(management.get("so_luu_tru"))) is None:
            errors.append("quan_ly.so_luu_tru sai dạng")
        discharge = management.get("ra_vien")
        if bool(encounter.get("thoi_diem_ket_thuc")) != isinstance(discharge, dict):
            errors.append("quan_ly.ra_vien không khớp thời điểm kết thúc")
        elif isinstance(discharge, dict):
            if discharge.get("hinh_thuc") not in DISCHARGE_TYPES:
                errors.append("quan_ly.ra_vien.hinh_thuc ngoài từ điển")
            if not {"hinh_thuc", "chuyen_vien_den", "ly_do"} <= discharge.keys() or discharge.get(
                "ly_do"
            ) != encounter.get("tong_ket"):
                errors.append("quan_ly.ra_vien không khớp tong_ket")
        if management.get("bac_si_dieu_tri") != "Bác sĩ điều trị":
            errors.append("quan_ly.bac_si_dieu_tri chỉ được ghi vai trò")
    return errors


def main() -> int:
    bad = 0
    for number, path in enumerate(source_paths(ROOT), 1):
        original_path = ROOT / "data/mock/_goc_truoc_T45" / path.name
        try:
            errors = check_record(
                json.loads(path.read_text("utf-8")),
                json.loads(original_path.read_text("utf-8")),
                number,
            )
        except (OSError, ValueError, KeyError, TypeError):
            errors = ["không đọc/kiểm được cấu trúc hồ sơ"]
        if errors:
            bad += 1
            print(f"[LỖI] {path.stem}: {'; '.join(errors)}")
    print(f"Tổng 66 hồ sơ, {bad} hồ sơ lỗi; đối chiếu chỉ thêm khóa với bản gốc T45.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
