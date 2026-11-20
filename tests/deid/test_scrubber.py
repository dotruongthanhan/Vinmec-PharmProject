"""Kiểm tra các quy tắc che định danh của brief T08."""

from typing import NoReturn

import pytest

from app.deid import scrubber
from app.deid.scrubber import DeidError, restore_text, scrub_text


@pytest.mark.parametrize(
    ("text", "kind", "original", "expected"),
    [
        ("Liên hệ a.b@example.org", "EMAIL", "a.b@example.org", "Liên hệ [EMAIL_1]"),
        ("Email test+deid@example.org", "EMAIL", "test+deid@example.org", "Email [EMAIL_1]"),
        ("Thẻ BHYT DN4010123456789", "BHYT", "DN4010123456789", "Thẻ BHYT [BHYT_1]"),
        ("Thẻ dn4010123456789", "BHYT", "dn4010123456789", "Thẻ [BHYT_1]"),
        ("CCCD 001099012345", "CCCD", "001099012345", "CCCD [CCCD_1]"),
        ("CCCD 002088123456", "CCCD", "002088123456", "CCCD [CCCD_1]"),
        ("sđt 0912 345 678", "SDT", "0912 345 678", "sđt [SDT_1]"),
        ("sđt +84912345678", "SDT", "+84912345678", "sđt [SDT_1]"),
        ("sđt 84912345678", "SDT", "84912345678", "sđt [SDT_1]"),
        ("sđt 03.1234.5678", "SDT", "03.1234.5678", "sđt [SDT_1]"),
        ("sđt 05-1234-5678", "SDT", "05-1234-5678", "sđt [SDT_1]"),
        ("sđt 07 1234 5678", "SDT", "07 1234 5678", "sđt [SDT_1]"),
        ("sđt 0812345678", "SDT", "0812345678", "sđt [SDT_1]"),
        ("HN 123456789", "HN", "123456789", "HN [HN_1]"),
        ("HN 234567891", "HN", "234567891", "HN [HN_1]"),
        ("Vào viện 05/11/2026", "NGAY", "05/11/2026", "Vào viện [NGAY_1]"),
        ("Tái khám 12-11-2026", "NGAY", "12-11-2026", "Tái khám [NGAY_1]"),
        ("Ngày 31.12.2026", "NGAY", "31.12.2026", "Ngày [NGAY_1]"),
        ("Ngày 5/11", "NGAY", "5/11", "Ngày [NGAY_1]"),
        ("Ngày 5/10", "NGAY", "5/10", "Ngày [NGAY_1]"),
        ("Ngày 05/11-2026", "NGAY", "05/11", "Ngày [NGAY_1]-2026"),
        ("BS Nguyễn Văn An", "TEN", "Nguyễn Văn An", "BS [TEN_1]"),
        ("BS An", "TEN", "An", "BS [TEN_1]"),
        ("BN Trần Thị Bình", "TEN", "Trần Thị Bình", "BN [TEN_1]"),
        ("ĐD Đỗ Ánh", "TEN", "Đỗ Ánh", "ĐD [TEN_1]"),
        ("DS Lê Thị Mỹ Duyên", "TEN", "Lê Thị Mỹ Duyên", "DS [TEN_1]"),
        (
            "BN Nguye\u0302\u0303n Va\u0306n An",
            "TEN",
            "Nguye\u0302\u0303n Va\u0306n An",
            "BN [TEN_1]",
        ),
        ("BS:\u00a0Nguyễn Văn An", "TEN", "Nguyễn Văn An", "BS:\u00a0[TEN_1]"),
        ("BN:Nguyễn Văn An", "TEN", "Nguyễn Văn An", "BN:[TEN_1]"),
    ],
)
def test_scrubs_each_identifier(text: str, kind: str, original: str, expected: str) -> None:
    result = scrub_text(text)

    assert result.van_ban == expected
    assert [(item.loai, item.ma_tam) for item in result.thay_the] == [(kind, f"[{kind}_1]")]
    assert result.anh_xa == {f"[{kind}_1]": original}
    assert restore_text(result.van_ban, result.anh_xa) == text


