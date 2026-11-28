"""Kiểm thử các mẫu bổ sung của lớp 2 (T48): ngày ISO, tên theo ngữ cảnh, địa chỉ, tên thường."""

import pytest

from app.deid.scrubber import restore_text, scrub_text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ngày sinh 1958-03-12", "Ngày sinh [NGAY_1]"),
        ("khám lúc 2026-11-06T10:00:00+07:00", "khám lúc [NGAY_1]T10:00:00+07:00"),
        ("người nhà Lê Văn Hùng đến thăm", "người nhà [TEN_1] đến thăm"),
        ("Người nhà: Lê Văn Hùng", "Người nhà: [TEN_1]"),
        ("họ tên: Lan", "họ tên: [TEN_1]"),
        ("vợ Nguyễn Thị Mai, sđt 0912 345 678", "vợ [TEN_1], sđt [SDT_1]"),
        ("con Nguyễn Văn Bình khai", "con [TEN_1] khai"),
        ("bà Trần thị hoa khỏe", "bà [TEN_1] khỏe"),
        ("bà trần thị hoa", "bà [TEN_1]"),
        ("ông Lê văn hùng đau bụng", "ông [TEN_1] đau bụng"),
        (
            "Địa chỉ: 9062 Phố Bạch Mai, Hai Bà Trưng, Hà Nội. Bệnh nhân sốt",
            "Địa chỉ: [DIACHI_1]. Bệnh nhân sốt",
        ),
        ("ĐC: số 12 ngõ 5 Láng Hạ\nLiên hệ", "ĐC: [DIACHI_1]\nLiên hệ"),
        ("trú tại TP. Hồ Chí Minh, quận 1; ổn", "trú tại [DIACHI_1]; ổn"),
        ("số nhà 12A ngõ 3, sđt 0912 345 678", "số nhà [DIACHI_1], sđt [SDT_1]"),
    ],
)
def test_layer2_catches_previously_leaking_patterns(text: str, expected: str) -> None:
    result = scrub_text(text)

    assert result.van_ban == expected
    assert restore_text(result.van_ban, result.anh_xa) == text


@pytest.mark.parametrize(
    "text",
    [
        "Paracetamol 500 mg uống khi sốt",
        "Vancomycin 1 g truyền tĩnh mạch",
        "Khoa Nội tim mạch",
        "Khoa Nội Tim Mạch",
        "Tiền sử mẹ Đái tháo đường",
        "tên thuốc Paracetamol",
        "anh em ruột khỏe",
        "chị em cùng ở",
        "nhà ở Hà Nội",
        "con sốt cao",
        "Hạ Kali máu, Tăng Huyết Áp",
    ],
)
def test_layer2_keeps_drugs_units_departments_and_clinical_words(text: str) -> None:
    result = scrub_text(text)

    assert result.van_ban == text
    assert result.thay_the == []


def test_token_kinds_diachi_and_ma_are_rejected_when_preexisting() -> None:
    from app.deid.scrubber import DeidError

    for kind in ("DIACHI", "MA"):
        with pytest.raises(DeidError):
            scrub_text(f"Ghi chú [{kind}_1] có sẵn")
