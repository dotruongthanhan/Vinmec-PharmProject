"""Kiểm thử DanhMucCongCu: đăng ký, ràng buộc lược đồ và xuất mô tả cho LLM."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from app.agent.tools.base import KetQuaCongCu, Tool, ToolContext
from app.agent.tools.registry import DanhMucCongCu


class _ValidParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tu_khoa: str


class _OpenParams(BaseModel):
    tu_khoa: str


class _CaseIdParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ca_id: str


class _SampleTool(Tool):
    ten: ClassVar[str] = "cong_cu_mau"
    ten_hien_thi: ClassVar[str] = "Công cụ mẫu"
    mo_ta: ClassVar[str] = "Mô tả công cụ mẫu."
    LuocDoThamSo: ClassVar[type[BaseModel]] = _ValidParams

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        del tham_so, ctx
        return KetQuaCongCu(trang_thai="ok", noi_dung="xong")


class _OtherValidTool(_SampleTool):
    ten: ClassVar[str] = "cong_cu_hai"
    ten_hien_thi: ClassVar[str] = "Công cụ hai"
    mo_ta: ClassVar[str] = "Mô tả công cụ hai."


class _OpenSchemaTool(_SampleTool):
    ten: ClassVar[str] = "cong_cu_thieu_forbid"
    LuocDoThamSo: ClassVar[type[BaseModel]] = _OpenParams


class _CaseIdTool(_SampleTool):
    ten: ClassVar[str] = "cong_cu_co_ca_id"
    LuocDoThamSo: ClassVar[type[BaseModel]] = _CaseIdParams


def test_dang_ky_trung_ten_bao_loi() -> None:
    registry = DanhMucCongCu()
    registry.dang_ky(_SampleTool())
    with pytest.raises(ValueError, match="Trùng tên"):
        registry.dang_ky(_SampleTool())


def test_dang_ky_thieu_extra_forbid_bao_loi() -> None:
    registry = DanhMucCongCu()
    with pytest.raises(ValueError, match="extra='forbid'"):
        registry.dang_ky(_OpenSchemaTool())


def test_dang_ky_co_ca_id_bao_loi() -> None:
    registry = DanhMucCongCu()
    with pytest.raises(ValueError, match="ca_id"):
        registry.dang_ky(_CaseIdTool())


def test_mo_ta_cho_llm_chi_tra_ten_duoc_hoi_va_da_dang_ky() -> None:
    registry = DanhMucCongCu()
    registry.dang_ky(_SampleTool())
    registry.dang_ky(_OtherValidTool())

    assert registry.ten_da_dang_ky() == ["cong_cu_mau", "cong_cu_hai"]
    assert registry.lay("cong_cu_mau") is not None
    assert registry.lay("khong_ton_tai") is None

    descriptions = registry.mo_ta_cho_llm(["cong_cu_hai", "khong_ton_tai", "cong_cu_hai"])
    assert len(descriptions) == 1
    assert descriptions[0]["ten"] == "cong_cu_hai"
    assert descriptions[0]["mo_ta"] == "Mô tả công cụ hai."
    assert descriptions[0]["tham_so"] == _ValidParams.model_json_schema()