@pytest.mark.parametrize(
    "text",
    [
        "Email a.b@example",
        "Thẻ DN40101234567890",
        "CCCD 0010990123456",
        "Số 0001234567890",
        "sđt 0612345678",
        "HN 12345678",
        "HN 1234567890",
        "Huyết áp 120/80 mmHg, creatinin 212 umol/L, K 4.5",
        "bệnh nhân sốt cao, ăn kém",
        "Nguyễn Văn An hội chẩn",
        "Ngày 32/12/2026",
        "Ngày 12/13/2026",
        "Ngày 00/11/2026",
        "Ngày 12/00/2026",
        "Ngày 05/11/20266",
        "Số 15/110 và 15/11/2",
        "Số 1.5/10 và 5/10.5",
        "Số 1,5/10 và 5/10,5",
        "Số /5/10 và 5/10/",
        "Na 0.123456789 mmol/L",
        "K 1.001099012345 mmol/L",
        "Giá trị 123456789.5 và 001099012345,5",
        "BSNguyễn Văn An",
    ],
)
def test_preserves_non_identifiers_and_clinical_numbers(text: str) -> None:
    result = scrub_text(text)

    assert result.van_ban == text
    assert result.thay_the == []
    assert result.anh_xa == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("báo BS lúc 5/11, CCCD 001099012345", "báo BS lúc [NGAY_1], CCCD [CCCD_1]"),
        ("BS. Đức khám lúc 5/11.", "BS. [TEN_1] khám lúc [NGAY_1]."),
        ("chị Hoa nhà ở Hà Nội", "chị [TEN_1] nhà ở Hà Nội"),
        ("anh Nam đau bụng", "anh [TEN_1] đau bụng"),
        ("liều 1/2 viên; tỉ lệ 3/4", "liều 1/2 viên; tỉ lệ 3/4"),
        ("uống 1/2 viên ngày 5/11", "uống 1/2 viên ngày [NGAY_1]"),
        ("mạch 123456789 mmHg", "mạch 123456789 mmHg"),
        ("tiểu cầu 150000000 /L, HN 123456789", "tiểu cầu 150000000 /L, HN [HN_1]"),
        (
            "ngày 5/11; 6/11: sốt (7/11)",
            "ngày [NGAY_1]; [NGAY_2]: sốt ([NGAY_3])",
        ),
        ("tỉ số 5/11,5", "tỉ số 5/11,5"),
        ("BN Nam, 65 tuổi", "BN Nam, 65 tuổi"),
        ("bệnh nhân Nữ 40 tuổi", "bệnh nhân Nữ 40 tuổi"),
        ("HBV DNA 123456789 IU/mL", "HBV DNA 123456789 IU/mL"),
        ("mã 123456789 mgx", "mã [HN_1] mgx"),
        ("tỷ lệ: 3/4", "tỷ lệ: 3/4"),
        ("dùng 1/2 ống", "dùng 1/2 ống"),
    ],
)
def test_scrubs_amended_brief_examples_and_restores(text: str, expected: str) -> None:
    result = scrub_text(text)

    assert result.van_ban == expected
    if expected == text:
        assert result.thay_the == []
        assert result.anh_xa == {}
    assert restore_text(result.van_ban, result.anh_xa) == text


@pytest.mark.parametrize("punctuation", [",", ".", ";", ":", ")"])
def test_short_date_accepts_punctuation_except_before_digit(punctuation: str) -> None:
    text = f"(5/11{punctuation}"
    result = scrub_text(text)

    assert result.van_ban == f"([NGAY_1]{punctuation}"
    assert restore_text(result.van_ban, result.anh_xa) == text
    assert scrub_text(f"5/11{punctuation}2").van_ban == f"5/11{punctuation}2"


@pytest.mark.parametrize("unit", ["viên", "ống", "lọ", "gói", "liều", "mg", "mcg", "ml", "g"])
@pytest.mark.parametrize("space", ["", " "])
def test_short_date_preserves_dose_units(unit: str, space: str) -> None:
    text = f"dùng 1/2{space}{unit.upper()}"
    result = scrub_text(text)

    assert result.van_ban == text
    assert result.thay_the == []
    assert scrub_text(f"ngày 5/11{space}{unit}x").van_ban == f"ngày [NGAY_1]{space}{unit}x"


