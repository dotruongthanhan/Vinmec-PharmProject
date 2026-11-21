"""Kiểm thử tích hợp engine 14 luật (D4–D7) với resolver giả lập và fallback."""

from pathlib import Path

import pytest

from app.domain.loader import load_case
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
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules import (
    allergy,
    antibiotic,
    drug_disease,
    duplicate,
    hepatic,
    lab_threshold,
    max_dose,
    renal_dose,
    required_fields,
    route,
    schedule,
    stewardship,
    toxicity,
)
from app.rules.d6_config import (
    NephrotoxicEntry,
    QtProlongationEntry,
    ToxicityConfig,
    ToxicitySource,
)
from app.rules.engine import _priority_key, run_rules
from app.rules.renal_dose import RenalRuleBook, load_renal_rules
from app.rules.types import PhatHien
from tests.rules import NOW, make_minimal_case

ROOT = Path(__file__).resolve().parents[2]


class _FakeResolver:
    """Bộ phân giải giả trả KetQuaPhanGiai dựng tay theo chi_tiet_y_lenh_id."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        del ca
        return self._mapping.get(
            line.chi_tiet_y_lenh_id,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien"),
        )


def _tp(hoat_chat_id: str, ten_inn: str) -> ThanhPhanPhanGiai:
    """Tạo thành phần đã phân giải tối thiểu cho test engine."""
    return ThanhPhanPhanGiai(
        hoat_chat_id=hoat_chat_id,
        ten_inn=ten_inn,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai="thuoc",
    )


def _disable_other_default_configs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    keep_toxicity: bool = False,
) -> None:
    """Trả None cho các bảng KB mặc định để test tổng hợp không phụ thuộc tệp trên đĩa."""
    targets = [
        (allergy, "try_load_default_allergy_config"),
        (route, "try_load_default_route_config"),
        (max_dose, "try_load_default_max_dose_config"),
        (hepatic, "try_load_default_hepatic_config"),
        (lab_threshold, "try_load_default_lab_threshold_config"),
        (drug_disease, "try_load_default_drug_disease_config"),
        (stewardship, "try_load_default_stewardship_config"),
    ]
    if not keep_toxicity:
        targets.append((toxicity, "try_load_default_toxicity_config"))
    for module, attr in targets:
        monkeypatch.setattr(module, attr, lambda: None)


def test_engine_without_resolver_matches_pre_t69_except_antibiotic_factor() -> None:
    """Không có resolver phải giữ nguyên kết quả trước T69 trừ số yếu tố luật kháng sinh."""
    ca = load_case(ROOT / "data/mock/demo/DEMO-04.json")
    renal_rules = load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json")

    findings = run_rules(ca, renal_rules)
    expected_legacy = sorted(
        [
            *allergy.check(ca),
            *duplicate.check(ca),
            *antibiotic.check(ca),
            *renal_dose.check(ca, renal_rules),
            *schedule.check(ca),
            *required_fields.check(ca),
        ],
        key=_priority_key,
    )

    assert findings == expected_legacy
    abx = [item for item in findings if item.ma_luat.startswith("khang_sinh_")]
    assert [item.ma_luat for item in abx] == ["khang_sinh_vi_sinh_nhay"]
    assert all(item.yeu_to == 6 for item in abx)
    assert all(item.ma_luat != "y_lenh_thieu_truong" for item in findings)


def test_engine_isolates_exception_from_new_d4_d7_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Một luật mới ném ngoại lệ vẫn sinh loi_luat đúng yếu tố và không chặn luật khác."""
    _disable_other_default_configs(monkeypatch)

    def _raise_hepatic(*_args: object, **_kwargs: object) -> list[PhatHien]:
        raise RuntimeError("lỗi suy gan giả lập")

    monkeypatch.setattr(hepatic, "check", _raise_hepatic)
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-DEFAULT",
                lieu_moi_lan=None,
                bat_dau=NOW,
                trang_thai_dong="active",
            )
        ]
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("acetaminophen", "Paracetamol")],
            )
        }
    )
    renal_rules = RenalRuleBook(phien_ban="0.3", quy_tac=[])

    findings = run_rules(ca, renal_rules, resolver=resolver)  # type: ignore[arg-type]

    errors = [item for item in findings if item.ma_luat == "loi_luat"]
    assert len(errors) == 1
    assert errors[0].yeu_to == 6
    assert errors[0].ket_luan == "khong_du_du_lieu"
    assert errors[0].muc_do is None
    assert errors[0].thong_tin_con_thieu == ["luat_chay_loi"]
    assert errors[0].can_cu[0].ban_ghi_id == "hepatic"
    assert any(item.ma_luat == "di_ung_khong_co" and item.yeu_to == 1 for item in findings)
    assert any(item.ma_luat == "y_lenh_thieu_truong" and item.yeu_to == 7 for item in findings)


