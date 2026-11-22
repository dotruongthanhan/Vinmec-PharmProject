"""Mô hình trao đổi JSON theo hợp đồng API v1, v1.1 và hỏi đáp v1.2."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.kb.interactions.models import MaTranTuongTac as MaTranTuongTac

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
    ma_y_lenh: str | None = None
    thoi_diem_ke: str | None = None
    nguoi_benh_tom_tat: str | None = None
    thuoc: list[str] = Field(default_factory=list)
    ho_ten: str | None = None
    ngay_sinh: date | None = None
    chan_doan_chinh: str | None = None
    vao_vien: datetime | None = None
    so_y_lenh: int | None = None


class LoadError(ApiModel):
    tep: str
    loi: str


class DanhSachCa(ApiModel):
    cases: list[DongHangDoi]
    loi_nap: list[LoadError]
    che_do: CheDo
    lam_moi_luc: datetime | None = Field(default=None, exclude_if=lambda value: value is None)


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


class Address(ApiModel):
    so_nha: str | None = None
    thon_pho: str | None = None
    xa_phuong: str | None = None
    huyen: str | None = None
    tinh_thanh: str | None = None


class Insurance(ApiModel):
    so_the: str | None = None
    gia_tri_den: date | None = None


class Contact(ApiModel):
    ho_ten: str | None = None
    quan_he: str | None = None
    dien_thoai: str | None = None


class Parent(ApiModel):
    ho_ten: str | None = None
    nghe_nghiep: str | None = None


class Parents(ApiModel):
    bo: Parent | None = None
    me: Parent | None = None


class FullIdentity(ApiModel):
    ho_ten: str | None = None
    ngay_sinh: date | None = None
    tuoi: int | None = None
    gioi_tinh: Literal["nam", "nu"] | None = None
    chieu_cao_cm: float | None = None
    can_nang_kg: float | None = None
    dan_toc: str | None = None
    ngoai_kieu: str | None = None
    nghe_nghiep: str | None = None
    dia_chi: Address | None = None
    dia_chi_text: str | None = None
    doi_tuong: Literal["bhyt", "thu_phi", "mien", "khac"] | None = None
    bhyt: Insurance | None = None
    nguoi_bao_tin: Contact | None = None
    bo_me: Parents | None = None
    nhom_mau: str | None = None


class Discharge(ApiModel):
    hinh_thuc: Literal["ra_vien", "xin_ve", "bo_ve", "dua_ve", "chuyen_vien"]
    chuyen_vien_den: str | None = None
    ly_do: str | None = None


class DepartmentStay(ApiModel):
    khoa: str
    tu: datetime | None = None
    den: datetime | None = None


class PatientManagement(ApiModel):
    dot_dieu_tri_id: str
    khoa_dieu_tri: str | None = None
    thoi_diem_bat_dau: datetime | None = None
    thoi_diem_ket_thuc: datetime | None = None
    hinh_thuc_vao: str | None = None
    so_ngay_dieu_tri: int | None = None
    lich_su_khoa: list[DepartmentStay] = Field(default_factory=list)
    noi_gioi_thieu: Literal["co_quan_y_te", "tu_den", "khac"] | None = None
    tuyen_chuyen_den: str | None = None
    vao_khoa_luc: datetime | None = None
    so_giuong: str | None = None
    so_luu_tru: str | None = None
    ma_yt: str | None = None
    ra_vien: Discharge | None = None
    bac_si_dieu_tri: str | None = None


class EncounterOrder(ApiModel):
    y_lenh_id: str
    thoi_diem_ke: datetime | None = None
    trang_thai: str | None = None
    thuoc: list[str] = Field(default_factory=list)


class EncounterNote(ApiModel):
    thoi_diem_ghi: datetime | None = None
    loai_ho_so: str | None = None
    noi_dung: str


class EncounterHistory(PatientManagement):
    thu_tu: int | None = None
    chan_doan_chinh: str | None = None
    y_lenh: list[EncounterOrder] = Field(default_factory=list)
    phieu_dieu_tri: list[EncounterNote] = Field(default_factory=list)


class AdministrativeRecord(ApiModel):
    dinh_danh_day_du: FullIdentity
    lich_su_vao_vien: list[EncounterHistory]


class MedicalOrder(ApiModel):
    """Y lệnh để xem hồ sơ, không làm đầu vào AI."""

    y_lenh_id: str
    dot_dieu_tri_id: str
    thu_tu_dot: int | None = None
    thoi_diem_ke: datetime | None = None
    trang_thai: str | None = None
    loai: str | None = None
    vai_tro_nguoi_ke: str | None = None
    khoa_ke_don: str | None = None
    luong_duyet: str | None = None
    ly_do_ngung: str | None = None
    thoi_diem_ngung: datetime | None = None
    thay_the_y_lenh_id: str | None = None
    la_trong_tam: bool
    cot: list[str] = Field(default_factory=list)
    dong: list[dict[str, str]]


class TreatmentSheet(ApiModel):
    """Phiếu theo ngày, tham chiếu y lệnh trong cùng đợt."""

    phieu_dieu_tri_id: str
    dot_dieu_tri_id: str
    thu_tu_dot: int | None = None
    ngay_dieu_tri: int
    thoi_diem_lap: datetime
    vai_tro_nguoi_lap: str
    dien_bien: str
    danh_gia: str
    huong_xu_tri: str
    y_lenh_trong_ngay: list[str]
    che_do_cham_soc: str | None
    che_do_an: str
    theo_doi: list[str]
    dan_do: str | None


class MedicalRecord(ApiModel):
    danh_sach_y_lenh: list[MedicalOrder] = Field(default_factory=list)
    phieu_dieu_tri: list[TreatmentSheet] = Field(default_factory=list)


class ChiTietCa(ApiModel):
    ca_id: str
    ma_tran_tuong_tac: MaTranTuongTac | None = None
    dinh_danh: DinhDanhCa
    tom_tat: TomTat
    chi_so: list[ChiSo]
    nhan_dinh: Findings
    chi_tiet: CaseDetails
    cau_hoi_goi_y: list[str]
    nhom_ly_do: list[str]
    thoi_gian_ms: float
    che_do: CheDo
    dinh_danh_day_du: FullIdentity | None = None
    quan_ly_nguoi_benh: PatientManagement | None = None
    lich_su_vao_vien: list[EncounterHistory] = Field(default_factory=list)
    danh_sach_y_lenh: list[MedicalOrder] = Field(default_factory=list)
    phieu_dieu_tri: list[TreatmentSheet] = Field(default_factory=list)


class BanGhi(ApiModel):
    loai: str
    tieu_de: str
    dong: list[tuple[str, str]]


class GuiPhanHoi(ApiModel):
    nhan_dinh_id: str = Field(max_length=128)
    phan_hoi: PhanHoiMa
    nhom_ly_do: str | None = Field(default=None, max_length=64)
    ly_do: str | None = Field(default=None, max_length=1000)


class ChatMessage(ApiModel):
    vai: Literal["nguoi_dung", "he_thong"]
    noi_dung: str = Field(max_length=4000)


class GuiCauHoi(ApiModel):
    """Thân yêu cầu hỏi đáp; trường lich_su bị bỏ qua từ T91, máy chủ tự dựng lịch sử."""

    cau_hoi: str
    lich_su: list[ChatMessage] = Field(
        default_factory=list,
        max_length=6,
        deprecated=True,
        description="Bị bỏ qua từ T91, máy chủ tự dựng lịch sử.",
    )
    nhan_dinh_id: str | None = Field(default=None, max_length=128)

    @field_validator("cau_hoi")
    @classmethod
    def _validate_cau_hoi(cls, value: str) -> str:
        """Cắt khoảng trắng đầu cuối và kiểm tra độ dài 1–1000 ký tự."""
        cleaned = value.strip()
        if not 1 <= len(cleaned) <= 1000:
            raise ValueError("cau_hoi phải dài từ 1 đến 1000 ký tự")
        return cleaned


class Citation(ApiModel):
    so: int
    loai_ma: LoaiCanCuMa
    nhan: str
    ban_ghi_id: str | None = None
    doan_trich_id: str | None = None
    trich_nguyen_van: str | None = None


class TraLoi(ApiModel):
    trang_thai: Literal["chua_san_sang", "ok", "khong_co_nguon", "ngoai_pham_vi", "loi"]
    noi_dung: str
    trich_dan: list[Citation]
    cong_cu_da_goi: list[str]
    thoi_gian_ms: int = 0


class AiFindings(ApiModel):
    can_chu_y: list[NhanDinh]
    dat: list[NhanDinh]


class NguonTomTat(ApiModel):
    nhan: str
    so_doan: int


class BuocAI(ApiModel):
    ma: str
    ten: str
    trang_thai: Literal["cho", "dang_chay", "xong", "loi", "bo_qua"]
    chi_tiet: str | None = None
    nguon: list[NguonTomTat] = Field(default_factory=list)
    thoi_gian_ms: float | None = None
    ly_do: str | None = None
    goi_y: str | None = None


class TienTrinhHoiDap(ApiModel):
    dang_chay: bool
    cac_buoc: list[BuocAI] = Field(default_factory=list)
    da_chay_ms: float | None = None


class KetQuaAI(ApiModel):
    trang_thai: Literal["tat", "dang_chay", "xong", "loi"]
    nhan_dinh: AiFindings | None = None
    canh_bao: list[str]
    thoi_gian_ms: float | None = None
    mo_hinh: str | None = None
    cac_buoc: list[BuocAI] = Field(default_factory=list)
    da_chay_ms: float | None = None
    thuong_le_ms: float | None = None


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


class KetLuanCounts(ApiModel):
    dat: int
    can_xem: int
    khong_du_du_lieu: int
    ngoai_hdsd: int


class TomTatThamDinh(ApiModel):
    tong_nhan_dinh: int
    dem: FindingCounts
    theo_ket_luan: KetLuanCounts
    theo_yeu_to: dict[str, int]


class LanThamDinhLichSu(ApiModel):
    ket_qua_id: str
    ca_id: str
    thoi_diem: datetime
    thoi_diem_text: str
    phien_ban_luat: str
    so_luat_da_chay: int
    che_do: Literal["file", "db"]
    tom_tat: TomTatThamDinh


class LichSuThamDinh(ApiModel):
    ca_id: str
    lich_su: list[LanThamDinhLichSu]


class KetQuaThuoc(ApiModel):
    hoat_chat_id: str
    ten_inn: str
    ten_viet: str | None
    ma_atc: list[str]
    so_che_pham: int
    co_nhan_fda: bool
    so_quy_tac: int


class DanhSachThuoc(ApiModel):
    tong: int
    trang: int
    so_dong: int
    ket_qua: list[KetQuaThuoc]
    goi_y_sua: str | None = None


class GoiYThuoc(ApiModel):
    nhan: str
    loai: Literal["hoat_chat", "dong_nghia", "biet_duoc"]
    hoat_chat_ids: list[str]
    ten_hoat_chat: list[str]
    gia_tri_gui: str
    khop: Literal["chinh_xac", "tien_to", "gan_dung"]


class KetQuaGoiYThuoc(ApiModel):
    ket_qua: list[GoiYThuoc]
    goi_y_sua: str | None = None


class DinhDanhThuoc(ApiModel):
    hoat_chat_id: str
    ten_inn: str
    ten_viet: str | None
    rxcui: str | None
    ma_atc: list[str]
    ddinter_id: str | None
    loai: str
    nguon: str
    trang_thai: str | None


class ChePham(ApiModel):
    ten_thuoc: str
    so_dang_ky: str | None
    dang_bao_che: str | None
    ham_luong: float | None
    don_vi: str | None


class DanhSachChePham(ApiModel):
    nguon: str
    trang_thai: str | None
    tong: int
    danh_sach: list[ChePham]


class DoanNhanFda(ApiModel):
    doan_trich_id: str
    duong_dan_muc: str
    noi_dung_goc: str
    url_goc: str | None
    tai_lieu_id: str
    set_id: str | None
    nguon: str
    phien_ban_nguon: str | None
    tang_tin_cay: int


class NhomNhanFda(ApiModel):
    muc: str
    doan: list[DoanNhanFda]


class NhanFda(ApiModel):
    nguon: str
    trang_thai: str | None
    tong_doan: int
    nhom: list[NhomNhanFda]


class QuyTacDong(ApiModel):
    nhom: str
    bang_luat: str
    phan: str
    phien_ban: str | None
    trang_thai: str | None
    du_lieu: dict[str, Any]


class SoCapTuongTac(ApiModel):
    major: int
    moderate: int
    minor: int
    unknown: int


class CapMajor(ApiModel):
    ddinter_id: str
    ten_thuoc_khac: str
    co_che: list[str]


class TuongTacTomTat(ApiModel):
    nguon: str
    trang_thai: str | None
    ddinter_id: str | None
    co_du_lieu: bool
    so_cap: SoCapTuongTac
    major: list[CapMajor]
    ghi_chu: str


class ChiTietThuoc(ApiModel):
    dinh_danh: DinhDanhThuoc
    che_pham: DanhSachChePham
    nhan_fda: NhanFda
    quy_tac: list[QuyTacDong]
    tuong_tac_tom_tat: TuongTacTomTat


class TraTuongTacYeuCau(ApiModel):
    thuoc: list[str]


class PhanGiaiTen(ApiModel):
    ten_nhap: str
    chi_tiet_y_lenh_id: str
    trang_thai: Literal["da_phan_giai", "mot_phan", "khong_nhan_dien", "khong_ap_dung"]
    hoat_chat: list[str]
    ly_do: str | None


class CapChiTiet(ApiModel):
    a: str
    b: str
    muc: str
    mo_ta: str
    can_cu: list[str]
    thong_tin_con_thieu: list[str]


class KetQuaTraTuongTac(ApiModel):
    ma_tran: MaTranTuongTac
    phan_giai: list[PhanGiaiTen]
    chi_tiet: list[CapChiTiet]


class DauVaoCongThuc(ApiModel):
    ten: str
    nhan: str
    kieu: Literal["so", "lua_chon"]
    don_vi: list[str]
    lua_chon: list[str]
    nhan_lua_chon: dict[str, str] = Field(default_factory=dict)
    truong_don_vi: str | None
    bat_buoc: bool
    mac_dinh: str | float | None


class DauRaCongThuc(ApiModel):
    don_vi: list[str]
    phan_hang: list[str]


class CongThucMuc(ApiModel):
    ma: str
    ten: str
    loai: str
    dau_vao: list[DauVaoCongThuc]
    dau_ra: DauRaCongThuc
    tham_khao_goc: list[str]
    tham_chieu_mdcalc: str | None
    trang_thai: str


class DanhMucCongThuc(ApiModel):
    cong_thuc: list[CongThucMuc]


class TinhCongThucYeuCau(ApiModel):
    dau_vao: dict[str, Any]

    @field_validator("dau_vao")
    @classmethod
    def _validate_dau_vao(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Giới hạn tối đa 30 khoá, tên khoá <= 64 và chuỗi giá trị <= 200 ký tự."""
        if len(value) > 30:
            raise ValueError("dau_vao tối đa 30 khoá")
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > 64:
                raise ValueError("Tên khoá trong dau_vao tối đa 64 ký tự")
            if isinstance(item, str) and len(item) > 200:
                raise ValueError("Giá trị chuỗi trong dau_vao tối đa 200 ký tự")
        return value


class DauVaoDaDung(ApiModel):
    ten: str
    gia_tri: float
    don_vi: str


class KetQuaCongThuc(ApiModel):
    ma: str
    cong_thuc: str
    phien_ban: str
    ket_qua: float | None
    don_vi: str
    dau_vao_da_dung: list[DauVaoDaDung]
    thieu_dau_vao: list[str]
    ghi_chu: list[str]
    tham_khao: str
    trang_thai: str
