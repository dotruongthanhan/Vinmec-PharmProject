"""Kiểm thử luật yếu tố 6: sàng lọc thuốc – bệnh DDInter 2.0 theo ICD-10."""

from pathlib import Path

import pytest

from app.domain.models import CaBenh, ChanDoan, ChiTietYLenh
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.d4_config import DrugDiseaseConfig, DrugDiseasePair, load_drug_disease_config
from app.rules.drug_disease import check
from tests.rules import make_minimal_case

_REAL_PATH = Path(__file__).resolve().parents[2] / "data" / "kb" / "thuoc_benh_icd.json"


class _FakeResolver:
    """Bộ phân giải giả cho test đơn vị."""

    def __init__(self, mapping: dict[str, KetQuaPhanGiai]) -> None:
        self._mapping = mapping

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        return self._mapping.get(
            line.chi_tiet_y_lenh_id,
            KetQuaPhanGiai(trang_thai="khong_nhan_dien"),
        )


def _tp(hoat_chat_id: str, ten_inn: str) -> ThanhPhanPhanGiai:
    return ThanhPhanPhanGiai(
        hoat_chat_id=hoat_chat_id,
        ten_inn=ten_inn,
        ten_viet=None,
        ma_atc=[],
        ddinter_id=None,
        loai="thuoc",
    )


def _case_with_diagnoses(chan_doan: list[ChanDoan]) -> CaBenh:
    return make_minimal_case().model_copy(update={"chan_doan": chan_doan})


def test_drug_disease_range_n00_n19_matches_n18_2() -> None:
    """Khớp khoảng N00-N19 với mã ca N18.2 và không dùng chữ chống chỉ định."""
    cfg = DrugDiseaseConfig(
        cap_thuoc_benh=(
            DrugDiseasePair(
                hoat_chat_id="enalapril",
                ddinter_id="DDInter649",
                ten_benh="Kidney Diseases",
                ma_icd10=("N00-N19",),
                muc_do="Moderate",
                noi_dung="Use with caution in renal impairment.",
                url="https://ddinter2.scbdd.com/server/drug-detail/DDInter649/",
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("enalapril", "Enalapril")],
            )
        }
    )
    ca = _case_with_diagnoses(
        [ChanDoan(chan_doan_id="CD-1", ma_icd10=" n18.2 ", noi_dung="Bệnh thận mạn", loai="chinh")]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    f = findings[0]
    assert f.ma_luat == "thuoc_benh_ddinter"
    assert f.yeu_to == 6
    assert f.ket_luan == "can_xem"
    assert f.muc_do == "can_luu_y"
    assert "chống chỉ định" not in f.mo_ta.lower()
    assert all("chống chỉ định" not in c.mo_ta.lower() for c in f.can_cu)
    assert any("DDInter 2.0, CC BY-NC-SA 4.0" in c.mo_ta for c in f.can_cu)


def test_drug_disease_dotted_code_e87_2_matches_exact_not_e87_1() -> None:
    """Mục E87.2 khớp E87.2 nhưng không khớp E87.1."""
    cfg = DrugDiseaseConfig(
        cap_thuoc_benh=(
            DrugDiseasePair(
                hoat_chat_id="metformin",
                ddinter_id="DDInter1186",
                ten_benh="Acidosis, Lactic",
                ma_icd10=("E87.2",),
                muc_do="Major",
                noi_dung="Avoid in lactic acidosis.",
                url="https://ddinter2.scbdd.com/server/drug-detail/DDInter1186/",
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("metformin", "Metformin")],
            )
        }
    )

    ca_match = _case_with_diagnoses(
        [ChanDoan(chan_doan_id="CD-1", ma_icd10="E87.2", noi_dung="Toan chuyển hóa", loai="chinh")]
    )
    f_match = check(ca_match, resolver, cfg)
    assert len(f_match) == 1
    assert f_match[0].ma_luat == "thuoc_benh_ddinter"
    assert f_match[0].muc_do == "nghiem_trong"

    ca_no_match = _case_with_diagnoses(
        [ChanDoan(chan_doan_id="CD-2", ma_icd10="E87.1", noi_dung="Hạ natri máu", loai="chinh")]
    )
    f_no_match = check(ca_no_match, resolver, cfg)
    assert len(f_no_match) == 1
    assert f_no_match[0].ma_luat == "thuoc_benh_khong_khop"
    assert f_no_match[0].ket_luan == "dat"
    assert f_no_match[0].muc_do == "thong_tin"


