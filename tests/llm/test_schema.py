"""Kiểm thử lược đồ dùng chung ở app/llm/schema.py."""

import pytest
from pydantic import ValidationError

from app.llm.schema import (
    GoiCanCu,
    KetQuaLLM,
    KetQuaTongHop,
    NhanDinhCuoi,
    NhanDinhDaKiem,
    NhanDinhDeXuat,
    TrichDanNguon,
    json_schema_for_llm,
)


def test_json_schema_for_llm_has_nhan_dinh() -> None:
    schema = json_schema_for_llm()
    assert isinstance(schema, dict)
    assert "nhan_dinh" in schema["properties"]


def test_all_schema_models_forbid_extra_fields() -> None:
    valid_dx = {
        "chi_tiet_y_lenh_id": [],
        "yeu_to": 1,
        "ket_luan": "dat",
        "muc_do": None,
        "nhan_xet": "Đạt",
        "ban_ghi_ids": ["CT-1"],
        "trich_dan": [],
    }
    cases = [
        (TrichDanNguon, {"doan_trich_id": "D1", "trich_nguyen_van": "a" * 20, "extra": 1}),
        (NhanDinhDeXuat, {**valid_dx, "extra": 1}),
        (KetQuaTongHop, {"nhan_dinh": [], "extra": 1}),
        (
            GoiCanCu,
            {
                "ca_id": "C1",
                "van_ban_ca": "x",
                "ban_ghi_ids": [],
                "dong_y_lenh_ids": [],
                "so_cho_phep": [],
                "extra": 1,
            },
        ),
        (NhanDinhDaKiem, {"de_xuat": valid_dx, "dat": True, "loi": [], "extra": 1}),
        (NhanDinhCuoi, {"nguon_goc": "luat", "extra": 1}),
        (
            KetQuaLLM,
            {
                "trang_thai": "ok",
                "nhan_dinh": [],
                "so_lan_goi": 0,
                "canh_bao": [],
                "phien_ban_prompt": "v1",
                "extra": 1,
            },
        ),
    ]
    for model_cls, payload in cases:
        with pytest.raises(ValidationError):
            model_cls.model_validate(payload)