@pytest.mark.parametrize("prefix", ["liều", "tỉ lệ", "tỷ lệ"])
@pytest.mark.parametrize("separator", ["", " ", ":", ": "])
def test_short_date_preserves_dose_and_ratio_prefixes(prefix: str, separator: str) -> None:
    text = f"{prefix.upper()}{separator}3/4"
    result = scrub_text(text)

    assert result.van_ban == text
    assert result.thay_the == []
    assert scrub_text(f"x{prefix}{separator}3/4").van_ban == f"x{prefix}{separator}[NGAY_1]"


@pytest.mark.parametrize(
    "unit",
    [
        "mmHg",
        "/L",
        "/l",
        "/uL",
        "/µL",
        "/mm3",
        "G/L",
        "T/L",
        "U/L",
        "IU/mL",
        "IU/ml",
        "copies/mL",
        "copies/ml",
        "mg",
        "ml",
        "mL",
        "umol/L",
        "µmol/L",
        "mmol/L",
    ],
)
@pytest.mark.parametrize("space", ["", " "])
def test_hn_preserves_only_listed_measurement_units(unit: str, space: str) -> None:
    text = f"giá trị 123456789{space}{unit}"
    result = scrub_text(text)

    assert result.van_ban == text
    assert result.thay_the == []
    assert scrub_text(f"{text}x").van_ban == f"giá trị [HN_1]{space}{unit}x"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("người bệnh Nam", "người bệnh Nam"),
        ("BN: Nữ", "BN: Nữ"),
        ("BỆNH NHÂN Nam", "BỆNH NHÂN Nam"),
        ("BN Nam Anh", "BN [TEN_1]"),
        ("chị Nữ", "chị [TEN_1]"),
        ("BS Nam", "BS [TEN_1]"),
        ("BN Hoa", "BN [TEN_1]"),
        ("Bà Rịa", "Bà [TEN_1]"),
        ("ngày 5/11/2026 mg", "ngày [NGAY_1] mg"),
        ("liều 5/11/2026", "liều [NGAY_1]"),
        ("mã 123456789 MMHG", "mã [HN_1] MMHG"),
        ("mã 123456789 kg", "mã [HN_1] kg"),
        ("ngày 5/11  viên", "ngày [NGAY_1]  viên"),
        ("mã 123456789  mg", "mã [HN_1]  mg"),
    ],
)
def test_amended_rules_keep_their_boundaries(text: str, expected: str) -> None:
    result = scrub_text(text)

    assert result.van_ban == expected
    assert restore_text(result.van_ban, result.anh_xa) == text


def test_preserves_titles_and_orders_tokens_by_first_appearance() -> None:
    result = scrub_text("BN Trần Thị Bình, HN 123456789, sđt 0912 345 678")

    assert result.van_ban == "BN [TEN_1], HN [HN_1], sđt [SDT_1]"
    assert [(item.loai, item.ma_tam) for item in result.thay_the] == [
        ("TEN", "[TEN_1]"),
        ("HN", "[HN_1]"),
        ("SDT", "[SDT_1]"),
    ]
    assert result.anh_xa == {
        "[TEN_1]": "Trần Thị Bình",
        "[HN_1]": "123456789",
        "[SDT_1]": "0912 345 678",
    }


def test_reuses_token_for_exact_repeated_name() -> None:
    result = scrub_text("BS Nguyễn Văn An hội chẩn. BS Nguyễn Văn An đồng ý.")

    assert result.van_ban == "BS [TEN_1] hội chẩn. BS [TEN_1] đồng ý."
    assert result.anh_xa == {"[TEN_1]": "Nguyễn Văn An"}
    assert len(result.thay_the) == 1


def test_counts_dates_independently() -> None:
    result = scrub_text("Vào viện 05/11/2026, tái khám 12-11-2026")

    assert result.van_ban == "Vào viện [NGAY_1], tái khám [NGAY_2]"
    assert result.anh_xa == {"[NGAY_1]": "05/11/2026", "[NGAY_2]": "12-11-2026"}