def test_drug_disease_minor_level_maps_to_thong_tin() -> None:
    """Mức Minor từ DDInter ánh xạ sang muc_do='thong_tin'."""
    cfg = DrugDiseaseConfig(
        cap_thuoc_benh=(
            DrugDiseasePair(
                hoat_chat_id="digoxin",
                ddinter_id="DDInter562",
                ten_benh="Hypokalemia",
                ma_icd10=("E87",),
                muc_do="Minor",
                noi_dung="Minor interaction note.",
                url="https://ddinter2.scbdd.com/",
            ),
        )
    )
    resolver = _FakeResolver(
        {"CT-1": KetQuaPhanGiai(trang_thai="da_phan_giai", thanh_phan=[_tp("digoxin", "Digoxin")])}
    )
    ca = _case_with_diagnoses(
        [ChanDoan(chan_doan_id="CD-1", ma_icd10="E87.6", noi_dung="Hạ kali máu", loai="kem")]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    assert findings[0].ma_luat == "thuoc_benh_ddinter"
    assert findings[0].ket_luan == "can_xem"
    assert findings[0].muc_do == "thong_tin"


def test_drug_disease_missing_icd_returns_khong_du_du_lieu() -> None:
    """Không khớp và có chẩn đoán thiếu mã ICD -> thuoc_benh_thieu_icd với muc_do=None."""
    cfg = DrugDiseaseConfig(
        cap_thuoc_benh=(
            DrugDiseasePair(
                hoat_chat_id="metformin",
                ddinter_id="DDInter1186",
                ten_benh="Acidosis, Lactic",
                ma_icd10=("E87.2",),
                muc_do="Major",
                noi_dung="Avoid in lactic acidosis.",
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("metformin", "Metformin")],
            )
        }
    )
    ca = _case_with_diagnoses(
        [ChanDoan(chan_doan_id="CD-NO-ICD", ma_icd10=None, noi_dung="Đái tháo đường", loai="chinh")]
    )
    findings = check(ca, resolver, cfg)
    assert len(findings) == 1
    assert findings[0].ma_luat == "thuoc_benh_thieu_icd"
    assert findings[0].ket_luan == "khong_du_du_lieu"
    assert findings[0].muc_do is None
    assert findings[0].thong_tin_con_thieu == ["ma_icd10_chan_doan"]


def test_drug_disease_empty_icd_pair_only_produces_no_finding() -> None:
    """Cặp có ma_icd10 rỗng bị bỏ qua và không làm hoạt chất thành đạt."""
    cfg = DrugDiseaseConfig(
        cap_thuoc_benh=(
            DrugDiseasePair(
                hoat_chat_id="omeprazole",
                ddinter_id="DDInter1",
                ten_benh="Unmapped Disease",
                ma_icd10=(),
                muc_do="Moderate",
                noi_dung="No ICD code mapped.",
            ),
        )
    )
    resolver = _FakeResolver(
        {
            "CT-1": KetQuaPhanGiai(
                trang_thai="da_phan_giai",
                thanh_phan=[_tp("omeprazole", "Omeprazole")],
            )
        }
    )
    ca = _case_with_diagnoses(
        [ChanDoan(chan_doan_id="CD-1", ma_icd10="K21.9", noi_dung="GERD", loai="chinh")]
    )
    assert check(ca, resolver, cfg) == []


def test_load_real_drug_disease_kb() -> None:
    """Nạp tệp data/kb/thuoc_benh_icd.json thật; skip nếu khoá MỚI cap_thuoc_benh chưa có."""
    if not _REAL_PATH.exists():
        pytest.skip("Thiếu tệp data/kb/thuoc_benh_icd.json")
    cfg = load_drug_disease_config(_REAL_PATH)
    if not cfg.cap_thuoc_benh:
        pytest.skip("Khoá MỚI cap_thuoc_benh chưa có trong thuoc_benh_icd.json")
    assert len(cfg.cap_thuoc_benh) > 0
