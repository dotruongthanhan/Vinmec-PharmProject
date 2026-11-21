"""Bổ sung thông tin giả lập T45 xác định; không sửa nội dung hồ sơ cũ."""

import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ETHNICITIES = ("Kinh", "Tày", "Mường", "Nùng", "Hoa")
PAYMENT_TYPES = ("bhyt", "thu_phi", "mien", "khac")
REFERRAL_TYPES = ("co_quan_y_te", "tu_den", "khac")
DISCHARGE_TYPES = ("ra_vien", "xin_ve", "bo_ve", "dua_ve", "chuyen_vien")
ADDRESSES = (
    ("Phố Kim Mã", "Kim Mã", "Ba Đình", "Hà Nội"),
    ("Phố Bạch Mai", "Bạch Mai", "Hai Bà Trưng", "Hà Nội"),
    ("Phố Dịch Vọng", "Dịch Vọng", "Cầu Giấy", "Hà Nội"),
    ("Thôn Đoài", "Việt Hùng", "Đông Anh", "Hà Nội"),
    ("Phố Ngô Gia Tự", "Tiền An", "Bắc Ninh", "Bắc Ninh"),
    ("Phố Trưng Trắc", "Quang Trung", "Hưng Yên", "Hưng Yên"),
)


def source_paths(root: Path) -> list[Path]:
    """Giữ đúng thứ tự đánh số 1–66 trong brief."""
    return [root / f"data/mock/hoso_gia_lap/HS-{n:03}.json" for n in range(1, 61)] + [
        root / f"data/mock/demo/DEMO-{n:02}.json" for n in range(1, 7)
    ]


def encounters(record: dict[str, Any]) -> list[dict[str, Any]]:
    value = record["dot_dieu_tri"]
    return value if isinstance(value, list) else [value]


def nearest_measurement(record: dict[str, Any], kind: str) -> float | None:
    """Lấy số đo gần thời điểm vào đợt mới nhất, không bù số liệu thiếu."""
    ordered = sorted(encounters(record), key=lambda row: row["thoi_diem_bat_dau"])
    admission = datetime.fromisoformat(ordered[-1]["thoi_diem_bat_dau"])
    measures = [
        measure
        for encounter in ordered
        for measure in encounter.get("sinh_hieu", record.get("sinh_hieu", []))
        if measure["loai"] == kind
    ]
    if not measures:
        return None
    measure = min(
        measures,
        key=lambda row: abs(
            (datetime.fromisoformat(row["thoi_diem_do"]) - admission).total_seconds()
        ),
    )
    return float(measure["gia_tri"])


