"""Kiểm thử luật yếu tố 5 (D6): độc tính thuốc và thuốc nguy cơ cao."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest

from app.calc.renal import cockcroft_gault
from app.domain.models import (
    CaBenh,
    ChiTietYLenh,
    CoDia,
    HoatChat,
    KetQuaXetNghiem,
    SinhHieu,
    ThanhPhan,
    Thuoc,
)
from app.kb.resolver import DrugResolver
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules import toxicity
from app.rules.d6_config import (
    LiverToxEntry,
    NarrowTherapeuticEntry,
    NephrotoxicEntry,
    QtProlongationEntry,
    ToxicityConfig,
    ToxicitySource,
    load_toxicity_config,
)
from app.rules.toxicity import (
    check,
    doc_gan_livertox,
    doc_than_cong_don,
    keo_dai_qt_cong_don,
    khoang_dieu_tri_hep,
    thuoc_nguy_co_cao,
)
from tests.rules import NOW, make_minimal_case


class _FakeResolver:
    """Bộ phân giải tên thuốc giả lập chỉ dùng cho kiểm thử."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        del ca
        key = line.thuoc_id or line.ten_tu_do or line.chi_tiet_y_lenh_id
        return self._mapping.get(
            key,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không có trong giả lập"),
        )


def _resolved(hoat_chat_id: str, ten_inn: str, *, loai: str = "thuoc") -> KetQuaPhanGiai:
    return KetQuaPhanGiai(
        trang_thai="da_phan_giai",
        thanh_phan=[
            ThanhPhanPhanGiai(
                hoat_chat_id=hoat_chat_id,
                ten_inn=ten_inn,
                ten_viet=None,
                ma_atc=[],
                ddinter_id=None,
                loai=loai,
            )
        ],
    )


def _fda_src(ten_nhan: str, set_id: str, quote: str, truong: str = "warnings") -> ToxicitySource:
    return ToxicitySource(
        loai="nhan_fda",
        ten_nhan=ten_nhan,
        set_id=set_id,
        truong_nhan=truong,
        trich_nguyen_van=quote,
        url=f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}",
        ngay_lay="2026-11-19",
    )


def _livertox_src(chapter: str, quote: str) -> ToxicitySource:
    return ToxicitySource(
        loai="livertox",
        ma_chuyen_luan=chapter,
        trich_nguyen_van=quote,
        url=f"https://www.ncbi.nlm.nih.gov/books/{chapter}/",
        ngay_lay="2026-11-19",
    )


def _sample_config() -> ToxicityConfig:
    return ToxicityConfig(
        phien_ban="D6-test",
        doc_than=(
            NephrotoxicEntry(
                hoat_chat_id="gentamicin",
                nhom="aminoglycosid",
                nguon=(
                    _fda_src(
                        "GENTAMICIN SULFATE",
                        "set-gent",
                        "Aminoglycosides are potentially nephrotoxic.",
                    ),
                ),
            ),
            NephrotoxicEntry(
                hoat_chat_id="vancomycin",
                nhom="glycopeptid",
                nguon=(
                    _fda_src(
                        "VANCOMYCIN HYDROCHLORIDE",
                        "set-vanc",
                        "Nephrotoxicity may occur following parenteral administration.",
                    ),
                ),
            ),
        ),
        keo_dai_qt=(
            QtProlongationEntry(
                hoat_chat_id="amiodarone",
                muc_nhan="warnings_and_cautions",
                nguon=(
                    _fda_src(
                        "AMIODARONE HYDROCHLORIDE",
                        "set-amio",
                        "Amiodarone causes prolongation of the QT interval.",
                        truong="warnings_and_cautions",
                    ),
                ),
            ),
            QtProlongationEntry(
                hoat_chat_id="levofloxacin",
                muc_nhan="warnings_and_cautions",
                nguon=(
                    _fda_src(
                        "LEVOFLOXACIN",
                        "set-levo",
                        "Fluoroquinolones have been associated with QT prolongation.",
                        truong="warnings_and_cautions",
                    ),
                ),
            ),
        ),
        khoang_dieu_tri_hep=(
            NarrowTherapeuticEntry(
                hoat_chat_id="digoxin",
                ma_xet_nghiem_nong_do=("digoxin",),
                nguon=(
                    _fda_src(
                        "DIGOXIN",
                        "set-digo",
                        "Monitor serum digoxin concentrations periodically.",
                    ),
                ),
            ),
        ),
        doc_gan_livertox=(
            LiverToxEntry(
                hoat_chat_id="amiodarone",
                likelihood_score="A",
                nguon=(
                    _livertox_src(
                        "NBK548127",
                        "Likelihood score: A (well known cause of liver injury).",
                    ),
                ),
            ),
            LiverToxEntry(
                hoat_chat_id="isoniazid",
                likelihood_score="B",
                nguon=(
                    _livertox_src(
                        "NBK548754",
                        "Likelihood score: B (highly likely cause of liver injury).",
                    ),
                ),
            ),
            LiverToxEntry(
                hoat_chat_id="paracetamol",
                likelihood_score="C",
                nguon=(
                    _livertox_src(
                        "NBK548162",
                        "Likelihood score: C (probable cause at supratherapeutic doses).",
                    ),
                ),
            ),
        ),
    )


