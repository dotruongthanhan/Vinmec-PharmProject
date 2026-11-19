"""Kiểm yếu tố 2 trên trục hoạt chất, ATC và các bất biến thiếu dữ liệu."""

from pathlib import Path

import pytest

from app.config.settings import load_settings
from app.container import Container
from app.domain.models import CaBenh, ChiTietYLenh, HoatChat, ThanhPhan, Thuoc
from app.kb.resolver import DrugResolver
from app.kb.resolver.resolver import KetQuaPhanGiai, ThanhPhanPhanGiai
from app.rules.duplicate import check
from app.rules.duplicate_config import DuplicateConfig, load_duplicate_config
from app.rules.registry import DuplicateRule, RuleContext
from tests.rules import NOW, make_minimal_case

ROOT = Path(__file__).resolve().parents[2]


class StaticResolver(DrugResolver):
    """Trả kết quả cố định, lỗi ngay nếu luật xét dòng ngoài hiệu lực."""

    def __init__(self, *results: KetQuaPhanGiai) -> None:
        self.results = {f"CT-{i}": result for i, result in enumerate(results, 1)}

    def resolve_line(self, ca: CaBenh, line: ChiTietYLenh) -> KetQuaPhanGiai:
        return self.results[line.chi_tiet_y_lenh_id]


def component(identifier: str, *codes: str, kind: str = "thuong") -> ThanhPhanPhanGiai:
    """Tạo thành phần giả lập trên trục, không suy thêm mã ATC."""
    return ThanhPhanPhanGiai(
        hoat_chat_id=identifier,
        ten_inn=identifier,
        ten_viet=None,
        ma_atc=list(codes),
        ddinter_id=None,
        loai=kind,
    )


def resolved(*rows: ThanhPhanPhanGiai) -> KetQuaPhanGiai:
    return KetQuaPhanGiai(trang_thai="da_phan_giai", thanh_phan=list(rows))


def case_with_names(*names: str) -> CaBenh:
    return make_minimal_case(
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id=f"CT-{i}",
                ten_tu_do=name,
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
            for i, name in enumerate(names, 1)
        ]
    )


@pytest.mark.parametrize(
    ("a", "code_a", "b", "code_b", "group", "level"),
    [
        ("enalapril", "C09AA", "losartan", "C09CA", "uc_che_ras", "nghiem_trong"),
        ("omeprazole", "A02BC", "esomeprazole", "A02BC", "ppi", "can_luu_y"),
        ("enoxaparin", "B01AB", "rivaroxaban", "B01AF", "chong_dong", "nghiem_trong"),
        ("ketorolac", "M01AB", "ibuprofen", "M01AE", "nsaid", "nghiem_trong"),
        ("h2_a", "A02BA", "h2_b", "A02BA", "khang_h2", "can_luu_y"),
        ("statin_a", "C10AA", "statin_b", "C10AA", "statin", "can_luu_y"),
        ("benzo_a", "N05BA", "benzo_b", "N05CD", "benzodiazepin", "can_luu_y"),
        ("sulfonylure_a", "A10BB", "sulfonylure_b", "A10BB", "sulfonylure", "can_luu_y"),
    ],
)
def test_configured_groups(
    a: str, code_a: str, b: str, code_b: str, group: str, level: str
) -> None:
    ca = case_with_names(a, b)
    resolver = StaticResolver(resolved(component(a, code_a)), resolved(component(b, code_b)))
    (finding,) = check(ca, resolver)
    assert (finding.ma_luat, finding.ket_luan, finding.muc_do) == (
        "trung_nhom_dieu_tri",
        "can_xem",
        level,
    )
    assert finding.chi_tiet_y_lenh_id == ["CT-1", "CT-2"]
    assert "kiểm lịch ngừng thuốc cũ" in finding.mo_ta
    assert finding.can_cu[-1].ban_ghi_id == group
    assert code_a in finding.can_cu[0].mo_ta
    assert code_b in finding.can_cu[1].mo_ta
    assert "phân loại ATC của WHO" in finding.can_cu[-1].mo_ta
    assert "chờ dược sĩ duyệt bảng nhóm" in finding.can_cu[-1].mo_ta


