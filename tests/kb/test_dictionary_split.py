"""Kiểm tra tách tên có muối, phối hợp và hàm lượng."""

import json
from pathlib import Path

import pytest

from app.kb.dictionary.split import split_components


@pytest.mark.parametrize(
    ("original", "strength", "expected"),
    [
        ("Amoxicilin (dưới dạng Amoxicilin trihydrat)", "500 mg", [("amoxicilin", 500, "mg")]),
        ("Amoxicillin (as amoxicillin sodium)", None, [("amoxicillin", None, None)]),
        (
            "Sulfamethoxazol 800mg; Trimethoprim 160mg",
            None,
            [("sulfamethoxazol", 800, "mg"), ("trimethoprim", 160, "mg")],
        ),
        (
            "Amoxicilin (dưới dạng Amoxicilin trihydrat) 875mg; "
            "Acid clavulanic (dưới dạng Kali clavulanat) 125mg",
            "875mg; 125mg",
            [("amoxicilin", 875, "mg"), ("acid clavulanic", 125, "mg")],
        ),
        (
            "Sulfamethoxazol/Trimethoprim",
            "800/160 mg",
            [("sulfamethoxazol", 800, "mg"), ("trimethoprim", 160, "mg")],
        ),
        (
            "Amoxicilin, Acid clavulanic",
            "875mg, 125mg",
            [("amoxicilin", 875, "mg"), ("acid clavulanic", 125, "mg")],
        ),
        (
            "Cefoperazon + Sulbactam",
            "1 g",
            [("cefoperazon", None, None), ("sulbactam", None, None)],
        ),
        (
            "Piperacilin và Tazobactam",
            None,
            [("piperacilin", None, None), ("tazobactam", None, None)],
        ),
        (
            "Paracetamol; Cafein; Codein phosphat",
            None,
            [("paracetamol", None, None), ("cafein", None, None), ("codein", None, None)],
        ),
        ("Ceftriaxon natri tương đương với Ceftriaxon 1 g", None, [("ceftriaxon", 1, "g")]),
        ("Ceftriaxon natri (tương đương Ceftriaxon 1 g)", None, [("ceftriaxon", 1, "g")]),
        ("Ceftriaxone sodium eq. to Ceftriaxone 1 g", None, [("ceftriaxone", 1, "g")]),
        ("Natri clorid 0,9%", None, [("natri clorid", 0.9, "%")]),
        ("Sodium chloride USP", "0.9 %", [("sodium chloride", 0.9, "%")]),
        ("Kali clorid", "10 mg/ml", [("kali clorid", 10, "mg/ml")]),
        ("Magnesi sulfat", None, [("magnesi sulfat", None, None)]),
        ("Ferrous sulfate", None, [("ferrous sulfate", None, None)]),
        ("Ceftriaxon (USP 2020)", "1g", [("ceftriaxon", 1, "g")]),
        ("Metoprolol tartrat BP 2022", None, [("metoprolol", None, None)]),
        ("Gentamicin sulfat (DĐVN V)", None, [("gentamicin", None, None)]),
        ("Ciprofloxacin Ph.Eur. 2020", None, [("ciprofloxacin", None, None)]),
        ("Amikacin (JP)", None, [("amikacin", None, None)]),
        ("Meropenem EP", None, [("meropenem", None, None)]),
        ("Amlodipin besilat", "5 mg", [("amlodipin", 5, "mg")]),
        ("Insulin glargine", "100 IU/ml", [("insulin glargine", 100, "IU/ml")]),
        ("Amlodipin (dưới dạng Amlodipin besilat, USP)", None, [("amlodipin", None, None)]),
        ("Morphin (dưới dạng morphin sulfat/hydrat)", None, [("morphin", None, None)]),
        ("Azithromycin", "200 mg/5 mL", [("azithromycin", 200, "mg/5mL")]),
        ("Vitamin B12", "5 µg", [("vitamin b12", 5, "µg")]),
        ("Paracetamol 500mg", "250 mg", [("paracetamol", None, None)]),
        # Trường hoạt chất và hàm lượng hiển thị trên trang công bố DAV.
        ("Prolgolimab", "100mg/5 ml", [("prolgolimab", 100, "mg/5ml")]),
    ],
)
def test_split_known(original: str, strength: str | None, expected: list[tuple]) -> None:
    """Chỉ lấy hàm lượng khi có căn cứ cho mỗi thành phần."""
    result = split_components(original, strength)
    assert result.trang_thai == "tach_duoc", result.ly_do
    assert [(c.ten_chuan_hoa, c.ham_luong, c.don_vi) for c in result.thanh_phan] == expected


