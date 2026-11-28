"""Mô hình đầu vào đã nạp và kết quả độ phủ."""

from pydantic import BaseModel, Field

DEFAULT_REQUIRED = ("dav", "rxcui", "atc", "ddinter", "nhan_fda")
SOURCE_COLUMNS = {
    "dav": "so_che_pham_dav",
    "rxcui": "co_rxcui",
    "atc": "ma_atc",
    "ddinter": "ddinter_da_cao_du",
    "nhan_fda": "so_doan_nhan_fda",
    "ndc": "co_ndc",
    "livertox": "co_livertox",
    "lactmed": "co_lactmed",
}


class AxisIngredient(BaseModel):
    """Một hoạt chất từ chỉ mục tra cứu, kèm số chế phẩm và dấu ca."""

    hoat_chat_id: str
    ten_inn: str
    ten_viet: str | None = None
    loai: str
    rxcui: str | None = None
    ma_atc: list[str]
    ddinter_id: str | None = None
    ddinter_cach_khop: str | None = None
    so_che_pham_dav: int
    trong_ca_gia_lap: bool


class LabelChunk(BaseModel):
    """Liên kết hoạt chất và nhãn lấy từ đoạn đã dựng."""

    nguon: str
    hoat_chat_ids: list[str]
    tai_lieu_id: str


class CoverageData(BaseModel):
    """Dữ liệu đã nạp; None ở danh mục tùy chọn nghĩa là chưa có nguồn."""

    hoat_chat: list[AxisIngredient]
    doan_nhan: list[LabelChunk]
    tong_ddinter: dict[str, int | None]
    so_dong_ddinter: dict[str, int]
    ten_ndc: set[str]
    ten_livertox: set[str] | None
    ten_lactmed: set[str] | None


class CoverageRow(BaseModel):
    """Một dòng ma trận, ô chưa biết được giữ là None."""

    hoat_chat_id: str
    ten_inn: str
    ten_viet: str | None
    loai: str
    so_che_pham_dav: int
    co_rxcui: bool
    ma_atc: list[str]
    ddinter_id: str | None
    ddinter_cach_khop: str | None
    ddinter_da_cao_du: bool | None
    so_doan_nhan_fda: int
    set_id_nhan_fda: list[str]
    co_ndc: bool
    co_livertox: bool | None
    co_lactmed: bool | None
    trong_ca_gia_lap: bool
    thieu: list[str] = Field(default_factory=list)


class IngredientGap(BaseModel):
    """Các nguồn còn thiếu của một hoạt chất trong ca."""

    hoat_chat_id: str
    ten_inn: str
    thieu: list[str]


class CaseCoverage(BaseModel):
    """Độ phủ riêng các hoạt chất xuất hiện trong bảng chuyển mã ca."""

    so_hoat_chat: int
    so_du_nguon_bat_buoc: int
    thieu_theo_nguon: dict[str, int]
    hoat_chat_thieu: list[IngredientGap]


class CoverageSummary(BaseModel):
    """Số hoạt chất có dữ liệu ở mỗi cột và các khoảng trống của ca."""

    so_hoat_chat: int
    nguon_bat_buoc: list[str]
    theo_cot: dict[str, int]
    tong_so_che_pham_dav: int
    tong_so_doan_nhan_fda: int
    so_du_nguon_bat_buoc: int
    thieu_theo_nguon: dict[str, int]
    trang_thai_nguon: dict[str, str]
    trong_ca_gia_lap: CaseCoverage