def test_augmentin_and_amoxicillin_use_axis_instead_of_case_codes() -> None:
    ctx = Container(load_settings("test")).rule_context
    assert ctx.resolver is not None
    ca = make_minimal_case(
        danh_muc_hoat_chat=[
            HoatChat(hoat_chat_id="HC-AUG-AMO", ten_hoat_chat="Amoxicillin"),
            HoatChat(hoat_chat_id="HC-AUG-CLA", ten_hoat_chat="Clavulanic acid"),
            HoatChat(hoat_chat_id="HC-AMO", ten_hoat_chat="Amoxicillin"),
        ],
        danh_muc_thuoc=[
            Thuoc(
                thuoc_id="AUG",
                ten_thuoc="Augmentin",
                thanh_phan=[
                    ThanhPhan(hoat_chat_id="HC-AUG-AMO"),
                    ThanhPhan(hoat_chat_id="HC-AUG-CLA"),
                ],
            ),
            Thuoc(
                thuoc_id="AMO",
                ten_thuoc="Amoxicillin 500 mg",
                thanh_phan=[ThanhPhan(hoat_chat_id="HC-AMO")],
            ),
        ],
        chi_tiet=[
            ChiTietYLenh(
                chi_tiet_y_lenh_id=f"CT-{i}",
                thuoc_id=drug,
                bat_dau=NOW,
                trang_thai_dong="pending",
            )
            for i, drug in enumerate(["AUG", "AMO"], 1)
        ],
    )
    assert check(ca)[0].ket_luan == "dat"
    (finding,) = DuplicateRule().check(ca, ctx)
    assert finding.ma_luat == "trung_hoat_chat"
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"
    assert finding.mo_ta == "Trùng hoạt chất amoxicillin ở 2 dòng đang hiệu lực"
    assert "Augmentin" in finding.can_cu[0].mo_ta
    assert "Amoxicillin 500 mg" in finding.can_cu[1].mo_ta


@pytest.mark.parametrize("other_code", ["M02AA", "C01EB", "M01AX", "B01AX"])
def test_ibuprofen_secondary_codes_and_excluded_prefixes_do_not_form_groups(
    other_code: str,
) -> None:
    ca = case_with_names("Ibuprofen", "Thuốc giả lập")
    resolver = StaticResolver(
        resolved(component("ibuprofen", "C01EB", "G02CC", "M01AE", "M02AA", "R02AX")),
        resolved(component("other", other_code)),
    )
    (finding,) = check(ca, resolver)
    assert finding.ket_luan == "dat"
    assert finding.mo_ta == (
        "Đã đối chiếu 2 dòng thuốc đang hiệu lực (2 hoạt chất) theo 8 nhóm điều trị: "
        "không có trùng hoạt chất hay trùng nhóm."
    )


def test_ibuprofen_only_matching_nsaid_code_is_cited() -> None:
    ca = case_with_names("Ketorolac", "Ibuprofen")
    resolver = StaticResolver(
        resolved(component("ketorolac", "M01AB")),
        resolved(component("ibuprofen", "C01EB", "G02CC", "M01AE", "M02AA", "R02AX")),
    )
    (finding,) = check(ca, resolver)
    assert finding.can_cu[-1].ban_ghi_id == "nsaid"
    assert "M01AE" in finding.mo_ta
    assert "C01EB" not in finding.mo_ta
    assert "M02AA" not in finding.mo_ta


