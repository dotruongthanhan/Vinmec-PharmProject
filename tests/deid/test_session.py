"""Kiểm thử phiên che định danh (lớp 1 theo giá trị đã biết + lớp 2 theo mẫu) của T48."""

import pytest

from app.deid.known import GiaTriDinhDanh
from app.deid.scrubber import DeidError
from app.deid.session import DeidSession

TEN = GiaTriDinhDanh(loai="TEN", gia_tri="Nguyễn Thị Lan")
NGAY = GiaTriDinhDanh(loai="NGAY", gia_tri="1958-03-12")
SDT = GiaTriDinhDanh(loai="SDT", gia_tri="0912 345 678")
BHYT = GiaTriDinhDanh(loai="BHYT", gia_tri="GD4010000000062")
DIACHI = GiaTriDinhDanh(loai="DIACHI", gia_tri="9062 Phố Bạch Mai")
MA = GiaTriDinhDanh(loai="MA", gia_tri="NB-HS-001")


def _session() -> DeidSession:
    return DeidSession([TEN, NGAY, SDT, BHYT, DIACHI, MA])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Nguyễn Thị Lan vào viện", "[TEN_1] vào viện"),
        ("NGUYEN THI LAN vào viện", "[TEN_1] vào viện"),
        ("nguyễn thị lan vào viện", "[TEN_1] vào viện"),
        ("Nguyễn  Thị\nLan vào viện", "[TEN_1] vào viện"),
        ("bà Lan đau bụng", "bà [TEN_1] đau bụng"),
        ("chị Thị Lan đau bụng", "chị [TEN_1] đau bụng"),
        ("BN: Lan khỏe", "BN: [TEN_1] khỏe"),
        ("sinh 12/03/1958", "sinh [NGAY_1]"),
        ("sinh 12/3/1958", "sinh [NGAY_1]"),
        ("sinh 1958-03-12", "sinh [NGAY_1]"),
        ("sinh 12.03.1958", "sinh [NGAY_1]"),
        ("sinh ngày 12 tháng 3 năm 1958", "sinh [NGAY_1]"),
        ("sinh năm 1958", "sinh năm [NGAY_1]"),
        ("sđt 0912 345 678", "sđt [SDT_1]"),
        ("sđt 0912345678", "sđt [SDT_1]"),
        ("sđt 091.234.5678", "sđt [SDT_1]"),
        ("sđt +84 912 345 678", "sđt [SDT_1]"),
        ("thẻ GD4010000000062", "thẻ [BHYT_1]"),
        ("thẻ gd 4010000000062", "thẻ [BHYT_1]"),
        ("ở 9062 Phố Bạch Mai", "ở [DIACHI_1]"),
        ("ở 9062, pho bach mai", "ở [DIACHI_1]"),
        ("mã NB-HS-001 và nb hs 001", "mã [MA_1] và [MA_1]"),
    ],
)
def test_layer1_masks_value_variants(text: str, expected: str) -> None:
    assert _session().scrub(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Lan là tên loài hoa",
        "ngày 13/03/1958 khác ngày sinh",
        "sinh năm 1985",
        "sđt 0912 345 679",
        "ở 9063 Phố Bạch Mai khác",
        "mã NB-HS-0010",
        "Creatinin 120 umol/L, 12 viên",
    ],
)
def test_layer1_does_not_over_mask_unrelated_text(text: str) -> None:
    assert _session().scrub(text, patterns=False) == text


def test_one_value_one_token_across_texts_and_restore() -> None:
    session = _session()

    first = session.scrub("Nguyễn Thị Lan vào viện, sđt 0912 345 678")
    second = session.scrub("Hỏi: chị Lan có dùng thuốc? sđt 0912345678")

    assert first == "[TEN_1] vào viện, sđt [SDT_1]"
    assert second == "Hỏi: chị [TEN_1] có dùng thuốc? sđt [SDT_1]"
    assert session.anh_xa["[TEN_1]"] == "Nguyễn Thị Lan"
    assert session.restore("Kết quả cho [TEN_1], [SDT_1] và [TEN_9]") == (
        "Kết quả cho Nguyễn Thị Lan, 0912 345 678 và [TEN_9]"
    )


def test_layer2_runs_after_layer1_with_shared_numbering() -> None:
    session = _session()

    text = session.scrub("Nguyễn Thị Lan; người nhà Lê Văn Hùng; BS Trần Văn Bình; 2026-11-06")

    assert text == "[TEN_1]; người nhà [TEN_2]; BS [TEN_3]; [NGAY_1]"
    assert session.anh_xa["[TEN_2]"] == "Lê Văn Hùng"


def test_layer1_only_mode_leaves_pattern_cases_and_existing_tokens() -> None:
    session = _session()

    assert (
        session.scrub("BS Trần Văn Bình, bà Lan", patterns=False) == "BS Trần Văn Bình, bà [TEN_1]"
    )
    assert session.mask_known("đã có [TEN_1] và Nguyễn Thị Lan") == "đã có [TEN_1] và [TEN_1]"


def test_numeric_name_suffix_is_not_masked_alone() -> None:
    session = DeidSession([GiaTriDinhDanh(loai="TEN", gia_tri="Nguyễn Văn 1")])

    assert session.scrub("Nguyễn Văn 1 vào viện, creatinin 1 mg/dL, 1 viên") == (
        "[TEN_1] vào viện, creatinin 1 mg/dL, 1 viên"
    )
    assert session.scrub("Nguyễn Văn 12 khác") == "Nguyễn Văn 12 khác"


def test_scrub_rejects_preexisting_tokens_and_non_strings() -> None:
    session = _session()

    with pytest.raises(DeidError):
        session.scrub("Ghi chú [TEN_1] có sẵn")
    with pytest.raises(DeidError):
        session.scrub(123)  # type: ignore[arg-type]


def test_empty_session_equals_pattern_layer_only() -> None:
    session = DeidSession()

    assert session.scrub("Nguyễn Thị Lan vào viện") == "Nguyễn Thị Lan vào viện"
    assert session.scrub("BS Nguyễn Văn An") == "BS [TEN_1]"
