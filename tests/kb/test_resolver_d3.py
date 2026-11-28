"""Kiểm tra sửa xung đột tên INN trên DrugResolver (Cephalexin, Paracetamol) ở D3."""

from collections import Counter, defaultdict
from pathlib import Path

import pytest

from app.db.reader import load_source_cases
from app.kb.resolver import DrugResolver
from app.kb.resolver.matching import IngredientNames
from app.kb.resolver.resolver import AxisIngredient

ROOT = Path(__file__).resolve().parents[2]


def _make_conflict_resolver() -> DrugResolver:
    """Tạo chỉ mục thu nhỏ mô phỏng tên INN có nhiều công thức DAV cùng tên gốc."""
    resolver = DrugResolver()
    resolver._axis = {
        "acetaminophen": AxisIngredient(
            ten_inn="paracetamol",
            ten_viet="Paracetamol",
            ma_atc=("N02BE",),
            loai="thuong",
            ddinter_id=None,
        ),
        "cephalexin": AxisIngredient(
            ten_inn="cephalexin",
            ten_viet="Cephalexin",
            ma_atc=("J01DB",),
            loai="thuong",
            ddinter_id=None,
        ),
        "caffeine": AxisIngredient(
            ten_inn="caffeine",
            ten_viet="Cafein",
            ma_atc=("N06BC",),
            loai="thuong",
            ddinter_id=None,
        ),
        "amoxicillin": AxisIngredient(
            ten_inn="amoxicillin",
            ten_viet="Amoxicillin",
            ma_atc=("J01CA",),
            loai="thuong",
            ddinter_id=None,
        ),
        "clavulanic_acid": AxisIngredient(
            ten_inn="clavulanic acid",
            ten_viet="Acid clavulanic",
            ma_atc=(),
            loai="thuong",
            ddinter_id=None,
        ),
    }
    resolver._names = IngredientNames(
        {identifier: row.ten_inn for identifier, row in resolver._axis.items()},
        [
            ("paracetamol", "acetaminophen", "inn"),
            ("cephalexin", "cephalexin", "inn"),
            ("ten trung cong thuc", "amoxicillin", "viet"),
            ("nhan hieu da cong thuc", "acetaminophen", "biet_duoc"),
        ],
    )
    resolver._case_codes = {}
    resolver._products = defaultdict(
        list,
        {
            "paracetamol": ["dav:p1", "dav:p2"],
            "cephalexin": ["dav:c1", "dav:c2"],
            "amoxicillin": ["dav:a1", "dav:a2"],
            "ten trung cong thuc": ["dav:x1", "dav:x2"],
            "nhan hieu da cong thuc": ["dav:b1", "dav:b2"],
        },
    )
    resolver._formulas = defaultdict(
        dict,
        {
            "dav:p1": {"acetaminophen": (500.0, "mg")},
            "dav:p2": {"acetaminophen": (500.0, "mg"), "caffeine": (65.0, "mg")},
            "dav:c1": {"cephalexin": (500.0, "mg")},
            "dav:c2": {"cephalexin": (500.0, "mg"), "clavulanic_acid": (125.0, "mg")},
            "dav:a1": {"amoxicillin": (250.0, "mg")},
            "dav:a2": {"amoxicillin": (500.0, "mg")},
            "dav:x1": {"amoxicillin": (500.0, "mg")},
            "dav:x2": {"clavulanic_acid": (125.0, "mg")},
            "dav:b1": {"acetaminophen": (500.0, "mg")},
            "dav:b2": {"acetaminophen": (500.0, "mg"), "caffeine": (65.0, "mg")},
        },
    )
    return resolver


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("Cephalexin", "cephalexin"),
        ("Cephalexin 500 mg", "cephalexin"),
        ("Paracetamol", "acetaminophen"),
        ("Paracetamol 500 mg", "acetaminophen"),
        ("Paracetamol 250 mg/5 mL", "acetaminophen"),
    ],
)
def test_canonical_inn_resolves_when_dav_key_has_multiple_formulas(
    query: str, expected_id: str
) -> None:
    resolver = _make_conflict_resolver()
    result = resolver.resolve_name(query)
    assert result.trang_thai == "da_phan_giai"
    assert [tp.hoat_chat_id for tp in result.thanh_phan] == [expected_id]
    assert result.nguon_khop == "dong_nghia"


@pytest.mark.parametrize(
    "query",
    [
        "Paracetamol 500/65",
        "Paracetamol 500 mg/65 mg",
        "Tên trùng công thức 10 mg",
        "Nhãn hiệu đa công thức 500 mg",
    ],
)
def test_genuine_product_conflicts_remain_unresolved(query: str) -> None:
    resolver = _make_conflict_resolver()
    result = resolver.resolve_name(query)
    assert result.trang_thai == "khong_nhan_dien"
    assert result.ly_do == "tên ứng với nhiều công thức"


def test_same_ingredient_different_strengths_in_dav_resolves() -> None:
    resolver = _make_conflict_resolver()
    result = resolver.resolve_name("Amoxicillin")
    assert result.trang_thai == "da_phan_giai"
    assert [tp.hoat_chat_id for tp in result.thanh_phan] == ["amoxicillin"]
    assert result.nguon_khop == "ten_thuoc_dav"


def test_combination_with_paracetamol_resolves_both_parts() -> None:
    resolver = _make_conflict_resolver()
    result = resolver.resolve_name("Paracetamol + Caffeine")
    assert result.trang_thai == "da_phan_giai"
    assert sorted(tp.hoat_chat_id for tp in result.thanh_phan) == [
        "acetaminophen",
        "caffeine",
    ]
    assert result.nguon_khop == "tach_phoi_hop"


@pytest.mark.can_du_lieu("data/kb_curated/tra_cuu/tra_cuu.sqlite")
def test_real_index_resolves_cephalexin_paracetamol_and_keeps_66_case_counts() -> None:
    resolver = DrugResolver.from_index(ROOT / "data/kb_curated/tra_cuu/tra_cuu.sqlite")

    ceph = resolver.resolve_name("Cephalexin")
    assert ceph.trang_thai == "da_phan_giai"
    assert [tp.hoat_chat_id for tp in ceph.thanh_phan] == ["cephalexin"]

    para = resolver.resolve_name("Paracetamol")
    assert para.trang_thai == "da_phan_giai"
    assert [tp.hoat_chat_id for tp in para.thanh_phan] == ["acetaminophen"]

    cefa = resolver.resolve_name("Cefalexin")
    assert cefa.trang_thai == "da_phan_giai"
    assert [tp.hoat_chat_id for tp in cefa.thanh_phan] == ["cephalexin"]

    cases = load_source_cases(ROOT)
    assert len(cases) == 66
    counts: Counter[str] = Counter()
    for ca in cases:
        for line in (*ca.y_lenh_cho_duyet.chi_tiet, *ca.thuoc_dang_dung):
            counts[resolver.resolve_line(ca, line).trang_thai] += 1

    assert counts["da_phan_giai"] == 117
    assert counts["khong_ap_dung"] == 47
    assert counts["khong_nhan_dien"] == 3
    assert counts["mot_phan"] == 0
