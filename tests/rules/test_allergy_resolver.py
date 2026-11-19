"""Kiểm tra luật yếu tố 1 dùng bộ phân giải thuốc và bảng dị ứng chéo D3."""

from pathlib import Path
from typing import Any

import pytest

from app.domain.models import CaBenh, ChiTietYLenh, DiUng, HoatChat, ThanhPhan, Thuoc
from app.kb.resolver import DrugResolver
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules import allergy
from app.rules.allergy import check
from app.rules.allergy_config import load_allergy_config
from app.rules.engine import run_rules
from app.rules.registry import AllergyRule, RuleContext
from app.rules.renal_dose import load_renal_rules
from tests.rules import NOW, make_minimal_case

ROOT = Path(__file__).resolve().parents[2]


class StubResolver(DrugResolver):
    """Bộ phân giải giả lập cho kiểm thử đơn vị yếu tố 1."""

    def __init__(
        self,
        *,
        line_results: dict[str, KetQuaPhanGiai] | None = None,
        name_results: dict[str, KetQuaPhanGiai] | None = None,
        case_codes: dict[str, str] | None = None,
        axis_ids: set[str] | None = None,
    ) -> None:
        self._line_results = line_results or {}
        self._name_results = name_results or {}
        self._case_codes = case_codes or {}
        self._axis: dict[str, Any] = {identifier: object() for identifier in (axis_ids or set())}

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        return self._line_results[line.chi_tiet_y_lenh_id]

    def resolve_name(self, ten: str) -> KetQuaPhanGiai:
        return self._name_results.get(
            ten,
            KetQuaPhanGiai(
                trang_thai="khong_nhan_dien",
                ly_do="Không khớp tên chế phẩm DAV hoặc đồng nghĩa",
            ),
        )


def _tp(identifier: str, kind: str = "thuoc") -> ThanhPhanPhanGiai:
    return ThanhPhanPhanGiai(
        hoat_chat_id=identifier,
        ten_inn=identifier,
        ten_viet=identifier,
        ma_atc=[],
        ddinter_id=None,
        loai=kind,
    )


def _resolved(*ids: str, kind: str = "thuoc") -> KetQuaPhanGiai:
    return KetQuaPhanGiai(
        trang_thai="da_phan_giai",
        thanh_phan=[_tp(identifier, kind=kind) for identifier in ids],
        nguon_khop="dong_nghia",
    )


def _pending_case(
    *,
    di_ung: list[DiUng],
    line_names: list[str],
    trang_thai_di_ung: str = "co_di_ung",
) -> CaBenh:
    return make_minimal_case(
        trang_thai_di_ung=trang_thai_di_ung,  # type: ignore[arg-type]
        di_ung=di_ung,
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id=f"CT-{idx}",
                ten_tu_do=name,
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
            for idx, name in enumerate(line_names, 1)
        ],
    )


def test_brand_allergy_augmentin_matches_amoxicillin_direct_overlap() -> None:
    ca = _pending_case(
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Augmentin",
                loai_tac_nhan="thuoc",
                phan_ung="Sốc phản vệ",
            )
        ],
        line_names=["Amoxicillin 500 mg"],
    )
    resolver = StubResolver(
        name_results={"Augmentin": _resolved("amoxicillin", "clavulanic_acid")},
        line_results={"CT-1": _resolved("amoxicillin")},
    )
    (finding,) = check(ca, resolver)
    assert finding.ma_luat == "di_ung_trung_hoat_chat"
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"
    assert finding.chi_tiet_y_lenh_id == ["CT-1"]
    assert any(cc.loai == "du_lieu" and cc.ban_ghi_id == "DU-1" for cc in finding.can_cu)


def test_penicillin_group_vs_ceftriaxone_cites_all_bl05_sources() -> None:
    ca = _pending_case(
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Penicillin",
                loai_tac_nhan="thuoc",
                phan_ung="Mày đay",
            )
        ],
        line_names=["Ceftriaxon 1 g"],
    )
    resolver = StubResolver(line_results={"CT-1": _resolved("ceftriaxone")})
    config = load_allergy_config()
    (finding,) = check(ca, resolver, config)

    assert finding.ma_luat == "di_ung_cheo"
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert "Ceftriaxon 1 g" in finding.mo_ta
    assert "ceftriaxone" in finding.mo_ta
    assert "thấp" in finding.mo_ta
    assert "chờ dược sĩ duyệt" in finding.mo_ta

    bl05 = next(g for g in config.nhom if g.ma_nhom == "BL05_PEN_CEPH_R1_KHAC")
    doc_evidences = [cc for cc in finding.can_cu if cc.loai == "tai_lieu"]
    assert len(doc_evidences) == len(bl05.nguon)
    for src, evidence in zip(bl05.nguon, doc_evidences, strict=True):
        assert evidence.ban_ghi_id == "BL05_PEN_CEPH_R1_KHAC"
        assert src.trich_nguyen_van in evidence.mo_ta
        assert src.url in evidence.mo_ta
        assert (src.set_id or src.doi or "") in evidence.mo_ta
        assert "chờ dược sĩ duyệt" in evidence.mo_ta