def test_applies_priority_without_scrubbing_inside_email_or_long_codes() -> None:
    result = scrub_text("0912345678@example.org DN4010123456789 001099012345 +84912345678")

    assert result.van_ban == "[EMAIL_1] [BHYT_1] [CCCD_1] [SDT_1]"
    assert [item.loai for item in result.thay_the] == ["EMAIL", "BHYT", "CCCD", "SDT"]


def test_scrubs_remaining_name_after_email_is_masked() -> None:
    result = scrub_text("BN Nguyễn Văn An@example.org")

    assert result.van_ban == "BN [TEN_1] [EMAIL_1]"
    assert result.anh_xa == {"[TEN_1]": "Nguyễn Văn", "[EMAIL_1]": "An@example.org"}
    assert restore_text(result.van_ban, result.anh_xa) == "BN Nguyễn Văn An@example.org"


def test_reuses_exact_values_and_keeps_different_spellings_separate() -> None:
    result = scrub_text("a@b.com 123456789 a@b.com A@b.com 234567891 123456789")

    assert result.van_ban == "[EMAIL_1] [HN_1] [EMAIL_1] [EMAIL_2] [HN_2] [HN_1]"
    assert [item.ma_tam for item in result.thay_the] == [
        "[EMAIL_1]",
        "[HN_1]",
        "[EMAIL_2]",
        "[HN_2]",
    ]


@pytest.mark.parametrize(
    "title",
    [
        "BN",
        "bệnh nhân",
        "người bệnh",
        "BS",
        "bác sĩ",
        "ĐD",
        "điều dưỡng",
        "DS",
        "dược sĩ",
        "ông",
        "bà",
        "anh",
        "chị",
        "BỆNH NHÂN",
        "bS",
    ],
)
@pytest.mark.parametrize("punctuation", ["", ".", ":"])
def test_recognizes_each_title_case_insensitively(title: str, punctuation: str) -> None:
    result = scrub_text(f"{title}{punctuation} Đỗ Ánh")

    assert result.van_ban == f"{title}{punctuation} [TEN_1]"
    assert result.anh_xa == {"[TEN_1]": "Đỗ Ánh"}


@pytest.mark.parametrize("kind", ["HN", "CCCD", "SDT", "BHYT", "EMAIL", "NGAY", "TEN"])
def test_rejects_preexisting_tokens(kind: str) -> None:
    with pytest.raises(DeidError):
        scrub_text(f"Ghi chú [{kind}_1] có sẵn")


@pytest.mark.parametrize("value", [None, 123, b"text", [], {}])
def test_rejects_non_string_input(value: object) -> None:
    with pytest.raises(DeidError):
        scrub_text(value)  # type: ignore[arg-type]


def test_wraps_unexpected_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_result(**kwargs: object) -> NoReturn:
        raise RuntimeError("Lỗi giả lập")

    monkeypatch.setattr(scrubber, "ScrubResult", fail_result)

    with pytest.raises(DeidError) as caught:
        scrub_text("HN 123456789")

    assert isinstance(caught.value.__cause__, RuntimeError)


def test_empty_input() -> None:
    result = scrub_text("")

    assert result.van_ban == ""
    assert result.thay_the == []
    assert result.anh_xa == {}
    assert restore_text("", {}) == ""


@pytest.mark.parametrize(
    "text",
    [
        "BN Trần Thị Bình, HN 123456789, sđt 0912 345 678",
        "CCCD 001099012345, BHYT DN4010123456789",
        "Vào viện 05/11/2026, tái khám 12-11-2026",
        "BS Nguyễn Văn An hội chẩn. BS Nguyễn Văn An đồng ý.",
        "Liên hệ a.b@example.org hoặc +84912345678",
        "Huyết áp 120/80 mmHg, creatinin 212 umol/L, K 4.5",
        "ĐD:\tĐỗ  Ánh\nNgày 5/11; mã khác [KHAC_1]",
    ],
)
def test_round_trip_preserves_original_text(text: str) -> None:
    result = scrub_text(text)

    assert restore_text(result.van_ban, result.anh_xa) == text


def test_restore_substitutes_tokens_once_and_leaves_unknown_tokens() -> None:
    assert restore_text("[TEN_1] [HN_1] [SDT_2]", {"[TEN_1]": "[HN_1]", "[HN_1]": "x"}) == (
        "[HN_1] x [SDT_2]"
    )
