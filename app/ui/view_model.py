"""Các hàm thuần chuẩn bị dữ liệu hiển thị cho giao diện (không phụ thuộc Streamlit)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.loader import latest_vital
from app.domain.models import CaBenh, ChiTietYLenh, KetQuaXetNghiem
from app.ui.labels import (
    NHAN_DAU_VAO as NHAN_DAU_VAO,
)
from app.ui.labels import (
    NHAN_KET_LUAN as NHAN_KET_LUAN,
)
from app.ui.labels import (
    NHAN_LOAI_CAN_CU as NHAN_LOAI_CAN_CU,
)
from app.ui.labels import (
    NHAN_LOAI_DIEU_TRI,
    NHAN_LOAI_HO_SO,
    NHAN_LOAI_TAC_NHAN,
    NHAN_SINH_HIEU,
    NHAN_TRANG_THAI_DONG,
)
from app.ui.labels import (
    NHAN_LUONG_DUYET as NHAN_LUONG_DUYET,
)
from app.ui.labels import (
    TEN_YEU_TO as TEN_YEU_TO,
)
from app.ui.labels import (
    label_of as label_of,
)

if TYPE_CHECKING:
    from app.feedback import PhanHoi
    from app.pipeline import KetQuaThamDinh
    from app.rules.types import CanCu, PhatHien

SO_THAP_PHAN: dict[str, int] = {"bsa_mosteller": 2}

_EVIDENCE_ORDER: dict[str, int] = {
    "du_lieu": 0,
    "tinh_toan": 1,
    "tai_lieu": 2,
}

_FIXED_QUESTIONS: tuple[str, ...] = (
    "Thuốc nào cần chỉnh liều theo chức năng thận?",
    "Có tương tác nào giữa các thuốc đang dùng?",
    "Tóm tắt diễn biến 3 ngày gần nhất",
)


def format_dt(dt: datetime | None) -> str:
    """Định dạng thời điểm theo ngày/tháng/năm giờ:phút."""
    if dt is None:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


def format_ref_range(low: float | None, high: float | None) -> str:
    """Định dạng khoảng tham chiếu xét nghiệm."""
    if low is not None and high is not None:
        return f"{format_number(low)} – {format_number(high)}"
    if low is not None:
        return f"≥ {format_number(low)}"
    if high is not None:
        return f"≤ {format_number(high)}"
    return "—"


def plain_label(text: str) -> str:
    """Thoát ký tự markdown và thay xuống dòng trong dữ liệu bằng dấu cách."""
    single_line = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    special_chars = "\\`*_[]()#~<>|!$:"
    return "".join(f"\\{char}" if char in special_chars else char for char in single_line)


def allergy_text(ca: CaBenh) -> str:
    """Tạo chuỗi mô tả tình trạng dị ứng theo 3 trạng thái chuẩn."""
    status = ca.tinh_trang_di_ung.trang_thai
    if status == "co_di_ung":
        details = [
            f"{du.tac_nhan} ({du.phan_ung})" if du.phan_ung else du.tac_nhan for du in ca.di_ung
        ]
        return f"Có dị ứng: {'; '.join(details)}"
    if status == "khong_di_ung_da_hoi":
        return "Đã hỏi, không ghi nhận dị ứng"
    return "CHƯA CÓ THÔNG TIN DỊ ỨNG"


def _find_order_line(ca: CaBenh, chi_tiet_y_lenh_id: str) -> ChiTietYLenh | None:
    """Tìm dòng chi tiết y lệnh trong y lệnh chờ duyệt hoặc thuốc đang dùng."""
    for line in (*ca.y_lenh_cho_duyet.chi_tiet, *ca.thuoc_dang_dung):
        if line.chi_tiet_y_lenh_id == chi_tiet_y_lenh_id:
            return line
    return None


def drug_label(ca: CaBenh, chi_tiet_y_lenh_id: str) -> str:
    """Tạo nhãn thuốc gồm tên thuốc (hoặc ten_tu_do), liều, đường dùng và tần suất."""
    line = _find_order_line(ca, chi_tiet_y_lenh_id)
    if line is None:
        return chi_tiet_y_lenh_id

    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    thuoc = thuoc_by_id.get(line.thuoc_id) if line.thuoc_id is not None else None

    if thuoc is not None:
        base_name = thuoc.ten_thuoc
    elif line.ten_tu_do is not None and line.ten_tu_do.strip() != "":
        base_name = line.ten_tu_do.strip()
    else:
        base_name = line.chi_tiet_y_lenh_id

    parts: list[str] = [base_name]

    if line.lieu_moi_lan is not None:
        unit = line.don_vi_lieu.strip() if line.don_vi_lieu else ""
        dose_text = f"{line.lieu_moi_lan:g} {unit}".strip()
        if dose_text and dose_text.lower() not in base_name.lower():
            parts.append(dose_text)

    route = line.duong_dung or (thuoc.duong_dung if thuoc is not None else None)
    if route is not None and route.strip() != "":
        parts.append(route.strip())

    freq = line.tan_suat
    if (freq is None or freq.strip() == "") and line.so_lan_moi_ngay is not None:
        freq = f"{line.so_lan_moi_ngay} lần/ngày"
    if freq is not None and freq.strip() != "":
        parts.append(freq.strip())

    return " – ".join(parts)


def lab_rows(ca: CaBenh) -> list[dict[str, object]]:
    """Chuyển danh sách xét nghiệm thành các dòng bảng, mới nhất trước, có cờ ngoài ngưỡng."""
    sorted_labs = sorted(ca.xet_nghiem, key=lambda xn: xn.thoi_diem_ket_qua, reverse=True)
    rows: list[dict[str, object]] = []
    for xn in sorted_labs:
        out_of_range = False
        if xn.gia_tri_so is not None:
            if xn.nguong_duoi is not None and xn.gia_tri_so < xn.nguong_duoi:
                out_of_range = True
            if xn.nguong_tren is not None and xn.gia_tri_so > xn.nguong_tren:
                out_of_range = True
        rows.append(
            {
                "xet_nghiem_id": xn.xet_nghiem_id,
                "ma_xet_nghiem": xn.ma_xet_nghiem,
                "ten_xet_nghiem": xn.ten_xet_nghiem,
                "gia_tri_so": xn.gia_tri_so,
                "gia_tri_text": xn.gia_tri_text,
                "don_vi": xn.don_vi,
                "nguong_duoi": xn.nguong_duoi,
                "nguong_tren": xn.nguong_tren,
                "thoi_diem_ket_qua": xn.thoi_diem_ket_qua,
                "ngoai_nguong": out_of_range,
            },
        )
    return rows


def finding_base_id(finding: PhatHien) -> str:
    """Tạo mã nhận định gốc từ mã luật và danh sách dòng y lệnh đã sắp xếp."""
    return finding.ma_luat + "|" + ",".join(sorted(finding.chi_tiet_y_lenh_id))


def _finding_content_digest(finding: PhatHien) -> str:
    """Băm ngắn toàn bộ nội dung phân biệt khi mô tả của hai phát hiện trùng nhau."""
    payload = {
        "yeu_to": finding.yeu_to,
        "ket_luan": finding.ket_luan,
        "muc_do": finding.muc_do,
        "mo_ta": finding.mo_ta,
        "thong_tin_con_thieu": list(finding.thong_tin_con_thieu),
        "can_cu": [(item.loai, item.ban_ghi_id, item.mo_ta) for item in finding.can_cu],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:8]


def finding_ids(phat_hien: Sequence[PhatHien]) -> list[str]:
    """Sinh mã nhận định duy nhất trong ca và ổn định (không phụ thuộc thứ tự).

    Nhận định không trùng (ma_luat, chi_tiet_y_lenh_id) giữ nguyên dạng gốc để tương thích
    phản hồi cũ; khi trùng, gắn hậu tố băm ngắn từ mo_ta (hoặc nội dung đầy đủ nếu cần).
    """
    bases = [finding_base_id(item) for item in phat_hien]
    base_counts = Counter(bases)
    mo_ta_hashes = [
        hashlib.sha256(item.mo_ta.encode("utf-8")).hexdigest()[:8] for item in phat_hien
    ]
    mo_ta_counts: Counter[tuple[str, str]] = Counter(zip(bases, mo_ta_hashes, strict=True))

    candidates: list[str] = []
    for item, base, mo_ta_hash in zip(phat_hien, bases, mo_ta_hashes, strict=True):
        if base_counts[base] == 1:
            candidates.append(base)
        elif mo_ta_counts[(base, mo_ta_hash)] == 1:
            candidates.append(f"{base}|{mo_ta_hash}")
        else:
            candidates.append(f"{base}|{_finding_content_digest(item)}")

    candidate_counts = Counter(candidates)
    seen_occurrences: Counter[str] = Counter()
    unique_ids: list[str] = []
    for candidate in candidates:
        if candidate_counts[candidate] == 1:
            unique_ids.append(candidate)
            continue
        seen_occurrences[candidate] += 1
        occ = seen_occurrences[candidate]
        unique_ids.append(candidate if occ == 1 else f"{candidate}~{occ}")
    return unique_ids


def finding_rows(ca: CaBenh, phat_hien: Sequence[PhatHien]) -> list[dict[str, object]]:
    """Chuyển danh sách PhatHien thành các dòng hiển thị có nhãn thuốc và yếu tố tiếng Việt."""
    nids = finding_ids(phat_hien)
    rows: list[dict[str, object]] = []
    for item, nid in zip(phat_hien, nids, strict=True):
        drug_text = " + ".join(drug_label(ca, line_id) for line_id in item.chi_tiet_y_lenh_id)
        factor_name = TEN_YEU_TO.get(item.yeu_to, str(item.yeu_to))
        rows.append(
            {
                "nhan_dinh_id": nid,
                "thuoc": drug_text,
                "yeu_to": f"{item.yeu_to}. {factor_name}",
                "nhan_xet": item.mo_ta,
                "ket_luan": NHAN_KET_LUAN.get(item.ket_luan, item.ket_luan),
                "muc_do": item.muc_do,
                "can_cu": list(item.can_cu),
                "thong_tin_con_thieu": list(item.thong_tin_con_thieu),
                "ma_luat": item.ma_luat,
                "chi_tiet_y_lenh_id": list(item.chi_tiet_y_lenh_id),
            },
        )
    return rows


def split_findings(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Tách danh sách nhận định thành (cần chú ý, đạt), giữ nguyên thứ tự đầu vào."""
    dat_label = NHAN_KET_LUAN["dat"]
    attention = [row for row in rows if row.get("ket_luan") != dat_label]
    passed = [row for row in rows if row.get("ket_luan") == dat_label]
    return attention, passed


