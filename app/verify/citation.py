"""Kiểm chứng mã bản ghi, mã dòng y lệnh, mã đoạn nguồn và câu trích nguyên văn."""

import unicodedata

from app.llm.schema import GoiCanCu, NhanDinhDeXuat


def normalize_text(text: str) -> str:
    """Chuẩn hoá Unicode NFC, gộp mọi khoảng trắng thành một dấu cách và bỏ hai đầu."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def quote_matches_source(quote: str, source: str) -> bool:
    """Kiểm tra câu trích khác rỗng có là chuỗi con của đoạn nguồn sau chuẩn hoá."""
    norm_quote = normalize_text(quote)
    if not norm_quote:
        return False
    return norm_quote in normalize_text(source)


def check_citations(de_xuat: NhanDinhDeXuat, goi: GoiCanCu) -> list[str]:
    """Kiểm tra tính hợp lệ của yếu tố, mức độ, mã bản ghi và câu trích dẫn nguồn."""
    errors: list[str] = []

    if isinstance(de_xuat.yeu_to, bool) or not 1 <= de_xuat.yeu_to <= 7:
        errors.append("yeu_to_ngoai_khoang")

    if de_xuat.ket_luan == "dat" and de_xuat.muc_do is not None:
        errors.append("muc_do_khong_hop_le")

    if not de_xuat.ban_ghi_ids and not de_xuat.trich_dan:
        errors.append("khong_co_can_cu")

    allowed_records = set(goi.ban_ghi_ids)
    if any(record_id not in allowed_records for record_id in de_xuat.ban_ghi_ids):
        errors.append("ma_ban_ghi_la")

    allowed_lines = set(goi.dong_y_lenh_ids)
    if any(line_id not in allowed_lines for line_id in de_xuat.chi_tiet_y_lenh_id):
        errors.append("dong_y_lenh_la")

    chunk_by_id = {chunk.doan_trich_id: chunk for chunk in goi.doan}
    for quote in de_xuat.trich_dan:
        norm_quote = normalize_text(quote.trich_nguyen_van)
        if len(norm_quote) < 15:
            errors.append("trich_qua_ngan")
        chunk = chunk_by_id.get(quote.doan_trich_id)
        if chunk is None:
            errors.append("ma_doan_la")
            continue
        norm_source = normalize_text(chunk.noi_dung_goc)
        if norm_quote not in norm_source:
            errors.append("trich_khong_khop")

    return list(dict.fromkeys(errors))
