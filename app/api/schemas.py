"""Mô hình trao đổi JSON theo hợp đồng API v1 và bổ sung v1.1."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MucDoMa = Literal["nghiem_trong", "can_luu_y"] | None
KetLuanMa = Literal["dat", "can_xem", "khong_du_du_lieu", "ngoai_hdsd"]
DiUngMa = Literal["co_di_ung", "khong_di_ung_da_hoi", "chua_co_thong_tin"]
LoaiCanCuMa = Literal["du_lieu", "tinh_toan", "tai_lieu"]
PhanHoiMa = Literal["dong_y", "bac_bo", "can_sua"]


class ApiModel(BaseModel):
    """Từ chối trường ngoài hợp đồng, kể cả trong các đối tượng lồng nhau."""

    model_config = ConfigDict(extra="forbid")


class CheDo(ApiModel):
    co_llm: bool
    truy_xuat: Literal["chua_co", "tu_khoa", "lai", "san_sang"]
    hoi_them: bool
    thong_bao: list[str]


class DongHangDoi(ApiModel):
    ca_id: str
    khoa: str
    mo_ta: str
    uu_tien: Literal[0, 1, 2, 3, 4]
    huy_hieu: str
    so_nghiem_trong: int
    so_can_luu_y: int
    so_thieu_du_lieu: int
    da_phan_hoi_het: bool


class LoadError(ApiModel):
    tep: str
    loi: str


class DanhSachCa(ApiModel):
    cases: list[DongHangDoi]
    loi_nap: list[LoadError]
    che_do: CheDo


class FindingCounts(ApiModel):
    nghiem_trong: int
    can_luu_y: int
    thieu_du_lieu: int
    ngoai_hdsd: int
    dat: int


class DinhDanhCa(ApiModel):
    ca_id: str
    gioi_tuoi: str
    can_nang: str
    khoa_loai: str
    crcl: str
    crcl_bat_thuong: bool
    di_ung_ma: DiUngMa
    di_ung_text: str
    dem: FindingCounts


class Diagnosis(ApiModel):
    loai_nhan: str
    noi_dung: str
    ma_icd10: str | None


class ProgressNote(ApiModel):
    thoi_diem_text: str
    loai_nhan: str
    noi_dung: str


class AbnormalLab(ApiModel):
    ten: str
    gia_tri_text: str
    don_vi: str
    huong: Literal["▲", "▼"]
    thoi_diem_text: str
    so_voi_truoc: str | None


class TomTat(ApiModel):
    chan_doan: list[Diagnosis]
    co_dia: list[str]
    vao_vien_text: str
    nam_vien_text: str | None
    dien_bien_moi_nhat: ProgressNote | None
    bat_thuong: list[AbnormalLab]
    bat_thuong_ghi_chu: str | None


class MetricInput(ApiModel):
    nhan: str
    gia_tri_text: str
    don_vi: str
    ban_ghi_id: str | None
    thoi_diem_text: str | None


class ChiSo(ApiModel):
    cong_thuc: str
    nhan: str
    don_vi: str
    gia_tri_text: str
    thieu: list[str]
    dau_vao: list[MetricInput]
    ghi_chu: list[str]
    tham_khao: str


class CanCu(ApiModel):
    so: int
    loai_ma: LoaiCanCuMa
    loai_nhan: str
    mo_ta: str
    ban_ghi_id: str | None
    mo_duoc: bool
    cong_thuc: str | None
    ghi_chu: str | None


class PhanHoiDaGhi(ApiModel):
    phan_hoi: PhanHoiMa
    phan_hoi_nhan: str
    nhom_ly_do: str | None
    ly_do: str | None
    thoi_diem_text: str


class TrichDan(ApiModel):
    so: int
    doan_trich_id: str
    nhan: str
    trich_nguyen_van: str


class NhanDinh(ApiModel):
    nhan_dinh_id: str
    thuoc: str
    yeu_to: str
    nhan_xet: str
    ket_luan_ma: KetLuanMa
    ket_luan_nhan: str
    muc_do_ma: MucDoMa
    muc_do_nhan: str | None
    nguon_goc_ma: Literal["luat", "ai_da_kiem_chung", "ai_chua_kiem_chung"]
    nguon_goc_nhan: str
    ma_luat: str | None
    chi_tiet_y_lenh_id: list[str]
    thong_tin_con_thieu: list[str]
    can_cu: list[CanCu]
    phan_hoi: PhanHoiDaGhi | None
    dien_giai_ai: str | None = None
    de_xuat_ai: str | None = None
    trich_dan: list[TrichDan] = Field(default_factory=list)


class BangYLenh(ApiModel):
    cot: list[str]
    dong: list[dict[str, str]]


class Findings(ApiModel):
    can_chu_y: list[NhanDinh]
    dat: list[NhanDinh]
    yeu_to_chua_kiem: list[str]
    so_luat_da_chay: int


class Orders(ApiModel):
    thong_tin_text: str
    cho_duyet: BangYLenh
    dang_dung: BangYLenh | None


class LabResult(ApiModel):
    thoi_diem_text: str
    ten: str
    gia_tri_text: str
    don_vi: str
    khoang_tham_chieu: str
    ngoai_nguong: bool
    huong: Literal["▲", "▼"] | None


class Susceptibility(ApiModel):
    hoat_chat: str
    ket_qua: str
    mic_text: str
    dang_ke: bool


class Culture(ApiModel):
    benh_pham: str
    lay_mau_text: str
    vi_khuan: str
    khang_sinh_do: list[Susceptibility]


class CaseDetails(ApiModel):
    y_lenh: Orders
    xet_nghiem: list[LabResult]
    vi_sinh: list[Culture]
    dien_bien: list[ProgressNote]


class ChiTietCa(ApiModel):
    ca_id: str
    dinh_danh: DinhDanhCa
    tom_tat: TomTat
    chi_so: list[ChiSo]
    nhan_dinh: Findings
    chi_tiet: CaseDetails
    cau_hoi_goi_y: list[str]
    nhom_ly_do: list[str]
    thoi_gian_ms: float
    che_do: CheDo


class BanGhi(ApiModel):
    loai: str
    tieu_de: str
    dong: list[tuple[str, str]]


class GuiPhanHoi(ApiModel):
    nhan_dinh_id: str
    phan_hoi: PhanHoiMa
    nhom_ly_do: str | None = None
    ly_do: str | None = None


class ChatMessage(ApiModel):
    vai: Literal["nguoi_dung", "he_thong"]
    noi_dung: str


class GuiCauHoi(ApiModel):
    cau_hoi: str
    lich_su: list[ChatMessage]


class Citation(ApiModel):
    so: int
    loai_ma: LoaiCanCuMa
    nhan: str
    ban_ghi_id: str | None


class TraLoi(ApiModel):
    trang_thai: Literal["chua_san_sang", "ok", "khong_co_nguon", "ngoai_pham_vi", "loi"]
    noi_dung: str
    trich_dan: list[Citation]
    cong_cu_da_goi: list[str]


class AiFindings(ApiModel):
    can_chu_y: list[NhanDinh]
    dat: list[NhanDinh]


class KetQuaAI(ApiModel):
    trang_thai: Literal["tat", "dang_chay", "xong", "loi"]
    nhan_dinh: AiFindings | None = None
    canh_bao: list[str]
    thoi_gian_ms: float | None = None
    mo_hinh: str | None = None


class DoanNguon(ApiModel):
    doan_trich_id: str
    nguon_nhan: str
    duong_dan_muc: str
    tang_tin_cay: int
    phien_ban: str
    url_goc: str | None
    noi_dung: str


class ChayAI(ApiModel):
    chay_lai: bool = False
