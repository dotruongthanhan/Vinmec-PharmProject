"""Chạy thử giao diện thật bằng AppTest, không ghi phản hồi."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app.domain.loader import load_case
from app.ui.state import select_case

_DEMO_DIR = Path(__file__).resolve().parents[2] / "data" / "mock" / "demo"


def test_app_renders_all_six_demo_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mỗi ca chọn trong phiên đều vẽ được và có định danh ở vùng chính."""
    monkeypatch.setenv("CDSS_CASE_DIR", str(_DEMO_DIR))
    app_path = _DEMO_DIR.parents[2] / "app" / "ui" / "streamlit_app.py"
    at = AppTest.from_file(app_path, default_timeout=30).run()
    assert not at.exception

    for number in range(1, 7):
        case_id = f"DEMO-{number:02d}"
        select_case(at.session_state, case_id)
        at.run()
        assert not at.exception, case_id
        assert any(element.value.startswith(f"{case_id} ·") for element in at.text), case_id
        elements = list(at.main)
        heading_index = next(
            index
            for index, element in enumerate(elements)
            if element.type == "subheader" and element.value.startswith("Bảng nhận định")
        )
        scope_caption = elements[heading_index + 1]
        assert scope_caption.type == "caption"
        assert scope_caption.value.startswith("Chưa có luật kiểm tra cho các yếu tố:")
        if case_id == "DEMO-02":
            assert any(
                "Nằm viện: 3 ngày (tính tới lúc kê y lệnh)" in element.value for element in at.text
            )


@pytest.mark.parametrize(
    ("abnormal", "missing", "expected"),
    [
        (False, False, "Không có xét nghiệm ngoài ngưỡng."),
        (False, True, "Chưa đánh giá được: 1 kết quả không có khoảng tham chiếu."),
        (True, False, None),
        (True, True, "1 kết quả khác không có khoảng tham chiếu."),
    ],
)
def test_summary_reports_missing_reference_ranges(
    abnormal: bool, missing: bool, expected: str | None
) -> None:
    """Thiếu khoảng tham chiếu luôn được thông báo dù có kết quả ngoài ngưỡng."""
    ca = load_case(_DEMO_DIR / "DEMO-02.json")
    latest, previous = ca.xet_nghiem
    labs = (
        [latest.model_copy(update={"nguong_duoi": 44.0, "nguong_tren": 80.0})] if abnormal else []
    )
    if missing:
        labs.append(previous.model_copy(update={"nguong_duoi": None, "nguong_tren": None}))
    ca = ca.model_copy(update={"xet_nghiem": labs})
    at = AppTest.from_string(
        "from pathlib import Path\n"
        "from app.pipeline import run_case\n"
        "from app.rules import load_renal_rules\n"
        "from app.ui.components.summary import render_summary\n"
        "from app.ui.view_model import lab_trends\n"
        "import streamlit as st\n"
        "ca = st.session_state['case']\n"
        "rules = load_renal_rules(Path('data/kb/quy_tac_lieu_than.json'))\n"
        "render_summary(ca, run_case(ca, rules), lab_trends(ca), 10)\n",
        default_timeout=30,
    )
    at.session_state["case"] = ca
    at.run()
    assert not at.exception
    values = [element.value for element in at.text] + [element.value for element in at.caption]
    if expected is not None:
        assert expected in values
    assert ("Không có xét nghiệm ngoài ngưỡng." in values) is (not abnormal and not missing)
    assert any("Creatinin máu: 212" in value for value in values) is abnormal
