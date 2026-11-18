"""Kiểm hồ sơ giả lập plan 1.7: cấu trúc, tham chiếu, khớp kịch bản, nạp thử vào CaBenh.

Chạy: uv run python tools/kiem_ho_so_gia_lap.py [HS-001 HS-002 ...]
Không sửa tệp nào; chỉ in lỗi. Mã thoát 1 nếu có lỗi.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOSO = ROOT / "data" / "mock" / "hoso_gia_lap"
GOLD = ROOT / "data" / "gold" / "hoso_gia_lap"
KB = ROOT / "data" / "kb" / "hoat_chat.json"

TRANG_THAI_YL = {"cho_duyet", "da_duyet", "dang_thuc_hien", "ngung", "hoan_tat"}
VAI_TRO = {"bac_si_dieu_tri", "bac_si_truc", "hoi_chan"}
LOAI_YL = {"thuong_quy", "cap_cuu", "khi_can", "hoi_chan"}
DOT_KEYS = {
    "dot_dieu_tri_id",
    "thu_tu",
    "khoa_dieu_tri",
    "loai_dieu_tri",
    "hinh_thuc_vao",
    "thoi_diem_bat_dau",
    "thoi_diem_ket_thuc",
    "so_ngay_dieu_tri",
    "lich_su_khoa",
    "ly_do_vao_vien",
    "benh_su",
    "tien_su",
    "kham_benh",
    "tom_tat",
    "chan_doan",
    "co_dia",
    "sinh_hieu",
    "xet_nghiem",
    "vi_sinh",
    "dien_bien",
    "y_lenh",
    "tong_ket",
    "quan_ly",
}
TOP_KEYS = {
    "ho_so_id",
    "kich_ban_id",
    "la_gia_lap",
    "phien_ban_sinh",
    "nguoi_benh",
    "tinh_trang_di_ung",
    "di_ung",
    "danh_muc_hoat_chat",
    "danh_muc_thuoc",
    "dot_dieu_tri",
    "y_lenh_trong_tam",
    "hanh_chinh",
}
YL_KEYS = {
    "y_lenh_id",
    "thoi_diem_ke",
    "khoa_ke_don",
    "vai_tro_nguoi_ke",
    "loai",
    "luong_duyet",
    "muc_uu_tien",
    "trang_thai",
    "thay_the_y_lenh_id",
    "ly_do_ngung",
    "thoi_diem_ngung",
    "chi_tiet",
}


def _dt(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def check(ho_so_id: str, scenario: dict, kb_ids: set[str]) -> list[str]:
    errs: list[str] = []
    path = HOSO / f"{ho_so_id}.json"
    gold_path = GOLD / f"{ho_so_id}.json"
    if not path.exists():
        return [f"thiếu tệp {path.name}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"JSON lỗi: {exc}"]
    missing = TOP_KEYS - set(data)
    extra = set(data) - TOP_KEYS
    if missing:
        errs.append(f"thiếu khóa cấp 1: {sorted(missing)}")
    if extra:
        errs.append(f"thừa khóa cấp 1: {sorted(extra)}")
    if errs:
        return errs
    if data["ho_so_id"] != ho_so_id or data["la_gia_lap"] is not True:
        errs.append("ho_so_id sai hoặc la_gia_lap khác true")
    nb = data["nguoi_benh"]
    if nb.get("tuoi") != scenario["tuoi"] or nb.get("gioi_tinh") != scenario["gioi"]:
        errs.append(f"tuổi/giới lệch kịch bản: {nb}")
    dots = data["dot_dieu_tri"]
    if len(dots) != scenario["so_dot"]:
        errs.append(f"số lần vào viện {len(dots)} khác kịch bản {scenario['so_dot']}")
    # danh mục
    hc_ids = {h["hoat_chat_id"] for h in data["danh_muc_hoat_chat"]}
    for h in data["danh_muc_hoat_chat"]:
        base = h["hoat_chat_id"].removeprefix("HC-").lower()
        if base not in kb_ids and scenario["nhom"] != "ngoai_hdsd":
            errs.append(f"hoạt chất ngoài bộ 50 tri thức: {h['hoat_chat_id']}")
    thuoc_ids = {t["thuoc_id"] for t in data["danh_muc_thuoc"]}
    for t in data["danh_muc_thuoc"]:
        for tp in t.get("thanh_phan", []):
            if tp["hoat_chat_id"] not in hc_ids:
                errs.append(f"thuốc {t['thuoc_id']} trỏ hoạt chất thiếu {tp['hoat_chat_id']}")
    # dị ứng
    trang_thai = data["tinh_trang_di_ung"].get("trang_thai")
    if (trang_thai == "co_di_ung") != bool(data["di_ung"]):
        errs.append("trang_thai dị ứng và danh sách di_ung không nhất quán")
    # đợt
    focus_ids: list[str] = []
    all_ids: set[str] = set()
    for index, dot in enumerate(dots, start=1):
        if set(dot) - DOT_KEYS - {"phieu_dieu_tri"}:
            errs.append(
                f"đợt {index} thừa khóa: {sorted(set(dot) - DOT_KEYS - {'phieu_dieu_tri'})}"
            )
        if DOT_KEYS - set(dot):
            errs.append(f"đợt {index} thiếu khóa: {sorted(DOT_KEYS - set(dot))}")
            continue
        if dot["thu_tu"] != index:
            errs.append(f"đợt {index}: thu_tu sai")
        if _dt(dot["thoi_diem_bat_dau"]) is None:
            errs.append(f"đợt {index}: thoi_diem_bat_dau không phải ISO có múi giờ")
        if not dot["y_lenh"]:
            errs.append(f"đợt {index}: không có y lệnh")
        for yl in dot["y_lenh"]:
            if set(yl) != YL_KEYS:
                errs.append(f"y lệnh {yl.get('y_lenh_id')}: khóa lệch {set(yl) ^ YL_KEYS}")
                continue
            if yl["y_lenh_id"] in all_ids:
                errs.append(f"trùng y_lenh_id {yl['y_lenh_id']}")
            all_ids.add(yl["y_lenh_id"])
            if yl["trang_thai"] not in TRANG_THAI_YL or yl["loai"] not in LOAI_YL:
                errs.append(f"y lệnh {yl['y_lenh_id']}: trang_thai hoặc loai sai")
            if yl["vai_tro_nguoi_ke"] not in VAI_TRO:
                errs.append(f"y lệnh {yl['y_lenh_id']}: vai_tro_nguoi_ke sai")
            if _dt(yl["thoi_diem_ke"]) is None:
                errs.append(f"y lệnh {yl['y_lenh_id']}: thoi_diem_ke không ISO có múi giờ")
            if yl["trang_thai"] == "cho_duyet":
                focus_ids.append(yl["y_lenh_id"])
            for line in yl["chi_tiet"]:
                tid = line.get("thuoc_id")
                if tid is not None and tid not in thuoc_ids:
                    errs.append(
                        f"dòng {line.get('chi_tiet_y_lenh_id')}: thuốc {tid} ngoài danh mục"
                    )
                if tid is None and not line.get("ten_tu_do"):
                    errs.append(
                        f"dòng {line.get('chi_tiet_y_lenh_id')}: thiếu thuoc_id và ten_tu_do"
                    )
                if _dt(line.get("bat_dau")) is None:
                    errs.append(
                        f"dòng {line.get('chi_tiet_y_lenh_id')}: bat_dau không ISO có múi giờ"
                    )
    if len(focus_ids) != 1 or focus_ids[:1] != [data["y_lenh_trong_tam"]]:
        errs.append(f"phải có đúng 1 y lệnh cho_duyet và trùng y_lenh_trong_tam: {focus_ids}")
    if dots and focus_ids:
        last_ids = {yl["y_lenh_id"] for yl in dots[-1]["y_lenh"]}
        if data["y_lenh_trong_tam"] not in last_ids:
            errs.append("y lệnh trọng tâm không nằm ở lần vào viện cuối")
    # nạp thử vào CaBenh
    if not errs:
        errs += _nap_ca_benh(data)
    # đáp án
    if not gold_path.exists():
        errs.append("thiếu đáp án trong data/gold/hoso_gia_lap")
    else:
        errs += _check_gold(gold_path, scenario, data)
    return errs


def _nap_ca_benh(data: dict) -> list[str]:
    sys.path.insert(0, str(ROOT))
    from app.domain.models import CaBenh  # noqa: PLC0415

    last = data["dot_dieu_tri"][-1]
    focus = next(y for y in last["y_lenh"] if y["trang_thai"] == "cho_duyet")
    active = [
        line
        for y in last["y_lenh"]
        if y is not focus
        for line in y["chi_tiet"]
        if line["trang_thai_dong"] == "active"
    ]
    dien_bien = [
        {
            k: v
            for k, v in d.items()
            if k in {"dien_bien_id", "loai_ho_so", "noi_dung", "thoi_diem_ghi"}
        }
        for d in last["dien_bien"]
    ]
    view = {
        "ca_id": data["ho_so_id"],
        "mo_ta_ngan": last["tom_tat"] or "hồ sơ giả lập",
        "nguoi_benh": data["nguoi_benh"],
        "tinh_trang_di_ung": data["tinh_trang_di_ung"],
        "di_ung": data["di_ung"],
        "dot_dieu_tri": {
            "dot_dieu_tri_id": last["dot_dieu_tri_id"],
            "khoa_dieu_tri": last["khoa_dieu_tri"],
            "loai_dieu_tri": last["loai_dieu_tri"],
            "thoi_diem_bat_dau": last["thoi_diem_bat_dau"],
        },
        "chan_doan": last["chan_doan"],
        "co_dia": last["co_dia"],
        "sinh_hieu": last["sinh_hieu"],
        "xet_nghiem": last["xet_nghiem"],
        "vi_sinh": last["vi_sinh"],
        "dien_bien": dien_bien,
        "thuoc_dang_dung": active,
        "y_lenh_cho_duyet": {
            "y_lenh_id": focus["y_lenh_id"],
            "khoa_ke_don": focus["khoa_ke_don"],
            "luong_duyet": focus["luong_duyet"],
            "muc_uu_tien": focus["muc_uu_tien"],
            "thoi_diem_ke": focus["thoi_diem_ke"],
            "chi_tiet": focus["chi_tiet"],
        },
        "danh_muc_thuoc": data["danh_muc_thuoc"],
        "danh_muc_hoat_chat": data["danh_muc_hoat_chat"],
    }
    try:
        CaBenh.model_validate(view)
    except Exception as exc:  # noqa: BLE001
        return [f"nạp thử CaBenh lỗi: {str(exc)[:600]}"]
    return []


def _check_gold(path: Path, scenario: dict, data: dict) -> list[str]:
    from app.domain.models import DapAn  # noqa: PLC0415

    errs: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        gold = DapAn.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        return [f"đáp án lỗi: {str(exc)[:400]}"]
    if gold.ca_id != data["ho_so_id"]:
        errs.append("đáp án: ca_id sai")
    expected = scenario["dap_an"]
    verdicts = {f.ket_luan for f in gold.phat_hien_ky_vong}
    if expected == "dat" and gold.phat_hien_ky_vong:
        errs.append("đáp án 'đạt' phải có phat_hien_ky_vong rỗng")
    if expected != "dat" and verdicts != {expected}:
        errs.append(f"đáp án lệch kịch bản: có {verdicts}, cần {expected}")
    if "CHÈN LỆNH" in scenario["khac"] and not gold.van_ban_bat_thuong:
        errs.append("kịch bản chèn lệnh nhưng van_ban_bat_thuong = false")
    if "CHÈN LỆNH" not in scenario["khac"] and gold.van_ban_bat_thuong:
        errs.append("van_ban_bat_thuong = true nhưng kịch bản không chèn lệnh")
    focus = next(y for y in data["dot_dieu_tri"][-1]["y_lenh"] if y["trang_thai"] == "cho_duyet")
    line_ids = {line["chi_tiet_y_lenh_id"] for line in focus["chi_tiet"]}
    for finding in gold.phat_hien_ky_vong:
        if not set(finding.chi_tiet_y_lenh_id) <= line_ids:
            errs.append("đáp án trỏ dòng thuốc không thuộc y lệnh trọng tâm")
    return errs


def main() -> int:
    scenarios = json.loads((HOSO / "_kich_ban.json").read_text(encoding="utf-8"))["kich_ban"]
    by_id = {s["id"]: s for s in scenarios}
    kb = json.loads(KB.read_text(encoding="utf-8"))["hoat_chat"]
    kb_ids = {h["hoat_chat_id"].lower() for h in kb}
    kb_ids.add("clavulanic_acid")
    targets = sys.argv[1:] or sorted(by_id)
    bad = 0
    for hs in targets:
        errs = check(hs, by_id[hs], kb_ids)
        if errs:
            bad += 1
            print(f"[LỖI] {hs}")
            for e in errs:
                print("   -", e)
        else:
            print(f"[ĐẠT] {hs}")
    print(f"Tổng {len(targets)} hồ sơ, {bad} hồ sơ lỗi")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
