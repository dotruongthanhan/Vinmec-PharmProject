"""Kiểm thử hàm thuần view_model và kiểm tra tĩnh an toàn giao diện Streamlit."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import get_args

import pytest

from app.domain.loader import load_all_cases, load_case
from app.domain.models import YLenh
from app.feedback import PhanHoi
from app.pipeline import run_case
from app.rules import load_renal_rules
from app.rules.types import CanCu, PhatHien
from app.ui import view_model
from app.ui.view_model import (
    NHAN_LOAI_CAN_CU,
    NHAN_LUONG_DUYET,
    allergy_text,
    count_by_level,
    count_serious,
    evidence_rows,
    feedback_status,
    finding_rows,
    format_number,
    header_info,
    lab_rows,
    lab_trends,
    label_of,
    length_of_stay_days,
    metric_text,
    plain_label,
    priority_of,
    queue_rows,
    record_detail,
    split_findings,
    suggested_questions,
    unchecked_factors,
)

_ROOT = Path(__file__).resolve().parents[2]
_DEMO_DIR = _ROOT / "data" / "mock" / "demo"
_RENAL_RULES_PATH = _ROOT / "data" / "kb" / "quy_tac_lieu_than.json"
_STREAMLIT_APP_PATH = _ROOT / "app" / "ui" / "streamlit_app.py"


def test_allergy_text_three_distinct_states() -> None:
    """Ba trạng thái dị ứng sinh ba chuỗi khác hẳn nhau đúng định dạng."""
    ca_no_allergy = load_case(_DEMO_DIR / "DEMO-01.json")
    ca_unknown = load_case(_DEMO_DIR / "DEMO-03.json")
    ca_has_allergy = load_case(_DEMO_DIR / "DEMO-06.json")

    txt_no = allergy_text(ca_no_allergy)
    txt_unknown = allergy_text(ca_unknown)
    txt_yes = allergy_text(ca_has_allergy)

    assert len({txt_no, txt_unknown, txt_yes}) == 3
    assert txt_no == "Đã hỏi, không ghi nhận dị ứng"
    assert txt_unknown == "CHƯA CÓ THÔNG TIN DỊ ỨNG"
    assert txt_yes == "Có dị ứng: Penicillin (Mày đay)"


def test_lab_rows_demo04_out_of_range_flags() -> None:
    """DEMO-04 có WBC và CRP ngoài ngưỡng, còn creatinin không ngoài ngưỡng."""
    ca = load_case(_DEMO_DIR / "DEMO-04.json")
    rows = lab_rows(ca)
    by_code = {row["ma_xet_nghiem"]: row for row in rows}

    assert by_code["wbc"]["ngoai_nguong"] is True
    assert by_code["crp"]["ngoai_nguong"] is True
    assert by_code["creatinin"]["ngoai_nguong"] is False


def test_finding_rows_and_split_findings_demo02() -> None:
    """DEMO-02 có đúng 1 dòng cần chú ý thuộc yếu tố 6 cho thuốc Meropenem."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)
    res = run_case(ca, renal_rules)

    rows = finding_rows(ca, res.phat_hien)
    attention, passed = split_findings(rows)

    assert len(attention) == 1
    assert len(passed) >= 1
    assert str(attention[0]["yeu_to"]).startswith("6.")
    assert "Meropenem" in str(attention[0]["thuoc"])
    assert count_serious(res.phat_hien) == 1
    renal_finding = next(item for item in res.phat_hien if item.yeu_to == 6)
    assert "Một nửa liều khuyến cáo, mỗi 12 giờ" in renal_finding.mo_ta


def test_format_number_vietnamese_decimal() -> None:
    """Định dạng số dùng dấu phẩy thập phân và trả '—' khi None."""
    assert format_number(None) == "—"
    assert format_number(15.9988) == "16,0"


@pytest.mark.parametrize(
    ("formula", "value", "expected"),
    [
        ("bsa_mosteller", 1.8182, "1,82"),
        ("bmi", 24.221, "24,2"),
        ("bmi", None, "—"),
    ],
)
def test_metric_text_precision(formula: str, value: float | None, expected: str) -> None:
    """BSA dùng hai chữ số thập phân, chỉ số khác dùng một và giữ trạng thái thiếu."""
    assert metric_text(formula, value) == expected


@pytest.mark.parametrize(("case_id", "expected"), [("DEMO-01", "1,82"), ("DEMO-02", "1,47")])
def test_metric_text_demo_bsa(case_id: str, expected: str) -> None:
    """BSA của hai ca demo hiển thị đúng hai chữ số thập phân."""
    ca = load_case(_DEMO_DIR / f"{case_id}.json")
    result = run_case(ca, load_renal_rules(_RENAL_RULES_PATH))
    bsa = next(calc for calc in result.chi_so if calc.cong_thuc == "bsa_mosteller")
    assert metric_text(bsa.cong_thuc, bsa.ket_qua) == expected


