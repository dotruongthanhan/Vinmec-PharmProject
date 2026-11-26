"""Mô hình trao đổi JSON cho dịch vụ Chrome Extension độc lập (hợp đồng v1.10)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.api import schemas as core_s
from app.api.schemas import ApiModel
from app.extension_api.extractor import (
    CaseRecalcPatch,
    ClassifiedField,
    EmrSectionPayload,
    SchemaFieldDescriptor,
)

MAX_SCHEMA_FIELDS = 120
MAX_EMR_SECTIONS = 60
MAX_TOTAL_EMR_CHARS = 120_000


class ClassifySchemaRequest(ApiModel):
    """Yêu cầu phân loại chỉ tên nhãn trường EMR (tuyệt đối không gửi giá trị người bệnh)."""

    schema_hash: str = Field(min_length=4, max_length=128)
    source_domain: str | None = Field(default=None, max_length=160)
    fields: list[SchemaFieldDescriptor] = Field(min_length=1, max_length=MAX_SCHEMA_FIELDS)


class ClassifySchemaResponse(ApiModel):
    """Kết quả phân loại nhãn trường trả về cho bộ nhớ đệm trình duyệt."""

    schema_hash: str
    mo_hinh: str | None
    fields: list[ClassifiedField]


class ExtractEmrPayload(ApiModel):
    """Dữ liệu văn bản EMR đã cắt bỏ PII ở trình duyệt gửi lên qua `emr_json`."""

    schema_hash: str | None = Field(default=None, max_length=128)
    tab_count: int = Field(default=1, ge=1, le=20)
    source_domains: list[str] = Field(default_factory=list, max_length=20)
    sections: list[EmrSectionPayload] = Field(min_length=1, max_length=MAX_EMR_SECTIONS)

    @field_validator("source_domains")
    @classmethod
    def _validate_domains(cls, value: list[str]) -> list[str]:
        """Giới hạn độ dài từng tên miền nguồn."""
        return [item.strip()[:160] for item in value if item.strip()]

    @field_validator("sections")
    @classmethod
    def _validate_total_chars(cls, value: list[EmrSectionPayload]) -> list[EmrSectionPayload]:
        """Giới hạn tổng độ dài văn bản EMR gửi trong một phiên."""
        total = sum(len(item.noi_dung) + len(item.tieu_de) for item in value)
        if total > MAX_TOTAL_EMR_CHARS:
            raise ValueError(f"Tổng dung lượng văn bản EMR vượt trần {MAX_TOTAL_EMR_CHARS} ký tự")
        return value


class ExtensionReviewResponse(ApiModel):
    """Kết quả thẩm định tức thì trả về cho Side Panel từ phiên RAM tạm thời."""

    session_id: str
    expires_in_seconds: int
    zero_retention: Literal[True] = True
    chi_tiet: core_s.ChiTietCa
    canh_bao_trinh_duyet: list[str] = Field(default_factory=list)
    canh_bao_pii_anh: list[str] = Field(default_factory=list)
    mo_hinh_da_dung: dict[str, str] = Field(default_factory=dict)
    thoi_gian_ms: float
    che_do: core_s.CheDo


class RecalcRequest(CaseRecalcPatch):
    """Dữ liệu sửa nhanh sinh hiệu/xét nghiệm/dị ứng/y lệnh cho `/recalc`."""


class ExtensionHealthResponse(ApiModel):
    """Trạng thái dịch vụ Chrome Extension độc lập."""

    ok: Literal[True] = True
    zero_retention: Literal[True] = True
    phien_ban: str = "1.10.0-extension"
    che_do: core_s.CheDo
    xac_thuc: str
    mo_hinh_trich_xuat: dict[str, str] = Field(default_factory=dict)
