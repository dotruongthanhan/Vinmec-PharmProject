"""Mô hình dữ liệu ca bệnh và đáp án thẩm định y lệnh bằng pydantic v2."""

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


def _ensure_unique_ids(ids: list[str], field_name: str) -> None:
    """Kiểm tra danh sách mã định danh không bị trùng lặp."""
    seen: set[str] = set()
    for item_id in ids:
        if item_id in seen:
            raise ValueError(f"Trùng lặp {field_name}: '{item_id}'")
        seen.add(item_id)


class NguoiBenh(BaseModel):
    """Thông tin nhân khẩu học đã tách định danh của người bệnh."""

    model_config = ConfigDict(extra="forbid")

    nguoi_benh_id: str
    tuoi: int | None = Field(default=None, ge=0, le=120)
    gioi_tinh: Literal["nam", "nu"] | None = None


class TinhTrangDiUng(BaseModel):
    """Trạng thái khai thác dị ứng cấp người bệnh."""

    model_config = ConfigDict(extra="forbid")

    trang_thai: Literal["co_di_ung", "khong_di_ung_da_hoi", "chua_co_thong_tin"]
    nguon: str | None = None
    thoi_diem: AwareDatetime | None = None


class DiUng(BaseModel):
    """Bản ghi dị ứng cụ thể của người bệnh."""

    model_config = ConfigDict(extra="forbid")

    di_ung_id: str
    tac_nhan: str
    loai_tac_nhan: Literal["thuoc", "thuc_an", "khac"]
    hoat_chat_id: str | None = None
    nhom_duoc_ly: str | None = None
    phan_ung: str | None = None
    muc_do: str | None = None


class DotDieuTri(BaseModel):
    """Thông tin đợt điều trị hiện tại."""

    model_config = ConfigDict(extra="forbid")

    dot_dieu_tri_id: str
    khoa_dieu_tri: str
    loai_dieu_tri: Literal["noi_tru", "ngoai_tru"]
    thoi_diem_bat_dau: AwareDatetime


class ChanDoan(BaseModel):
    """Chẩn đoán bệnh chính hoặc bệnh kèm."""

    model_config = ConfigDict(extra="forbid")

    chan_doan_id: str
    ma_icd10: str | None = None
    noi_dung: str
    loai: Literal["chinh", "kem"]


class CoDia(BaseModel):
    """Tình trạng cơ địa đặc biệt ảnh hưởng dùng thuốc."""

    model_config = ConfigDict(extra="forbid")

    loai: Literal["mang_thai", "cho_con_bu", "suy_than", "suy_gan", "hau_phau", "khac"]
    trang_thai: Literal["co", "khong", "chua_ro"]
    gia_tri: str | None = None
    thoi_diem: AwareDatetime | None = None
    nguon: str | None = None


class SinhHieu(BaseModel):
    """Chỉ số sinh hiệu hoặc nhân trắc đo được."""

    model_config = ConfigDict(extra="forbid")

    sinh_hieu_id: str
    loai: str
    gia_tri: float
    don_vi: str
    thoi_diem_do: AwareDatetime


class KetQuaXetNghiem(BaseModel):
    """Kết quả xét nghiệm cận lâm sàng."""

    model_config = ConfigDict(extra="forbid")

    xet_nghiem_id: str
    ma_xet_nghiem: str
    ten_xet_nghiem: str
    gia_tri_so: float | None = None
    gia_tri_text: str | None = None
    don_vi: str | None = None
    nguong_duoi: float | None = None
    nguong_tren: float | None = None
    thoi_diem_ket_qua: AwareDatetime

    @model_validator(mode="after")
    def _check_result_value(self) -> Self:
        """Bảo đảm kết quả có ít nhất giá trị số hoặc giá trị chữ."""
        has_so = self.gia_tri_so is not None
        has_text = self.gia_tri_text is not None and self.gia_tri_text.strip() != ""
        if not has_so and not has_text:
            raise ValueError("KetQuaXetNghiem phải có ít nhất gia_tri_so hoặc gia_tri_text")
        return self


class KhangSinhDo(BaseModel):
    """Kết quả kháng sinh đồ cho một hoạt chất."""

    model_config = ConfigDict(extra="forbid")

    hoat_chat_id: str
    ket_qua: Literal["S", "I", "R"]
    mic: float | None = None