@pytest.mark.parametrize("code", ["B01AX05", "B01AX"])
def test_anticoagulant_prefix_requires_the_configured_specificity(code: str) -> None:
    ca = case_with_names("Heparin", "Thuốc giả lập")
    resolver = StaticResolver(
        resolved(component("heparin", "B01AB", "C05BA", "S01XA")),
        resolved(component("other", code)),
    )
    (finding,) = check(ca, resolver)
    if code == "B01AX05":
        assert finding.ma_luat == "trung_nhom_dieu_tri"
        assert finding.can_cu[-1].ban_ghi_id == "chong_dong"
        assert "C05BA" not in finding.mo_ta
        assert "S01XA" not in finding.mo_ta
    else:
        assert finding.ket_luan == "dat"


def test_same_ingredient_does_not_also_trigger_group() -> None:
    ca = case_with_names("Omeprazole A", "Omeprazole B")
    row = resolved(component("omeprazole", "A02BC"))
    (finding,) = check(ca, StaticResolver(row, row))
    assert finding.ma_luat == "trung_hoat_chat"


def test_components_of_one_combination_are_not_compared() -> None:
    ca = case_with_names("Phối hợp giả lập")
    resolver = StaticResolver(
        resolved(component("enalapril", "C09AA"), component("losartan", "C09CA"))
    )
    assert check(ca, resolver)[0].ket_luan == "dat"


@pytest.mark.parametrize("reverse", [False, True])
def test_group_exception_is_symmetric_and_cited_in_pass(reverse: bool) -> None:
    config = load_duplicate_config()
    groups = [
        group.model_copy(update={"ngoai_le": [("omeprazole", "esomeprazole")]})
        if group.ma_nhom == "ppi"
        else group
        for group in config.nhom_dieu_tri.nhom
    ]
    config = config.model_copy(
        update={"nhom_dieu_tri": config.nhom_dieu_tri.model_copy(update={"nhom": groups})}
    )
    names = ["omeprazole", "esomeprazole"]
    if reverse:
        names.reverse()
    ca = case_with_names(*names)
    resolver = StaticResolver(*(resolved(component(name, "A02BC")) for name in names))
    (finding,) = check(ca, resolver, config)
    assert finding.ket_luan == "dat"
    assert any("Ngoại lệ nhóm PPI" in note.mo_ta for note in finding.can_cu)
    assert any("omeprazole" in note.mo_ta for note in finding.can_cu)
    assert any("esomeprazole" in note.mo_ta for note in finding.can_cu)


@pytest.mark.parametrize("status", ["khong_nhan_dien", "mot_phan"])
def test_unresolved_or_partial_active_line_prevents_pass(status: str) -> None:
    ca = case_with_names("Oresol", "Omeprazole")
    ca.thuoc_dang_dung = [ca.y_lenh_cho_duyet.chi_tiet.pop(0)]
    result = KetQuaPhanGiai.model_validate(
        {
            "trang_thai": status,
            "ly_do": "Thiếu thành phần giả lập",
            "thanh_phan": [component("known", "A02BC")] if status == "mot_phan" else [],
        }
    )
    resolver = StaticResolver(result, resolved(component("omeprazole", "A02BC")))
    if status == "mot_phan":
        resolver.results["CT-1"].thanh_phan = [component("known", "N03AG")]
    (finding,) = check(ca, resolver)
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None
    assert finding.chi_tiet_y_lenh_id == ["CT-1"]
    assert "Oresol" in finding.mo_ta
    assert finding.thong_tin_con_thieu == ["CT-1.hoat_chat_id"]


def test_all_normal_components_without_atc_prevent_pass() -> None:
    (finding,) = check(case_with_names("Thuốc giả lập"), StaticResolver(resolved(component("x"))))
    assert finding.ket_luan == "khong_du_du_lieu"
    assert "x thiếu ma_atc" in finding.mo_ta
    assert finding.thong_tin_con_thieu == ["CT-1.x.ma_atc"]


def test_combination_with_one_atc_is_sufficient_and_notes_missing_component() -> None:
    result = resolved(component("amoxicillin", "J01CA"), component("clavulanic_acid"))
    (finding,) = check(case_with_names("Augmentin"), StaticResolver(result))
    assert finding.ket_luan == "dat"
    assert any("clavulanic_acid thiếu ma_atc" in note.mo_ta for note in finding.can_cu)


