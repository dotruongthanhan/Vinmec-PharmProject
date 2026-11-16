"""Dựng gói ngữ cảnh ca bệnh đã che định danh để đưa cho bước tổng hợp LLM."""

from datetime import datetime

from app.calc.types import CalcResult
from app.config.settings import CaseContextSettings
from app.deid import scrubber
from app.deid.scrubber import DeidError, scrub_text
from app.domain.loader import ingredients_of, latest_vital
from app.domain.models import CaBenh, ChiTietYLenh, SinhHieu
from app.llm.schema import GoiCanCu
from app.pipeline import KetQuaThamDinh

_DEFAULT_SCRUB_TEXT = scrub_text
_OPEN_MARKER = "<<<DU_LIEU_BENH_AN"
_CLOSE_MARKER = "DU_LIEU_BENH_AN>>>"
_SCRUB_FALLBACK = "[không đưa được vào vì lỗi che định danh]"
_MARKER_REPLACEMENT = "[đã bỏ ký hiệu]"

_NHAN_GIOI_TINH = {"nam": "Nam", "nu": "Nữ"}
_NHAN_LOAI_DIEU_TRI = {"noi_tru": "Nội trú", "ngoai_tru": "Ngoại trú"}
_NHAN_DI_UNG = {
    "co_di_ung": "Có dị ứng",
    "khong_di_ung_da_hoi": "Đã hỏi, không ghi nhận dị ứng",
    "chua_co_thong_tin": "Chưa có thông tin dị ứng",
}


def _call_scrub(text: str) -> str:
    """Gọi hàm che định danh, hỗ trợ monkeypatch ở cả hai module."""
    if scrub_text is not _DEFAULT_SCRUB_TEXT:
        return scrub_text(text).van_ban
    return scrubber.scrub_text(text).van_ban


def _sanitize_free_text(text: str, record_id: str, warnings: list[str]) -> str:
    """Che định danh văn bản tự do và loại chuỗi đánh dấu dữ liệu nếu có."""
    try:
        cleaned = _call_scrub(text)
    except DeidError:
        warnings.append(f"Lỗi che định danh tại bản ghi {record_id}")
        return _SCRUB_FALLBACK
    while _OPEN_MARKER in cleaned or _CLOSE_MARKER in cleaned:
        cleaned = cleaned.replace(_OPEN_MARKER, _MARKER_REPLACEMENT).replace(
            _CLOSE_MARKER, _MARKER_REPLACEMENT
        )
    return cleaned


def _wrap_free_text(text: str, record_id: str, warnings: list[str]) -> list[str]:
    """Bọc đoạn văn bản tự do giữa hai dòng đánh dấu dữ liệu bệnh án."""
    return [_OPEN_MARKER, _sanitize_free_text(text, record_id, warnings), _CLOSE_MARKER]


def _format_dt(dt: datetime) -> str:
    """Định dạng thời điểm theo ngày/tháng/năm giờ:phút."""
    return dt.strftime("%d/%m/%Y %H:%M")


