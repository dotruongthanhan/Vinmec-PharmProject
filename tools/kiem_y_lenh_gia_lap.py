"""Kiểm y lệnh trong 60 hồ sơ giả lập: form, thuốc, liều, lịch dùng, chuỗi đổi/ngưng.

Chạy: PYTHONUTF8=1 uv run python tools/kiem_y_lenh_gia_lap.py [--chi-tiet]
Chỉ đọc, không sửa dữ liệu. Mức LOI = sai form/nhất quán; CANH_BAO = thiếu trường nên thêm.
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUONG_CHUAN = {
    "uống",
    "tiêm tĩnh mạch",
    "truyền tĩnh mạch",
    "tiêm dưới da",
    "tiêm bắp",
    "đường thở",
    "nhỏ mũi",
    "tại chỗ",
    "đặt hậu môn",
    "ngậm dưới lưỡi",
}
DUONG_KHONG_THUOC = {"lấy máu tĩnh mạch", "không áp dụng"}
DON_VI_CHUAN = {
    "mg",
    "g",
    "mcg",
    "mL",
    "IU",
    "viên",
    "mg/kg",
    "mL/giờ",
    "L/phút",
    "triệu đơn vị",
    "lần",
}
DUONG_TREN_THUOC = {  # đường dùng của thuốc (danh mục) phải khớp đường dùng của dòng y lệnh
    "uống": {"uống"},
    "tiêm tĩnh mạch": {"tiêm tĩnh mạch", "truyền tĩnh mạch"},
    "truyền tĩnh mạch": {"tiêm tĩnh mạch", "truyền tĩnh mạch"},
}


def _dt(v):
    return datetime.fromisoformat(v) if v else None


def kiem(path: Path) -> tuple[list[str], list[str]]:
    d = json.loads(path.read_text(encoding="utf-8"))
    loi, canh = [], []
    hs = d["ho_so_id"]
    dm = {t["thuoc_id"]: t for t in d["danh_muc_thuoc"]}
    y_ids = {y["y_lenh_id"]: y for dot in d["dot_dieu_tri"] for y in dot["y_lenh"]}
    trong_tam = d.get("y_lenh_trong_tam")
    cho_duyet = [i for i, y in y_ids.items() if y["trang_thai"] == "cho_duyet"]
    if cho_duyet != [trong_tam]:
        loi.append(f"{hs}: y lệnh chờ duyệt {cho_duyet} khác trọng tâm {trong_tam}")
    for dot in d["dot_dieu_tri"]:
        b, k = _dt(dot["thoi_diem_bat_dau"]), _dt(dot.get("thoi_diem_ket_thuc"))
        for y in dot["y_lenh"]:
            yid = y["y_lenh_id"]
            ke = _dt(y["thoi_diem_ke"])
            if ke < b or (k and ke > k):
                loi.append(f"{yid}: thời điểm kê ngoài đợt điều trị")
            if y["khoa_ke_don"] != dot["khoa_dieu_tri"] and y["khoa_ke_don"] not in json.dumps(
                dot.get("lich_su_khoa") or [], ensure_ascii=False
            ):
                canh.append(
                    f"{yid}: khoa kê '{y['khoa_ke_don']}' khác khoa đợt '{dot['khoa_dieu_tri']}'"
                )
            if not y["chi_tiet"]:
                loi.append(f"{yid}: không có dòng chi tiết")
            if y["trang_thai"] == "ngung" and not (
                y.get("ly_do_ngung") and y.get("thoi_diem_ngung")
            ):
                loi.append(f"{yid}: trạng thái ngưng nhưng thiếu lý do hoặc thời điểm ngưng")
            if y["trang_thai"] != "ngung" and (y.get("ly_do_ngung") or y.get("thoi_diem_ngung")):
                loi.append(f"{yid}: có lý do/thời điểm ngưng nhưng trạng thái {y['trang_thai']}")
            tt = y.get("thay_the_y_lenh_id")
            if tt and tt not in y_ids:
                loi.append(f"{yid}: thay thế y lệnh không tồn tại {tt}")
            if tt and y_ids.get(tt, {}).get("trang_thai") != "ngung":
                canh.append(f"{yid}: thay thế {tt} nhưng y lệnh cũ chưa ở trạng thái ngưng")
            if (
                y["luong_duyet"] == "truc_tiep"
                and y["loai"] == "cap_cuu"
                and y["muc_uu_tien"] is None
            ):
                canh.append(f"{yid}: y lệnh cấp cứu nhưng mức ưu tiên trống")
            for c in y["chi_tiet"]:
                cid = c["chi_tiet_y_lenh_id"]
                tid = c.get("thuoc_id")
                duong = c.get("duong_dung")
                if c["loai_san_pham"] == "thuoc" and not tid:
                    loi.append(f"{cid}: loại thuốc nhưng không có thuoc_id")
                if tid and tid not in dm:
                    loi.append(f"{cid}: thuốc {tid} không có trong danh mục")
                if duong and duong not in DUONG_CHUAN | DUONG_KHONG_THUOC:
                    loi.append(f"{cid}: đường dùng '{duong}' sai chuẩn")
                if c["loai_san_pham"] == "thuoc":
                    if c.get("lieu_moi_lan") in (None, 0):
                        loi.append(f"{cid}: thuốc thiếu liều mỗi lần")
                    du = c.get("don_vi_lieu")
                    if du not in DON_VI_CHUAN:
                        loi.append(f"{cid}: đơn vị liều '{du}' sai chuẩn")
                    if not duong:
                        loi.append(f"{cid}: thuốc thiếu đường dùng")
                    if not c.get("tan_suat"):
                        loi.append(f"{cid}: thuốc thiếu tần suất")
                    if (
                        c.get("so_lan_moi_ngay") is None
                        and "khi" not in (c.get("tan_suat") or "")
                        and "truyền" not in (c.get("tan_suat") or "")
                        and "lần" != du
                    ):
                        canh.append(
                            f"{cid}: thiếu số lần mỗi ngày (tần suất '{c.get('tan_suat')}')"
                        )
                    if tid in dm and duong and dm[tid].get("duong_dung") in DUONG_TREN_THUOC:
                        if duong not in DUONG_TREN_THUOC[dm[tid]["duong_dung"]]:
                            loi.append(
                                f"{cid}: đường '{duong}' không khớp danh mục '{dm[tid]['duong_dung']}'"  # noqa: E501
                            )
                bd, kt = _dt(c["bat_dau"]), _dt(c.get("ket_thuc"))
                if bd < ke:
                    loi.append(f"{cid}: bắt đầu trước thời điểm kê")
                if kt and kt < bd:
                    loi.append(f"{cid}: kết thúc trước bắt đầu")
                n, gap = c.get("so_lan_moi_ngay"), c.get("khoang_cach_gio")
                if n and gap and abs(n * gap - 24) > 0.01 and n * gap <= 24:
                    canh.append(f"{cid}: {n} lần x {gap} giờ không phủ 24 giờ")
                ld = c.get("lich_dung") or []
                if ld and any(
                    x["don_vi"] != c.get("don_vi_lieu") or x["lieu"] != c.get("lieu_moi_lan")
                    for x in ld
                ):
                    loi.append(f"{cid}: lịch dùng lệch liều/đơn vị của dòng")
                if ld and gap and len(ld) > 1:
                    ts = [_dt(x["thoi_diem_du_kien"]) for x in ld]
                    if any(
                        abs((b2 - a).total_seconds() / 3600 - gap) > 0.01
                        for a, b2 in zip(ts, ts[1:], strict=False)
                    ):
                        loi.append(f"{cid}: lịch dùng không đều theo khoảng cách {gap} giờ")
                if (
                    c["loai_san_pham"] == "thuoc"
                    and not ld
                    and y["trang_thai"] in ("dang_thuc_hien", "cho_duyet", "da_duyet")
                ):
                    canh.append(f"{cid}: thiếu lịch dùng (đang hiệu lực)")
                cd = c.get("cach_dung") or ""
                if c["loai_san_pham"] == "thuoc" and not cd:
                    canh.append(f"{cid}: thiếu cách dùng")
                tt_dong, tt_yl = c["trang_thai_dong"], y["trang_thai"]
                ok = {
                    "cho_duyet": {"pending"},
                    "da_duyet": {"pending", "active"},
                    "dang_thuc_hien": {"active"},
                    "ngung": {"discontinued"},
                    "hoan_tat": {"completed"},
                }
                if tt_dong not in ok[tt_yl]:
                    loi.append(f"{cid}: trạng thái dòng '{tt_dong}' không khớp y lệnh '{tt_yl}'")
    return loi, canh


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chi-tiet", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    tong_loi, tong_canh = defaultdict(list), defaultdict(list)
    for p in sorted((ROOT / "data/mock/hoso_gia_lap").glob("HS-*.json")):
        loi, canh = kiem(p)
        if loi:
            tong_loi[p.stem] = loi
        if canh:
            tong_canh[p.stem] = canh
    nhom = Counter()
    for v in list(tong_loi.values()) + list(tong_canh.values()):
        for m in v:
            nhom[m.split(": ", 1)[1].split(" '")[0].split(" (")[0][:60]] += 1
    print(
        f"Hồ sơ có LỖI: {len(tong_loi)}/60 ({sum(map(len, tong_loi.values()))} mục); "
        f"CẢNH BÁO: {len(tong_canh)}/60 ({sum(map(len, tong_canh.values()))} mục)"
    )
    for k, v in nhom.most_common():
        print(f"  {v:4d}  {k}")
    if a.chi_tiet:
        for hs, v in tong_loi.items():
            print(hs, "LOI", *v, sep="\n   ")
        for hs, v in tong_canh.items():
            print(hs, "CANH_BAO", *v, sep="\n   ")
    return 1 if tong_loi else 0


if __name__ == "__main__":
    raise SystemExit(main())
