"""Đường chạy kiểm chứng toàn bộ các đề xuất từ bước LLM tổng hợp."""

from app.llm.schema import GoiCanCu, KetQuaTongHop, NhanDinhDaKiem
from app.tracing import che_chu_so_ma_ly_do, span, vet_hien_tai
from app.verify.citation import check_citations
from app.verify.number import check_numbers


def verify_all(tong_hop: KetQuaTongHop, goi: GoiCanCu) -> list[NhanDinhDaKiem]:
    """Chạy kiểm chứng trích dẫn và con số cho từng đề xuất trong KetQuaTongHop."""
    with span("kiem_chung", "kiem_chung_tong_hop") as kc_span:
        results: list[NhanDinhDaKiem] = []
        for de_xuat in tong_hop.nhan_dinh:
            errors = list(
                dict.fromkeys([*check_citations(de_xuat, goi), *check_numbers(de_xuat, goi)])
            )
            results.append(NhanDinhDaKiem(de_xuat=de_xuat, dat=not errors, loi=errors))
        blocked = [item for item in results if not item.dat]
        reasons = [
            che_chu_so_ma_ly_do(err)
            for err in dict.fromkeys(err for item in blocked for err in item.loi)
        ]
        kc_span.dat_thuoc_tinh(
            tong_so=len(results),
            so_dat=len(results) - len(blocked),
            so_bi_chan=len(blocked),
            ma_ly_do=reasons,
            trang_thai_ket_qua="ok" if not blocked else "co_bi_chan",
        )
        if blocked:
            vet = vet_hien_tai.get()
            if vet is not None:
                vet.tang_so_bi_chan(len(blocked))
        return results
