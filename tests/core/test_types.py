import pytest
from pydantic import ValidationError

from app.core.errors import CdssError, ConfigError, ProviderError, RetrievalError, VerificationError
from app.core.types import Chunk, RetrievalQuery, SearchFilter, matches


def make_chunk(
    code: str = "c1",
    text: str = "chỉnh liều khi suy thận",
    drug: str = "meropenem",
    **updates: object,
) -> Chunk:
    data = {
        "doan_trich_id": code,
        "tai_lieu_id": "doc1",
        "muc_cha_id": None,
        "nhom_nguon": "nhan_thuoc",
        "nguon": "Nguồn giả lập",
        "tang_tin_cay": 1,
        "hoat_chat_ids": [drug],
        "muc": "lieu_dung",
        "duong_dan_muc": "Thuốc/Liều dùng",
        "loai_noi_dung": "van_ban",
        "ngon_ngu": "vi",
        "phien_ban_nguon": None,
        "url_goc": None,
        "noi_dung_goc": text,
        "noi_dung_nhung": text,
        **updates,
    }
    return Chunk.model_validate(data)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, True),
        ({"nhom_nguon": "nhan_thuoc"}, True),
        ({"nhom_nguon": "van_ban_byt"}, False),
        ({"hoat_chat_ids": ["khac", "meropenem"]}, True),
        ({"hoat_chat_ids": ["amlodipin"]}, False),
        ({"muc": ["lieu_dung", "canh_bao"]}, True),
        ({"muc": ["canh_bao"]}, False),
        ({"hoat_chat_ids": ["meropenem"], "muc": ["canh_bao"]}, False),
    ],
)
def test_matches(data: dict, expected: bool) -> None:
    assert matches(make_chunk(), SearchFilter(**data)) is expected


def test_frozen_models_and_independent_defaults() -> None:
    chunk = make_chunk()
    with pytest.raises(ValidationError):
        chunk.muc = "khac"
    with pytest.raises(ValidationError):
        make_chunk(tang_tin_cay=5)
    first, second = SearchFilter(), SearchFilter()
    first.hoat_chat_ids.append("a")
    assert second.hoat_chat_ids == []
    query = RetrievalQuery(van_ban=["vi", "en"], bo_loc=second, k_query=5, k_rerank=2)
    assert query.van_ban == ["vi", "en"]


def test_error_hierarchy_and_retryability() -> None:
    for cls in (ConfigError, ProviderError, RetrievalError, VerificationError):
        assert isinstance(cls("lỗi"), CdssError)
    assert ProviderError("lỗi", retryable=True).retryable is True
    assert ProviderError("lỗi", retryable=False).retryable is False