def test_penicillin_vs_cefazolin_uses_very_low_risk_phrase() -> None:
    ca = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan="Penicillin", loai_tac_nhan="thuoc")],
        line_names=["Cefazolin 1 g"],
    )
    resolver = StubResolver(line_results={"CT-1": _resolved("cefazolin")})
    (finding,) = check(ca, resolver)
    assert finding.ma_luat == "di_ung_cheo"
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert "nguy cơ chéo rất thấp theo nguồn" in finding.mo_ta
    assert any(
        cc.loai == "tai_lieu" and "00dd6da7-50a8-44c9-b2dc-7948973df392" in cc.mo_ta
        for cc in finding.can_cu
    )


def test_parenthetical_strip_sulfamethoxazol_direct_and_cross_furosemide() -> None:
    du = DiUng(
        di_ung_id="DU-1",
        tac_nhan="Sulfamethoxazol (sulfonamide)",
        loai_tac_nhan="thuoc",
        phan_ung="Phát ban",
    )
    resolver_direct = StubResolver(
        name_results={"Sulfamethoxazol": _resolved("sulfamethoxazole")},
        line_results={"CT-1": _resolved("sulfamethoxazole", "trimethoprim")},
    )
    ca_direct = _pending_case(
        di_ung=[du],
        line_names=["Sulfamethoxazol + trimethoprim 800/160 mg"],
    )
    (direct_finding,) = check(ca_direct, resolver_direct)
    assert direct_finding.ma_luat == "di_ung_trung_hoat_chat"
    assert direct_finding.muc_do == "nghiem_trong"

    resolver_furo = StubResolver(
        name_results={"Sulfamethoxazol": _resolved("sulfamethoxazole")},
        line_results={"CT-1": _resolved("furosemide")},
    )
    ca_furo = _pending_case(di_ung=[du], line_names=["Furosemide 40 mg"])
    (furo_finding,) = check(ca_furo, resolver_furo)
    assert furo_finding.ma_luat == "di_ung_cheo"
    assert furo_finding.muc_do == "can_luu_y"
    assert "nguy cơ chéo rất thấp theo nguồn" in furo_finding.mo_ta
    assert any(
        cc.loai == "tai_lieu" and "10.1056/nejmoa022963" in cc.mo_ta for cc in furo_finding.can_cu
    )


@pytest.mark.parametrize(
    ("allergen_name", "allergen_id", "order_name", "order_ids"),
    [
        ("Furosemide", "furosemide", "Cotrimoxazol", ("sulfamethoxazole", "trimethoprim")),
        ("Cefazolin", "cefazolin", "Penicillin G", ("penicillin_g",)),
    ],
)
def test_one_way_cross_rule_does_not_fire_in_reverse(
    allergen_name: str,
    allergen_id: str,
    order_name: str,
    order_ids: tuple[str, ...],
) -> None:
    ca = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan=allergen_name, loai_tac_nhan="thuoc")],
        line_names=[order_name],
    )
    resolver = StubResolver(
        name_results={allergen_name: _resolved(allergen_id)},
        line_results={"CT-1": _resolved(*order_ids)},
    )
    (finding,) = check(ca, resolver)
    assert finding.ma_luat == "di_ung_khong_khop"
    assert finding.ket_luan == "dat"


def test_multiple_matching_groups_take_highest_risk_and_merge_once() -> None:
    config = load_allergy_config()
    expected_groups = {
        group.ma_nhom
        for group in config.nhom
        if any(
            ("amoxicillin" in group.hoat_chat_ids and "cefadroxil" in rel.hoat_chat_ids)
            or (
                group.huong == "hai_chieu"
                and "amoxicillin" in rel.hoat_chat_ids
                and "cefadroxil" in group.hoat_chat_ids
            )
            for rel in group.hoat_chat_lien_quan
        )
    }
    assert len(expected_groups) >= 2

    ca = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan="Amoxicillin", loai_tac_nhan="thuoc")],
        line_names=["Cefadroxil 500 mg"],
    )
    resolver = StubResolver(
        name_results={"Amoxicillin": _resolved("amoxicillin")},
        line_results={"CT-1": _resolved("cefadroxil")},
    )
    (finding,) = check(ca, resolver, config)
    assert finding.ma_luat == "di_ung_cheo"
    assert finding.muc_do == "nghiem_trong"
    group_ids = {cc.ban_ghi_id for cc in finding.can_cu if cc.loai == "tai_lieu"}
    assert group_ids == expected_groups


