"""Kiểm thử tách và đối chiếu con số ở app/verify/number.py."""

import pytest

from app.core.types import Chunk
from app.llm.schema import GoiCanCu, NhanDinhDeXuat, TrichDanNguon
from app.verify.number import (
    check_numbers,
    extract_numbers,
    mask_citation_markers,
    unverified_numbers,
)


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        doan_trich_id=chunk_id,
        tai_lieu_id="TL-1",
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
        noi_dung_goc=text,
        noi_dung_nhung=text,
    )


def _goi(chunks: list[Chunk] | None = None) -> GoiCanCu:
    return GoiCanCu(
        ca_id="DEMO-02",
        van_ban_ca="CrCl 16,0 mL/phút",
        ban_ghi_ids=["XN-DEMO02-01"],
        dong_y_lenh_ids=["CT-DEMO02-01"],
        so_cho_phep=[212.0, 16.0, 1.0, 8.0],
        doan=chunks or [],
    )


def test_extract_numbers_parses_decimals_and_skips_ids_dates_times_factors() -> None:
    assert extract_numbers("CrCl 16,0 mL/phút, liều 1 g mỗi 8 giờ") == [16.0, 1.0, 8.0]
    text = (
        "[XN-DEMO02-01] Creatinin 212 umol/L lúc 10/11/2026 05:30; yếu tố 6 cho CrCl 16.0 mL/phút."
    )
    assert extract_numbers(text) == [212.0, 16.0]


def test_extract_numbers_handles_thousand_grouping_only_with_counting_unit() -> None:
    assert extract_numbers("Liều 1.000 mg và 2.500 viên, tối đa 1.000.000 UI.") == [
        1000.0,
        2500.0,
        1000000.0,
    ]
    assert extract_numbers("Giá trị 1.000 và CrCl 15.999 mL/phút") == [1.0, 15.999]


@pytest.mark.parametrize(
    "unit",
    [
        "/1,73 m²",
        "/1.73 m²",
        "/1,73m²",
        "/1.73m2",
        "/1.73 m^2",
        "mL/phút/1,73 m²",
        "mL/min / 1.73 m^2",
    ],
)
def test_normalized_surface_area_unit_does_not_require_source(unit: str) -> None:
    reply = mask_citation_markers(f"eGFR 45 {unit} [1]", {1})
    assert unverified_numbers([reply], [45.0]) == []
    assert unverified_numbers([reply], []) == ["so_khong_co_nguon:45"]


def test_surface_area_without_slash_still_requires_source() -> None:
    assert unverified_numbers(["BSA 1,73 m²"], []) == ["so_khong_co_nguon:1.73"]
    assert unverified_numbers(["/1,74 m²"], []) == ["so_khong_co_nguon:1.74"]
    assert unverified_numbers(["/1,73 mg"], []) == ["so_khong_co_nguon:1.73"]


def test_check_numbers_allows_case_and_cited_chunk_and_flags_fabricated() -> None:
    cited = _chunk("DT-01", "For CrCl 10 to 25 mL/min, give every 12 hours.")
    uncited = _chunk("DT-02", "Other limit 99 mg.")
    goi = _goi([cited, uncited])

    ok_from_case_and_cited = NhanDinhDeXuat(
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        yeu_to=6,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        nhan_xet="CrCl 16,0 mL/phút, ngưỡng 10 đến 25 mỗi 12 giờ.",
        ban_ghi_ids=["XN-DEMO02-01"],
        trich_dan=[
            TrichDanNguon(
                doan_trich_id="DT-01",
                trich_nguyen_van="For CrCl 10 to 25 mL/min, give every 12 hours.",
            )
        ],
    )
    assert check_numbers(ok_from_case_and_cited, goi) == []

    fabricated = ok_from_case_and_cited.model_copy(
        update={"nhan_xet": "CrCl 28 mL/phút cần giảm liều."}
    )
    assert check_numbers(fabricated, goi) == ["so_khong_co_nguon:28"]

    from_uncited_chunk = ok_from_case_and_cited.model_copy(update={"de_xuat": "Giới hạn 99 mg."})
    assert check_numbers(from_uncited_chunk, goi) == ["so_khong_co_nguon:99"]