def _nephro_case(*, with_renal_comorbidity: bool) -> tuple[CaBenh, DrugResolver]:
    hc_gent = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    hc_vanc = HoatChat(hoat_chat_id="vancomycin", ten_hoat_chat="Vancomycin")
    t_gent = Thuoc(
        thuoc_id="T-GENT",
        ten_thuoc="Gentamicin 80 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    t_vanc = Thuoc(
        thuoc_id="T-VANC",
        ten_thuoc="Vancomycin 1 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="vancomycin")],
    )
    ca = make_minimal_case(
        tuoi=70,
        gioi_tinh="nam",
        sinh_hieu=[
            SinhHieu(
                sinh_hieu_id="SH-WT",
                loai="can_nang",
                gia_tri=60.0,
                don_vi="kg",
                thoi_diem_do=NOW,
            )
        ],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-CR",
                ma_xet_nghiem="creatinin",
                ten_xet_nghiem="Creatinin máu",
                gia_tri_so=176.8,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            )
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENT",
                thuoc_id="T-GENT",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-VANC",
                thuoc_id="T-VANC",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[t_gent, t_vanc],
        danh_muc_hoat_chat=[hc_gent, hc_vanc],
    )
    if with_renal_comorbidity:
        ca = ca.model_copy(update={"co_dia": [CoDia(loai="suy_than", trang_thai="co")]})
    resolver = _FakeResolver(
        {
            "T-GENT": _resolved("gentamicin", "Gentamicin"),
            "T-VANC": _resolved("vancomycin", "Vancomycin"),
        }
    )
    return ca, cast(DrugResolver, resolver)


@pytest.mark.parametrize(
    ("with_renal_comorbidity", "expected_muc_do"),
    [(True, "nghiem_trong"), (False, "can_luu_y")],
)
def test_nephrotoxic_combination_with_and_without_renal_comorbidity(
    with_renal_comorbidity: bool,
    expected_muc_do: str,
) -> None:
    """Gentamicin + vancomycin + CrCl ~30 ra nghiem_trong nếu có suy_than=co, else can_luu_y."""
    ca, resolver = _nephro_case(with_renal_comorbidity=with_renal_comorbidity)
    expected_crcl = cockcroft_gault(
        tuoi=70,
        gioi_tinh="nam",
        can_nang_kg=60.0,
        creatinin=176.8,
        creatinin_don_vi="umol/L",
        loai_can_nang="thuc_te",
    ).ket_qua
    assert expected_crcl is not None
    assert 28.0 <= expected_crcl <= 32.0

    findings = doc_than_cong_don(ca, resolver, _sample_config())
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "doc_than_cong_don"
    assert finding.yeu_to == 5
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == expected_muc_do
    assert set(finding.chi_tiet_y_lenh_id) == {"CT-GENT", "CT-VANC"}

    calc_evidences = [cc for cc in finding.can_cu if cc.loai == "tinh_toan"]
    assert len(calc_evidences) == 1
    assert f"{expected_crcl:.1f}" in calc_evidences[0].mo_ta

    doc_evidences = [cc for cc in finding.can_cu if cc.loai == "tai_lieu"]
    assert len(doc_evidences) == 2
    for cc in doc_evidences:
        assert "Nhãn FDA " in cc.mo_ta
        assert "(chờ dược sĩ duyệt)" in cc.mo_ta


