"""Kiểm thử đối chiếu trích dẫn và mã căn cứ ở app/verify/citation.py."""

import unicodedata

from app.core.types import Chunk
from app.llm.schema import GoiCanCu, NhanDinhDeXuat, TrichDanNguon
from app.verify.citation import check_citations


def _sample_chunk(text: str | None = None) -> Chunk:
    source = text or (
        "For creatinine clearance 10 to 25 mL/min, administer one-half the\n"
        "recommended   dose every 12 hours."
    )
    return Chunk(
        doan_trich_id="DT-MERO-01",
        tai_lieu_id="TL-MERO",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon="openfda",
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage and Administration > Renal Impairment",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="2025-01-01",
        url_goc=None,
        noi_dung_goc=source,
        noi_dung_nhung=source,
    )


def _sample_goi(chunk: Chunk | None = None) -> GoiCanCu:
    return GoiCanCu(
        ca_id="DEMO-02",
        van_ban_ca="[XN-DEMO02-01] Creatinin 212 umol/L",
        ban_ghi_ids=["XN-DEMO02-01", "CT-DEMO02-01"],
        dong_y_lenh_ids=["CT-DEMO02-01"],
        so_cho_phep=[212.0, 16.0],
        doan=[chunk or _sample_chunk()],
    )


def _base_proposal(**overrides: object) -> NhanDinhDeXuat:
    payload: dict[str, object] = {
        "chi_tiet_y_lenh_id": ["CT-DEMO02-01"],
        "yeu_to": 6,
        "ket_luan": "can_xem",
        "muc_do": "nghiem_trong",
        "nhan_xet": "Cần xem xét chỉnh liều.",
        "ban_ghi_ids": ["XN-DEMO02-01"],
        "trich_dan": [
            TrichDanNguon(
                doan_trich_id="DT-MERO-01",
                trich_nguyen_van="administer one-half the recommended dose every 12 hours.",
            )
        ],
    }
    payload.update(overrides)
    return NhanDinhDeXuat.model_validate(payload)


def test_check_citations_passes_with_normalized_whitespace_and_nfc() -> None:
    vi_source = unicodedata.normalize("NFD", "Chỉnh  liều\n\tmỗi 12 giờ khi CrCl từ 10 đến 25.")
    chunk = _sample_chunk(vi_source)
    goi = _sample_goi(chunk)
    proposal = _base_proposal(
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-MERO-01",
                trich_nguyen_van=unicodedata.normalize(
                    "NFC", "Chỉnh liều mỗi 12 giờ khi CrCl từ 10 đến 25."
                ),
            )
        ]
    )
    assert check_citations(proposal, goi) == []


def test_check_citations_rejects_digit_mismatch_in_quote() -> None:
    goi = _sample_goi()
    proposal = _base_proposal(
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-MERO-01",
                trich_nguyen_van="administer one-half the recommended dose every 8 hours.",
            )
        ]
    )
    assert check_citations(proposal, goi) == ["trich_khong_khop"]


def test_check_citations_covers_all_eight_error_codes() -> None:
    goi = _sample_goi()

    assert "ma_doan_la" in check_citations(
        _base_proposal(
            trich_dan=[
                TrichDanNguon(
                    doan_trich_id="DT-LA",
                    trich_nguyen_van="administer one-half the recommended dose every 12 hours.",
                )
            ]
        ),
        goi,
    )
    assert "trich_khong_khop" in check_citations(
        _base_proposal(
            trich_dan=[
                TrichDanNguon(
                    doan_trich_id="DT-MERO-01",
                    trich_nguyen_van="câu trích hoàn toàn bịa đặt trong kiểm thử.",
                )
            ]
        ),
        goi,
    )
    assert "trich_qua_ngan" in check_citations(
        _base_proposal(
            trich_dan=[TrichDanNguon(doan_trich_id="DT-MERO-01", trich_nguyen_van="every 12 hours")]
        ),
        goi,
    )
    assert "ma_ban_ghi_la" in check_citations(
        _base_proposal(ban_ghi_ids=["XN-KHONG-CO"], trich_dan=[]),
        goi,
    )
    assert "dong_y_lenh_la" in check_citations(
        _base_proposal(chi_tiet_y_lenh_id=["CT-KHONG-CO"], trich_dan=[]),
        goi,
    )
    assert "khong_co_can_cu" in check_citations(_base_proposal(ban_ghi_ids=[], trich_dan=[]), goi)
    assert "yeu_to_ngoai_khoang" in check_citations(_base_proposal(yeu_to=8, trich_dan=[]), goi)
    assert "yeu_to_ngoai_khoang" in check_citations(_base_proposal(yeu_to=0, trich_dan=[]), goi)
    assert "muc_do_khong_hop_le" in check_citations(
        _base_proposal(ket_luan="dat", muc_do="can_luu_y", trich_dan=[]),
        goi,
    )
