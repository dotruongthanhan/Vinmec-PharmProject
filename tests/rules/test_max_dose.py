"""Kiểm thử luật yếu tố 3 (max_dose.py): liều tối đa theo nhãn FDA và quy đổi SI."""

from __future__ import annotations

from app.domain.models import CaBenh, ChiTietYLenh, HoatChat, SinhHieu, ThanhPhan, Thuoc
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d5_config import (
    DoseLimit,
    MaxDoseConfig,
    MaxDoseRule,
    MaxDoseSource,
    MissingMaxDoseNote,
    PerKgLimit,
    PopulationDefinition,
    load_max_dose_config,
)
from app.rules.max_dose import check
from tests.rules import NOW, make_minimal_case


class _FakeResolver:
    """Bộ phân giải giả trả về KetQuaPhanGiai dựng sẵn theo chi_tiet_y_lenh_id."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: object, line: ChiTietYLenh) -> KetQuaPhanGiai:
        del ca
        return self._mapping.get(
            line.chi_tiet_y_lenh_id,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không có trong giả lập"),
        )


def _tp(
    hoat_chat_id: str,
    ten_inn: str | None = None,
    *,
    loai: str = "thuoc",
    ham_luong: float | None = None,
    don_vi: str | None = None,
) -> ThanhPhanPhanGiai:
    """Tạo thành phần phân giải tối thiểu cho test liều tối đa."""
    return ThanhPhanPhanGiai(
        hoat_chat_id=hoat_chat_id,
        ten_inn=ten_inn or hoat_chat_id,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai=loai,
        ham_luong=ham_luong,
        don_vi=don_vi,
    )


def _src(name: str = "Nhãn FDA") -> MaxDoseSource:
    """Tạo nguồn trích dẫn ngắn dùng chung trong test."""
    return MaxDoseSource(
        loai="nhan_fda",
        ten_nhan=name,
        set_id="set-test",
        trich_nguyen_van="Maximum daily dose...",
        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=set-test",
    )


def test_paracetamol_1g_six_times_exceeds_4g() -> None:
    """Paracetamol 1 g × 6 lần/ngày ở người lớn 60 kg -> lieu_toi_da_vuot."""
    hc = HoatChat(hoat_chat_id="acetaminophen", ten_hoat_chat="Paracetamol")
    thuoc = Thuoc(
        thuoc_id="T-PARA-1G",
        ten_thuoc="Paracetamol 1 g",
        duong_dung="uống",
        thanh_phan=[
            ThanhPhan(hoat_chat_id="acetaminophen", ham_luong_thanh_phan=1000, don_vi="mg")
        ],
    )
    ca = make_minimal_case(
        tuoi=55,
        sinh_hieu=[
            SinhHieu(
                sinh_hieu_id="SH-WT",
                loai="can_nang",
                gia_tri=60.0,
                don_vi="kg",
                thoi_diem_do=NOW,
            )
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-PARA",
                thuoc_id="T-PARA-1G",
                lieu_moi_lan=1.0,
                don_vi_lieu="g",
                so_lan_moi_ngay=6,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-PARA": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol", ham_luong=1000, don_vi="mg")],
            )
        }
    )
    cfg = MaxDoseConfig(
        doi_tuong_dinh_nghia={
            "nguoi_lon_va_thieu_nien_tu_50kg": PopulationDefinition(tuoi_tu=12, can_nang_tu=50)
        },
        nhom=(
            MaxDoseRule(
                ma_dong="acetaminophen|uong|nguoi_lon_va_thieu_nien_tu_50kg",
                hoat_chat_ids=("acetaminophen",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon_va_thieu_nien_tu_50kg",
                loai_gioi_han="toi_da_ro",
                lieu_toi_da_lan=DoseLimit(gia_tri=1000, don_vi="mg"),
                lieu_toi_da_ngay=DoseLimit(gia_tri=4000, don_vi="mg"),
                nguon=_src("ACETAMINOPHEN"),
            ),
        ),
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.yeu_to == 3
    assert f.ma_luat == "lieu_toi_da_vuot"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "nghiem_trong"
    assert "6000" in f.mo_ta
    assert "4000" in f.mo_ta
    assert any(c.loai == "tinh_toan" and "6000" in c.mo_ta for c in f.can_cu)
    assert any(c.loai == "tai_lieu" and "(chờ dược sĩ duyệt)" in c.mo_ta for c in f.can_cu)


def test_gentamicin_per_kg_without_weight() -> None:
    """Hàng chỉ có theo_kg.ngay_mg_kg, ca thiếu cân nặng -> khong_du_du_lieu can_nang."""
    hc = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    thuoc = Thuoc(
        thuoc_id="T-GENTA-80",
        ten_thuoc="Gentamicin 80 mg",
        duong_dung="truyền tĩnh mạch",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin", ham_luong_thanh_phan=80, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=70,
        sinh_hieu=[],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENTA",
                thuoc_id="T-GENTA-80",
                lieu_moi_lan=320.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=1,
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-GENTA": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("gentamicin", "Gentamicin", ham_luong=80, don_vi="mg")],
            )
        }
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="gentamicin|iv|nguoi_lon",
                hoat_chat_ids=("gentamicin",),
                duong_dung=("tiem_tinh_mach", "truyen_tinh_mach"),
                doi_tuong="nguoi_lon",
                loai_gioi_han="toi_da_ro",
                theo_kg=PerKgLimit(ngay_mg_kg=5.0),
                nguon=_src("Gentamicin"),
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_thieu_du_lieu"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert "can_nang" in f.thong_tin_con_thieu


def test_tablet_count_multiplied_by_strength_and_missing_strength() -> None:
    """Liều đơn vị viên nhân với ham_luong_thanh_phan; thiếu hàm lượng -> khong_du_du_lieu."""
    hc = HoatChat(hoat_chat_id="acetaminophen", ten_hoat_chat="Paracetamol")
    thuoc_ok = Thuoc(
        thuoc_id="T-PARA-500",
        ten_thuoc="Paracetamol 500 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="acetaminophen", ham_luong_thanh_phan=500, don_vi="mg")],
    )
    thuoc_no_strength = Thuoc(
        thuoc_id="T-PARA-NO",
        ten_thuoc="Paracetamol viên",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="acetaminophen")],
    )
    ca = make_minimal_case(
        tuoi=40,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-OK",
                thuoc_id="T-PARA-500",
                lieu_moi_lan=2.0,
                don_vi_lieu="viên",
                so_lan_moi_ngay=3,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NO",
                thuoc_id="T-PARA-NO",
                lieu_moi_lan=2.0,
                don_vi_lieu="viên",
                so_lan_moi_ngay=3,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[thuoc_ok, thuoc_no_strength],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-OK": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol", ham_luong=500, don_vi="mg")],
            ),
            "CT-NO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol")],
            ),
        }
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="acetaminophen|uong|nguoi_lon",
                hoat_chat_ids=("acetaminophen",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                lieu_toi_da_lan=DoseLimit(gia_tri=1000, don_vi="mg"),
                lieu_toi_da_ngay=DoseLimit(gia_tri=4000, don_vi="mg"),
                nguon=_src("ACETAMINOPHEN"),
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    by_line = {f.chi_tiet_y_lenh_id[0]: f for f in findings}
    assert by_line["CT-OK"].ma_luat == "lieu_toi_da_trong_gioi_han"
    assert by_line["CT-OK"].ket_luan == "dat"
    assert "3000" in by_line["CT-OK"].mo_ta
    assert by_line["CT-NO"].ket_luan == "khong_du_du_lieu"
    assert by_line["CT-NO"].muc_do is None
    assert by_line["CT-NO"].thong_tin_con_thieu == ["ham_luong_thanh_phan"]


def test_missing_frequency_checks_single_dose_and_adds_missing_daily() -> None:
    """Thiếu so_lan_moi_ngay vẫn so trần một lần và thêm phát hiện thiếu liều ngày."""
    hc = HoatChat(hoat_chat_id="acetaminophen", ten_hoat_chat="Paracetamol")
    thuoc = Thuoc(
        thuoc_id="T-PARA",
        ten_thuoc="Paracetamol 500 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="acetaminophen", ham_luong_thanh_phan=500, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=40,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-PRN",
                thuoc_id="T-PARA",
                lieu_moi_lan=1000.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=None,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-PRN": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol")],
            )
        }
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="acetaminophen|uong|nguoi_lon",
                hoat_chat_ids=("acetaminophen",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                lieu_toi_da_lan=DoseLimit(gia_tri=1000, don_vi="mg"),
                lieu_toi_da_ngay=DoseLimit(gia_tri=4000, don_vi="mg"),
                nguon=_src("ACETAMINOPHEN"),
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 2
    assert findings[0].ma_luat == "lieu_toi_da_trong_gioi_han"
    assert findings[0].ket_luan == "dat"
    assert findings[1].ma_luat == "lieu_toi_da_thieu_du_lieu"
    assert findings[1].ket_luan == "khong_du_du_lieu"
    assert findings[1].muc_do is None
    assert findings[1].thong_tin_con_thieu == ["so_lan_moi_ngay"]


def test_soft_cap_tran_up_to_returns_can_luu_y() -> None:
    """Vượt trần mềm tran_up_to -> can_xem mức can_luu_y."""
    hc = HoatChat(hoat_chat_id="fluconazole", ten_hoat_chat="Fluconazole")
    thuoc = Thuoc(
        thuoc_id="T-FLU",
        ten_thuoc="Fluconazole 200 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="fluconazole", ham_luong_thanh_phan=200, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=45,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-FLU",
                thuoc_id="T-FLU",
                lieu_moi_lan=300.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=2,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-FLU": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("fluconazole", "Fluconazole")],
            )
        }
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="fluconazole|uong|nguoi_lon",
                hoat_chat_ids=("fluconazole",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                loai_gioi_han="tran_up_to",
                lieu_toi_da_ngay=DoseLimit(gia_tri=400, don_vi="mg"),
                nguon=_src("Fluconazole"),
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_vuot_tran_mem"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "can_luu_y"


def test_row_with_dieu_kien_khac_not_used_for_auto_check() -> None:
    """Hoạt chất chỉ có hàng dieu_kien_khac -> lieu_toi_da_chi_co_muc_dieu_kien."""
    hc = HoatChat(hoat_chat_id="esomeprazole", ten_hoat_chat="Esomeprazole")
    thuoc = Thuoc(
        thuoc_id="T-ESO",
        ten_thuoc="Esomeprazole 40 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="esomeprazole", ham_luong_thanh_phan=40, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=50,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-ESO",
                thuoc_id="T-ESO",
                lieu_moi_lan=40.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=2,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-ESO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("esomeprazole", "Esomeprazole")],
            )
        }
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="esomeprazole|uong|nguoi_lon_child_pugh_c",
                hoat_chat_ids=("esomeprazole",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                dieu_kien_khac="Suy gan nặng Child-Pugh C (20 mg/ngày)",
                lieu_toi_da_ngay=DoseLimit(gia_tri=20, don_vi="mg"),
                nguon=_src("Esomeprazole"),
            ),
        ),
        khong_ghi_toi_da=(
            MissingMaxDoseNote(
                hoat_chat_id="esomeprazole",
                ly_do="Chỉ có trần cho Child-Pugh C; nhãn không ghi tối đa chung.",
            ),
        ),
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_chi_co_muc_dieu_kien"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["dieu_kien_ap_dung"]
    assert "Suy gan nặng Child-Pugh C" in f.mo_ta
    assert "80" in f.mo_ta
    assert "20" in f.mo_ta


def test_co_med_rule_applies_only_when_co_med_present() -> None:
    """Hàng thuoc_dung_cung_hoat_chat_ids chỉ áp dụng khi có thuốc dùng cùng trong ca."""
    hc_sim = HoatChat(hoat_chat_id="simvastatin", ten_hoat_chat="Simvastatin")
    hc_amio = HoatChat(hoat_chat_id="amiodarone", ten_hoat_chat="Amiodarone")
    t_sim = Thuoc(
        thuoc_id="T-SIM",
        ten_thuoc="Simvastatin 30 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="simvastatin", ham_luong_thanh_phan=30, don_vi="mg")],
    )
    t_amio = Thuoc(
        thuoc_id="T-AMIO",
        ten_thuoc="Amiodaron 200 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="amiodarone", ham_luong_thanh_phan=200, don_vi="mg")],
    )
    sim_line = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-SIM",
        thuoc_id="T-SIM",
        lieu_moi_lan=30.0,
        don_vi_lieu="mg",
        so_lan_moi_ngay=1,
        duong_dung="uống",
        bat_dau=NOW,
        trang_thai_dong="active",
    )
    amio_line = ChiTietYLenh(
        chi_tiet_y_lenh_id="CT-AMIO",
        thuoc_id="T-AMIO",
        lieu_moi_lan=200.0,
        don_vi_lieu="mg",
        so_lan_moi_ngay=1,
        duong_dung="uống",
        bat_dau=NOW,
        trang_thai_dong="active",
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="simvastatin|uong|nguoi_lon",
                hoat_chat_ids=("simvastatin",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                lieu_toi_da_ngay=DoseLimit(gia_tri=40, don_vi="mg"),
                nguon=_src("Simvastatin"),
            ),
            MaxDoseRule(
                ma_dong="simvastatin|uong|amiodarone",
                hoat_chat_ids=("simvastatin",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                lieu_toi_da_ngay=DoseLimit(gia_tri=20, don_vi="mg"),
                thuoc_dung_cung_hoat_chat_ids=("amiodarone",),
                nguon=_src("Simvastatin"),
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-SIM": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("simvastatin", "Simvastatin")],
            ),
            "CT-AMIO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("amiodarone", "Amiodarone")],
            ),
        }
    )

    ca_alone = make_minimal_case(
        tuoi=65,
        chi_tiet=[sim_line],
        danh_muc_thuoc=[t_sim],
        danh_muc_hoat_chat=[hc_sim],
    )
    findings_alone = check(ca_alone, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings_alone) == 1
    assert findings_alone[0].ket_luan == "dat"

    ca_with_amio = make_minimal_case(
        tuoi=65,
        thuoc_dang_dung=[amio_line],
        chi_tiet=[sim_line],
        danh_muc_thuoc=[t_sim, t_amio],
        danh_muc_hoat_chat=[hc_sim, hc_amio],
    )
    findings_with = check(ca_with_amio, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings_with) == 1
    f = findings_with[0]
    assert f.ma_luat == "lieu_toi_da_vuot"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "nghiem_trong"
    assert "Amiodaron 200 mg" in f.mo_ta


def test_missing_source_returns_khong_co_nguon() -> None:
    """Hoạt chất không có hàng áp dụng -> lieu_toi_da_khong_co_nguon kèm lý do."""
    hc = HoatChat(hoat_chat_id="warfarin", ten_hoat_chat="Warfarin")
    thuoc = Thuoc(
        thuoc_id="T-WARF",
        ten_thuoc="Warfarin 5 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="warfarin", ham_luong_thanh_phan=5, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=60,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-WARF",
                thuoc_id="T-WARF",
                lieu_moi_lan=5.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=1,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-WARF": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("warfarin", "Warfarin")],
            )
        }
    )
    cfg = MaxDoseConfig(
        khong_ghi_toi_da=(
            MissingMaxDoseNote(
                hoat_chat_id="warfarin",
                ly_do="Liều warfarin cá thể hoá theo INR; nhãn không ghi liều tối đa.",
            ),
        )
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_khong_co_nguon"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["nguon_lieu_toi_da"]
    assert "INR" in f.mo_ta


def test_mg_per_kg_order_without_weight_and_other_units() -> None:
    """Dòng mg/kg so trực tiếp không cần cân nặng; đơn vị lạ lệch trần -> don_vi_lieu_quy_doi."""
    hc_para = HoatChat(hoat_chat_id="acetaminophen", ten_hoat_chat="Paracetamol")
    hc_col = HoatChat(hoat_chat_id="colistimethate", ten_hoat_chat="Colistimethate")
    t_para = Thuoc(
        thuoc_id="T-PARA-SIRO",
        ten_thuoc="Paracetamol siro",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="acetaminophen")],
    )
    t_col = Thuoc(
        thuoc_id="T-COL",
        ten_thuoc="Colistimethate 4.5M UI",
        duong_dung="truyền tĩnh mạch",
        thanh_phan=[ThanhPhan(hoat_chat_id="colistimethate")],
    )
    ca = make_minimal_case(
        tuoi=6,
        sinh_hieu=[],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-MGKG",
                thuoc_id="T-PARA-SIRO",
                lieu_moi_lan=15.0,
                don_vi_lieu="mg/kg",
                so_lan_moi_ngay=4,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UI",
                thuoc_id="T-COL",
                lieu_moi_lan=4.5,
                don_vi_lieu="triệu đơn vị",
                so_lan_moi_ngay=2,
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[t_para, t_col],
        danh_muc_hoat_chat=[hc_para, hc_col],
    )
    resolver = _FakeResolver(
        {
            "CT-MGKG": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol")],
            ),
            "CT-UI": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("colistimethate", "Colistimethate")],
            ),
        }
    )
    cfg = MaxDoseConfig(
        doi_tuong_dinh_nghia={
            "tre_em_2_12": PopulationDefinition(tuoi_tu=2, tuoi_den=12),
        },
        nhom=(
            MaxDoseRule(
                ma_dong="acetaminophen|uong|tre_em_2_12",
                hoat_chat_ids=("acetaminophen",),
                duong_dung=("uong",),
                doi_tuong="tre_em_2_12",
                theo_kg=PerKgLimit(lan_mg_kg=15, ngay_mg_kg=75),
                nguon=_src("ACETAMINOPHEN"),
            ),
            MaxDoseRule(
                ma_dong="colistimethate|iv|all",
                hoat_chat_ids=("colistimethate",),
                duong_dung=("tiem_tinh_mach", "truyen_tinh_mach"),
                doi_tuong="nguoi_lon_va_tre_em",
                theo_kg=PerKgLimit(ngay_mg_kg=5),
                nguon=_src("COLISTIMETHATE"),
            ),
        ),
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    by_line = {f.chi_tiet_y_lenh_id[0]: f for f in findings}
    assert by_line["CT-MGKG"].ma_luat == "lieu_toi_da_trong_gioi_han"
    assert by_line["CT-MGKG"].ket_luan == "dat"
    assert by_line["CT-UI"].ket_luan == "khong_du_du_lieu"
    assert by_line["CT-UI"].muc_do is None
    assert by_line["CT-UI"].thong_tin_con_thieu == ["don_vi_lieu_quy_doi"]


def _gentamicin_conditional_setup(
    *,
    tuoi: int | None,
    weight_kg: float | None,
) -> tuple[CaBenh, _FakeResolver, MaxDoseConfig]:
    """Dựng ca và cấu hình gentamicin chỉ có một hàng mang điều kiện đặc biệt."""
    hc = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    thuoc = Thuoc(
        thuoc_id="T-GENTA-80",
        ten_thuoc="Gentamicin 80 mg",
        duong_dung="truyền tĩnh mạch",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin", ham_luong_thanh_phan=80, don_vi="mg")],
    )
    sinh_hieu: list[SinhHieu] = []
    if weight_kg is not None:
        sinh_hieu = [
            SinhHieu(
                sinh_hieu_id="SH-WT",
                loai="can_nang",
                gia_tri=weight_kg,
                don_vi="kg",
                thoi_diem_do=NOW,
            )
        ]
    ca = make_minimal_case(
        tuoi=tuoi,
        sinh_hieu=sinh_hieu,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENTA",
                thuoc_id="T-GENTA-80",
                lieu_moi_lan=320.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=1,
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-GENTA": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("gentamicin", "Gentamicin", ham_luong=80, don_vi="mg")],
            )
        }
    )
    cfg = MaxDoseConfig(
        doi_tuong_dinh_nghia={
            "nguoi_lon_nhiem_trung_de_doa_tinh_mang": PopulationDefinition(
                tuoi_tu=18,
                dieu_kien_khac="Nhiễm khuẩn đe dọa tính mạng",
            )
        },
        nhom=(
            MaxDoseRule(
                ma_dong="gentamicin|iv|nguoi_lon_nhiem_trung_de_doa_tinh_mang",
                hoat_chat_ids=("gentamicin",),
                duong_dung=("tiem_tinh_mach", "truyen_tinh_mach"),
                doi_tuong="nguoi_lon_nhiem_trung_de_doa_tinh_mang",
                loai_gioi_han="toi_da_ro",
                theo_kg=PerKgLimit(ngay_mg_kg=5.0),
                nguon=_src("GENTAMICIN"),
            ),
        ),
    )
    return ca, resolver, cfg


def test_gentamicin_conditional_only_missing_weight() -> None:
    """Gentamicin chỉ có hàng điều kiện theo kg, thiếu cân nặng -> nhắc điều kiện + can_nang."""
    ca, resolver, cfg = _gentamicin_conditional_setup(tuoi=70, weight_kg=None)
    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_chi_co_muc_dieu_kien"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["dieu_kien_ap_dung", "can_nang"]
    assert "Nhiễm khuẩn đe dọa tính mạng" in f.mo_ta
    assert "5 mg/kg/ngày" in f.mo_ta


def test_gentamicin_conditional_only_with_weight_includes_ref_calc() -> None:
    """Gentamicin chỉ có hàng điều kiện, đủ cân nặng -> kèm phép tính tham khảo."""
    ca, resolver, cfg = _gentamicin_conditional_setup(tuoi=70, weight_kg=64.0)
    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_chi_co_muc_dieu_kien"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["dieu_kien_ap_dung"]
    assert "Nhiễm khuẩn đe dọa tính mạng" in f.mo_ta
    assert "320 mg / 64 kg = 5 mg/kg/ngày, trần 5 mg/kg/ngày" in f.mo_ta
    assert any(
        c.loai == "tinh_toan" and "320 mg / 64 kg = 5 mg/kg/ngày" in c.mo_ta for c in f.can_cu
    )
    assert any(c.loai == "tai_lieu" for c in f.can_cu)


def test_gentamicin_conditional_only_missing_age_also_lists_tuoi() -> None:
    """Thiếu cả tuổi và cân nặng ở hàng điều kiện -> báo đủ trong thong_tin_con_thieu."""
    ca, resolver, cfg = _gentamicin_conditional_setup(tuoi=None, weight_kg=None)
    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_chi_co_muc_dieu_kien"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["dieu_kien_ap_dung", "can_nang", "tuoi"]


def test_no_matching_rows_returns_khong_co_nguon() -> None:
    """Hoạt chất không có hàng khớp đường dùng -> lieu_toi_da_khong_co_nguon."""
    hc = HoatChat(hoat_chat_id="esomeprazole", ten_hoat_chat="Esomeprazole")
    thuoc = Thuoc(
        thuoc_id="T-ESO",
        ten_thuoc="Esomeprazole 40 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="esomeprazole", ham_luong_thanh_phan=40, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=50,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-ESO",
                thuoc_id="T-ESO",
                lieu_moi_lan=40.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=1,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-ESO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("esomeprazole", "Esomeprazole")],
            )
        }
    )
    cfg = MaxDoseConfig(
        nhom=(),
        khong_ghi_toi_da=(
            MissingMaxDoseNote(hoat_chat_id="esomeprazole", ly_do="Chưa có trần tối đa."),
        ),
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_khong_co_nguon"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["nguon_lieu_toi_da"]


def test_mixed_general_and_conditional_rows_keeps_auto_check() -> None:
    """Có cả hàng thường và hàng điều kiện đặc biệt -> vẫn so hàng thường + ghi chú."""
    hc = HoatChat(hoat_chat_id="esomeprazole", ten_hoat_chat="Esomeprazole")
    thuoc = Thuoc(
        thuoc_id="T-ESO",
        ten_thuoc="Esomeprazole 40 mg",
        duong_dung="uống",
        thanh_phan=[ThanhPhan(hoat_chat_id="esomeprazole", ham_luong_thanh_phan=40, don_vi="mg")],
    )
    ca = make_minimal_case(
        tuoi=50,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-ESO",
                thuoc_id="T-ESO",
                lieu_moi_lan=40.0,
                don_vi_lieu="mg",
                so_lan_moi_ngay=2,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc],
        danh_muc_hoat_chat=[hc],
    )
    resolver = _FakeResolver(
        {
            "CT-ESO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("esomeprazole", "Esomeprazole")],
            )
        }
    )
    cfg = MaxDoseConfig(
        nhom=(
            MaxDoseRule(
                ma_dong="esomeprazole|uong|nguoi_lon",
                hoat_chat_ids=("esomeprazole",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                loai_gioi_han="toi_da_ro",
                lieu_toi_da_ngay=DoseLimit(gia_tri=40, don_vi="mg"),
                nguon=_src("Esomeprazole"),
            ),
            MaxDoseRule(
                ma_dong="esomeprazole|uong|nguoi_lon_child_pugh_c",
                hoat_chat_ids=("esomeprazole",),
                duong_dung=("uong",),
                doi_tuong="nguoi_lon",
                dieu_kien_khac="Suy gan nặng Child-Pugh C (20 mg/ngày)",
                lieu_toi_da_ngay=DoseLimit(gia_tri=20, don_vi="mg"),
                nguon=_src("Esomeprazole"),
            ),
        ),
    )

    findings = check(ca, resolver=resolver, config=cfg)  # type: ignore[arg-type]
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_toi_da_vuot"
    assert f.ket_luan == "can_xem"
    assert "nhãn có mức riêng cho: Suy gan nặng Child-Pugh C" in f.mo_ta


def test_load_real_max_dose_config_from_kb() -> None:
    """Nạp tệp thật data/kb/lieu_toi_da.json và kiểm tra có hàng."""
    cfg = load_max_dose_config()
    assert len(cfg.nhom) > 0
    assert len(cfg.khong_ghi_toi_da) > 0