def test_nephrotoxic_combination_still_fires_when_crcl_inputs_missing() -> None:
    """Thiếu creatinine vẫn phát hiện cộng dồn độc thận và ghi thiếu đầu vào ở căn cứ tính toán."""
    ca, resolver = _nephro_case(with_renal_comorbidity=False)
    ca = ca.model_copy(update={"xet_nghiem": []})
    findings = doc_than_cong_don(ca, resolver, _sample_config())
    assert len(findings) == 1
    assert findings[0].ma_luat == "doc_than_cong_don"
    calc_evidences = [cc for cc in findings[0].can_cu if cc.loai == "tinh_toan"]
    assert len(calc_evidences) == 1
    assert "creatinin" in calc_evidences[0].mo_ta


def test_nephrotoxic_both_in_current_meds_not_reported() -> None:
    """Hai thuốc độc thận đều nằm ở thuốc đang dùng thì không sinh phát hiện."""
    hc_para = HoatChat(hoat_chat_id="paracetamol", ten_hoat_chat="Paracetamol")
    hc_gent = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    hc_vanc = HoatChat(hoat_chat_id="vancomycin", ten_hoat_chat="Vancomycin")
    t_para = Thuoc(
        thuoc_id="T-PARA",
        ten_thuoc="Paracetamol 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="paracetamol")],
    )
    t_gent = Thuoc(
        thuoc_id="T-GENT",
        ten_thuoc="Gentamicin 80 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    t_vanc = Thuoc(
        thuoc_id="T-VANC",
        ten_thuoc="Vancomycin 1 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="vancomycin")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-PARA",
                thuoc_id="T-PARA",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENT",
                thuoc_id="T-GENT",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-VANC",
                thuoc_id="T-VANC",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=[t_para, t_gent, t_vanc],
        danh_muc_hoat_chat=[hc_para, hc_gent, hc_vanc],
    )
    resolver = cast(
        DrugResolver,
        _FakeResolver(
            {
                "T-PARA": _resolved("paracetamol", "Paracetamol"),
                "T-GENT": _resolved("gentamicin", "Gentamicin"),
                "T-VANC": _resolved("vancomycin", "Vancomycin"),
            }
        ),
    )
    assert doc_than_cong_don(ca, resolver, _sample_config()) == []


def test_single_nephrotoxic_drug_not_reported() -> None:
    """Chỉ có một thuốc độc thận thì không sinh phát hiện doc_than_cong_don."""
    hc_gent = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    t_gent = Thuoc(
        thuoc_id="T-GENT",
        ten_thuoc="Gentamicin 80 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENT",
                thuoc_id="T-GENT",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        danh_muc_thuoc=[t_gent],
        danh_muc_hoat_chat=[hc_gent],
    )
    resolver = cast(DrugResolver, _FakeResolver({"T-GENT": _resolved("gentamicin", "Gentamicin")}))
    assert doc_than_cong_don(ca, resolver, _sample_config()) == []