def test_unresolved_drug_allergy_never_passes_as_dat() -> None:
    ca = _pending_case(
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Thuốc bí ẩn",
                loai_tac_nhan="thuoc",
                nhom_duoc_ly="penicillin",
            )
        ],
        line_names=["Paracetamol 500 mg"],
    )
    resolver = StubResolver(line_results={"CT-1": _resolved("acetaminophen")})
    (finding,) = check(ca, resolver)
    assert finding.ma_luat == "di_ung_tac_nhan_khong_ro"
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert finding.chi_tiet_y_lenh_id == ["CT-1"]
    assert finding.thong_tin_con_thieu == ["hoat_chat_tac_nhan_di_ung"]
    assert finding.mo_ta == 'Chưa nhận diện được hoạt chất của tác nhân dị ứng "Thuốc bí ẩn"'


def test_unresolved_and_excluded_pending_lines() -> None:
    ca = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan="Penicillin", loai_tac_nhan="thuoc")],
        line_names=[
            "Thuốc gõ tay chưa rõ",
            "Phối hợp nhận diện một phần",
            "Natri clorid 0,9% 500 mL",
        ],
    )
    resolver = StubResolver(
        line_results={
            "CT-1": KetQuaPhanGiai(trang_thai="khong_nhan_dien", ly_do="Không khớp từ điển"),
            "CT-2": KetQuaPhanGiai(
                trang_thai="mot_phan",
                thanh_phan=[_tp("amoxicillin")],
                ly_do="Thiếu thành phần thứ 2",
            ),
            "CT-3": KetQuaPhanGiai(trang_thai="khong_ap_dung", ly_do="Dịch truyền"),
        }
    )
    findings = check(ca, resolver)
    assert all("CT-3" not in f.chi_tiet_y_lenh_id for f in findings)
    assert all(f.ket_luan != "dat" for f in findings)

    by_rule = {f.ma_luat: f for f in findings if f.chi_tiet_y_lenh_id == ["CT-2"]}
    assert set(by_rule) == {"di_ung_cheo", "di_ung_san_pham_khong_ro"}
    assert by_rule["di_ung_cheo"].muc_do == "nghiem_trong"
    assert by_rule["di_ung_san_pham_khong_ro"].ket_luan == "khong_du_du_lieu"
    assert by_rule["di_ung_san_pham_khong_ro"].muc_do is None

    (ct1_finding,) = [f for f in findings if f.chi_tiet_y_lenh_id == ["CT-1"]]
    assert ct1_finding.ket_luan == "khong_du_du_lieu"
    assert ct1_finding.thong_tin_con_thieu == ["thanh_phan_san_pham"]


def test_all_excluded_lines_with_unresolved_allergy_returns_empty() -> None:
    ca = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan="Thuốc bí ẩn", loai_tac_nhan="thuoc")],
        line_names=["Natri clorid 0,9% 500 mL"],
    )
    resolver = StubResolver(line_results={"CT-1": KetQuaPhanGiai(trang_thai="khong_ap_dung")})
    assert check(ca, resolver) == []


def test_step1_hc_case_code_mapping_precedes_free_text() -> None:
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        danh_muc_hoat_chat=[
            HoatChat(
                hoat_chat_id="HC-SULFAMETHOXAZOLE",
                ten_hoat_chat="Sulfamethoxazol",
            )
        ],
        danh_muc_thuoc=[],
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Tên tự do không có trong từ điển",
                loai_tac_nhan="thuoc",
                hoat_chat_id="HC-SULFAMETHOXAZOLE",
            )
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                ten_tu_do="Cotrimoxazol",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
    )
    resolver = StubResolver(
        case_codes={"HC-SULFAMETHOXAZOLE": "sulfamethoxazole"},
        line_results={"CT-1": _resolved("sulfamethoxazole", "trimethoprim")},
    )
    (finding,) = check(ca, resolver)
    assert finding.ma_luat == "di_ung_trung_hoat_chat"
    assert finding.muc_do == "nghiem_trong"


