"""Hàm trợ giúp tạo ca bệnh tối thiểu dùng chung cho bộ kiểm thử app/rules."""

from datetime import datetime, timedelta, timezone
from typing import Literal

from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    DiUng,
    DotDieuTri,
    HoatChat,
    KetQuaXetNghiem,
    NguoiBenh,
    SinhHieu,
    ThanhPhan,
    Thuoc,
    TinhTrangDiUng,
    ViSinh,
    YLenh,
)

TZ_VN = timezone(timedelta(hours=7))
NOW = datetime(2026, 11, 10, 8, 0, tzinfo=TZ_VN)

AllergyStatus = Literal["co_di_ung", "khong_di_ung_da_hoi", "chua_co_thong_tin"]


def make_minimal_case(
    *,
    ca_id: str = "TEST-RULE-01",
    tuoi: int | None = 50,
    gioi_tinh: Literal["nam", "nu"] | None = "nam",
    trang_thai_di_ung: AllergyStatus = "khong_di_ung_da_hoi",
    di_ung: list[DiUng] | None = None,
    sinh_hieu: list[SinhHieu] | None = None,
    xet_nghiem: list[KetQuaXetNghiem] | None = None,
    vi_sinh: list[ViSinh] | None = None,
    thuoc_dang_dung: list[ChiTietYLenh] | None = None,
    chi_tiet: list[ChiTietYLenh] | None = None,
    danh_muc_thuoc: list[Thuoc] | None = None,
    danh_muc_hoat_chat: list[HoatChat] | None = None,
) -> CaBenh:
    """Tạo một CaBenh hợp lệ tối thiểu để kiểm thử từng luật độc lập."""
    if danh_muc_hoat_chat is None:
        danh_muc_hoat_chat = [
            HoatChat(
                hoat_chat_id="HC-DEFAULT",
                ten_hoat_chat="Paracetamol",
                ten_quoc_te="paracetamol",
                nhom_duoc_ly="giam_dau",
            ),
        ]
    if danh_muc_thuoc is None:
        danh_muc_thuoc = [
            Thuoc(
                thuoc_id="T-DEFAULT",
                ten_thuoc="Paracetamol 500 mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-DEFAULT")],
            ),
        ]
    if chi_tiet is None:
        chi_tiet = [
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-DEFAULT",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ]
    if sinh_hieu is None:
        sinh_hieu = [
            SinhHieu(
                sinh_hieu_id="SH-WT",
                loai="can_nang",
                gia_tri=60.0,
                don_vi="kg",
                thoi_diem_do=NOW,
            ),
        ]
    if xet_nghiem is None:
        xet_nghiem = [
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=80.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            ),
        ]
    return CaBenh(
        ca_id=ca_id,
        mo_ta_ngan=f"Ca kiểm thử {ca_id}",
        nguoi_benh=NguoiBenh(nguoi_benh_id=f"NB-{ca_id}", tuoi=tuoi, gioi_tinh=gioi_tinh),
        tinh_trang_di_ung=TinhTrangDiUng(
            trang_thai=trang_thai_di_ung,
            nguon="EMR" if trang_thai_di_ung != "chua_co_thong_tin" else None,
            thoi_diem=NOW if trang_thai_di_ung != "chua_co_thong_tin" else None,
        ),
        di_ung=di_ung if di_ung is not None else [],
        dot_dieu_tri=DotDieuTri(
            dot_dieu_tri_id=f"DT-{ca_id}",
            khoa_dieu_tri="Nội",
            loai_dieu_tri="noi_tru",
            thoi_diem_bat_dau=NOW,
        ),
        sinh_hieu=sinh_hieu,
        xet_nghiem=xet_nghiem,
        vi_sinh=vi_sinh if vi_sinh is not None else [],
        thuoc_dang_dung=thuoc_dang_dung if thuoc_dang_dung is not None else [],
        y_lenh_cho_duyet=YLenh(
            y_lenh_id=f"YL-{ca_id}",
            khoa_ke_don="Nội",
            luong_duyet="truc_tiep",
            thoi_diem_ke=NOW,
            chi_tiet=chi_tiet,
        ),
        danh_muc_thuoc=danh_muc_thuoc,
        danh_muc_hoat_chat=danh_muc_hoat_chat,
    )


__all__ = ["AllergyStatus", "NOW", "TZ_VN", "make_minimal_case"]