def test_qt_prolongation_two_drugs_and_one_drug() -> None:
    """QT: hai hoạt chất sinh can_luu_y nêu tên thuốc + mục nhãn; một hoạt chất không sinh."""
    hc_amio = HoatChat(hoat_chat_id="amiodarone", ten_hoat_chat="Amiodarone")
    hc_levo = HoatChat(hoat_chat_id="levofloxacin", ten_hoat_chat="Levofloxacin")
    t_amio = Thuoc(
        thuoc_id="T-AMIO",
        ten_thuoc="Cordarone 200 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="amiodarone")],
    )
    t_levo = Thuoc(
        thuoc_id="T-LEVO",
        ten_thuoc="Levofloxacin 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="levofloxacin")],
    )
    resolver = cast(
        DrugResolver,
        _FakeResolver(
            {
                "T-AMIO": _resolved("amiodarone", "Amiodarone"),
                "T-LEVO": _resolved("levofloxacin", "Levofloxacin"),
            }
        ),
    )

    ca_one = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMIO",
                thuoc_id="T-AMIO",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        danh_muc_thuoc=[t_amio],
        danh_muc_hoat_chat=[hc_amio],
    )
    assert keo_dai_qt_cong_don(ca_one, resolver, _sample_config()) == []

    ca_two = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-LEVO",
                thuoc_id="T-LEVO",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMIO",
                thuoc_id="T-AMIO",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[t_amio, t_levo],
        danh_muc_hoat_chat=[hc_amio, hc_levo],
    )
    findings = keo_dai_qt_cong_don(ca_two, resolver, _sample_config())
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "keo_dai_qt_cong_don"
    assert finding.yeu_to == 5
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert set(finding.chi_tiet_y_lenh_id) == {"CT-LEVO", "CT-AMIO"}
    assert "Cordarone 200 mg" in finding.mo_ta
    assert "Levofloxacin 500 mg" in finding.mo_ta
    assert "warnings_and_cautions" in finding.mo_ta


def test_narrow_therapeutic_digoxin_with_and_without_lab() -> None:
    """Khoảng điều trị hẹp: có xét nghiệm digoxin -> dat; chưa có -> nong_do_chua_theo_doi."""
    hc_dig = HoatChat(hoat_chat_id="digoxin", ten_hoat_chat="Digoxin")
    t_dig = Thuoc(
        thuoc_id="T-DIG",
        ten_thuoc="Digoxin 0.25 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="digoxin")],
    )
    resolver = cast(DrugResolver, _FakeResolver({"T-DIG": _resolved("digoxin", "Digoxin")}))

    ca_with_lab = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-DIG",
                thuoc_id="T-DIG",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        xet_nghiem=[
            KetQuaXetNghiem(
                xet_nghiem_id="XN-DIG-OLD",
                ma_xet_nghiem="digoxin",
                ten_xet_nghiem="Nồng độ digoxin",
                gia_tri_so=0.9,
                don_vi="ng/mL",
                thoi_diem_ket_qua=NOW - timedelta(days=2),
            ),
            KetQuaXetNghiem(
                xet_nghiem_id="XN-DIG-NEW",
                ma_xet_nghiem="digoxin",
                ten_xet_nghiem="Nồng độ digoxin",
                gia_tri_so=1.4,
                don_vi="ng/mL",
                thoi_diem_ket_qua=NOW,
            ),
        ],
        danh_muc_thuoc=[t_dig],
        danh_muc_hoat_chat=[hc_dig],
    )
    findings_ok = khoang_dieu_tri_hep(ca_with_lab, resolver, _sample_config())
    assert len(findings_ok) == 1
    assert findings_ok[0].ma_luat == "nong_do_da_theo_doi"
    assert findings_ok[0].ket_luan == "dat"
    assert findings_ok[0].muc_do == "thong_tin"
    assert "1.4" in findings_ok[0].mo_ta
    assert NOW.isoformat() in findings_ok[0].mo_ta

    ca_no_lab = ca_with_lab.model_copy(update={"xet_nghiem": []})
    findings_missing = khoang_dieu_tri_hep(ca_no_lab, resolver, _sample_config())
    assert len(findings_missing) == 1
    assert findings_missing[0].ma_luat == "nong_do_chua_theo_doi"
    assert findings_missing[0].ket_luan == "can_xem"
    assert findings_missing[0].muc_do == "can_luu_y"
    assert "nhãn khuyến cáo theo dõi nồng độ; hồ sơ chưa có kết quả" in findings_missing[0].mo_ta