@pytest.mark.parametrize(
    ("original", "reason", "kind"),
    [
        (None, "thieu_hoat_chat_goc", "thuoc"),
        ("Amoxicilin (dưới dạng", "ngoac_khong_can_bang", "thuoc"),
        ("Amoxicilin;", "ten_thanh_phan_khong_ro", "thuoc"),
        ("Tá dược vừa đủ", "ten_thanh_phan_khong_ro", "thuoc"),
        ("Amoxicilin tương đương Ceftriaxon 500 mg", "tuong_duong_khong_ro", "thuoc"),
        ("Cao khô Radix Angelicae; Herba Menthae", "duoc_lieu_can_duyet", "duoc_lieu"),
        ("Vắc-xin (không rõ)", "ten_thanh_phan_khong_ro", "sinh_pham"),
    ],
)
def test_split_review(original: str | None, reason: str, kind: str) -> None:
    result = split_components(original, None)
    assert (result.trang_thai, result.ly_do, result.loai_san_pham) == ("chua_khop", reason, kind)
    assert not result.thanh_phan


def test_preserves_salt_and_marks_vaccine() -> None:
    result = split_components("Amoxicilin (dưới dạng Amoxicilin trihydrat)", None)
    assert result.thanh_phan[0].dang_muoi == "Amoxicilin trihydrat"
    assert split_components("Kháng nguyên viêm gan B", None).loai_san_pham == "sinh_pham"


@pytest.mark.parametrize(
    ("key", "original", "strength", "base", "value", "unit"),
    [
        ("acetaminophen", "ACETAMINOPHEN", "10 mg/mL", "acetaminophen", 10, "mg/mL"),
        ("acyclovir", "ACYCLOVIR SODIUM", "50 mg/mL", "acyclovir", 50, "mg/mL"),
        ("amikacin", "AMIKACIN SULFATE", "250 mg/mL", "amikacin", 250, "mg/mL"),
        ("amiodarone", "AMIODARONE HYDROCHLORIDE", "1.5 mg/mL", "amiodarone", 1.5, "mg/mL"),
        ("cefepime", "CEFEPIME HYDROCHLORIDE", "1 g/50mL", "cefepime", 1, "g/50mL"),
        ("ciprofloxacin", "CIPROFLOXACIN", "2 mg/mL", "ciprofloxacin", 2, "mg/mL"),
        ("digoxin", "DIGOXIN", "100 ug/mL", "digoxin", 100, "ug/mL"),
        ("enalapril", "ENALAPRIL MALEATE", "1 mg/mL", "enalapril", 1, "mg/mL"),
        ("enoxaparin", "ENOXAPARIN SODIUM", "100 mg/mL", "enoxaparin", 100, "mg/mL"),
        ("fentanyl", "FENTANYL CITRATE", "50 ug/mL", "fentanyl", 50, "ug/mL"),
        ("fluconazole", "FLUCONAZOLE", "10 mg/mL", "fluconazole", 10, "mg/mL"),
        ("furosemide", "FUROSEMIDE", "30 mg/mL", "furosemide", 30, "mg/mL"),
        ("gentamicin", "GENTAMICIN SULFATE", "3 mg/mL", "gentamicin", 3, "mg/mL"),
        ("ibuprofen", "IBUPROFEN", "800 mg/200mL", "ibuprofen", 800, "mg/200mL"),
        ("ketorolac", "KETOROLAC TROMETHAMINE", "15 mg/mL", "ketorolac", 15, "mg/mL"),
        ("levetiracetam", "LEVETIRACETAM", "10 mg/mL", "levetiracetam", 10, "mg/mL"),
        ("levofloxacin", "LEVOFLOXACIN", "25 mg/mL", "levofloxacin", 25, "mg/mL"),
        ("linezolid", "LINEZOLID", "100 mg/5mL", "linezolid", 100, "mg/5mL"),
        ("losartan", "LOSARTAN POTASSIUM", "10 mg/mL", "losartan", 10, "mg/mL"),
        ("meropenem", "MEROPENEM", "1 g/30mL", "meropenem", 1, "g/30mL"),
        ("methotrexate", "METHOTREXATE SODIUM", "25 mg/mL", "methotrexate", 25, "mg/mL"),
        ("metoprolol_tartrate", "METOPROLOL TARTRATE", "1 mg/mL", "metoprolol", 1, "mg/mL"),
        ("morphine", "MORPHINE SULFATE", "1 mg/mL", "morphine", 1, "mg/mL"),
        ("phenytoin", "PHENYTOIN SODIUM", "50 mg/mL", "phenytoin", 50, "mg/mL"),
        ("spironolactone", "SPIRONOLACTONE", "25 mg/5mL", "spironolactone", 25, "mg/5mL"),
        ("tramadol", "TRAMADOL HYDROCHLORIDE", "5 mg/mL", "tramadol", 5, "mg/mL"),
        ("valproate", "VALPROATE SODIUM", "100 mg/mL", "valproate", 100, "mg/mL"),
    ],
)
def test_split_real_ndc(
    key: str, original: str, strength: str, base: str, value: float, unit: str
) -> None:
    """Đối chiếu cặp tên và hàm lượng với bản openFDA NDC có sẵn trong kho."""
    source = Path(__file__).resolve().parents[2] / "data/kb_sources/openfda_ndc" / f"{key}.json"
    products = json.loads(source.read_bytes())["san_pham"]
    assert {"hoat_chat": original, "ham_luong": strength} in [
        part for product in products for part in product["ham_luong"]
    ]
    result = split_components(original, strength)
    assert result.trang_thai == "tach_duoc"
    assert [(c.ten_chuan_hoa, c.ham_luong, c.don_vi) for c in result.thanh_phan] == [
        (base, value, unit)
    ]