def test_plain_label_escapes_markdown() -> None:
    """Nhãn thoát mọi ký tự markdown được brief liệt kê, kể cả dấu gạch chéo ngược."""
    assert plain_label("a*b_[c](d)") == r"a\*b\_\[c\]\(d\)"
    assert plain_label("\\`*_[]()#~<>|!$:") == r"\\\`\*\_\[\]\(\)\#\~\<\>\|\!\$\:"


@pytest.mark.parametrize("text", ["x\ny", "x\r\ny", "x\ry"])
def test_plain_label_flattens_newlines(text: str) -> None:
    """Xuống dòng từ dữ liệu được thay bằng một dấu cách."""
    assert plain_label(text) == "x y"


def test_plain_label_preserves_vietnamese() -> None:
    """Nhãn tiếng Việt có dấu được giữ nguyên."""
    assert plain_label("Hô hấp · Nữ 75 tuổi") == "Hô hấp · Nữ 75 tuổi"


def test_label_of_known_and_unknown_codes() -> None:
    """Mã đã biết có nhãn tiếng Việt, mã chưa biết được giữ nguyên."""
    assert label_of(NHAN_LOAI_CAN_CU, "tinh_toan") == "Tính toán"
    assert label_of(NHAN_LOAI_CAN_CU, "la") == "la"


def test_review_flow_labels_cover_all_literals() -> None:
    """Bảng nhãn luồng duyệt bao phủ đúng mọi giá trị của mô hình y lệnh."""
    codes = get_args(YLenh.model_fields["luong_duyet"].annotation)
    assert set(NHAN_LUONG_DUYET) == set(codes)


def test_streamlit_app_has_no_unsafe_html() -> None:
    """Kiểm tra tĩnh: streamlit_app.py không chứa chuỗi unsafe_allow_html."""
    content = _STREAMLIT_APP_PATH.read_text(encoding="utf-8")
    assert "unsafe_allow_html" not in content


def test_priority_of_and_count_by_level() -> None:
    """priority_of và count_by_level phân bậc đúng theo mức độ phát hiện."""
    cc = [CanCu(loai="du_lieu", ban_ghi_id="X1", mo_ta="Dữ liệu")]
    p_serious = PhatHien(
        ma_luat="r1",
        yeu_to=6,
        ket_luan="can_xem",
        muc_do="nghiem_trong",
        chi_tiet_y_lenh_id=["C1"],
        mo_ta="M1",
        can_cu=cc,
    )
    p_warn = PhatHien(
        ma_luat="r2",
        yeu_to=7,
        ket_luan="can_xem",
        muc_do="can_luu_y",
        chi_tiet_y_lenh_id=["C1"],
        mo_ta="M2",
        can_cu=cc,
    )
    p_offlabel = PhatHien(
        ma_luat="r3",
        yeu_to=3,
        ket_luan="ngoai_hdsd",
        muc_do="can_luu_y",
        chi_tiet_y_lenh_id=["C1"],
        mo_ta="M3",
        can_cu=cc,
    )
    p_missing = PhatHien(
        ma_luat="r4",
        yeu_to=1,
        ket_luan="khong_du_du_lieu",
        muc_do=None,
        chi_tiet_y_lenh_id=["C1"],
        mo_ta="M4",
        can_cu=cc,
        thong_tin_con_thieu=["di_ung"],
    )
    p_ok = PhatHien(
        ma_luat="r5",
        yeu_to=2,
        ket_luan="dat",
        muc_do=None,
        chi_tiet_y_lenh_id=["C1"],
        mo_ta="M5",
        can_cu=cc,
    )

    assert priority_of([p_ok, p_serious]) == 0
    assert priority_of([p_ok, p_warn]) == 1
    assert priority_of([p_ok, p_offlabel]) == 2
    assert priority_of([p_ok, p_missing]) == 3
    assert priority_of([p_ok]) == 4
    assert priority_of([]) == 4

    counts = count_by_level([p_serious, p_warn, p_offlabel, p_missing, p_ok])
    assert counts == {
        "nghiem_trong": 1,
        "can_luu_y": 1,
        "thieu_du_lieu": 1,
        "ngoai_hdsd": 1,
        "dat": 1,
    }


