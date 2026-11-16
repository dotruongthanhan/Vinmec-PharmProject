"""Kiểm thử bộ nạp JSON và các hàm truy xuất bối cảnh trong app.domain.loader."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.domain.loader import (
    ingredients_of,
    latest_lab,
    latest_vital,
    load_all_cases,
    load_answer,
    load_case,
)
from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    DapAn,
    DotDieuTri,
    HoatChat,
    KetQuaXetNghiem,
    NguoiBenh,
    SinhHieu,
    ThanhPhan,
    Thuoc,
    TinhTrangDiUng,
    YLenh,
)

TZ_VN = timezone(timedelta(hours=7))


def _sample_case(ca_id: str) -> CaBenh:
    """Tạo một CaBenh mẫu phục vụ kiểm thử bộ nạp và các hàm truy xuất."""
    t_old = datetime(2026, 11, 7, 8, 0, tzinfo=TZ_VN)
    t_mid = datetime(2026, 11, 9, 8, 0, tzinfo=TZ_VN)
    t_new = datetime(2026, 11, 10, 8, 0, tzinfo=TZ_VN)
    return CaBenh(
        ca_id=ca_id,
        mo_ta_ngan=f"Ca mẫu {ca_id}",
        nguoi_benh=NguoiBenh(nguoi_benh_id=f"NB-{ca_id}", tuoi=50, gioi_tinh="nam"),
        tinh_trang_di_ung=TinhTrangDiUng(trang_thai="khong_di_ung_da_hoi"),
        dot_dieu_tri=DotDieuTri(
            dot_dieu_tri_id=f"DT-{ca_id}",
            khoa_dieu_tri="Nội",
            loai_dieu_tri="noi_tru",
            thoi_diem_bat_dau=t_old,
        ),
        sinh_hieu=[
            SinhHieu(
                sinh_hieu_id="SH-NEW",
                loai="can_nang",
                gia_tri=68.5,
                don_vi="kg",
                thoi_diem_do=t_new,
            ),
            SinhHieu(
                sinh_hieu_id="SH-OLD",
                loai="can_nang",
                gia_tri=70.0,
                don_vi="kg",
                thoi_diem_do=t_old,
            ),
        ],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-NEW",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=110.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=t_new,
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-MID",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=95.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=t_mid,
            ),
        ],
        y_lenh_cho_duyet=YLenh(
            y_lenh_id=f"YL-{ca_id}",
            khoa_ke_don="Nội",
            luong_duyet="truc_tiep",
            thoi_diem_ke=t_new,
            chi_tiet=[
                ChiTietYLenh(
                    chi_tiet_y_lenh_id="CT-COMBO",
                    thuoc_id="T-COMBO",
                    bat_dau=t_new,
                    trang_thai_dong="active",
                ),
                ChiTietYLenh(
                    chi_tiet_y_lenh_id="CT-FREETEXT",
                    ten_tu_do="Thực phẩm bổ sung",
                    loai_san_pham="tpcn",
                    bat_dau=t_new,
                    trang_thai_dong="active",
                ),
            ],
        ),
        danh_muc_thuoc=[
            Thuoc(
                thuoc_id="T-COMBO",
                ten_thuoc="Amoxicillin + acid clavulanic",
                thanh_phan=[
                    ThanhPhan(hoat_chat_id="HC-AMOX"),
                    ThanhPhan(hoat_chat_id="HC-CLAV"),
                ],
                la_khang_sinh=True,
            ),
        ],
        danh_muc_hoat_chat=[
            HoatChat(
                hoat_chat_id="HC-AMOX",
                ten_hoat_chat="Amoxicillin",
                nhom_duoc_ly="penicillin",
            ),
            HoatChat(
                hoat_chat_id="HC-CLAV",
                ten_hoat_chat="Acid clavulanic",
                nhom_duoc_ly="uc_che_beta_lactamase",
            ),
        ],
    )


def test_load_case_and_load_all_cases_sorted_by_ca_id(tmp_path: Path) -> None:
    """load_all_cases nạp mọi *.json theo UTF-8 và sắp xếp theo ca_id."""
    case_b = _sample_case("CA-02")
    case_a = _sample_case("CA-01")
    (tmp_path / "z_file.json").write_text(case_a.model_dump_json(), encoding="utf-8")
    (tmp_path / "a_file.json").write_text(case_b.model_dump_json(), encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("not json", encoding="utf-8")

    loaded_single = load_case(tmp_path / "z_file.json")
    assert loaded_single.ca_id == "CA-01"

    loaded_all = load_all_cases(tmp_path)
    assert [ca.ca_id for ca in loaded_all] == ["CA-01", "CA-02"]


def test_load_answer(tmp_path: Path) -> None:
    """load_answer đọc tệp JSON đáp án chuẩn."""
    answer = DapAn(ca_id="CA-01", van_ban_bat_thuong=True, ghi_chu="Ghi chú tiếng Việt")
    path = tmp_path / "answer.json"
    path.write_text(answer.model_dump_json(), encoding="utf-8")

    loaded = load_answer(path)
    assert loaded.ca_id == "CA-01"
    assert loaded.van_ban_bat_thuong is True
    assert loaded.ghi_chu == "Ghi chú tiếng Việt"


def test_latest_lab_and_latest_vital() -> None:
    """latest_lab và latest_vital chọn đúng bản ghi mới nhất theo thời điểm."""
    ca = _sample_case("CA-01")

    lab = latest_lab(ca, "creatinin")
    assert lab is not None
    assert lab.xet_nghiem_id == "XN-NEW"
    assert lab.gia_tri_so == 110.0
    assert latest_lab(ca, "khong_co") is None

    vital = latest_vital(ca, "can_nang")
    assert vital is not None
    assert vital.sinh_hieu_id == "SH-NEW"
    assert vital.gia_tri == 68.5
    assert latest_vital(ca, "khong_co") is None


def test_ingredients_of() -> None:
    """ingredients_of trả hoạt chất cho dòng có thuoc_id và rỗng khi không có thuoc_id."""
    ca = _sample_case("CA-01")
    combo_line, free_line = ca.y_lenh_cho_duyet.chi_tiet

    ingredients = ingredients_of(ca, combo_line)
    assert [hc.hoat_chat_id for hc in ingredients] == ["HC-AMOX", "HC-CLAV"]
    assert ingredients_of(ca, free_line) == []
