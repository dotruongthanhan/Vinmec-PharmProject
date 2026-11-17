import pytest

from app.config.settings import load_settings
from app.retrieval.query_builder import QueryBuilder


def test_renal_query_uses_templates_filters_and_configured_counts() -> None:
    settings = load_settings("test").retrieval
    query = QueryBuilder(settings).for_finding("meropenem", "meropenem", "meropenem", 6, None)
    assert query.bo_loc.hoat_chat_ids == ["meropenem"]
    assert query.bo_loc.nhom_nguon == "nhan_thuoc"
    assert query.bo_loc.muc == ["lieu_than", "lieu_gan", "lieu", "thai_ky_cho_bu", "nhi_cao_tuoi"]
    assert query.van_ban == [
        "meropenem chỉnh liều suy thận độ thanh thải creatinin",
        "meropenem renal impairment dosage adjustment creatinine clearance",
    ]
    assert query.k_query == settings.nhan_thuoc.k_query
    assert query.k_rerank == settings.nhan_thuoc.k_rerank


@pytest.mark.parametrize("factor", [2, 7])
def test_no_template_uses_only_names_in_language_order(factor: int) -> None:
    settings = load_settings("test").retrieval.model_copy(update={"query_languages": ["en", "vi"]})
    query = QueryBuilder(settings).for_finding(
        "amoxicillin", "amoxicillin", "amoxicilin", factor, "R"
    )
    assert query.bo_loc.muc == []
    assert query.van_ban == ["amoxicillin", "amoxicilin"]


@pytest.mark.parametrize(
    "factor,sections,vi,en",
    [
        (
            1,
            ["chong_chi_dinh", "canh_bao"],
            "dị ứng quá mẫn chống chỉ định phản ứng chéo",
            "hypersensitivity contraindication cross-reactivity allergy",
        ),
        (
            3,
            ["chi_dinh", "lieu"],
            "chỉ định liều dùng đường dùng",
            "indications dosage and administration",
        ),
        (4, ["tuong_tac"], "tương tác thuốc", "drug interactions"),
        (
            5,
            ["canh_bao", "tac_dung_phu"],
            "cảnh báo độc tính tác dụng không mong muốn",
            "warnings toxicity adverse reactions",
        ),
    ],
)
def test_other_templates(factor: int, sections: list[str], vi: str, en: str) -> None:
    query = QueryBuilder(load_settings("test").retrieval).for_finding(
        "x", "inn", "viet", factor, None
    )
    assert query.bo_loc.muc == sections
    assert query.van_ban == [f"viet {vi}", f"inn {en}"]


def test_baseline_always_returns_contraindication_and_interaction_queries() -> None:
    builder = QueryBuilder(load_settings("test").retrieval)
    assert builder.baseline("meropenem", "meropenem", "meropenem") == [
        builder.for_finding("meropenem", "meropenem", "meropenem", factor, None)
        for factor in (1, 4)
    ]