def test_livertox_elevated_normal_missing_and_score_c() -> None:
    """LiverTox A/B đối chiếu ALT/AST với nguong_tren; không có số/điểm C không sinh phát hiện."""
    hc_amio = HoatChat(hoat_chat_id="amiodarone", ten_hoat_chat="Amiodarone")
    hc_para = HoatChat(hoat_chat_id="paracetamol", ten_hoat_chat="Paracetamol")
    t_amio = Thuoc(
        thuoc_id="T-AMIO",
        ten_thuoc="Amiodarone 200 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="amiodarone")],
    )
    t_para = Thuoc(
        thuoc_id="T-PARA",
        ten_thuoc="Paracetamol 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="paracetamol")],
    )
    resolver = cast(
        DrugResolver,
        _FakeResolver(
            {
                "T-AMIO": _resolved("amiodarone", "Amiodarone"),
                "T-PARA": _resolved("paracetamol", "Paracetamol"),
            }
        ),
    )

    def _amio_case(labs: list[KetQuaXetNghiem]) -> CaBenh:
        return make_minimal_case(
            chi_tiet=[
                ChiTietYLenh(
                    chi_tiet_y_lenh_id="CT-AMIO",
                    thuoc_id="T-AMIO",
                    bat_dau=NOW,
                    trang_thai_dong="pending",
                )
            ],
            xet_nghiem=labs,
            danh_muc_thuoc=[t_amio],
            danh_muc_hoat_chat=[hc_amio],
        )

    alt_high = KetQuaXetNghiem(
        xet_nghiem_id="XN-ALT-HIGH",
        ma_xet_nghiem="alt",
        ten_xet_nghiem="ALT",
        gia_tri_so=120.0,
        don_vi="U/L",
        nguong_tren=40.0,
        thoi_diem_ket_qua=NOW,
    )
    high_findings = doc_gan_livertox(_amio_case([alt_high]), resolver, _sample_config())
    assert len(high_findings) == 1
    assert high_findings[0].ma_luat == "doc_gan_men_gan_tang"
    assert high_findings[0].ket_luan == "can_xem"
    assert high_findings[0].muc_do == "can_luu_y"
    assert "LiverTox A" in high_findings[0].mo_ta
    doc_refs = [cc for cc in high_findings[0].can_cu if cc.loai == "tai_lieu"]
    assert len(doc_refs) == 1
    assert "LiverTox chương NBK548127:" in doc_refs[0].mo_ta
    assert "(chờ dược sĩ duyệt)" in doc_refs[0].mo_ta

    alt_norm = KetQuaXetNghiem(
        xet_nghiem_id="XN-ALT-OK",
        ma_xet_nghiem="alt",
        ten_xet_nghiem="ALT",
        gia_tri_so=30.0,
        don_vi="U/L",
        nguong_tren=40.0,
        thoi_diem_ket_qua=NOW,
    )
    norm_findings = doc_gan_livertox(_amio_case([alt_norm]), resolver, _sample_config())
    assert len(norm_findings) == 1
    assert norm_findings[0].ket_luan == "dat"
    assert norm_findings[0].muc_do == "thong_tin"
    assert "LiverTox A" in norm_findings[0].mo_ta

    assert doc_gan_livertox(_amio_case([]), resolver, _sample_config()) == []

    alt_text_only = KetQuaXetNghiem(
        xet_nghiem_id="XN-ALT-TEXT",
        ma_xet_nghiem="alt",
        ten_xet_nghiem="ALT",
        gia_tri_text="Bình thường",
        thoi_diem_ket_qua=NOW,
    )
    assert doc_gan_livertox(_amio_case([alt_text_only]), resolver, _sample_config()) == []

    alt_no_upper = KetQuaXetNghiem(
        xet_nghiem_id="XN-ALT-NO-ULN",
        ma_xet_nghiem="alt",
        ten_xet_nghiem="ALT",
        gia_tri_so=35.0,
        don_vi="U/L",
        nguong_tren=None,
        thoi_diem_ket_qua=NOW,
    )
    no_uln_findings = doc_gan_livertox(_amio_case([alt_no_upper]), resolver, _sample_config())
    assert len(no_uln_findings) == 1
    assert no_uln_findings[0].ma_luat == "doc_gan_thieu_xet_nghiem"
    assert no_uln_findings[0].ket_luan == "khong_du_du_lieu"
    assert no_uln_findings[0].muc_do is None
    assert no_uln_findings[0].thong_tin_con_thieu == ["nguong_tren_alt_ast"]

    ca_score_c = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-PARA",
                thuoc_id="T-PARA",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        xet_nghiem=[alt_high],
        danh_muc_thuoc=[t_para],
        danh_muc_hoat_chat=[hc_para],
    )
    assert doc_gan_livertox(ca_score_c, resolver, _sample_config()) == []


