"""Đường chạy kiểm chứng toàn bộ các đề xuất từ bước LLM tổng hợp."""

from app.llm.schema import GoiCanCu, KetQuaTongHop, NhanDinhDaKiem
from app.verify.citation import check_citations
from app.verify.number import check_numbers


def verify_all(tong_hop: KetQuaTongHop, goi: GoiCanCu) -> list[NhanDinhDaKiem]:
    """Chạy kiểm chứng trích dẫn và con số cho từng đề xuất trong KetQuaTongHop."""
    results: list[NhanDinhDaKiem] = []
    for de_xuat in tong_hop.nhan_dinh:
        errors = list(dict.fromkeys([*check_citations(de_xuat, goi), *check_numbers(de_xuat, goi)]))
        results.append(NhanDinhDaKiem(de_xuat=de_xuat, dat=not errors, loi=errors))
    return results