def sort_attention_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Xếp dòng cần chú ý: nghiêm trọng → cần lưu ý → thiếu → ngoài HDSD."""

    def _rank(row: dict[str, object]) -> int:
        ket_luan = row.get("ket_luan")
        muc_do = row.get("muc_do")
        if ket_luan == NHAN_KET_LUAN["can_xem"] and muc_do == "nghiem_trong":
            return 0
        if ket_luan == NHAN_KET_LUAN["can_xem"]:
            return 1
        if ket_luan == NHAN_KET_LUAN["khong_du_du_lieu"]:
            return 2
        if ket_luan == NHAN_KET_LUAN["ngoai_hdsd"]:
            return 3
        return 4

    return sorted(rows, key=_rank)


def count_serious(phat_hien: Sequence[PhatHien]) -> int:
    """Đếm số phát hiện có kết luận can_xem và mức độ nghiem_trong."""
    return sum(
        1 for item in phat_hien if item.ket_luan == "can_xem" and item.muc_do == "nghiem_trong"
    )


def format_number(x: float | None, digits: int = 1) -> str:
    """Định dạng số thập phân kiểu Việt (dấu phẩy), trả '—' nếu giá trị là None."""
    if x is None:
        return "—"
    return f"{x:.{digits}f}".replace(".", ",")


def metric_text(cong_thuc: str, ket_qua: float | None) -> str:
    """Định dạng chỉ số theo số chữ số thập phân của từng công thức."""
    return format_number(ket_qua, digits=SO_THAP_PHAN.get(cong_thuc, 1))


def priority_of(phat_hien: Sequence[PhatHien]) -> int:
    """Tính mức ưu tiên hàng đợi của một ca từ danh sách phát hiện."""
    if any(p.ket_luan == "can_xem" and p.muc_do == "nghiem_trong" for p in phat_hien):
        return 0
    if any(p.ket_luan == "can_xem" for p in phat_hien):
        return 1
    if any(p.ket_luan == "ngoai_hdsd" for p in phat_hien):
        return 2
    if any(p.ket_luan == "khong_du_du_lieu" for p in phat_hien):
        return 3
    return 4


def count_by_level(phat_hien: Sequence[PhatHien]) -> dict[str, int]:
    """Đếm số lượng phát hiện theo từng nhóm mức độ hiển thị."""
    counts = {
        "nghiem_trong": 0,
        "can_luu_y": 0,
        "thieu_du_lieu": 0,
        "ngoai_hdsd": 0,
        "dat": 0,
    }
    for item in phat_hien:
        if item.ket_luan == "dat":
            counts["dat"] += 1
        elif item.ket_luan == "khong_du_du_lieu":
            counts["thieu_du_lieu"] += 1
        elif item.ket_luan == "ngoai_hdsd":
            counts["ngoai_hdsd"] += 1
        elif item.ket_luan == "can_xem":
            if item.muc_do == "nghiem_trong":
                counts["nghiem_trong"] += 1
            else:
                counts["can_luu_y"] += 1
    return counts


def _queue_badge(uu_tien: int, counts: dict[str, int]) -> str:
    """Tạo chuỗi huy hiệu vừa có biểu tượng vừa có chữ cho hàng đợi."""
    if uu_tien == 0:
        return f"⛔ {counts['nghiem_trong']} nghiêm trọng"
    if uu_tien == 1:
        return f"⚠ {counts['can_luu_y']} cần lưu ý"
    if uu_tien == 2:
        return f"⚠ {counts['ngoai_hdsd']} ngoài HDSD"
    if uu_tien == 3:
        return f"? {counts['thieu_du_lieu']} thiếu dữ liệu"
    return "✓ Đạt"


def queue_rows(
    cases: Sequence[CaBenh],
    results: Mapping[str, KetQuaThamDinh],
) -> list[dict[str, object]]:
    """Tạo danh sách dòng hàng đợi sắp theo mức ưu tiên và thời điểm kê đơn."""
    items: list[tuple[tuple[int, datetime, str], dict[str, object]]] = []
    for ca in cases:
        res = results.get(ca.ca_id)
        phat_hien = res.phat_hien if res is not None else []
        uu_tien = priority_of(phat_hien)
        counts = count_by_level(phat_hien)
        row: dict[str, object] = {
            "ca_id": ca.ca_id,
            "khoa": ca.dot_dieu_tri.khoa_dieu_tri,
            "mo_ta": ca.mo_ta_ngan,
            "uu_tien": uu_tien,
            "huy_hieu": _queue_badge(uu_tien, counts),
            "so_nghiem_trong": counts["nghiem_trong"],
            "so_can_luu_y": counts["can_luu_y"],
            "so_thieu_du_lieu": counts["thieu_du_lieu"],
        }
        sort_key = (uu_tien, ca.y_lenh_cho_duyet.thoi_diem_ke, ca.ca_id)
        items.append((sort_key, row))

    items.sort(key=lambda pair: pair[0])
    return [pair[1] for pair in items]


def header_info(ca: CaBenh, result: KetQuaThamDinh) -> dict[str, object]:
    """Chuẩn bị thông tin cho dải định danh ca bệnh trên cùng."""
    nb = ca.nguoi_benh
    if nb.gioi_tinh == "nam":
        sex_label = "Nam"
    elif nb.gioi_tinh == "nu":
        sex_label = "Nữ"
    else:
        sex_label = "Chưa rõ giới"
    age_label = f"{nb.tuoi} tuổi" if nb.tuoi is not None else "chưa rõ tuổi"

    weight = latest_vital(ca, "can_nang")
    if weight is not None:
        weight_text = f"{format_number(weight.gia_tri)} {weight.don_vi}"
    else:
        weight_text = "chưa có cân nặng"

    care_label = label_of(NHAN_LOAI_DIEU_TRI, ca.dot_dieu_tri.loai_dieu_tri).lower()
    khoa_loai = f"{ca.dot_dieu_tri.khoa_dieu_tri}, {care_label}"

    crcl_calc = next(
        (calc for calc in result.chi_so if calc.cong_thuc == "cockcroft_gault"),
        None,
    )
    if crcl_calc is not None and crcl_calc.ket_qua is not None:
        crcl_text = f"{metric_text(crcl_calc.cong_thuc, crcl_calc.ket_qua)} mL/phút"
        crcl_bat_thuong = crcl_calc.ket_qua < 60.0
    else:
        crcl_text = "—"
        crcl_bat_thuong = False

    return {
        "ca_id": ca.ca_id,
        "gioi_tuoi": f"{sex_label} {age_label}",
        "can_nang": weight_text,
        "khoa_loai": khoa_loai,
        "crcl": crcl_text,
        "crcl_bat_thuong": crcl_bat_thuong,
        "di_ung_trang_thai": ca.tinh_trang_di_ung.trang_thai,
        "di_ung_text": allergy_text(ca),
    }


def length_of_stay_days(ca: CaBenh, now: datetime) -> int | None:
    """Tính số ngày nằm viện từ thoi_diem_bat_dau tới now; trả None nếu now trước lúc bắt đầu."""
    start = ca.dot_dieu_tri.thoi_diem_bat_dau
    if now.tzinfo is None:
        now_aware = now.replace(tzinfo=start.tzinfo)
    else:
        now_aware = now.astimezone(start.tzinfo)
    if now_aware < start:
        return None
    return (now_aware - start).days


def labs_without_range(ca: CaBenh) -> int:
    """Đếm kết quả số thiếu cả hai ngưỡng tham chiếu."""
    return sum(
        xn.gia_tri_so is not None and xn.nguong_duoi is None and xn.nguong_tren is None
        for xn in ca.xet_nghiem
    )


def lab_trends(ca: CaBenh, limit: int = 5) -> list[dict[str, object]]:
    """Lấy tối đa limit xét nghiệm ngoài ngưỡng mới nhất theo từng ma_xet_nghiem."""
    grouped: dict[str, list[KetQuaXetNghiem]] = {}
    for xn in ca.xet_nghiem:
        grouped.setdefault(xn.ma_xet_nghiem, []).append(xn)

    collected: list[tuple[datetime, dict[str, object]]] = []
    for records in grouped.values():
        ordered = sorted(records, key=lambda item: item.thoi_diem_ket_qua, reverse=True)
        latest = ordered[0]
        if latest.gia_tri_so is None:
            continue

        if latest.nguong_tren is not None and latest.gia_tri_so > latest.nguong_tren:
            huong = "▲"
        elif latest.nguong_duoi is not None and latest.gia_tri_so < latest.nguong_duoi:
            huong = "▼"
        else:
            continue

        so_voi_truoc: str | None = None
        if len(ordered) > 1:
            prev = ordered[1]
            if prev.gia_tri_so is not None:
                prev_text = format_number(prev.gia_tri_so)
            else:
                prev_text = prev.gia_tri_text or "—"
            delta = latest.thoi_diem_ket_qua - prev.thoi_diem_ket_qua
            if delta.days >= 1:
                gap_text = f"sau {delta.days} ngày"
            else:
                hours = int(delta.total_seconds() // 3600)
                gap_text = f"sau {hours} giờ" if hours >= 1 else "cùng ngày"
            so_voi_truoc = f"từ {prev_text}, {gap_text}"

        row: dict[str, object] = {
            "ten": latest.ten_xet_nghiem,
            "gia_tri_text": format_number(latest.gia_tri_so),
            "don_vi": latest.don_vi or "",
            "huong": huong,
            "thoi_diem": latest.thoi_diem_ket_qua,
            "so_voi_truoc": so_voi_truoc,
        }
        collected.append((latest.thoi_diem_ket_qua, row))

    collected.sort(key=lambda pair: pair[0], reverse=True)
    return [pair[1] for pair in collected[:limit]]


def evidence_rows(can_cu: Sequence[CanCu]) -> list[dict[str, object]]:
    """Chuẩn hoá danh sách căn cứ theo đúng thứ tự Dữ liệu ca → Tính toán → Tài liệu."""
    ordered = sorted(can_cu, key=lambda cc: _EVIDENCE_ORDER.get(cc.loai, 99))
    rows: list[dict[str, object]] = []
    for idx, cc in enumerate(ordered, start=1):
        mo_duoc = (cc.loai == "du_lieu" and bool(cc.ban_ghi_id)) or cc.loai == "tinh_toan"
        rows.append(
            {
                "so": idx,
                "loai": cc.loai,
                "loai_nhan": label_of(NHAN_LOAI_CAN_CU, cc.loai),
                "mo_ta": cc.mo_ta,
                "ban_ghi_id": cc.ban_ghi_id,
                "mo_duoc": mo_duoc,
            },
        )
    return rows


def record_detail(ca: CaBenh, ban_ghi_id: str) -> dict[str, object] | None:
    """Tìm bản ghi theo mã trong hồ sơ ca bệnh để hiển thị trong hộp thoại căn cứ."""
    for xn in ca.xet_nghiem:
        if xn.xet_nghiem_id == ban_ghi_id:
            val_text = (
                f"{format_number(xn.gia_tri_so)} {xn.don_vi or ''}".strip()
                if xn.gia_tri_so is not None
                else (xn.gia_tri_text or "—")
            )
            return {
                "loai": "Xét nghiệm",
                "tieu_de": f"{xn.ten_xet_nghiem} ({xn.xet_nghiem_id})",
                "dong": [
                    ("Mã bản ghi", xn.xet_nghiem_id),
                    ("Mã xét nghiệm", xn.ma_xet_nghiem),
                    ("Giá trị", val_text),
                    ("Khoảng tham chiếu", format_ref_range(xn.nguong_duoi, xn.nguong_tren)),
                    ("Thời điểm kết quả", format_dt(xn.thoi_diem_ket_qua)),
                ],
            }

    for sh in ca.sinh_hieu:
        if sh.sinh_hieu_id == ban_ghi_id:
            vital_name = label_of(NHAN_SINH_HIEU, sh.loai)
            return {
                "loai": "Sinh hiệu",
                "tieu_de": f"{vital_name} ({sh.sinh_hieu_id})",
                "dong": [
                    ("Mã bản ghi", sh.sinh_hieu_id),
                    ("Chỉ số", vital_name),
                    ("Giá trị", f"{format_number(sh.gia_tri)} {sh.don_vi}"),
                    ("Thời điểm đo", format_dt(sh.thoi_diem_do)),
                ],
            }

    for du in ca.di_ung:
        if du.di_ung_id == ban_ghi_id:
            return {
                "loai": "Dị ứng",
                "tieu_de": f"Dị ứng {du.tac_nhan} ({du.di_ung_id})",
                "dong": [
                    ("Mã bản ghi", du.di_ung_id),
                    ("Tác nhân", du.tac_nhan),
                    ("Loại tác nhân", label_of(NHAN_LOAI_TAC_NHAN, du.loai_tac_nhan)),
                    ("Phản ứng", du.phan_ung or "—"),
                    ("Mức độ", du.muc_do or "—"),
                ],
            }

    for cd in ca.chan_doan:
        if cd.chan_doan_id == ban_ghi_id:
            dx_type = "Chính" if cd.loai == "chinh" else "Kèm"
            return {
                "loai": "Chẩn đoán",
                "tieu_de": f"{cd.noi_dung} ({cd.chan_doan_id})",
                "dong": [
                    ("Mã bản ghi", cd.chan_doan_id),
                    ("Loại", dx_type),
                    ("Mã ICD-10", cd.ma_icd10 or "—"),
                    ("Nội dung", cd.noi_dung),
                ],
            }

    for line in (*ca.y_lenh_cho_duyet.chi_tiet, *ca.thuoc_dang_dung):
        if line.chi_tiet_y_lenh_id == ban_ghi_id:
            label = drug_label(ca, line.chi_tiet_y_lenh_id)
            return {
                "loai": "Dòng y lệnh",
                "tieu_de": f"{label} ({line.chi_tiet_y_lenh_id})",
                "dong": [
                    ("Mã dòng y lệnh", line.chi_tiet_y_lenh_id),
                    ("Thuốc", label),
                    ("Cách dùng", line.cach_dung or "—"),
                    ("Trạng thái", label_of(NHAN_TRANG_THAI_DONG, line.trang_thai_dong)),
                    ("Bắt đầu", format_dt(line.bat_dau)),
                ],
            }

    for db in ca.dien_bien:
        if db.dien_bien_id == ban_ghi_id:
            doc_type = label_of(NHAN_LOAI_HO_SO, db.loai_ho_so)
            return {
                "loai": "Diễn biến",
                "tieu_de": f"{doc_type} ({db.dien_bien_id})",
                "dong": [
                    ("Mã bản ghi", db.dien_bien_id),
                    ("Loại hồ sơ", doc_type),
                    ("Thời điểm ghi", format_dt(db.thoi_diem_ghi)),
                    ("Nội dung", db.noi_dung),
                ],
            }

    return None


def unchecked_factors(phat_hien: Sequence[PhatHien]) -> list[str]:
    """Liệt kê tên các yếu tố (trong 7 yếu tố) chưa có phát hiện nào ở ca này."""
    checked = {item.yeu_to for item in phat_hien}
    return [
        f"{factor_num}. {TEN_YEU_TO[factor_num]}"
        for factor_num in sorted(TEN_YEU_TO)
        if factor_num not in checked
    ]


def suggested_questions(ca: CaBenh) -> list[str]:
    """Sinh danh sách câu hỏi gợi ý từ bối cảnh ca bệnh đang mở."""
    line_thuoc_ids = {
        line.thuoc_id
        for line in (*ca.y_lenh_cho_duyet.chi_tiet, *ca.thuoc_dang_dung)
        if line.thuoc_id is not None
    }
    has_antibiotic = any(
        thuoc.la_khang_sinh for thuoc in ca.danh_muc_thuoc if thuoc.thuoc_id in line_thuoc_ids
    )
    questions: list[str] = []
    if ca.vi_sinh or has_antibiotic:
        questions.append("Vì sao kê kháng sinh này?")
    questions.extend(_FIXED_QUESTIONS)
    return questions


def feedback_status(
    ca_id: str,
    row: Mapping[str, object],
    feedbacks: Sequence[PhanHoi],
) -> PhanHoi | None:
    """Tìm phản hồi mới nhất khớp ca_id, nhận định (hoặc ma_luat cũ) và đúng tập dòng y lệnh."""
    ma_luat = str(row.get("ma_luat", ""))
    raw_nid = row.get("nhan_dinh_id")
    nhan_dinh_id = str(raw_nid) if raw_nid is not None and str(raw_nid) != "" else None
    raw_ids = row.get("chi_tiet_y_lenh_id", [])
    if isinstance(raw_ids, list | tuple | set):
        target_ids = {str(item) for item in raw_ids}
    else:
        target_ids = set()

    base_id = ma_luat + "|" + ",".join(sorted(target_ids))
    is_disambiguated = (
        nhan_dinh_id is not None and not nhan_dinh_id.startswith("ai|") and nhan_dinh_id != base_id
    )

    latest: PhanHoi | None = None
    for fb in feedbacks:
        if fb.ca_id != ca_id:
            continue
        if is_disambiguated:
            if fb.ma_luat != nhan_dinh_id:
                continue
        elif fb.ma_luat != ma_luat and (nhan_dinh_id is None or fb.ma_luat != nhan_dinh_id):
            continue
        if set(fb.chi_tiet_y_lenh_id) != target_ids:
            continue
        if latest is None or fb.thoi_diem >= latest.thoi_diem:
            latest = fb
    return latest


def order_table_rows(
    ca: CaBenh,
    lines: Sequence[ChiTietYLenh],
    *,
    include_status: bool = False,
    finding_line_ids: set[str] | None = None,
) -> list[dict[str, str]]:
    """Chuyển danh sách dòng y lệnh thành các dòng bảng tiếng Việt an toàn."""
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    rows: list[dict[str, str]] = []
    for line in lines:
        thuoc = thuoc_by_id.get(line.thuoc_id) if line.thuoc_id is not None else None
        if thuoc is not None:
            name = thuoc.ten_thuoc
        elif line.ten_tu_do is not None and line.ten_tu_do.strip() != "":
            name = line.ten_tu_do.strip()
        else:
            name = line.chi_tiet_y_lenh_id

        if line.lieu_moi_lan is not None:
            dose = f"{format_number(line.lieu_moi_lan)} {line.don_vi_lieu or ''}".strip()
        else:
            dose = "—"

        freq = line.tan_suat
        if (freq is None or freq.strip() == "") and line.so_lan_moi_ngay is not None:
            freq = f"{line.so_lan_moi_ngay} lần/ngày"

        route = line.duong_dung or (thuoc.duong_dung if thuoc is not None else None) or "—"
        schedule_parts = [
            f"{format_dt(ld.thoi_diem_du_kien)} ({format_number(ld.lieu)} {ld.don_vi})"
            for ld in line.lich_dung
        ]

        row: dict[str, str] = {
            "Thuốc": name,
            "Liều": dose,
            "Tần suất": freq or "—",
            "Đường dùng": route,
            "Lịch dùng": ", ".join(schedule_parts) if schedule_parts else "—",
        }
        if include_status:
            row["Trạng thái"] = label_of(NHAN_TRANG_THAI_DONG, line.trang_thai_dong)
        if finding_line_ids is not None:
            has_finding = line.chi_tiet_y_lenh_id in finding_line_ids
            row["Nhận định"] = "⚠ Có nhận định" if has_finding else ""
        rows.append(row)
    return rows


def prescribed_active_ingredient_ids(ca: CaBenh) -> set[str]:
    """Lấy tập mã hoạt chất đang có trong y lệnh chờ duyệt hoặc thuốc đang dùng hiệu lực."""
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    active_ids: set[str] = set()
    active_lines = [
        *ca.y_lenh_cho_duyet.chi_tiet,
        *(line for line in ca.thuoc_dang_dung if line.trang_thai_dong in ("active", "pending")),
    ]
    for line in active_lines:
        if line.thuoc_id is None:
            continue
        thuoc = thuoc_by_id.get(line.thuoc_id)
        if thuoc is None:
            continue
        for tp in thuoc.thanh_phan:
            active_ids.add(tp.hoat_chat_id)
    return active_ids