class ViSinh(BaseModel):
    """Kết quả nuôi cấy vi sinh và kháng sinh đồ."""

    model_config = ConfigDict(extra="forbid")

    vi_sinh_id: str
    benh_pham: str
    vi_khuan: str | None = None
    thoi_diem_lay_mau: AwareDatetime
    khang_sinh_do: list[KhangSinhDo] = Field(default_factory=list)


class DienBien(BaseModel):
    """Ghi chép diễn biến lâm sàng hoặc phiếu khám."""

    model_config = ConfigDict(extra="forbid")

    dien_bien_id: str
    loai_ho_so: str
    noi_dung: str
    thoi_diem_ghi: AwareDatetime


class HoatChat(BaseModel):
    """Danh mục hoạt chất chuẩn hoá."""

    model_config = ConfigDict(extra="forbid")

    hoat_chat_id: str
    ten_hoat_chat: str
    ten_quoc_te: str | None = None
    ma_atc: str | None = None
    nhom_duoc_ly: str | None = None


class ThanhPhan(BaseModel):
    """Thành phần hoạt chất trong một chế phẩm thuốc."""

    model_config = ConfigDict(extra="forbid")

    hoat_chat_id: str
    ham_luong_thanh_phan: float | None = None
    don_vi: str | None = None


class Thuoc(BaseModel):
    """Danh mục thuốc thương mại hoặc chế phẩm."""

    model_config = ConfigDict(extra="forbid")

    thuoc_id: str
    ten_thuoc: str
    ham_luong: str | None = None
    duong_dung: str | None = None
    thanh_phan: list[ThanhPhan] = Field(min_length=1)
    la_thuoc_nguy_co_cao: bool = False
    la_khang_sinh: bool = False


class LichDung(BaseModel):
    """Mốc thời gian dùng thuốc dự kiến."""

    model_config = ConfigDict(extra="forbid")

    thoi_diem_du_kien: AwareDatetime
    lieu: float
    don_vi: str


class ChiTietYLenh(BaseModel):
    """Một dòng thuốc hoặc sản phẩm trong y lệnh."""

    model_config = ConfigDict(extra="forbid")

    chi_tiet_y_lenh_id: str
    thuoc_id: str | None = None
    ten_tu_do: str | None = None
    loai_san_pham: Literal["thuoc", "tpcn", "dinh_duong", "khac"] = "thuoc"
    lieu_moi_lan: float | None = None
    don_vi_lieu: str | None = None
    tan_suat: str | None = None
    so_lan_moi_ngay: int | None = None
    khoang_cach_gio: float | None = None
    duong_dung: str | None = None
    cach_dung: str | None = None
    bat_dau: AwareDatetime
    ket_thuc: AwareDatetime | None = None
    nguon_thuoc: str | None = None
    trang_thai_dong: Literal["active", "pending", "discontinued", "completed"]
    lich_dung: list[LichDung] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_drug_reference(self) -> Self:
        """Bảo đảm dòng y lệnh có ít nhất thuoc_id hoặc ten_tu_do."""
        has_thuoc_id = self.thuoc_id is not None and self.thuoc_id.strip() != ""
        has_ten_tu_do = self.ten_tu_do is not None and self.ten_tu_do.strip() != ""
        if not has_thuoc_id and not has_ten_tu_do:
            raise ValueError("ChiTietYLenh phải có ít nhất thuoc_id hoặc ten_tu_do")
        return self


class YLenh(BaseModel):
    """Y lệnh chờ dược sĩ thẩm định."""

    model_config = ConfigDict(extra="forbid")

    y_lenh_id: str
    khoa_ke_don: str
    luong_duyet: Literal["truc_tiep", "hau_kiem"]
    muc_uu_tien: str | None = None
    thoi_diem_ke: AwareDatetime
    chi_tiet: list[ChiTietYLenh] = Field(min_length=1)