def test_split_accepts_decomposed_unicode() -> None:
    """Văn bản thật của Cục Quản lý Dược dùng dấu tổ hợp (NFD)."""
    import unicodedata

    text = unicodedata.normalize("NFD", "Cefixime (dưới dạng Cefixime trihydrate USP 224mg)")
    result = split_components(text, "200mg")
    assert result.trang_thai == "tach_duoc"
    assert [(c.ten_chuan_hoa, c.ham_luong) for c in result.thanh_phan] == [("cefixime", 200)]


@pytest.mark.parametrize(
    ("original", "strength", "expected"),
    [
        (
            "Mỗi viên nén bao phim chứa: Ethinylestradiol 0,02mg; Desogestrel 0,150mg",
            None,
            [("ethinylestradiol", 0.02, "mg"), ("desogestrel", 0.15, "mg")],
        ),
        ("Mỗi gói 3g chứa: Ibuprofen 100mg", "100mg", [("ibuprofen", 100, "mg")]),
        ("Lọ 12ml chứa: Natri clorid 34,8mg", None, [("natri clorid", 34.8, "mg")]),
    ],
)
def test_split_strips_container_prefix(
    original: str, strength: str | None, expected: list[tuple[str, float | None, str | None]]
) -> None:
    result = split_components(original, strength)
    assert result.trang_thai == "tach_duoc"
    assert [(c.ten_chuan_hoa, c.ham_luong, c.don_vi) for c in result.thanh_phan] == expected


def test_split_equivalent_same_base_and_duplicates() -> None:
    result = split_components("Ceftriaxone natri tương đương Ceftriaxone", "1g")
    assert [(c.ten_chuan_hoa, c.dang_muoi, c.ham_luong, c.don_vi) for c in result.thanh_phan] == [
        ("ceftriaxone", "natri", 1, "g")
    ]
    gam = split_components("Ceftriaxone (dưới dạng Ceftriaxon natri hydrat)", "1 gam")
    assert (gam.thanh_phan[0].ham_luong, gam.thanh_phan[0].don_vi) == (1, "g")
    dup = split_components(
        "Amoxicillin trihydrate, Amoxicillin Sodium; Potassium  clavulanate", "1000mg; 62,5mg"
    )
    assert (dup.trang_thai, dup.ly_do) == ("chua_khop", "thanh_phan_trung_lap")


def test_split_strength_in_parentheses() -> None:
    result = split_components(
        "Lansoprazole (30mg); Tinidazole (500mg); Clarithromycin (250mg)", "30mg; 500mg; 250mg"
    )
    assert [(c.ten_chuan_hoa, c.ham_luong) for c in result.thanh_phan] == [
        ("lansoprazole", 30),
        ("tinidazole", 500),
        ("clarithromycin", 250),
    ]