def _format_num(value: float) -> str:
    """Định dạng số gọn, tránh ký hiệu khoa học."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _add_number(allowed: list[float], seen: set[float], value: float | int | None) -> None:
    """Thêm số hợp lệ vào danh sách số cho phép, giữ thứ tự và tránh trùng."""
    if value is None:
        return
    num = float(value)
    if num == 0.0:
        num = 0.0
    if num not in seen:
        seen.add(num)
        allowed.append(num)


def _format_vital_line(sh: SinhHieu) -> str:
    """Định dạng một bản ghi sinh hiệu có mã đầu dòng."""
    ten = {"can_nang": "Cân nặng", "chieu_cao": "Chiều cao"}.get(sh.loai, sh.loai)
    val = _format_num(sh.gia_tri)
    return f"[{sh.sinh_hieu_id}] {ten}: {val} {sh.don_vi} lúc {_format_dt(sh.thoi_diem_do)}"


def _format_calc_line(cs: CalcResult) -> str:
    """Định dạng một chỉ số đã tính kèm đầu vào hoặc thông tin còn thiếu."""
    if cs.ket_qua is None:
        missing = ", ".join(cs.thieu_dau_vao) if cs.thieu_dau_vao else "không rõ"
        return f"- {cs.cong_thuc}: không tính được, thiếu: {missing}"
    digits = 2 if cs.cong_thuc == "bsa_mosteller" else 1
    rounded_display = f"{cs.ket_qua:.{digits}f}"
    inputs = ", ".join(
        f"{item.ten}={_format_num(item.gia_tri)} {item.don_vi}"
        + (f" [{item.ban_ghi_id}]" if item.ban_ghi_id else "")
        for item in cs.dau_vao
    )
    return f"- {cs.cong_thuc}: {rounded_display} {cs.don_vi} (đầu vào: {inputs})"


def _format_order_lines(
    ca: CaBenh,
    lines: list[ChiTietYLenh],
    warnings: list[str],
    ban_ghi_ids: list[str],
    allowed: list[float],
    seen_nums: set[float],
    *,
    is_pending: bool,
    dong_y_lenh_ids: list[str],
) -> list[str]:
    """Định dạng danh sách dòng thuốc trong y lệnh chờ duyệt hoặc đang dùng."""
    if not lines:
        return ["(không có)"]
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    output: list[str] = []
    for line in lines:
        ban_ghi_ids.append(line.chi_tiet_y_lenh_id)
        if is_pending:
            dong_y_lenh_ids.append(line.chi_tiet_y_lenh_id)
        _add_number(allowed, seen_nums, line.lieu_moi_lan)
        _add_number(allowed, seen_nums, line.so_lan_moi_ngay)
        _add_number(allowed, seen_nums, line.khoang_cach_gio)
        for ld in line.lich_dung:
            _add_number(allowed, seen_nums, ld.lieu)

        thuoc = thuoc_by_id.get(line.thuoc_id) if line.thuoc_id else None
        ingredients = ingredients_of(ca, line)
        ing_text = ", ".join(hc.ten_hoat_chat for hc in ingredients)
        if thuoc is not None:
            drug_desc = thuoc.ten_thuoc + (f" (hoạt chất: {ing_text})" if ing_text else "")
        elif line.ten_tu_do:
            drug_desc = "Sản phẩm gõ tay"
        else:
            drug_desc = line.chi_tiet_y_lenh_id

        parts = [f"[{line.chi_tiet_y_lenh_id}] {drug_desc}"]
        if line.lieu_moi_lan is not None:
            unit = f" {line.don_vi_lieu}" if line.don_vi_lieu else ""
            parts.append(f"liều {_format_num(line.lieu_moi_lan)}{unit}")
        if line.so_lan_moi_ngay is not None:
            parts.append(f"{line.so_lan_moi_ngay} lần/ngày")
        if line.khoang_cach_gio is not None:
            parts.append(f"cách {_format_num(line.khoang_cach_gio)} giờ")
        if line.duong_dung:
            parts.append(f"đường dùng: {line.duong_dung}")
        parts.append(f"trạng thái: {line.trang_thai_dong}")
        if line.lich_dung:
            times = ", ".join(_format_dt(ld.thoi_diem_du_kien) for ld in line.lich_dung)
            parts.append(f"lịch dùng: {times}")
        output.append(" | ".join(parts))

        if line.ten_tu_do and line.ten_tu_do.strip():
            output.append("Tên thuốc gõ tay:")
            output.extend(_wrap_free_text(line.ten_tu_do, line.chi_tiet_y_lenh_id, warnings))
        if line.cach_dung and line.cach_dung.strip():
            output.append("Cách dùng:")
            output.extend(_wrap_free_text(line.cach_dung, line.chi_tiet_y_lenh_id, warnings))
    return output


def _order_drug_terms(ca: CaBenh) -> list[str]:
    """Thu thập tên thuốc và hoạt chất trong y lệnh chờ duyệt để lọc diễn biến."""
    thuoc_by_id = {thuoc.thuoc_id: thuoc for thuoc in ca.danh_muc_thuoc}
    terms: set[str] = set()
    for line in ca.y_lenh_cho_duyet.chi_tiet:
        if line.thuoc_id and line.thuoc_id in thuoc_by_id:
            terms.add(thuoc_by_id[line.thuoc_id].ten_thuoc.casefold())
        if line.ten_tu_do and line.ten_tu_do.strip():
            terms.add(line.ten_tu_do.strip().casefold())
        for hc in ingredients_of(ca, line):
            terms.add(hc.ten_hoat_chat.casefold())
            if hc.ten_quoc_te and hc.ten_quoc_te.strip():
                terms.add(hc.ten_quoc_te.strip().casefold())
    return [term for term in terms if term]


def _render_sections(
    prefix_sections: list[str],
    note_blocks: list[list[str]],
    skipped_count: int,
    rules_section: str,
) -> str:
    """Ghép toàn bộ 10 nhóm tiêu đề cố định thành văn bản gói ngữ cảnh."""
    note_lines = [line for block in note_blocks for line in block]
    if not note_lines and skipped_count == 0:
        note_lines = ["(không có)"]
    if skipped_count > 0:
        note_lines.append(f"đã lược {skipped_count} ghi chép cũ hơn")
    dien_bien_section = "\n".join(["DIỄN BIẾN", *note_lines])
    return "\n\n".join([*prefix_sections, dien_bien_section, rules_section])


def build_case_context(
    ca: CaBenh,
    ket_qua: KetQuaThamDinh,
    settings: CaseContextSettings,
) -> tuple[GoiCanCu, list[str]]:
    """Dựng gói ngữ cảnh ca bệnh đã che định danh kèm danh sách cảnh báo."""
    warnings: list[str] = []
    ban_ghi_ids: list[str] = []
    dong_y_lenh_ids: list[str] = []
    allowed: list[float] = []
    seen_nums: set[float] = set()

    _add_number(allowed, seen_nums, ca.nguoi_benh.tuoi)
    for sh in ca.sinh_hieu:
        _add_number(allowed, seen_nums, sh.gia_tri)

    # 1. HÀNH CHÍNH (không có tên, không có mã người bệnh)
    tuoi_text = str(ca.nguoi_benh.tuoi) if ca.nguoi_benh.tuoi is not None else "không rõ"
    gioi_text = _NHAN_GIOI_TINH.get(ca.nguoi_benh.gioi_tinh or "", "không rõ")
    loai_dt = _NHAN_LOAI_DIEU_TRI.get(ca.dot_dieu_tri.loai_dieu_tri, ca.dot_dieu_tri.loai_dieu_tri)
    khoa_safe = _sanitize_free_text(ca.dot_dieu_tri.khoa_dieu_tri, "DOT_DIEU_TRI", warnings)
    admin_lines = [
        "HÀNH CHÍNH",
        f"- Tuổi: {tuoi_text} | Giới: {gioi_text} | Khoa: {khoa_safe} | Loại: {loai_dt} "
        f"| Vào viện: {_format_dt(ca.dot_dieu_tri.thoi_diem_bat_dau)}",
    ]
    if latest_vital(ca, "can_nang") is None:
        admin_lines.append("- Cân nặng: thiếu")
    if latest_vital(ca, "chieu_cao") is None:
        admin_lines.append("- Chiều cao: thiếu")
    for sh in ca.sinh_hieu:
        ban_ghi_ids.append(sh.sinh_hieu_id)
        admin_lines.append(_format_vital_line(sh))

    # 2. CHẨN ĐOÁN VÀ CƠ ĐỊA
    diag_lines = ["CHẨN ĐOÁN VÀ CƠ ĐỊA"]
    if not ca.chan_doan and not ca.co_dia:
        diag_lines.append("(không có)")
    for cd in ca.chan_doan:
        ban_ghi_ids.append(cd.chan_doan_id)
        icd = cd.ma_icd10 or "không có"
        diag_lines.append(f"[{cd.chan_doan_id}] Chẩn đoán {cd.loai} (ICD-10: {icd}):")
        diag_lines.extend(_wrap_free_text(cd.noi_dung, cd.chan_doan_id, warnings))
    for cdia in ca.co_dia:
        extra = ""
        if cdia.gia_tri and cdia.gia_tri.strip():
            safe_val = _sanitize_free_text(cdia.gia_tri, f"CO_DIA_{cdia.loai}", warnings)
            extra = f" ({safe_val})"
        diag_lines.append(f"- Cơ địa {cdia.loai}: {cdia.trang_thai}{extra}")

    # 3. DỊ ỨNG
    allergy_status = _NHAN_DI_UNG[ca.tinh_trang_di_ung.trang_thai]
    status_parts = [f"Trạng thái: {allergy_status}"]
    if ca.tinh_trang_di_ung.nguon:
        status_parts.append(f"nguồn: {ca.tinh_trang_di_ung.nguon}")
    if ca.tinh_trang_di_ung.thoi_diem:
        status_parts.append(f"lúc {_format_dt(ca.tinh_trang_di_ung.thoi_diem)}")
    allergy_lines = ["DỊ ỨNG", "- " + ", ".join(status_parts)]
    for du in ca.di_ung:
        ban_ghi_ids.append(du.di_ung_id)
        meta = [f"[{du.di_ung_id}] Loại: {du.loai_tac_nhan}"]
        if du.hoat_chat_id:
            meta.append(f"hoạt chất: {du.hoat_chat_id}")
        if du.nhom_duoc_ly:
            meta.append(f"nhóm: {du.nhom_duoc_ly}")
        if du.muc_do:
            meta.append(f"mức độ: {du.muc_do}")
        allergy_lines.append(" | ".join(meta))
        reaction = du.phan_ung if du.phan_ung else "chưa rõ phản ứng"
        allergy_text = f"Tác nhân: {du.tac_nhan}; phản ứng: {reaction}"
        allergy_lines.extend(_wrap_free_text(allergy_text, du.di_ung_id, warnings))

    # 4. CHỈ SỐ ĐÃ TÍNH
    calc_lines = ["CHỈ SỐ ĐÃ TÍNH"]
    if not ket_qua.chi_so:
        calc_lines.append("(không có)")
    for cs in ket_qua.chi_so:
        if cs.ket_qua is not None:
            for digits in (0, 1, 2):
                _add_number(allowed, seen_nums, round(float(cs.ket_qua), digits))
        for inp in cs.dau_vao:
            _add_number(allowed, seen_nums, inp.gia_tri)
        calc_lines.append(_format_calc_line(cs))

    # 5. XÉT NGHIỆM
    lab_lines = ["XÉT NGHIỆM"]
    if not ca.xet_nghiem:
        lab_lines.append("(không có)")
    for xn in ca.xet_nghiem:
        ban_ghi_ids.append(xn.xet_nghiem_id)
        _add_number(allowed, seen_nums, xn.gia_tri_so)
        _add_number(allowed, seen_nums, xn.nguong_duoi)
        _add_number(allowed, seen_nums, xn.nguong_tren)
        val_parts: list[str] = []
        if xn.gia_tri_so is not None:
            val_parts.append(_format_num(xn.gia_tri_so))
        if xn.don_vi:
            val_parts.append(xn.don_vi)
        val_str = " ".join(val_parts)
        ref_str = ""
        if xn.nguong_duoi is not None and xn.nguong_tren is not None:
            low = _format_num(xn.nguong_duoi)
            high = _format_num(xn.nguong_tren)
            ref_str = f" (tham chiếu {low}–{high})"
        elif xn.nguong_duoi is not None:
            ref_str = f" (tham chiếu ≥ {_format_num(xn.nguong_duoi)})"
        elif xn.nguong_tren is not None:
            ref_str = f" (tham chiếu ≤ {_format_num(xn.nguong_tren)})"
        line_text = (
            f"[{xn.xet_nghiem_id}] {xn.ten_xet_nghiem} {val_str} "
            f"lúc {_format_dt(xn.thoi_diem_ket_qua)}{ref_str}"
        ).strip()
        lab_lines.append(line_text)
        if xn.gia_tri_text and xn.gia_tri_text.strip():
            lab_lines.extend(_wrap_free_text(xn.gia_tri_text, xn.xet_nghiem_id, warnings))

    # 6. VI SINH
    micro_lines = ["VI SINH"]
    if not ca.vi_sinh:
        micro_lines.append("(không có)")
    hc_by_id = {hc.hoat_chat_id: hc.ten_hoat_chat for hc in ca.danh_muc_hoat_chat}
    for vs in ca.vi_sinh:
        ban_ghi_ids.append(vs.vi_sinh_id)
        bacteria = vs.vi_khuan or "chưa phân lập"
        ksd_items: list[str] = []
        for ksd in vs.khang_sinh_do:
            _add_number(allowed, seen_nums, ksd.mic)
            hc_name = hc_by_id.get(ksd.hoat_chat_id, ksd.hoat_chat_id)
            mic_part = f" (MIC {_format_num(ksd.mic)})" if ksd.mic is not None else ""
            ksd_items.append(f"{hc_name}: {ksd.ket_qua}{mic_part}")
        ksd_text = ", ".join(ksd_items) if ksd_items else "chưa có kháng sinh đồ"
        micro_lines.append(
            f"[{vs.vi_sinh_id}] Bệnh phẩm: {vs.benh_pham} | Vi khuẩn: {bacteria} "
            f"| Lấy mẫu: {_format_dt(vs.thoi_diem_lay_mau)} | Kháng sinh đồ: {ksd_text}"
        )

    # 7. Y LỆNH CHỜ DUYỆT
    khoa_ke = _sanitize_free_text(ca.y_lenh_cho_duyet.khoa_ke_don, "Y_LENH", warnings)
    pending_header = (
        f"Khoa kê: {khoa_ke} | Luồng duyệt: {ca.y_lenh_cho_duyet.luong_duyet} "
        f"| Thời điểm kê: {_format_dt(ca.y_lenh_cho_duyet.thoi_diem_ke)}"
    )
    pending_lines = [
        "Y LỆNH CHỜ DUYỆT",
        pending_header,
        *_format_order_lines(
            ca,
            ca.y_lenh_cho_duyet.chi_tiet,
            warnings,
            ban_ghi_ids,
            allowed,
            seen_nums,
            is_pending=True,
            dong_y_lenh_ids=dong_y_lenh_ids,
        ),
    ]

    # 8. THUỐC ĐANG DÙNG
    current_lines = [
        "THUỐC ĐANG DÙNG",
        *_format_order_lines(
            ca,
            ca.thuoc_dang_dung,
            warnings,
            ban_ghi_ids,
            allowed,
            seen_nums,
            is_pending=False,
            dong_y_lenh_ids=dong_y_lenh_ids,
        ),
    ]

    # 10. PHÁT HIỆN CỦA BỘ LUẬT
    rule_lines = ["PHÁT HIỆN CỦA BỘ LUẬT"]
    if not ket_qua.phat_hien:
        rule_lines.append("(không có phát hiện)")
    for ph in ket_qua.phat_hien:
        line_ids = ", ".join(ph.chi_tiet_y_lenh_id) if ph.chi_tiet_y_lenh_id else "cả đơn"
        missing_info = (
            f" | thieu={', '.join(ph.thong_tin_con_thieu)}" if ph.thong_tin_con_thieu else ""
        )
        rule_lines.append(
            f"- ma_luat={ph.ma_luat} | yeu_to={ph.yeu_to} | ket_luan={ph.ket_luan} "
            f"| muc_do={ph.muc_do} | dong=[{line_ids}]{missing_info} | mo_ta: {ph.mo_ta}"
        )

    prefix_sections = [
        "\n".join(admin_lines),
        "\n".join(diag_lines),
        "\n".join(allergy_lines),
        "\n".join(calc_lines),
        "\n".join(lab_lines),
        "\n".join(micro_lines),
        "\n".join(pending_lines),
        "\n".join(current_lines),
    ]
    rules_section = "\n".join(rule_lines)

    # 9. DIỄN BIẾN (kiểm tra tổng độ dài để giữ N mới nhất + ghi chép có nhắc tên thuốc)
    note_blocks: list[list[str]] = []
    for db in ca.dien_bien:
        header = f"[{db.dien_bien_id}] {db.loai_ho_so} ({_format_dt(db.thoi_diem_ghi)}):"
        note_blocks.append([header, *_wrap_free_text(db.noi_dung, db.dien_bien_id, warnings)])

    full_text = _render_sections(prefix_sections, note_blocks, 0, rules_section)
    if len(full_text) <= settings.max_chars or not ca.dien_bien:
        for db in ca.dien_bien:
            ban_ghi_ids.append(db.dien_bien_id)
        final_text = full_text
    else:
        indexed_notes = list(enumerate(ca.dien_bien))
        newest_indices = {
            idx
            for idx, _ in sorted(
                indexed_notes,
                key=lambda pair: (pair[1].thoi_diem_ghi, pair[0]),
                reverse=True,
            )[: settings.notes_latest_n]
        }
        terms = _order_drug_terms(ca)
        drug_indices = {
            idx
            for idx, note in indexed_notes
            if any(term in note.noi_dung.casefold() for term in terms)
        }
        kept_indices = newest_indices | drug_indices
        kept_blocks = [block for idx, block in enumerate(note_blocks) if idx in kept_indices]
        for idx, db in indexed_notes:
            if idx in kept_indices:
                ban_ghi_ids.append(db.dien_bien_id)
        skipped_count = len(note_blocks) - len(kept_blocks)
        final_text = _render_sections(prefix_sections, kept_blocks, skipped_count, rules_section)

    goi = GoiCanCu(
        ca_id=ca.ca_id,
        van_ban_ca=final_text,
        ban_ghi_ids=list(dict.fromkeys(ban_ghi_ids)),
        dong_y_lenh_ids=list(dict.fromkeys(dong_y_lenh_ids)),
        so_cho_phep=allowed,
        doan=[],
    )
    return goi, warnings
