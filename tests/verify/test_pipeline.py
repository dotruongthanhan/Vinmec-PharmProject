"""Kiểm thử verify_all kết hợp kiểm chứng trích dẫn và con số."""

from app.core.types import Chunk
from app.llm.schema import GoiCanCu, KetQuaTongHop, NhanDinhDeXuat, TrichDanNguon
from app.verify.pipeline import verify_all


def test_verify_all_combines_citation_and_number_checks() -> None:
    chunk = Chunk(
        doan_trich_id="DT-01",
        tai_lieu_id="TL-01",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon="openfda",
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="2025",
        url_goc=None,
        noi_dung_goc="Administer 500 mg every 12 hours for creatinine clearance 10 to 25.",
        noi_dung_nhung="Administer 500 mg every 12 hours for creatinine clearance 10 to 25.",
    )
    goi = GoiCanCu(
        ca_id="DEMO-02",
        van_ban_ca="[XN-01] Creatinin 212 umol/L",
        ban_ghi_ids=["XN-01"],
        dong_y_lenh_ids=["CT-01"],
        so_cho_phep=[212.0, 16.0],
        doan=[chunk],
    )
    ok_item = NhanDinhDeXuat(
        chi_tiet_y_lenh_id=["CT-01"],
        yeu_to=6,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        nhan_xet="CrCl 16,0 mL/phút: đề nghị đối chiếu liều 500 mg mỗi 12 giờ.",
        ban_ghi_ids=["XN-01"],
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-01",
                trich_nguyen_van="Administer 500 mg every 12 hours",
            )
        ],
    )
    bad_item = ok_item.model_copy(
        update={
            "nhan_xet": "CrCl 28 mL/phút.",
            "trich_dan": [
                TrichDanNguon(doan_trich_id="DT-LA", trich_nguyen_van="ngắn"),
            ],
        }
    )

    results = verify_all(KetQuaTongHop(nhan_dinh=[ok_item, bad_item]), goi)
    assert len(results) == 2
    assert results[0].dat is True
    assert results[0].loi == []
    assert results[1].dat is False
    assert set(results[1].loi) == {"trich_qua_ngan", "ma_doan_la", "so_khong_co_nguon:28"}
