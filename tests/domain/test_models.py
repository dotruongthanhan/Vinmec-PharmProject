"""Kiểm thử mô hình dữ liệu và các ràng buộc validation của ca bệnh."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.domain.models import (
    CaBenh,
    ChanDoan,
    ChiTietYLenh,
    DapAn,
    DienBien,
    DiUng,
    DotDieuTri,
    HoatChat,
    KetQuaXetNghiem,
    KhangSinhDo,
    NguoiBenh,
    PhatHienKyVong,
    SinhHieu,
    ThanhPhan,
    Thuoc,
    TinhTrangDiUng,
    ViSinh,
    YLenh,
)

TZ_VN = timezone(timedelta(hours=7))
NOW = datetime(2026, 11, 10, 8, 0, tzinfo=TZ_VN)


def _make_base_case_dict() -> dict:
    """Tạo từ điển dữ liệu ca bệnh hợp lệ tối thiểu để biến tấu trong kiểm thử."""
    ts = "2026-11-10T08:00:00+07:00"
    return {
        "ca_id": "TEST-01",
        "mo_ta_ngan": "Ca kiểm thử chuẩn",
        "nguoi_benh": {
            "nguoi_benh_id": "NB-TEST-01",
            "tuoi": 45,
            "gioi_tinh": "nam",
        },
        "tinh_trang_di_ung": {
            "trang_thai": "khong_di_ung_da_hoi",
            "nguon": "EMR",
            "thoi_diem": ts,
        },
        "di_ung": [],
        "dot_dieu_tri": {
            "dot_dieu_tri_id": "DT-TEST-01",
            "khoa_dieu_tri": "Nội tổng hợp",
            "loai_dieu_tri": "noi_tru",
            "thoi_diem_bat_dau": ts,
        },
        "chan_doan": [
            {
                "chan_doan_id": "CD-01",
                "ma_icd10": "I10",
                "noi_dung": "Tăng huyết áp",
                "loai": "chinh",
            },
        ],
        "co_dia": [],
        "sinh_hieu": [
            {
                "sinh_hieu_id": "SH-01",
                "loai": "can_nang",
                "gia_tri": 65.0,
                "don_vi": "kg",
                "thoi_diem_do": ts,
            },
        ],
        "xet_nghiem": [
            {
                "xet_nghiem_id": "XN-01",
                "ma_xet_nghiem": "creatinin",
                "ten_xet_nghiem": "Creatinin máu",
                "gia_tri_so": 80.0,
                "don_vi": "umol/L",
                "thoi_diem_ket_qua": ts,
            },
        ],
        "vi_sinh": [],
        "dien_bien": [
            {
                "dien_bien_id": "DB-01",
                "loai_ho_so": "Phiếu điều trị",
                "noi_dung": "",
                "thoi_diem_ghi": ts,
            },
        ],
        "thuoc_dang_dung": [],
        "y_lenh_cho_duyet": {
            "y_lenh_id": "YL-01",
            "khoa_ke_don": "Nội tổng hợp",
            "luong_duyet": "truc_tiep",
            "thoi_diem_ke": ts,
            "chi_tiet": [
                {
                    "chi_tiet_y_lenh_id": "CT-01",
                    "thuoc_id": "T-01",
                    "loai_san_pham": "thuoc",
                    "lieu_moi_lan": 5.0,
                    "don_vi_lieu": "mg",
                    "bat_dau": ts,
                    "trang_thai_dong": "active",
                    "lich_dung": [],
                },
            ],
        },
        "danh_muc_thuoc": [
            {
                "thuoc_id": "T-01",
                "ten_thuoc": "Amlodipin 5 mg",
                "thanh_phan": [
                    {
                        "hoat_chat_id": "HC-01",
                        "ham_luong_thanh_phan": 5.0,
                        "don_vi": "mg",
                    },
                ],
            },
        ],
        "danh_muc_hoat_chat": [
            {
                "hoat_chat_id": "HC-01",
                "ten_hoat_chat": "Amlodipin",
                "nhom_duoc_ly": "chen_kenh_canxi_dhp",
            },
        ],
    }


def test_valid_case_and_empty_note_allowed() -> None:
    """Ca bệnh hợp lệ và diễn biến có nội dung rỗng đều được chấp nhận."""
    ca = CaBenh.model_validate(_make_base_case_dict())
    assert ca.ca_id == "TEST-01"
    assert ca.dien_bien[0].noi_dung == ""
    assert ca.y_lenh_cho_duyet.chi_tiet[0].loai_san_pham == "thuoc"


def test_extra_field_in_json_raises_validation_error() -> None:
    """Ràng buộc extra='forbid': trường lạ trong JSON gây ValidationError."""
    data = _make_base_case_dict()
    data["truong_la"] = "khong_hop_le"
    with pytest.raises(ValidationError):
        CaBenh.model_validate_json(json.dumps(data))

    nested_data = _make_base_case_dict()
    nested_data["nguoi_benh"]["ho_ten"] = "An danh"
    with pytest.raises(ValidationError):
        CaBenh.model_validate_json(json.dumps(nested_data))

    with pytest.raises(ValidationError):
        DapAn.model_validate_json('{"ca_id": "DEMO-01", "extra": 1}')


def test_naive_datetime_raises_validation_error() -> None:
    """Ràng buộc AwareDatetime: datetime không có múi giờ gây ValidationError."""
    data = _make_base_case_dict()
    data["dot_dieu_tri"]["thoi_diem_bat_dau"] = "2026-11-10T08:00:00"
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data)

    with pytest.raises(ValidationError):
        DotDieuTri(
            dot_dieu_tri_id="DT-NAIVE",
            khoa_dieu_tri="Tim mạch",
            loai_dieu_tri="noi_tru",
            thoi_diem_bat_dau=datetime(2026, 11, 10, 8, 0),
        )


def test_constraint_1_chi_tiet_y_lenh_requires_thuoc_id_or_ten_tu_do() -> None:
    """Ràng buộc 1: ChiTietYLenh thiếu cả thuoc_id và ten_tu_do gây ValidationError."""
    with pytest.raises(ValidationError):
        ChiTietYLenh(
            chi_tiet_y_lenh_id="CT-EMPTY",
            bat_dau=NOW,
            trang_thai_dong="active",
        )

    valid_free_text = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-FREE",
        ten_tu_do="Sữa dinh dưỡng Fresubin",
        loai_san_pham="dinh_duong",
        bat_dau=NOW,
        trang_thai_dong="active",
    )
    assert valid_free_text.thuoc_id is None


def test_constraint_2_ket_qua_xet_nghiem_requires_numeric_or_text() -> None:
    """Ràng buộc 2: KetQuaXetNghiem thiếu cả gia_tri_so và gia_tri_text gây ValidationError."""
    with pytest.raises(ValidationError):
        KetQuaXetNghiem(
            xet_nghiem_id="XN-EMPTY",
            ma_xet_nghiem="creatinin",
            ten_xet_nghiem="Creatinin máu",
            thoi_diem_ket_qua=NOW,
        )

    zero_lab = KetQuaXetNghiem(
        xet_nghiem_id="XN-ZERO",
        ma_xet_nghiem="procalcitonin",
        ten_xet_nghiem="Procalcitonin",
        gia_tri_so=0.0,
        thoi_diem_ket_qua=NOW,
    )
    assert zero_lab.gia_tri_so == 0.0

    text_lab = KetQuaXetNghiem(
        xet_nghiem_id="XN-TEXT",
        ma_xet_nghiem="hbsag",
        ten_xet_nghiem="HBsAg",
        gia_tri_text="Âm tính",
        thoi_diem_ket_qua=NOW,
    )
    assert text_lab.gia_tri_text == "Âm tính"


def test_constraint_3_thuoc_id_must_exist_in_danh_muc_thuoc() -> None:
    """Ràng buộc 3: thuoc_id trong y lệnh hoặc thuốc đang dùng phải có trong danh_muc_thuoc."""
    data = _make_base_case_dict()
    data["y_lenh_cho_duyet"]["chi_tiet"][0]["thuoc_id"] = "T-KHONG-TON-TAI"
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data)

    data_current = _make_base_case_dict()
    data_current["thuoc_dang_dung"] = [
        {
            "chi_tiet_y_lenh_id": "CT-DANG-DUNG",
            "thuoc_id": "T-KHONG-TON-TAI",
            "bat_dau": "2026-11-09T08:00:00+07:00",
            "trang_thai_dong": "active",
        },
    ]
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_current)


def test_constraint_4_hoat_chat_id_must_exist_in_danh_muc_hoat_chat() -> None:
    """Ràng buộc 4: mọi hoat_chat_id trong Thuoc, DiUng, KhangSinhDo phải có trong danh mục."""
    data_thuoc = _make_base_case_dict()
    data_thuoc["danh_muc_thuoc"][0]["thanh_phan"][0]["hoat_chat_id"] = "HC-LA"
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_thuoc)

    data_di_ung = _make_base_case_dict()
    data_di_ung["tinh_trang_di_ung"]["trang_thai"] = "co_di_ung"
    data_di_ung["di_ung"] = [
        {
            "di_ung_id": "DU-01",
            "tac_nhan": "Penicillin",
            "loai_tac_nhan": "thuoc",
            "hoat_chat_id": "HC-LA",
        },
    ]
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_di_ung)

    data_vi_sinh = _make_base_case_dict()
    data_vi_sinh["vi_sinh"] = [
        {
            "vi_sinh_id": "VS-01",
            "benh_pham": "nước tiểu",
            "vi_khuan": "E. coli",
            "thoi_diem_lay_mau": "2026-11-10T07:00:00+07:00",
            "khang_sinh_do": [
                {"hoat_chat_id": "HC-LA", "ket_qua": "S"},
            ],
        },
    ]
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_vi_sinh)


def test_constraint_5_no_duplicate_ids_within_case() -> None:
    """Ràng buộc 5: không trùng chi_tiet_y_lenh_id, xet_nghiem_id, sinh_hieu_id."""
    data_ct = _make_base_case_dict()
    data_ct["thuoc_dang_dung"] = [
        {
            "chi_tiet_y_lenh_id": "CT-01",
            "ten_tu_do": "Sản phẩm trùng mã",
            "bat_dau": "2026-11-09T08:00:00+07:00",
            "trang_thai_dong": "active",
        },
    ]
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_ct)

    data_xn = _make_base_case_dict()
    data_xn["xet_nghiem"].append(dict(data_xn["xet_nghiem"][0]))
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_xn)

    data_sh = _make_base_case_dict()
    data_sh["sinh_hieu"].append(dict(data_sh["sinh_hieu"][0]))
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_sh)


def test_constraint_6_allergy_status_matches_allergy_list() -> None:
    """Ràng buộc 6: trạng thái dị ứng phải khớp với danh sách di_ung rỗng hay có phần tử."""
    data_no_allergy = _make_base_case_dict()
    data_no_allergy["tinh_trang_di_ung"]["trang_thai"] = "khong_di_ung_da_hoi"
    data_no_allergy["di_ung"] = [
        {
            "di_ung_id": "DU-01",
            "tac_nhan": "Tôm",
            "loai_tac_nhan": "thuc_an",
        },
    ]
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_no_allergy)

    data_unknown = _make_base_case_dict()
    data_unknown["tinh_trang_di_ung"]["trang_thai"] = "chua_co_thong_tin"
    data_unknown["di_ung"] = data_no_allergy["di_ung"]
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_unknown)

    data_has_allergy = _make_base_case_dict()
    data_has_allergy["tinh_trang_di_ung"]["trang_thai"] = "co_di_ung"
    data_has_allergy["di_ung"] = []
    with pytest.raises(ValidationError):
        CaBenh.model_validate(data_has_allergy)


def test_field_bounds_and_non_empty_lists() -> None:
    """Kiểm tra giới hạn tuổi, yếu tố, danh sách bắt buộc ít nhất 1 phần tử và DapAn."""
    with pytest.raises(ValidationError):
        NguoiBenh(nguoi_benh_id="NB-1", tuoi=-1)
    with pytest.raises(ValidationError):
        NguoiBenh(nguoi_benh_id="NB-2", tuoi=121)

    with pytest.raises(ValidationError):
        Thuoc(thuoc_id="T-EMPTY", ten_thuoc="Thuốc rỗng", thanh_phan=[])

    with pytest.raises(ValidationError):
        YLenh(
            y_lenh_id="YL-EMPTY",
            khoa_ke_don="Tim mạch",
            luong_duyet="truc_tiep",
            thoi_diem_ke=NOW,
            chi_tiet=[],
        )

    with pytest.raises(ValidationError):
        PhatHienKyVong(yeu_to=0, ket_luan="dat", mo_ta="Sai yếu tố")
    with pytest.raises(ValidationError):
        PhatHienKyVong(yeu_to=8, ket_luan="dat", mo_ta="Sai yếu tố")

    answer = DapAn(
        ca_id="DEMO-01",
        phat_hien_ky_vong=[
            PhatHienKyVong(yeu_to=1, ket_luan="dat", muc_do=None, mo_ta="Hợp lệ"),
        ],
    )
    assert answer.van_ban_bat_thuong is False
    assert isinstance(
        ChanDoan(chan_doan_id="CD-1", noi_dung="Viêm phổi", loai="chinh"),
        ChanDoan,
    )
    assert isinstance(
        DiUng(di_ung_id="DU-1", tac_nhan="Đậu phộng", loai_tac_nhan="thuc_an"),
        DiUng,
    )
    assert isinstance(
        SinhHieu(
            sinh_hieu_id="SH-1",
            loai="can_nang",
            gia_tri=60.0,
            don_vi="kg",
            thoi_diem_do=NOW,
        ),
        SinhHieu,
    )
    assert isinstance(
        DienBien(
            dien_bien_id="DB-1",
            loai_ho_so="Phiếu khám",
            noi_dung="Ổn",
            thoi_diem_ghi=NOW,
        ),
        DienBien,
    )
    assert isinstance(HoatChat(hoat_chat_id="HC-1", ten_hoat_chat="Amlodipin"), HoatChat)
    assert isinstance(ThanhPhan(hoat_chat_id="HC-1"), ThanhPhan)
    assert isinstance(
        TinhTrangDiUng(trang_thai="chua_co_thong_tin"),
        TinhTrangDiUng,
    )
    assert isinstance(
        ViSinh(vi_sinh_id="VS-1", benh_pham="máu", thoi_diem_lay_mau=NOW),
        ViSinh,
    )
    assert isinstance(KhangSinhDo(hoat_chat_id="HC-1", ket_qua="S"), KhangSinhDo)
