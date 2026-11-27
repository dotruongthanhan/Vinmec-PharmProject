"""Các cấu trúc dữ liệu của hợp đồng minh hoạ."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CotDuLieu(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ten: str
    kieu: Literal["dinh_luong", "thu_tu", "danh_muc", "thoi_gian", "logic"]
    don_vi: str | None = None
    nhan: str | None = None
    nhan_dung: str | None = Field(default=None, max_length=120)
    nhan_sai: str | None = Field(default=None, max_length=120)


class BoDuLieu(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ma: str
    cot: list[CotDuLieu] = Field(max_length=20)
    dong: list[dict[str, str | float | bool | None]] = Field(max_length=2000)
    can_cu: list[str] = Field(default_factory=list)


class KhoiMinhHoa(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ma: str
    phien_ban: Literal["mh-1"]
    dac_ta: dict[str, Any]
    bo_du_lieu: list[BoDuLieu]
    cong_thuc_hien_thi: str | None = None
    nguon: list[str]
