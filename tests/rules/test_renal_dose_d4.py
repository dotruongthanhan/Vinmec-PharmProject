"""Kiểm thử luật yếu tố 6: mở rộng chỉnh liều thận (D4) qua DrugResolver."""

from pathlib import Path

import pytest

from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    HoatChat,
    KetQuaXetNghiem,
    SinhHieu,
    ThanhPhan,
    Thuoc,
)
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.renal_dose import (
    RenalDoseTier,
    RenalDrugRule,
    RenalRuleBook,
    RenalSourceDetail,
    check,
    load_renal_rules,
    select_renal_tier,
)
from tests.rules import NOW, make_minimal_case

_REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "quy_tac_lieu_than.json"


class _FakeResolver:
    """Bộ phân giải giả cho test đơn vị, trả KetQuaPhanGiai dựng tay."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        return self._mapping.get(
            line.chi_tiet_y_lenh_id,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien"),
        )


def _tp(hoat_chat_id: str, ten_inn: str, loai: str = "thuoc") -> ThanhPhanPhanGiai:
    return ThanhPhanPhanGiai(
        hoat_chat_id=hoat_chat_id,
        ten_inn=ten_inn,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai=loai,
    )


def _case_with_line(
    line_id: str = "CT-1",
    *,
    tuoi: int | None = 60,
    gioi_tinh: str | None = "nam",
    weight: float | None = 60.0,
    creatinin: float | None = 120.0,
) -> CaBenh:
    sinh_hieu = (
        [
            SinhHieu(
                sinh_hieu_id="SH-WT",
                loai="can_nang",
                gia_tri=weight,
                don_vi="kg",
                thoi_diem_do=NOW,
            )
        ]
        if weight is not None
        else []
    )
    xet_nghiem = (
        [
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=creatinin,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            )
        ]
        if creatinin is not None
        else []
    )
    return make_minimal_case(
        tuoi=tuoi,
        gioi_tinh=gioi_tinh,  # type: ignore[arg-type]
        sinh_hieu=sinh_hieu,
        xet_nghiem=xet_nghiem,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id=line_id,
                ten_tu_do="Thuốc thử",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
    )


def test_select_renal_tier_bao_gom_can_tren_false_at_30() -> None:
    """bao_gom_can_tren=false ở điểm 30 phải rơi đúng vào mức trên (>= 30)."""
    rule = RenalDrugRule(
        ten_quoc_te="test_drug",
        hoat_chat_ids=["test_drug"],
        nguon="FDA label",
        muc=[
            RenalDoseTier(
                crcl_tu=15,
                crcl_den=30,
                bao_gom_can_duoi=True,
                bao_gom_can_tren=False,
                can_chinh=True,
                khuyen_cao="Mức 15 đến < 30",
            ),
            RenalDoseTier(
                crcl_tu=30,
                crcl_den=None,
                bao_gom_can_duoi=True,
                can_chinh=False,
                khuyen_cao="Mức >= 30",
            ),
        ],
    )
    assert select_renal_tier(30.0, rule).khuyen_cao == "Mức >= 30"
    assert select_renal_tier(29.99, rule).khuyen_cao == "Mức 15 đến < 30"


def test_renal_d4_missing_weight_returns_khong_du_du_lieu() -> None:
    """Thiếu cân nặng khi dùng resolver phải trả khong_du_du_lieu và muc_do=None."""
    ca = _case_with_line(weight=None)
    rules = RenalRuleBook(
        phien_ban="0.2",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="cefepime",
                hoat_chat_ids=["cefepime"],
                nguon="FDA Cefepime",
                muc=[
                    RenalDoseTier(
                        crcl_tu=None,
                        crcl_den=60,
                        bao_gom_can_duoi=False,
                        can_chinh=True,
                        khuyen_cao="Giảm liều",
                    )
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("cefepime", "Cefepime")],
            ),
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_than_thieu_du_lieu"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert "can_nang_kg" in f.thong_tin_con_thieu


def test_renal_d4_pending_rule_has_can_luu_y_and_suffix() -> None:
    """Quy tắc từ quy_tac_cho_duyet phải hạ xuống can_luu_y và gắn hậu tố chờ duyệt."""
    # Nam 60t, 60kg, Cr 200 umol/L -> CrCl ~ 29.5 mL/min
    ca = _case_with_line(tuoi=60, gioi_tinh="nam", weight=60.0, creatinin=200.0)
    rules = RenalRuleBook(
        phien_ban="0.2",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="enoxaparin",
                hoat_chat_ids=["enoxaparin"],
                nguon="FDA Enoxaparin",
                muc=[
                    RenalDoseTier(
                        crcl_tu=30,
                        crcl_den=None,
                        bao_gom_can_duoi=True,
                        can_chinh=False,
                        khuyen_cao="Không chỉnh",
                    ),
                    RenalDoseTier(
                        crcl_tu=None,
                        crcl_den=30,
                        bao_gom_can_duoi=False,
                        bao_gom_can_tren=False,
                        can_chinh=True,
                        khuyen_cao="30 mg SC 1 lần/ngày",
                    ),
                ],
                nguon_chi_tiet=[
                    RenalSourceDetail(
                        loai="nhan_fda",
                        ten_nhan="Enoxaparin",
                        set_id="1e0ac5e2",
                        trich_nguyen_van="creatinine clearance <30 mL/min",
                        url="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1e0ac5e2",
                    )
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("enoxaparin", "Enoxaparin")],
            )
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_than_can_chinh"
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "can_luu_y"
    assert f.mo_ta.endswith(" (quy tắc từ nhãn FDA, chờ dược sĩ duyệt)")
    tai_lieu = [c for c in f.can_cu if c.loai == "tai_lieu"]
    assert len(tai_lieu) == 1
    assert "set_id=1e0ac5e2" in tai_lieu[0].mo_ta
    assert "creatinine clearance <30 mL/min" in tai_lieu[0].mo_ta
    assert "https://dailymed.nlm.nih.gov" in tai_lieu[0].mo_ta


def test_renal_d4_bsa_indexed_rule_returns_missing_bsa() -> None:
    """Chỉ số chứa 1.73 phải trả lieu_than_can_crcl_hieu_chinh_bsa với muc_do=None."""
    ca = _case_with_line()
    rules = RenalRuleBook(
        phien_ban="0.2",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="levetiracetam",
                hoat_chat_ids=["levetiracetam"],
                chi_so="CrCl (Cockcroft-Gault) hiệu chỉnh theo diện tích da, mL/min/1.73 m2",
                nguon="FDA Levetiracetam",
                muc=[
                    RenalDoseTier(
                        crcl_tu=80,
                        crcl_den=None,
                        bao_gom_can_duoi=False,
                        can_chinh=False,
                        khuyen_cao="500-1500 mg q12h",
                    )
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levetiracetam", "Levetiracetam")],
            )
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_than_can_crcl_hieu_chinh_bsa"
    assert f.ket_luan == "khong_du_du_lieu"
    assert f.muc_do is None
    assert f.thong_tin_con_thieu == ["crcl_hieu_chinh_dien_tich_da"]
    assert "1,73" in f.mo_ta


def test_renal_d4_no_label_data_tier_returns_ngoai_hdsd() -> None:
    """Mức chọn được có khong_co_so_lieu_nhan=true phải trả ngoai_hdsd mức can_luu_y."""
    # CrCl ~ 49 mL/min -> rơi vào mức < 10? đặt ngưỡng < 60 cho dễ kiểm
    ca = _case_with_line(tuoi=70, gioi_tinh="nam", weight=60.0, creatinin=150.0)
    rules = RenalRuleBook(
        phien_ban="0.2",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="levofloxacin",
                hoat_chat_ids=["levofloxacin"],
                nguon="FDA Levofloxacin",
                muc=[
                    RenalDoseTier(
                        crcl_tu=None,
                        crcl_den=50,
                        bao_gom_can_duoi=False,
                        bao_gom_can_tren=False,
                        can_chinh=True,
                        khuyen_cao="Nhãn không nêu liều cho mức này",
                        khong_co_so_lieu_nhan=True,
                    )
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin", "Levofloxacin")],
            )
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_than_ngoai_nhan"
    assert f.ket_luan == "ngoai_hdsd"
    assert f.muc_do == "can_luu_y"
    assert "nhãn không có khuyến cáo" in f.mo_ta


def test_renal_d4_combination_piperacillin_tazobactam_single_finding() -> None:
    """Thuốc phối hợp piperacillin + tazobactam chỉ sinh đúng một phát hiện."""
    ca = _case_with_line(tuoi=75, gioi_tinh="nu", weight=50.0, creatinin=200.0)
    rules = RenalRuleBook(
        phien_ban="0.2",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="piperacillin",
                hoat_chat_ids=["piperacillin", "tazobactam"],
                nguon="FDA Piperacillin-Tazobactam",
                muc=[
                    RenalDoseTier(
                        crcl_tu=40,
                        crcl_den=None,
                        bao_gom_can_duoi=False,
                        can_chinh=False,
                        khuyen_cao="Liều thường",
                    ),
                    RenalDoseTier(
                        crcl_tu=None,
                        crcl_den=40,
                        bao_gom_can_duoi=False,
                        can_chinh=True,
                        khuyen_cao="2,25 g q6h",
                    ),
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[
                    _tp("piperacillin", "Piperacillin"),
                    _tp("tazobactam", "Tazobactam"),
                ],
            )
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    assert findings[0].ma_luat == "lieu_than_can_chinh"
    assert "Piperacillin + Tazobactam" in findings[0].mo_ta


def test_renal_d4_without_resolver_matches_legacy_meropenem() -> None:
    """Không truyền resolver giữ nguyên kết quả cũ với meropenem."""
    hc_mero = HoatChat(
        hoat_chat_id="HC-MERO",
        ten_hoat_chat="Meropenem",
        ten_quoc_te="meropenem",
    )
    thuoc_mero = Thuoc(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="HC-MERO")],
        la_khang_sinh=True,
    )
    ca = make_minimal_case(
        tuoi=75,
        gioi_tinh="nu",
        sinh_hieu=[
            SinhHieu(
                sinh_hieu_id="SH-50",
                loai="can_nang",
                gia_tri=50.0,
                don_vi="kg",
                thoi_diem_do=NOW,
            )
        ],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-212",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=212.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            )
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-MERO",
                thuoc_id="T-MERO",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[thuoc_mero],
        danh_muc_hoat_chat=[hc_mero],
    )
    rules = load_renal_rules(_REAL_PATH)
    findings = check(ca, rules)
    assert len(findings) == 1
    assert findings[0].ma_luat == "lieu_than_can_chinh"
    assert findings[0].muc_do == "nghiem_trong"
    assert "chờ dược sĩ duyệt" not in findings[0].mo_ta


def test_renal_d4_approved_rule_shadows_pending_rule() -> None:
    """Hoạt chất đã khớp trong quy_tac thì bỏ qua ở quy_tac_cho_duyet."""
    ca = _case_with_line(tuoi=75, gioi_tinh="nu", weight=50.0, creatinin=212.0)
    approved = RenalDrugRule(
        ten_quoc_te="meropenem",
        hoat_chat_ids=["meropenem"],
        nguon="Nhãn duyệt",
        muc=[
            RenalDoseTier(
                crcl_tu=None,
                crcl_den=50,
                bao_gom_can_duoi=False,
                can_chinh=True,
                khuyen_cao="Chỉnh theo bản duyệt",
            )
        ],
    )
    pending = RenalDrugRule(
        ten_quoc_te="meropenem",
        hoat_chat_ids=["meropenem"],
        nguon="Nhãn chờ duyệt",
        muc=[
            RenalDoseTier(
                crcl_tu=None,
                crcl_den=50,
                bao_gom_can_duoi=False,
                can_chinh=True,
                khuyen_cao="Chỉnh theo bản chờ duyệt",
            )
        ],
    )
    rules = RenalRuleBook(phien_ban="0.2", quy_tac=[approved], quy_tac_cho_duyet=[pending])
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("meropenem", "Meropenem")],
            )
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    assert findings[0].muc_do == "nghiem_trong"
    assert "Chỉnh theo bản duyệt" in findings[0].mo_ta


def test_renal_d4_paracetamol_crcl_109_no_label_data_returns_dat() -> None:
    """Paracetamol CrCl ~109 ở mức can_chinh=False, khong_co_so_lieu_nhan=True -> dat."""
    # Nam 45t, 75kg, Cr 80 umol/L -> CrCl ~ 109.3 mL/min
    ca = _case_with_line(tuoi=45, gioi_tinh="nam", weight=75.0, creatinin=80.0)
    rules = RenalRuleBook(
        phien_ban="0.3",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="acetaminophen",
                hoat_chat_ids=["acetaminophen"],
                nguon="FDA Acetaminophen",
                muc=[
                    RenalDoseTier(
                        crcl_tu=30,
                        crcl_den=None,
                        bao_gom_can_duoi=False,
                        can_chinh=False,
                        khuyen_cao="Nhãn không nêu chỉnh",
                        khong_co_so_lieu_nhan=True,
                    ),
                    RenalDoseTier(
                        crcl_tu=None,
                        crcl_den=30,
                        bao_gom_can_duoi=True,
                        can_chinh=True,
                        khuyen_cao="Có thể cần giãn khoảng cách liều",
                    ),
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol")],
            ),
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_than_khong_can_chinh"
    assert f.ket_luan == "dat"
    assert f.muc_do == "thong_tin"
    assert "nhãn không nêu chỉnh liều ở mức CrCl này" in f.mo_ta
    assert "109.3" in f.mo_ta
    assert f.mo_ta.endswith(" (quy tắc từ nhãn FDA, chờ dược sĩ duyệt)")


def test_renal_d4_below_10_with_can_chinh_true_still_ngoai_hdsd() -> None:
    """Mức <10 có can_chinh=True và khong_co_so_lieu_nhan=True -> vẫn ngoai_hdsd."""
    # Nam 80t, 50kg, Cr 400 umol/L -> CrCl ~ 9.2 mL/min
    ca = _case_with_line(tuoi=80, gioi_tinh="nam", weight=50.0, creatinin=400.0)
    rules = RenalRuleBook(
        phien_ban="0.3",
        quy_tac=[],
        quy_tac_cho_duyet=[
            RenalDrugRule(
                ten_quoc_te="levofloxacin",
                hoat_chat_ids=["levofloxacin"],
                nguon="FDA Levofloxacin",
                muc=[
                    RenalDoseTier(
                        crcl_tu=10,
                        crcl_den=None,
                        bao_gom_can_duoi=True,
                        can_chinh=True,
                        khuyen_cao="Giảm liều",
                    ),
                    RenalDoseTier(
                        crcl_tu=None,
                        crcl_den=10,
                        bao_gom_can_duoi=False,
                        can_chinh=True,
                        khuyen_cao="Nhãn không nêu liều cho CrCl < 10 mL/min",
                        khong_co_so_lieu_nhan=True,
                    ),
                ],
            )
        ],
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("levofloxacin", "Levofloxacin")],
            ),
        }
    )
    findings = check(ca, rules, resolver)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "lieu_than_ngoai_nhan"
    assert f.ket_luan == "ngoai_hdsd"
    assert f.muc_do == "can_luu_y"


def test_load_real_renal_rules_kb() -> None:
    """Nạp tệp data/kb/quy_tac_lieu_than.json thật và kiểm có dữ liệu quy tắc."""
    if not _REAL_PATH.exists():
        pytest.skip("Thiếu tệp data/kb/quy_tac_lieu_than.json")
    book = load_renal_rules(_REAL_PATH)
    assert len(book.quy_tac) > 0
    assert len(book.quy_tac_cho_duyet) > 0
    has_new_upper = any(
        tier.bao_gom_can_tren is not None for rule in book.quy_tac_cho_duyet for tier in rule.muc
    )
    if not has_new_upper and not book.khong_co_nguong:
        pytest.skip("Khoá MỚI bao_gom_can_tren/khong_co_nguong chưa có trong tệp thật")