@pytest.mark.parametrize("kind", ["dich_truyen_dien_giai", "duoc_lieu"])
@pytest.mark.parametrize("status", ["khong_ap_dung", "da_phan_giai"])
def test_excluded_lines_or_herbs_do_not_prevent_pass(kind: str, status: str) -> None:
    result = KetQuaPhanGiai.model_validate(
        {
            "trang_thai": status,
            "thanh_phan": [component("excluded", kind=kind)],
        }
    )
    (finding,) = check(case_with_names("Dòng không áp dụng"), StaticResolver(result))
    assert finding.ket_luan == "dat"
    assert any("không áp dụng" in note.mo_ta for note in finding.can_cu)


def test_atc_supplement_prevents_missing_and_does_not_mutate_resolver() -> None:
    row = component("valproic_acid")
    (finding,) = check(case_with_names("Valproic acid"), StaticResolver(resolved(row)))
    assert finding.ket_luan == "dat"
    assert row.ma_atc == []
    assert any(
        "N03AG" in note.mo_ta
        and "WHO ATC/DDD Index, N03AG01" in note.mo_ta
        and "chờ Claude kiểm" in note.mo_ta
        for note in finding.can_cu
    )


def test_missing_data_does_not_hide_a_positive_finding() -> None:
    resolver = StaticResolver(
        resolved(component("omeprazole", "A02BC")),
        resolved(component("esomeprazole", "A02BC")),
        KetQuaPhanGiai(trang_thai="khong_nhan_dien"),
    )
    (finding,) = check(case_with_names("Omeprazole", "Esomeprazole", "Oresol"), resolver)
    assert finding.ket_luan == "can_xem"
    assert any("Oresol chưa nhận diện" in note.mo_ta for note in finding.can_cu)


@pytest.mark.parametrize("status", ["discontinued", "completed"])
def test_inactive_lines_are_not_resolved(status: str) -> None:
    ca = case_with_names("Omeprazole", "Esomeprazole")
    inactive = ca.y_lenh_cho_duyet.chi_tiet.pop()
    inactive.trang_thai_dong = status
    ca.thuoc_dang_dung = [inactive]
    resolver = StaticResolver(resolved(component("omeprazole", "A02BC")))
    assert check(ca, resolver)[0].ket_luan == "dat"


def test_group_pair_needs_one_pending_line() -> None:
    ca = case_with_names("Khác", "Omeprazole", "Esomeprazole")
    ca.thuoc_dang_dung = ca.y_lenh_cho_duyet.chi_tiet[1:]
    ca.y_lenh_cho_duyet.chi_tiet = ca.y_lenh_cho_duyet.chi_tiet[:1]
    resolver = StaticResolver(
        resolved(component("other", "N03AG")),
        resolved(component("omeprazole", "A02BC")),
        resolved(component("esomeprazole", "A02BC")),
    )
    assert check(ca, resolver)[0].ket_luan == "dat"


def test_missing_resolver_keeps_legacy_free_text_behavior() -> None:
    ca = case_with_names("Không nhận diện")
    assert check(ca)[0].mo_ta == "Không có hoạt chất trùng lặp trong các dòng thuốc đang hiệu lực"
    ctx = Container(load_settings("test")).rule_context
    assert DuplicateRule().check(ca, RuleContext(ctx.renal_rules)) == check(ca)


def test_config_loads_through_shared_reader(tmp_path: Path) -> None:
    for name in ["nhom_dieu_tri_trung.yaml", "atc_bo_sung.yaml"]:
        (tmp_path / name).write_bytes((ROOT / "config/kb" / name).read_bytes())
    config: DuplicateConfig = load_duplicate_config(tmp_path)
    assert len(config.nhom_dieu_tri.nhom) == 8
    assert config.atc_bo_sung.ma_atc == {"valproic_acid": ["N03AG"]}
    assert config.nhom_dieu_tri.trang_thai == "cho_duoc_si_duyet"