def test_status_branches_and_non_drug_allergy_preserved_with_resolver() -> None:
    resolver = StubResolver(line_results={"CT-1": _resolved("acetaminophen")})

    ca_missing = _pending_case(
        di_ung=[], line_names=["Paracetamol"], trang_thai_di_ung="chua_co_thong_tin"
    )
    assert check(ca_missing, resolver)[0].ma_luat == "di_ung_thieu_thong_tin"

    ca_none = _pending_case(
        di_ung=[], line_names=["Paracetamol"], trang_thai_di_ung="khong_di_ung_da_hoi"
    )
    assert check(ca_none, resolver)[0].ma_luat == "di_ung_khong_co"

    ca_food = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan="Tôm cua", loai_tac_nhan="thuc_an")],
        line_names=["Paracetamol"],
    )
    (food_finding,) = check(ca_food, resolver)
    assert food_finding.ma_luat == "di_ung_khong_khop"
    assert food_finding.ket_luan == "dat"


def test_fallback_when_resolver_or_cross_table_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fallback theo cách gọi không có resolver phải giữ kết quả di_ung_cung_nhom.
    ca = make_minimal_case(
        trang_thai_di_ung="co_di_ung",
        danh_muc_hoat_chat=[
            HoatChat(
                hoat_chat_id="HC-AMO",
                ten_hoat_chat="Amoxicillin",
                nhom_duoc_ly="penicillin",
            )
        ],
        danh_muc_thuoc=[
            Thuoc(
                thuoc_id="T-AMO",
                ten_thuoc="Amoxicillin 500 mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMO")],
            )
        ],
        di_ung=[
            DiUng(
                di_ung_id="DU-1",
                tac_nhan="Penicillin",
                loai_tac_nhan="thuoc",
                nhom_duoc_ly="penicillin",
            )
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id="CT-1",
                thuoc_id="T-AMO",
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
        ],
    )

    legacy_no_resolver = check(ca)
    assert legacy_no_resolver[0].ma_luat == "di_ung_cung_nhom"

    resolver = StubResolver(line_results={"CT-1": _resolved("amoxicillin")})
    monkeypatch.setattr(allergy, "try_load_default_allergy_config", lambda: None)
    legacy_no_table = check(ca, resolver)
    assert legacy_no_table == legacy_no_resolver


def test_two_allergies_matching_same_line_merge_without_presenter_collision() -> None:
    ca = _pending_case(
        di_ung=[
            DiUng(di_ung_id="DU-1", tac_nhan="Penicillin", loai_tac_nhan="thuoc"),
            DiUng(di_ung_id="DU-2", tac_nhan="Ceftriaxon", loai_tac_nhan="thuoc"),
        ],
        line_names=["Cefepime 1 g"],
    )
    resolver = StubResolver(
        name_results={"Ceftriaxon": _resolved("ceftriaxone")},
        line_results={"CT-1": _resolved("cefepime")},
    )
    (finding,) = check(ca, resolver)
    assert finding.ma_luat == "di_ung_cheo"
    assert finding.muc_do == "nghiem_trong"
    allergy_ids = {cc.ban_ghi_id for cc in finding.can_cu if cc.loai == "du_lieu"}
    assert {"DU-1", "DU-2", "CT-1"}.issubset(allergy_ids)


def test_group_alias_normalization_handles_case_whitespace_and_plural() -> None:
    config = load_allergy_config()
    assert config.resolve_group_alias("  SULFONAMID  ") is not None
    assert config.resolve_group_alias("Penicillins") is not None
    assert config.resolve_group_alias("NSAIDs") is not None


def test_registry_and_engine_forward_resolver_for_factor_1() -> None:
    ca = _pending_case(
        di_ung=[DiUng(di_ung_id="DU-1", tac_nhan="Penicillin", loai_tac_nhan="thuoc")],
        line_names=["Ceftriaxon 1 g"],
    )
    resolver = StubResolver(line_results={"CT-1": _resolved("ceftriaxone")})
    renal = load_renal_rules(ROOT / "data/kb/quy_tac_lieu_than.json")

    rule_findings = AllergyRule().check(ca, RuleContext(renal_rules=renal, resolver=resolver))
    engine_y1 = [f for f in run_rules(ca, renal, resolver=resolver) if f.yeu_to == 1]

    assert len(rule_findings) == 1
    assert rule_findings[0].ma_luat == "di_ung_cheo"
    assert engine_y1 == rule_findings