def test_engine_synthetic_nephrotoxicity_gentamicin_vancomycin_with_ckd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gentamicin + vancomycin chờ duyệt kèm suy thận CrCl ~ 30 -> doc_than_cong_don."""
    _disable_other_default_configs(monkeypatch, keep_toxicity=True)
    cfg = ToxicityConfig(
        doc_than=(
            NephrotoxicEntry(
                hoat_chat_id="gentamicin",
                nhom="aminoglycosid",
                nguon=(
                    ToxicitySource(
                        loai="nhan_fda",
                        ten_nhan="Gentamicin",
                        trich_nguyen_van="gentamicin injection is potentially nephrotoxic.",
                    ),
                ),
            ),
            NephrotoxicEntry(
                hoat_chat_id="vancomycin",
                nhom="glycopeptid",
                nguon=(
                    ToxicitySource(
                        loai="nhan_fda",
                        ten_nhan="Vancomycin",
                        trich_nguyen_van="Systemic vancomycin exposure may result in AKI.",
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr(toxicity, "try_load_default_toxicity_config", lambda: cfg)

    hoat_chats = [
        HoatChat(hoat_chat_id="HC-GENTA", ten_hoat_chat="Gentamicin", ten_quoc_te="gentamicin"),
        HoatChat(hoat_chat_id="HC-VANC", ten_hoat_chat="Vancomycin", ten_quoc_te="vancomycin"),
    ]
    thuocs = [
        Thuoc(
            thuoc_id="T-GENTA",
            ten_thuoc="Gentamicin 80 mg",
            duong_dung="truyền tĩnh mạch",
            thanh_phan=[ThanhPhan(hoat_chat_id="HC-GENTA", ham_luong_thanh_phan=80, don_vi="mg")],
        ),
        Thuoc(
            thuoc_id="T-VANC",
            ten_thuoc="Vancomycin 1 g",
            duong_dung="truyền tĩnh mạch",
            thanh_phan=[ThanhPhan(hoat_chat_id="HC-VANC", ham_luong_thanh_phan=1000, don_vi="mg")],
        ),
    ]
    ca = make_minimal_case(
        tuoi=60,
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
                gia_tri_so=200.0,
                don_vi="umol/L",
                thoi_diem_ket_qua=NOW,
            )
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-GENTA",
                thuoc_id="T-GENTA",
                lieu_moi_lan=240.0,
                don_vi_lieu="mg",
                tan_suat="1 lần/ngày",
                so_lan_moi_ngay=1,
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-VANC",
                thuoc_id="T-VANC",
                lieu_moi_lan=1000.0,
                don_vi_lieu="mg",
                tan_suat="2 lần/ngày",
                so_lan_moi_ngay=2,
                duong_dung="truyền tĩnh mạch",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=thuocs,
        danh_muc_hoat_chat=hoat_chats,
    ).model_copy(update={"co_dia": [CoDia(loai="suy_than", trang_thai="co", thoi_diem=NOW)]})

    resolver = _FakeResolver(
        {
            "CT-GENTA": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("gentamicin", "Gentamicin")],
            ),
            "CT-VANC": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("vancomycin", "Vancomycin")],
            ),
        }
    )
    renal_rules = RenalRuleBook(phien_ban="0.3", quy_tac=[])

    findings = run_rules(ca, renal_rules, resolver=resolver)  # type: ignore[arg-type]

    nephro = [item for item in findings if item.ma_luat == "doc_than_cong_don"]
    assert len(nephro) == 1
    assert nephro[0].yeu_to == 5
    assert nephro[0].ket_luan == "can_xem"
    assert nephro[0].muc_do == "nghiem_trong"
    assert set(nephro[0].chi_tiet_y_lenh_id) == {"CT-GENTA", "CT-VANC"}


def test_engine_synthetic_qt_prolongation_custom_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hai thuốc thuộc danh sách keo_dai_qt tự tạo -> keo_dai_qt_cong_don mức can_luu_y."""
    _disable_other_default_configs(monkeypatch, keep_toxicity=True)
    cfg = ToxicityConfig(
        keo_dai_qt=(
            QtProlongationEntry(
                hoat_chat_id="amiodarone",
                muc_nhan="warnings_and_cautions",
                nguon=(
                    ToxicitySource(
                        loai="nhan_fda",
                        ten_nhan="Amiodarone",
                        trich_nguyen_van="QTc interval prolongation.",
                    ),
                ),
            ),
            QtProlongationEntry(
                hoat_chat_id="clarithromycin",
                muc_nhan="warnings_and_cautions",
                nguon=(
                    ToxicitySource(
                        loai="nhan_fda",
                        ten_nhan="Clarithromycin",
                        trich_nguyen_van="Prolongation of the QT interval.",
                    ),
                ),
            ),
        )
    )
    monkeypatch.setattr(toxicity, "try_load_default_toxicity_config", lambda: cfg)

    hoat_chats = [
        HoatChat(hoat_chat_id="HC-AMIO", ten_hoat_chat="Amiodarone", ten_quoc_te="amiodarone"),
        HoatChat(
            hoat_chat_id="HC-CLAR",
            ten_hoat_chat="Clarithromycin",
            ten_quoc_te="clarithromycin",
        ),
    ]
    thuocs = [
        Thuoc(
            thuoc_id="T-AMIO",
            ten_thuoc="Amiodarone 200 mg",
            duong_dung="uống",
            thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMIO", ham_luong_thanh_phan=200, don_vi="mg")],
        ),
        Thuoc(
            thuoc_id="T-CLAR",
            ten_thuoc="Clarithromycin 500 mg",
            duong_dung="uống",
            thanh_phan=[ThanhPhan(hoat_chat_id="HC-CLAR", ham_luong_thanh_phan=500, don_vi="mg")],
        ),
    ]
    ca = make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-AMIO",
                thuoc_id="T-AMIO",
                lieu_moi_lan=200.0,
                don_vi_lieu="mg",
                tan_suat="1 lần/ngày",
                so_lan_moi_ngay=1,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-CLAR",
                thuoc_id="T-CLAR",
                lieu_moi_lan=500.0,
                don_vi_lieu="mg",
                tan_suat="2 lần/ngày",
                so_lan_moi_ngay=2,
                duong_dung="uống",
                bat_dau=NOW,
                trang_thai_dong="active",
            ),
        ],
        danh_muc_thuoc=thuocs,
        danh_muc_hoat_chat=hoat_chats,
    )

    resolver = _FakeResolver(
        {
            "CT-AMIO": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("amiodarone", "Amiodarone")],
            ),
            "CT-CLAR": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("clarithromycin", "Clarithromycin")],
            ),
        }
    )
    renal_rules = RenalRuleBook(phien_ban="0.3", quy_tac=[])

    findings = run_rules(ca, renal_rules, resolver=resolver)  # type: ignore[arg-type]

    qt_findings = [item for item in findings if item.ma_luat == "keo_dai_qt_cong_don"]
    assert len(qt_findings) == 1
    assert qt_findings[0].yeu_to == 5
    assert qt_findings[0].ket_luan == "can_xem"
    assert qt_findings[0].muc_do == "can_luu_y"
    assert set(qt_findings[0].chi_tiet_y_lenh_id) == {"CT-AMIO", "CT-CLAR"}