def test_queue_rows_ordering_on_six_demo_cases() -> None:
    """6 ca demo được xếp đúng thứ tự ưu tiên: DEMO-02/06 đầu, 05 trước 03, 01/04 cuối."""
    cases = load_all_cases(_DEMO_DIR)
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)
    results = {ca.ca_id: run_case(ca, renal_rules) for ca in cases}

    rows = queue_rows(cases, results)
    order = [str(row["ca_id"]) for row in rows]

    assert set(order[:2]) == {"DEMO-02", "DEMO-06"}
    assert order[:2] == ["DEMO-02", "DEMO-06"]
    assert order[2] == "DEMO-05"
    assert order[3] == "DEMO-03"
    assert set(order[4:]) == {"DEMO-01", "DEMO-04"}
    assert "⛔" in str(rows[0]["huy_hieu"]) and "nghiêm trọng" in str(rows[0]["huy_hieu"])
    assert str(rows[-1]["huy_hieu"]) == "✓ Đạt"


def test_header_info_demo02_and_demo03() -> None:
    """header_info trả đúng thông tin định danh, CrCl và trạng thái dị ứng."""
    renal_rules = load_renal_rules(_RENAL_RULES_PATH)
    ca_02 = load_case(_DEMO_DIR / "DEMO-02.json")
    info_02 = header_info(ca_02, run_case(ca_02, renal_rules))

    assert info_02["gioi_tuoi"] == "Nữ 75 tuổi"
    assert info_02["can_nang"] == "50,0 kg"
    assert info_02["khoa_loai"] == "Hô hấp, nội trú"
    assert info_02["crcl"] == "16,0 mL/phút"
    assert info_02["crcl_bat_thuong"] is True

    ca_03 = load_case(_DEMO_DIR / "DEMO-03.json")
    info_03 = header_info(ca_03, run_case(ca_03, renal_rules))
    assert info_03["di_ung_trang_thai"] == "chua_co_thong_tin"


def test_length_of_stay_days() -> None:
    """Tính số ngày nằm viện theo tham số now truyền vào."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    tz_vn = timezone(timedelta(hours=7))

    assert length_of_stay_days(ca, now=ca.y_lenh_cho_duyet.thoi_diem_ke) == 3
    assert length_of_stay_days(ca, datetime(2026, 11, 10, 10, 0, tzinfo=tz_vn)) == 4
    assert length_of_stay_days(ca, datetime(2026, 11, 10, 6, 0, tzinfo=tz_vn)) == 3
    assert length_of_stay_days(ca, datetime(2026, 11, 5, 10, 0, tzinfo=tz_vn)) is None


def test_lab_trends_out_of_range_and_trend_text() -> None:
    """lab_trends lọc đúng xét nghiệm ngoài ngưỡng và tính xu hướng từ kết quả trước."""
    ca_04 = load_case(_DEMO_DIR / "DEMO-04.json")
    trends_04 = lab_trends(ca_04)
    assert len(trends_04) == 2
    assert all(row["huong"] == "▲" for row in trends_04)
    assert all(row["so_voi_truoc"] is None for row in trends_04)

    ca_02 = load_case(_DEMO_DIR / "DEMO-02.json")
    labs_without_bounds = [
        xn.model_copy(update={"nguong_duoi": None, "nguong_tren": None}) for xn in ca_02.xet_nghiem
    ]
    assert lab_trends(ca_02.model_copy(update={"xet_nghiem": labs_without_bounds})) == []

    # Kiểm tra thêm trường hợp chỉ có ngưỡng trên trên bản sao.
    labs_with_bound = [
        xn.model_copy(update={"nguong_duoi": None, "nguong_tren": 100.0})
        if xn.ma_xet_nghiem == "creatinin"
        else xn
        for xn in ca_02.xet_nghiem
    ]
    ca_02_bounded = ca_02.model_copy(update={"xet_nghiem": labs_with_bound})
    trends_02 = lab_trends(ca_02_bounded)

    assert len(trends_02) == 1
    assert trends_02[0]["ten"] == "Creatinin máu"
    assert trends_02[0]["huong"] == "▲"
    assert trends_02[0]["gia_tri_text"] == "212,0"
    assert "150,0" in str(trends_02[0]["so_voi_truoc"])
    assert "3 ngày" in str(trends_02[0]["so_voi_truoc"])


def test_lab_trends_demo02_creatinine_has_reference_range() -> None:
    """Creatinin DEMO-02 có một dòng tăng và giá trị trước để đối chiếu."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    trends = lab_trends(ca)

    assert len(trends) == 1
    assert trends[0]["ten"] == "Creatinin máu"
    assert trends[0]["huong"] == "▲"
    assert "212" in str(trends[0]["gia_tri_text"])
    assert "150" in str(trends[0]["so_voi_truoc"])