def enrich_record(record: dict[str, Any], number: int) -> dict[str, Any]:
    """Sinh giá trị từ số thứ tự cố định, giữ nguyên tất cả khóa cũ."""
    result = copy.deepcopy(record)
    patient = record["nguoi_benh"]
    age = patient["tuoi"]
    first = min(encounters(record), key=lambda row: row["thoi_diem_bat_dau"])
    admission = datetime.fromisoformat(first["thoi_diem_bat_dau"]).date()
    # Dùng cùng ngày/tháng vào viện để khớp chính xác tuổi tại lần vào đầu.
    birth = admission.replace(year=admission.year - age)
    street, ward, district, province = ADDRESSES[(number - 1) % len(ADDRESSES)]
    payment = "thu_phi" if number % 9 == 0 else "bhyt"
    guardian = {"ho_ten": f"Nguyễn Thị {number}", "nghe_nghiep": "Lao động tự do"}
    height = nearest_measurement(record, "chieu_cao")
    # Chỉ tạo chiều cao giả lập khi brief cho phép; không suy diễn cân nặng còn thiếu.
    if height is None:
        height = float(
            {3: 95, 4: 102, 5: 109, 6: 115, 8: 127}.get(
                age, 170 if patient["gioi_tinh"] == "nam" else 158
            )
        )
    administrative = {
        "ho_ten": f"Nguyễn {'Văn' if patient['gioi_tinh'] == 'nam' else 'Thị'} {number}",
        "ngay_sinh": birth.isoformat(),
        "dan_toc": ETHNICITIES[1 + (number // 11) % 4] if number % 11 == 0 else "Kinh",
        "ngoai_kieu": None,
        "nghe_nghiep": None
        if age < 6
        else "Học sinh"
        if age < 18
        else "Hưu trí"
        if age >= 60
        else "Lao động tự do",
        "dia_chi": {
            "so_nha": f"{9000 + number}",
            "thon_pho": street,
            "xa_phuong": ward,
            "huyen": district,
            "tinh_thanh": province,
        },
        "doi_tuong": payment,
        "bhyt": {"so_the": f"GD401{number:010d}", "gia_tri_den": "2030-12-31"}
        if payment == "bhyt"
        else None,
        "nguoi_bao_tin": {
            "ho_ten": guardian["ho_ten"],
            "quan_he": "Mẹ" if age < 16 else "Người thân",
            "dien_thoai": f"0900 000 0{number:02d}",
        },
        "bo_me": {
            "bo": {"ho_ten": f"Nguyễn Văn {number}", "nghe_nghiep": "Lao động tự do"},
            "me": guardian,
        }
        if age < 16
        else None,
        "chieu_cao_cm": height,
        "can_nang_kg": nearest_measurement(record, "can_nang"),
        "nhom_mau": None,
    }
    result.setdefault("hanh_chinh", administrative)
    for index, encounter in enumerate(encounters(result), 1):
        referral = (
            "co_quan_y_te"
            if encounter.get("hinh_thuc_vao") == "cap_cuu"
            and number % 4 == 0
            and encounter["loai_dieu_tri"] != "ngoai_tru"
            else "tu_den"
        )
        history = encounter.get("lich_su_khoa") or []
        management = {
            "noi_gioi_thieu": referral,
            "tuyen_chuyen_den": "Cơ sở y tế chuyển đến (giả lập)"
            if referral == "co_quan_y_te"
            else None,
            "vao_khoa_luc": history[0]["tu"] if history else encounter["thoi_diem_bat_dau"],
            "so_giuong": f"G-{number:03d}-{index:02d}"
            if encounter["loai_dieu_tri"] == "noi_tru"
            else None,
            "so_luu_tru": f"LT-2026-{number * 100 + index:05d}",
            "ma_yt": f"YT-2026-{number:03d}-{index:02d}",
            "ra_vien": {
                "hinh_thuc": "ra_vien",
                "chuyen_vien_den": None,
                "ly_do": encounter.get("tong_ket"),
            }
            if encounter.get("thoi_diem_ket_thuc")
            else None,
            "bac_si_dieu_tri": "Bác sĩ điều trị",
        }
        encounter.setdefault("quan_ly", management)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    paths = source_paths(ROOT)
    originals = ROOT / "data/mock/_goc_truoc_T45"
    if len(list(originals.glob("*.json"))) != 66:
        print("Thiếu 66 bản gốc trước T45; dừng, không ghi tệp.")
        return 1
    pending = []
    # Kiểm toàn bộ trước khi ghi, không tự sửa dữ liệu không khớp bản gốc.
    from tools.kiem_hanh_chinh import check_record

    for number, path in enumerate(paths, 1):
        record = json.loads(path.read_text(encoding="utf-8"))
        original = json.loads((originals / path.name).read_text(encoding="utf-8"))
        enriched = enrich_record(record, number)
        errors = check_record(enriched, original, number)
        if errors:
            print(f"Lỗi {path.name}: {'; '.join(errors)}")
            return 1
        pending.append((path, record, enriched))
    changed = 0
    for path, record, enriched in pending:
        if record != enriched:
            changed += 1
            if not args.dry_run:
                path.write_text(
                    json.dumps(enriched, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
    print(f"{'DRY-RUN: ' if args.dry_run else ''}66 tệp hợp lệ; {changed} tệp cần bổ sung.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
