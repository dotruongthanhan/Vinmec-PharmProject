"""Kiểm cấu trúc và tính nhất quán cơ bản của phiếu điều trị giả lập."""

import hashlib
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
HOSO = ROOT / "data/mock/hoso_gia_lap"
GOC = ROOT / "data/mock/_goc_hoso_truoc_T42"
KEYS = {
    "phieu_dieu_tri_id",
    "ngay_dieu_tri",
    "thoi_diem_lap",
    "vai_tro_nguoi_lap",
    "dien_bien",
    "danh_gia",
    "huong_xu_tri",
    "y_lenh_trong_ngay",
    "che_do_cham_soc",
    "che_do_an",
    "theo_doi",
    "dan_do",
}
TEXT = ("dien_bien", "danh_gia", "huong_xu_tri")
ROLES = {"bac_si_dieu_tri", "bac_si_truc", "hoi_chan"}
NUMBER = re.compile(
    r"(?i)\b(HA|huyết áp|mạch|nhiệt độ|SpO2|creatinin|kali|natri|đường huyết)"
    r"\s*[:=]?\s*(\d+(?:[.,]\d+)?(?:\s*/\s*\d+(?:[.,]\d+)?)?)"
)


def dt(value: str) -> datetime:
    """Đọc thời gian ISO có múi giờ."""
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("thiếu múi giờ")
    return result


def digest(value: Any) -> str:
    """Băm JSON sau chuẩn hóa."""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def day_number(start: datetime, current: datetime) -> int:
    return (current.date() - start.date()).days + 1