@pytest.mark.parametrize(
    ("value", "low", "high", "expected"),
    [
        (0.0, None, None, 2),
        (212.0, None, None, 2),
        (None, None, None, 0),
        (212.0, 44.0, None, 0),
        (212.0, None, 80.0, 0),
        (212.0, 44.0, 80.0, 0),
    ],
)
def test_labs_without_range_counts_numeric_results_only(
    value: float | None, low: float | None, high: float | None, expected: int
) -> None:
    """Đếm từng kết quả số thiếu cả hai ngưỡng, kể cả giá trị bằng không."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    labs = [
        xn.model_copy(update={"gia_tri_so": value, "nguong_duoi": low, "nguong_tren": high})
        for xn in ca.xet_nghiem
    ]
    assert view_model.labs_without_range(ca.model_copy(update={"xet_nghiem": labs})) == expected
    assert view_model.labs_without_range(ca.model_copy(update={"xet_nghiem": []})) == 0


def test_evidence_rows_demo02_order_and_openable() -> None:
    """Căn cứ yếu tố 6 của DEMO-02 có 3 dòng đúng thứ tự và quyền mở ở đợt 1."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    res = run_case(ca, load_renal_rules(_RENAL_RULES_PATH))
    renal_finding = next(item for item in res.phat_hien if item.yeu_to == 6)

    ev_rows = evidence_rows(renal_finding.can_cu)
    assert len(ev_rows) == 3
    assert [row["loai_nhan"] for row in ev_rows] == ["Dữ liệu ca", "Tính toán", "Tài liệu"]
    assert [row["mo_duoc"] for row in ev_rows] == [True, True, False]


def test_record_detail_found_and_missing() -> None:
    """record_detail tìm đúng bản ghi theo mã và trả None khi không thấy."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")

    detail = record_detail(ca, "XN-DEMO02-01")
    assert detail is not None
    assert detail["loai"] == "Xét nghiệm"
    assert "212,0" in str(detail["dong"])

    assert record_detail(ca, "SH-DEMO02-01") is not None
    assert record_detail(ca, "CD-DEMO02-01") is not None
    assert record_detail(ca, "CT-DEMO02-01") is not None
    assert record_detail(ca, "DB-DEMO02-01") is not None
    assert record_detail(ca, "MA-KHONG-TON-TAI") is None


def test_unchecked_factors_and_suggested_questions() -> None:
    """unchecked_factors nêu yếu tố chưa kiểm; câu hỏi kháng sinh chỉ hiện khi liên quan."""
    ca_01 = load_case(_DEMO_DIR / "DEMO-01.json")
    res_01 = run_case(ca_01, load_renal_rules(_RENAL_RULES_PATH))
    unchecked = unchecked_factors(res_01.phat_hien)
    assert "5. Độc tính" in unchecked
    assert "4. Tương tác thuốc" not in unchecked

    q_01 = suggested_questions(ca_01)
    assert len(q_01) == 3
    assert "Vì sao kê kháng sinh này?" not in q_01

    ca_02 = load_case(_DEMO_DIR / "DEMO-02.json")
    q_02 = suggested_questions(ca_02)
    assert len(q_02) == 4
    assert q_02[0] == "Vì sao kê kháng sinh này?"


def test_feedback_status_latest_and_line_set_match() -> None:
    """feedback_status trả phản hồi mới nhất và chỉ khớp khi đúng tập chi_tiet_y_lenh_id."""
    tz_vn = timezone(timedelta(hours=7))
    row = {
        "ma_luat": "lieu_than_can_chinh",
        "chi_tiet_y_lenh_id": ["CT-1", "CT-2"],
    }
    fb_old = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, 9, 0, tzinfo=tz_vn),
        ca_id="DEMO-02",
        ma_luat="lieu_than_can_chinh",
        yeu_to=6,
        chi_tiet_y_lenh_id=["CT-2", "CT-1"],
        phan_hoi="dong_y",
    )
    fb_new = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, 10, 0, tzinfo=tz_vn),
        ca_id="DEMO-02",
        ma_luat="lieu_than_can_chinh",
        yeu_to=6,
        chi_tiet_y_lenh_id=["CT-1", "CT-2"],
        phan_hoi="can_sua",
        nhom_ly_do="khong_phu_hop_lam_sang",
    )
    fb_other_lines = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, 11, 0, tzinfo=tz_vn),
        ca_id="DEMO-02",
        ma_luat="lieu_than_can_chinh",
        yeu_to=6,
        chi_tiet_y_lenh_id=["CT-1"],
        phan_hoi="bac_bo",
    )

    matched = feedback_status("DEMO-02", row, [fb_old, fb_other_lines, fb_new])
    assert matched == fb_new
    assert feedback_status("DEMO-02", row, [fb_other_lines]) is None