def test_high_alert_medication_and_no_config_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cờ la_thuoc_nguy_co_cao=True -> thong_tin; False -> không; thiếu bảng vẫn chạy phần này."""
    hc_ins = HoatChat(hoat_chat_id="insulin", ten_hoat_chat="Insulin")
    hc_vitc = HoatChat(hoat_chat_id="ascorbic_acid", ten_hoat_chat="Vitamin C")
    t_high = Thuoc(
        thuoc_id="T-INS",
        ten_thuoc="Insulin glargine 100 UI/mL",
        thanh_phan=[ThanhPhan(hoat_chat_id="insulin")],
        la_thuoc_nguy_co_cao=True,
    )
    t_normal = Thuoc(
        thuoc_id="T-NORM",
        ten_thuoc="Vitamin C 500 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="ascorbic_acid")],
        la_thuoc_nguy_co_cao=False,
    )

    ca_high = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-INS",
                thuoc_id="T-INS",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        danh_muc_thuoc=[t_high],
        danh_muc_hoat_chat=[hc_ins],
    )
    findings = thuoc_nguy_co_cao(ca_high)
    assert len(findings) == 1
    assert findings[0].ma_luat == "thuoc_nguy_co_cao"
    assert findings[0].ket_luan == "can_xem"
    assert findings[0].muc_do == "thong_tin"
    expected_msg = "thuốc thuộc danh mục nguy cơ cao của viện: kiểm tra kép liều, đường dùng"
    assert expected_msg in findings[0].mo_ta

    ca_normal = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NORM",
                thuoc_id="T-NORM",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        danh_muc_thuoc=[t_normal],
        danh_muc_hoat_chat=[hc_vitc],
    )
    assert thuoc_nguy_co_cao(ca_normal) == []

    resolver = cast(DrugResolver, _FakeResolver({"T-INS": _resolved("insulin", "Insulin")}))
    assert check(ca_high, None, _sample_config()) == []

    monkeypatch.setattr(toxicity, "try_load_default_toxicity_config", lambda: None)
    fallback_findings = check(ca_high, resolver)
    assert [item.ma_luat for item in fallback_findings] == ["thuoc_nguy_co_cao"]


def test_unresolved_line_with_single_nephrotoxic_drug_returns_missing_data_never_dat() -> None:
    """Dòng không nhận diện được + một thuốc độc thận khác -> khong_du_du_lieu, muc_do=None."""
    hc_gent = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    t_gent = Thuoc(
        thuoc_id="T-GENT",
        ten_thuoc="Gentamicin 80 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UNK",
                ten_tu_do="Thuốc lạ chưa mã hoá",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENT",
                thuoc_id="T-GENT",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[t_gent],
        danh_muc_hoat_chat=[hc_gent],
    )
    resolver = cast(
        DrugResolver,
        _FakeResolver(
            {
                "T-GENT": _resolved("gentamicin", "Gentamicin"),
                "Thuốc lạ chưa mã hoá": KetQuaPhanGiai(
                    trang_thai="khong_nhan_dien",
                    ly_do="Không khớp từ điển",
                ),
            }
        ),
    )

    nephro_findings = doc_than_cong_don(ca, resolver, _sample_config())
    assert len(nephro_findings) == 1
    assert nephro_findings[0].ket_luan == "khong_du_du_lieu"
    assert nephro_findings[0].muc_do is None
    assert nephro_findings[0].thong_tin_con_thieu == ["hoat_chat"]

    all_findings = check(ca, resolver, _sample_config())
    assert any(item.ket_luan == "khong_du_du_lieu" for item in all_findings)
    assert all(item.ket_luan != "dat" for item in all_findings)
    for item in all_findings:
        if item.ket_luan == "khong_du_du_lieu":
            assert item.muc_do is None


def test_excluded_electrolyte_line_ignored() -> None:
    """Dòng dịch truyền điện giải không bị tính vào tổ hợp hoặc báo thiếu hoạt chất."""
    hc_gent = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    hc_nacl = HoatChat(hoat_chat_id="natri_clorid", ten_hoat_chat="Natri clorid")
    t_gent = Thuoc(
        thuoc_id="T-GENT",
        ten_thuoc="Gentamicin 80 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    t_nacl = Thuoc(
        thuoc_id="T-NACL",
        ten_thuoc="Natri clorid 0,9% 500 mL",
        thanh_phan=[ThanhPhan(hoat_chat_id="natri_clorid")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-NACL",
                thuoc_id="T-NACL",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENT",
                thuoc_id="T-GENT",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[t_gent, t_nacl],
        danh_muc_hoat_chat=[hc_gent, hc_nacl],
    )
    resolver = cast(
        DrugResolver,
        _FakeResolver(
            {
                "T-GENT": _resolved("gentamicin", "Gentamicin"),
                "T-NACL": KetQuaPhanGiai(
                    trang_thai="khong_ap_dung",
                    thanh_phan=[
                        ThanhPhanPhanGiai(
                            hoat_chat_id="natri_clorid",
                            ten_inn="Sodium chloride",
                            ten_viet="Natri clorid",
                            ma_atc=[],
                            ddinter_id=None,
                            loai="dich_truyen_dien_giai",
                        )
                    ],
                    ly_do="Dịch truyền điện giải",
                ),
            }
        ),
    )
    findings = check(ca, resolver, _sample_config())
    assert [item.ma_luat for item in findings] == ["doc_tinh_khong_thuoc_danh_sach"]
    assert findings[0].ket_luan == "dat"
    assert findings[0].chi_tiet_y_lenh_id == ["CT-GENT"]
    assert all("CT-NACL" not in item.chi_tiet_y_lenh_id for item in findings)


def test_no_toxicity_match_returns_dat_for_meropenem() -> None:
    """Ca chỉ có meropenem không thuộc danh sách trả về đúng 1 nhận định đạt."""
    hc_mero = HoatChat(hoat_chat_id="meropenem", ten_hoat_chat="Meropenem")
    t_mero = Thuoc(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="meropenem")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-MERO",
                thuoc_id="T-MERO",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        danh_muc_thuoc=[t_mero],
        danh_muc_hoat_chat=[hc_mero],
    )
    resolver = cast(DrugResolver, _FakeResolver({"T-MERO": _resolved("meropenem", "Meropenem")}))

    findings = check(ca, resolver, _sample_config())
    assert len(findings) == 1
    finding = findings[0]
    assert finding.ma_luat == "doc_tinh_khong_thuoc_danh_sach"
    assert finding.yeu_to == 5
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"
    assert finding.chi_tiet_y_lenh_id == ["CT-MERO"]
    assert finding.thong_tin_con_thieu == []
    assert finding.mo_ta == (
        "Không thuốc nào thuộc danh sách theo dõi độc tính "
        "(độc thận, kéo dài QT, khoảng điều trị hẹp, độc gan LiverTox) trong nguồn đã lấy"
    )
    assert len(finding.can_cu) == 1
    assert finding.can_cu[0].loai == "tai_lieu"
    assert "doc_tinh" in finding.can_cu[0].mo_ta
    assert "D6-test" in finding.can_cu[0].mo_ta


def test_gentamicin_in_toxicity_list_does_not_emit_not_in_list_finding() -> None:
    """Ca có gentamicin sinh nhận định độc tính, không sinh doc_tinh_khong_thuoc_danh_sach."""
    hc_gent = HoatChat(hoat_chat_id="gentamicin", ten_hoat_chat="Gentamicin")
    t_gent = Thuoc(
        thuoc_id="T-GENT",
        ten_thuoc="Gentamicin 80 mg",
        thanh_phan=[ThanhPhan(hoat_chat_id="gentamicin")],
    )
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENT",
                thuoc_id="T-GENT",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        danh_muc_thuoc=[t_gent],
        danh_muc_hoat_chat=[hc_gent],
    )
    resolver = cast(DrugResolver, _FakeResolver({"T-GENT": _resolved("gentamicin", "Gentamicin")}))
    base = _sample_config()
    cfg_with_gent_narrow = base.model_copy(
        update={
            "khoang_dieu_tri_hep": (
                *base.khoang_dieu_tri_hep,
                NarrowTherapeuticEntry(
                    hoat_chat_id="gentamicin",
                    ma_xet_nghiem_nong_do=("gentamicin",),
                    nguon=(
                        _fda_src(
                            "GENTAMICIN SULFATE",
                            "set-gent",
                            "Serum concentrations of aminoglycosides should be monitored.",
                        ),
                    ),
                ),
            )
        }
    )

    findings = check(ca, resolver, cfg_with_gent_narrow)
    assert [item.ma_luat for item in findings] == ["nong_do_chua_theo_doi"]
    assert all(item.ma_luat != "doc_tinh_khong_thuoc_danh_sach" for item in findings)

    ca_combo, combo_resolver = _nephro_case(with_renal_comorbidity=False)
    combo_findings = check(ca_combo, combo_resolver, base)
    assert any(item.ma_luat == "doc_than_cong_don" for item in combo_findings)
    assert all(item.ma_luat != "doc_tinh_khong_thuoc_danh_sach" for item in combo_findings)


def test_all_unresolved_lines_do_not_emit_dat_and_partial_excludes_unresolved() -> None:
    """Mọi dòng chưa phân giải thì không sinh nhận định đạt; dòng lạ không tính đạt."""
    ca_all_pending_unknown = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UNK-1",
                ten_tu_do="Thuốc chưa mã hoá 1",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ]
    )
    resolver_unknown = cast(DrugResolver, _FakeResolver({}))
    pending_findings = check(ca_all_pending_unknown, resolver_unknown, _sample_config())
    assert all(item.ma_luat != "doc_tinh_khong_thuoc_danh_sach" for item in pending_findings)
    assert all(item.ket_luan != "dat" for item in pending_findings)

    ca_all_active_unknown = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UNK-2",
                ten_tu_do="Thuốc chưa mã hoá 2",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UNK-ACT",
                ten_tu_do="Thuốc đang dùng chưa rõ",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
    )
    active_findings = check(ca_all_active_unknown, resolver_unknown, _sample_config())
    assert all(item.ma_luat != "doc_tinh_khong_thuoc_danh_sach" for item in active_findings)
    assert all(item.ket_luan != "dat" for item in active_findings)

    hc_mero = HoatChat(hoat_chat_id="meropenem", ten_hoat_chat="Meropenem")
    t_mero = Thuoc(
        thuoc_id="T-MERO",
        ten_thuoc="Meropenem 1 g",
        thanh_phan=[ThanhPhan(hoat_chat_id="meropenem")],
    )
    ca_mixed = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-MERO",
                thuoc_id="T-MERO",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
        thuoc_dang_dung=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-UNK-ACT",
                ten_tu_do="Thuốc đang dùng chưa rõ",
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ],
        danh_muc_thuoc=[t_mero],
        danh_muc_hoat_chat=[hc_mero],
    )
    mixed_resolver = cast(
        DrugResolver,
        _FakeResolver({"T-MERO": _resolved("meropenem", "Meropenem")}),
    )
    mixed_findings = check(ca_mixed, mixed_resolver, _sample_config())
    assert [item.ma_luat for item in mixed_findings] == ["doc_tinh_khong_thuoc_danh_sach"]
    assert mixed_findings[0].chi_tiet_y_lenh_id == ["CT-MERO"]


def test_load_real_doc_tinh_config_or_skip() -> None:
    """Nạp data/kb/doc_tinh.json thật nếu đã có, bỏ qua nếu sub dữ liệu chưa tạo."""
    path = Path(__file__).resolve().parents[2] / "data" / "kb" / "doc_tinh.json"
    if not path.exists():
        pytest.skip("Chưa có tệp data/kb/doc_tinh.json")
    cfg = load_toxicity_config(path)
    assert cfg.phien_ban
    assert (
        len(cfg.doc_than)
        + len(cfg.keo_dai_qt)
        + len(cfg.khoang_dieu_tri_hep)
        + len(cfg.doc_gan_livertox)
        > 0
    )