def check(path: Path, seen_ids: set[str], seen_text: set[tuple[str, ...]]) -> tuple[list[str], int]:
    errors: list[str] = []
    count = 0
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        original = json.loads((GOC / path.name).read_text(encoding="utf-8"))
        stripped = json.loads(json.dumps(record))
        for item in stripped["dot_dieu_tri"]:
            item.pop("phieu_dieu_tri", None)
        if digest(stripped) != digest(original):
            errors.append("phần hồ sơ gốc thay đổi")
        for encounter in record["dot_dieu_tri"]:
            start = dt(encounter["thoi_diem_bat_dau"])
            orders = encounter["y_lenh"]
            end = (
                dt(encounter["thoi_diem_ket_thuc"])
                if encounter["thoi_diem_ket_thuc"]
                else max(dt(y["thoi_diem_ke"]) for y in orders)
            )
            days = (
                1
                if encounter["loai_dieu_tri"] == "ngoai_tru"
                else (encounter["so_ngay_dieu_tri"] or max(1, day_number(start, end)))
            )
            forms = encounter.get("phieu_dieu_tri")
            if not isinstance(forms, list):
                errors.append(f"đợt {encounter['thu_tu']}: thiếu danh sách phiếu")
                continue
            count += len(forms)
            numbers: list[int] = []
            previous: datetime | None = None
            lookup = {y["y_lenh_id"]: y for y in orders}
            clinical = json.dumps(
                [encounter["sinh_hieu"], encounter["xet_nghiem"], encounter["vi_sinh"]],
                ensure_ascii=False,
            ).lower()
            for form in forms:
                if not isinstance(form, dict) or set(form) != KEYS:
                    errors.append("phiếu thiếu hoặc thừa khóa")
                    continue
                n = form["ngay_dieu_tri"]
                if type(n) is not int or not 1 <= n <= days:
                    errors.append("ngày điều trị không hợp lệ")
                    continue
                numbers.append(n)
                ident = form["phieu_dieu_tri_id"]
                if (
                    ident != f"PDT-{record['ho_so_id']}-{encounter['thu_tu']}-{n:02d}"
                    or ident in seen_ids
                ):
                    errors.append(f"ID sai hoặc trùng: {ident}")
                seen_ids.add(ident)
                timestamp = dt(form["thoi_diem_lap"])
                if (
                    not start <= timestamp <= end
                    or day_number(start, timestamp) != n
                    or (previous is not None and timestamp <= previous)
                ):
                    errors.append(f"{ident}: thời điểm không hợp lệ")
                previous = timestamp
                if form["vai_tro_nguoi_lap"] not in ROLES:
                    errors.append(f"{ident}: vai trò sai")
                if any(not isinstance(form[k], str) or not form[k].strip() for k in TEXT):
                    errors.append(f"{ident}: trường văn bản sai kiểu hoặc rỗng")
                    continue
                content = tuple(form[k] for k in TEXT)
                if not 500 <= sum(map(len, content)) <= 1200:
                    errors.append(f"{ident}: tổng độ dài ngoài 500–1200")
                if content in seen_text:
                    errors.append(f"{ident}: trùng nguyên văn")
                seen_text.add(content)
                for match in NUMBER.finditer(" ".join(content)):
                    for value in re.findall(r"\d+(?:[.,]\d+)?", match.group(2)):
                        number = float(value.replace(",", "."))
                        available = [
                            float(x) for x in re.findall(r"(?<![\w-])\d+(?:\.\d+)?", clinical)
                        ]
                        if number not in available:
                            errors.append(
                                f"{ident}: số liệu {match.group()} không có trong dữ liệu lâm sàng"
                            )
                if not isinstance(form["y_lenh_trong_ngay"], list) or any(
                    not isinstance(x, str) for x in form["y_lenh_trong_ngay"]
                ):
                    errors.append(f"{ident}: danh sách y lệnh sai kiểu")
                else:
                    for oid in form["y_lenh_trong_ngay"]:
                        order = lookup.get(oid)
                        current: date = timestamp.date()
                        if (
                            order is None
                            or dt(order["thoi_diem_ke"]).date() > current
                            or (
                                order["thoi_diem_ngung"]
                                and dt(order["thoi_diem_ngung"]).date() < current
                            )
                            or (
                                order["trang_thai"] == "cho_duyet"
                                and dt(order["thoi_diem_ke"]).date() != current
                            )
                        ):
                            errors.append(f"{ident}: y lệnh {oid} không hiệu lực")
                care = form["che_do_cham_soc"]
                if (encounter["loai_dieu_tri"] == "ngoai_tru" and care is not None) or (
                    encounter["loai_dieu_tri"] != "ngoai_tru"
                    and care not in {"cấp 1", "cấp 2", "cấp 3"}
                ):
                    errors.append(f"{ident}: chế độ chăm sóc sai")
                if (
                    not isinstance(form["che_do_an"], str)
                    or not form["che_do_an"].strip()
                    or not isinstance(form["theo_doi"], list)
                    or not 1 <= len(form["theo_doi"]) <= 4
                    or any(not isinstance(x, str) or not x.strip() for x in form["theo_doi"])
                    or (form["dan_do"] is not None and not isinstance(form["dan_do"], str))
                ):
                    errors.append(f"{ident}: chế độ ăn, theo dõi hoặc dặn dò sai")
            if numbers != sorted(set(numbers)) or len(numbers) != min(days, 10):
                errors.append(f"đợt {encounter['thu_tu']}: số phiếu hoặc thứ tự ngày sai")
            required = {1, days}
            if encounter["loai_dieu_tri"] != "ngoai_tru":
                required.update(
                    day_number(start, dt(y["thoi_diem_ngung"]))
                    for y in orders
                    if y["thoi_diem_ngung"]
                )
                required.update(
                    day_number(start, dt(y["thoi_diem_ke"]))
                    for y in orders
                    if y["thay_the_y_lenh_id"]
                )
            if not required.issubset(numbers):
                errors.append(
                    f"đợt {encounter['thu_tu']}: thiếu ngày bắt buộc "
                    f"{sorted(required - set(numbers))}"
                )
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f"không kiểm được: {exc}")
    return errors, count


def main() -> int:
    seen_ids: set[str] = set()
    seen_text: set[tuple[str, ...]] = set()
    bad = total = 0
    for i in range(1, 61):
        path = HOSO / f"HS-{i:03d}.json"
        errors, count = check(path, seen_ids, seen_text)
        total += count
        if errors:
            bad += 1
            print(f"{path.stem}: {'; '.join(errors)}")
    print(f"60 hồ sơ, {total} phiếu, {bad} hồ sơ lỗi")
    return int(bad > 0)


if __name__ == "__main__":
    sys.exit(main())
