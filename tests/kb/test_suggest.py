"""Kiem thu chi muc goi y ten thuoc (du lieu nho dung tay, khong I/O)."""

from __future__ import annotations

import pytest

from app.kb.suggest import DrugSuggestIndex, SuggestTuple, normalize_suggest_query


def _sample_index() -> DrugSuggestIndex:
    entries: list[SuggestTuple] = [
        ("acetaminophen", "acetaminophen", "hoat_chat", ["acetaminophen"], "acetaminophen"),
        ("paracetamol", "Paracetamol", "dong_nghia", ["acetaminophen"], "paracetamol"),
        # Dong nghia trung ten_inn phai bi bo qua theo quy tac gop trung.
        ("acetaminophen", "Acetaminophen dup", "dong_nghia", ["acetaminophen"], "acetaminophen"),
        ("panadol", "Panadol", "biet_duoc", ["acetaminophen"], "Panadol"),
        ("efferalgan", "Efferalgan", "biet_duoc", ["acetaminophen"], "Efferalgan"),
        ("hapacol", "Hapacol", "biet_duoc", ["acetaminophen"], "Hapacol"),
        (
            "panadol extra",
            "Panadol Extra",
            "biet_duoc",
            ["acetaminophen", "caffeine"],
            "Panadol Extra",
        ),
        ("amiodarone", "amiodarone", "hoat_chat", ["amiodarone"], "amiodarone"),
        ("amiodaron", "amiodaron", "dong_nghia", ["amiodarone"], "amiodaron"),
        ("cordarone", "Cordarone", "biet_duoc", ["amiodarone"], "Cordarone"),
        ("caffeine", "caffeine", "hoat_chat", ["caffeine"], "caffeine"),
    ]
    return DrugSuggestIndex(
        entries,
        inn_by_id={
            "acetaminophen": "acetaminophen",
            "amiodarone": "amiodarone",
            "caffeine": "caffeine",
        },
    )


def test_normalize_suggest_query_strips_trailing_strength() -> None:
    assert normalize_suggest_query("Amiodaron 200 mg") == "amiodaron"
    assert normalize_suggest_query("amiodaron 500mg") == "amiodaron"
    assert normalize_suggest_query("ceftriaxon 1 g") == "ceftriaxon"
    assert normalize_suggest_query("glucose 5%") == "glucose"
    assert normalize_suggest_query("paracetamol 10 mg/ml") == "paracetamol"
    assert normalize_suggest_query("paracetamol mg/ml") == "paracetamol"
    assert normalize_suggest_query("penicillin g") == "penicillin g"
    assert normalize_suggest_query("200 mg") == ""


def test_fuzzy_typo_returns_acetaminophen_and_spelling_suggestion() -> None:
    index = _sample_index()
    res = index.goi_y("parecetamo")
    assert res.ket_qua
    first = res.ket_qua[0]
    assert first.hoat_chat_ids == ["acetaminophen"]
    assert first.khop == "gan_dung"
    assert res.goi_y_sua is not None


def test_exact_match_after_stripping_dosage() -> None:
    index = _sample_index()
    res = index.goi_y("amiodaron 200 mg")
    assert res.ket_qua
    first = res.ket_qua[0]
    assert first.hoat_chat_ids == ["amiodarone"]
    assert first.khop == "chinh_xac"
    assert res.goi_y_sua is None


def test_prefix_matches_brand_cordarone() -> None:
    index = _sample_index()
    res = index.goi_y("cordar")
    assert res.ket_qua
    first = res.ket_qua[0]
    assert first.nhan == "Cordarone"
    assert first.loai == "biet_duoc"
    assert first.khop == "tien_to"
    assert first.hoat_chat_ids == ["amiodarone"]
    assert res.goi_y_sua is None


def test_tier2_internal_word_prefix_matches_panadol_extra() -> None:
    index = _sample_index()
    res = index.goi_y("extra")
    assert [item.nhan for item in res.ket_qua] == ["Panadol Extra"]
    assert res.ket_qua[0].khop == "tien_to"
    assert res.ket_qua[0].ten_hoat_chat == ["acetaminophen", "caffeine"]
    assert res.goi_y_sua is None


@pytest.mark.parametrize("query", ["", "a", "  ", "1%", "500 mg"])
def test_short_or_empty_query_returns_empty(query: str) -> None:
    index = _sample_index()
    res = index.goi_y(query)
    assert res.ket_qua == []
    assert res.goi_y_sua is None


def test_deduplicates_non_brand_ingredients_and_caps_brands_at_two() -> None:
    index = _sample_index()
    res_dup = index.goi_y("acet")
    non_brands = [item for item in res_dup.ket_qua if item.loai != "biet_duoc"]
    assert [item.hoat_chat_ids for item in non_brands] == [["acetaminophen"]]
    assert non_brands[0].nhan == "acetaminophen"

    extra_index = DrugSuggestIndex(
        [
            ("paracetamol", "paracetamol", "dong_nghia", ["acetaminophen"], "paracetamol"),
            ("paracet", "Paracet", "biet_duoc", ["acetaminophen"], "Paracet"),
            ("paracold", "Paracold", "biet_duoc", ["acetaminophen"], "Paracold"),
            ("paracin", "Paracin", "biet_duoc", ["acetaminophen"], "Paracin"),
        ],
        inn_by_id={"acetaminophen": "acetaminophen"},
    )
    res_brand = extra_index.goi_y("parac")
    brands = [item for item in res_brand.ket_qua if item.loai == "biet_duoc"]
    assert len(brands) <= 2


def test_tier_ordering_is_strict() -> None:
    index = DrugSuggestIndex(
        [
            ("abdc", "Exact abdc", "biet_duoc", ["d0"], "Exact abdc"),
            ("abdcx", "Prefix abdcx", "biet_duoc", ["d1"], "Prefix abdcx"),
            ("thuoc abdc", "Word abdc", "biet_duoc", ["d2"], "Word abdc"),
            ("abcd", "Fuzzy abcd", "biet_duoc", ["d3"], "Fuzzy abcd"),
        ],
        inn_by_id={"d0": "d0", "d1": "d1", "d2": "d2", "d3": "d3"},
    )
    res = index.goi_y("abdc", gioi_han=8)
    assert [item.nhan for item in res.ket_qua] == [
        "Exact abdc",
        "Prefix abdcx",
        "Word abdc",
        "Fuzzy abcd",
    ]
    assert [item.khop for item in res.ket_qua] == [
        "chinh_xac",
        "tien_to",
        "tien_to",
        "gan_dung",
    ]
    assert res.goi_y_sua is None