class CaBenh(BaseModel):
    """Toàn bộ bối cảnh một ca bệnh phục vụ thẩm định y lệnh."""

    model_config = ConfigDict(extra="forbid")

    ca_id: str
    mo_ta_ngan: str
    nguoi_benh: NguoiBenh
    tinh_trang_di_ung: TinhTrangDiUng
    di_ung: list[DiUng] = Field(default_factory=list)
    dot_dieu_tri: DotDieuTri
    chan_doan: list[ChanDoan] = Field(default_factory=list)
    co_dia: list[CoDia] = Field(default_factory=list)
    sinh_hieu: list[SinhHieu] = Field(default_factory=list)
    xet_nghiem: list[KetQuaXetNghiem] = Field(default_factory=list)
    vi_sinh: list[ViSinh] = Field(default_factory=list)
    dien_bien: list[DienBien] = Field(default_factory=list)
    thuoc_dang_dung: list[ChiTietYLenh] = Field(default_factory=list)
    y_lenh_cho_duyet: YLenh
    danh_muc_thuoc: list[Thuoc] = Field(default_factory=list)
    danh_muc_hoat_chat: list[HoatChat] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_case_integrity(self) -> Self:
        """Kiểm tra toàn vẹn tham chiếu, trùng lặp mã và trạng thái dị ứng."""
        all_lines = [*self.y_lenh_cho_duyet.chi_tiet, *self.thuoc_dang_dung]
        self._check_drug_catalog_refs(all_lines)
        self._check_ingredient_catalog_refs()
        _ensure_unique_ids(
            [line.chi_tiet_y_lenh_id for line in all_lines],
            "chi_tiet_y_lenh_id",
        )
        _ensure_unique_ids(
            [lab.xet_nghiem_id for lab in self.xet_nghiem],
            "xet_nghiem_id",
        )
        _ensure_unique_ids(
            [vital.sinh_hieu_id for vital in self.sinh_hieu],
            "sinh_hieu_id",
        )
        self._check_allergy_consistency()
        return self

    def _check_drug_catalog_refs(self, all_lines: list[ChiTietYLenh]) -> None:
        """Kiểm tra mọi thuoc_id đều có trong danh_muc_thuoc."""
        thuoc_ids = {thuoc.thuoc_id for thuoc in self.danh_muc_thuoc}
        for line in all_lines:
            if line.thuoc_id is not None and line.thuoc_id not in thuoc_ids:
                raise ValueError(f"Thiếu thuoc_id '{line.thuoc_id}' trong danh_muc_thuoc")

    def _check_ingredient_catalog_refs(self) -> None:
        """Kiểm tra mọi hoat_chat_id đều có trong danh_muc_hoat_chat."""
        hoat_chat_ids = {hc.hoat_chat_id for hc in self.danh_muc_hoat_chat}
        for thuoc in self.danh_muc_thuoc:
            for tp in thuoc.thanh_phan:
                if tp.hoat_chat_id not in hoat_chat_ids:
                    raise ValueError(
                        f"Thiếu hoat_chat_id '{tp.hoat_chat_id}' trong danh_muc_hoat_chat"
                    )
        for du in self.di_ung:
            if du.hoat_chat_id is not None and du.hoat_chat_id not in hoat_chat_ids:
                raise ValueError(f"Thiếu hoat_chat_id '{du.hoat_chat_id}' trong danh_muc_hoat_chat")
        for vs in self.vi_sinh:
            for ksd in vs.khang_sinh_do:
                if ksd.hoat_chat_id not in hoat_chat_ids:
                    raise ValueError(
                        f"Thiếu hoat_chat_id '{ksd.hoat_chat_id}' trong danh_muc_hoat_chat"
                    )

    def _check_allergy_consistency(self) -> None:
        """Kiểm tra tính nhất quán giữa trạng thái dị ứng và danh sách di_ung."""
        if self.tinh_trang_di_ung.trang_thai == "co_di_ung":
            if not self.di_ung:
                raise ValueError("trang_thai là 'co_di_ung' nhưng di_ung đang rỗng")
        elif self.di_ung:
            raise ValueError(
                f"trang_thai là '{self.tinh_trang_di_ung.trang_thai}' nhưng di_ung không rỗng"
            )


class PhatHienKyVong(BaseModel):
    """Một phát hiện kỳ vọng trong bộ đáp án chuẩn."""

    model_config = ConfigDict(extra="forbid")

    yeu_to: int = Field(ge=1, le=7)
    ket_luan: Literal["dat", "can_xem", "khong_du_du_lieu", "ngoai_hdsd"]
    muc_do: Literal["nghiem_trong", "can_luu_y", "thong_tin"] | None = None
    chi_tiet_y_lenh_id: list[str] = Field(default_factory=list)
    mo_ta: str


class DapAn(BaseModel):
    """Đáp án chuẩn của một ca bệnh kiểm thử."""

    model_config = ConfigDict(extra="forbid")

    ca_id: str
    phat_hien_ky_vong: list[PhatHienKyVong] = Field(default_factory=list)
    van_ban_bat_thuong: bool = False
    ghi_chu: str | None = None
