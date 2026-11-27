"""Kiểm thử chấm điểm minh hoạ trong bộ đánh giá hỏi đáp (VZ5)."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.agent.minh_hoa.models import BoDuLieu, CotDuLieu, KhoiMinhHoa
from app.db.reader import load_source_cases
from app.deid.known import GiaTriDinhDanh
from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.eval.hoi_dap import (
    DEFAULT_QUESTIONS_PATH,
    CauHoiDanhGia,
    KyVong,
    KyVongMinhHoa,
    load_questions,
    rescore_details,
    run_evaluation,
    score_answer,
    summarize_results,
)
from app.orchestration.ask import AskCitation, AskResult
from app.pipeline import KetQuaThamDinh, run_case
from app.rules import load_renal_rules

ROOT = Path(__file__).resolve().parents[2]
DEMO_02_PATH = ROOT / "data/mock/demo/DEMO-02.json"
VISUAL_QUESTIONS_PATH = ROOT / "data/gold/hoi_dap/cau_hoi_minh_hoa_v1.jsonl"

_FAKE_NAME = "Trần Thị Mẫu 88"


def _make_visual_block(
    marks: Sequence[str],
    *,
    tieu_de: str = "Diễn tiến chỉ số",
    cell_label: str = "Mốc 1",
    cell_value: float = 120.0,
) -> KhoiMinhHoa:
    """Dựng tay một khối KhoiMinhHoa hợp lệ theo hợp đồng mh-1."""
    return KhoiMinhHoa(
        ma="mh-1",
        phien_ban="mh-1",
        dac_ta={
            "tieu_de": tieu_de,
            "lop": [
                {
                    "dau": mark,
                    "du_lieu": "ds-1",
                    "ma_hoa": {"x": {"cot": "moc"}, "y": {"cot": "gia_tri"}},
                }
                for mark in marks
            ],
        },
        bo_du_lieu=[
            BoDuLieu(
                ma="ds-1",
                cot=[
                    CotDuLieu(ten="moc", kieu="danh_muc"),
                    CotDuLieu(ten="gia_tri", kieu="dinh_luong", don_vi="umol/L"),
                ],
                dong=[{"moc": cell_label, "gia_tri": cell_value}],
                can_cu=["ca:xet_nghiem"],
            )
        ],
        nguon=["ca:xet_nghiem"],
    )


def _make_question(
    *,
    qid: str = "HD-MH-TEST-01",
    ca_id: str = "DEMO-02",
    loai: str = "than_gan",
    minh_hoa: dict[str, Any] | None = None,
    ky_vong_extra: dict[str, Any] | None = None,
) -> CauHoiDanhGia:
    """Dựng tay một câu hỏi đánh giá có hoặc không có kỳ vọng minh hoạ."""
    ky_vong: dict[str, Any] = {
        "trang_thai": ["ok"],
        "so_bat_buoc": [],
        "dung_sai": 0.05,
        "nhom_cum_bat_buoc": [],
        "cum_cam": [],
        "can_trich_dan": False,
        "loai_trich_dan": [],
    }
    if minh_hoa is not None:
        ky_vong["minh_hoa"] = minh_hoa
    if ky_vong_extra:
        ky_vong.update(ky_vong_extra)
    return CauHoiDanhGia.model_validate(
        {
            "id": qid,
            "che_do": "ca",
            "ca_id": ca_id,
            "loai": loai,
            "cau_hoi": "Câu hỏi kiểm thử minh hoạ.",
            "ky_vong": ky_vong,
            "can_cu_dap_an": "Dữ liệu dựng tay cho unit test.",
            "trang_thai_duyet": "cho_duoc_si_duyet",
            "ghi_chu": None,
        }
    )


class _FakeAsker:
    """Bộ hỏi đáp giả trả kết quả dựng tay theo câu hỏi."""

    def __init__(self, responder: Callable[[str, str], AskResult]) -> None:
        self._responder = responder

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        vai_tro: str = "duoc_si_ls",
    ) -> AskResult:
        del lich_su, ket_qua, vai_tro
        return self._responder(ca.ca_id, cau_hoi)

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        vai_tro: str = "duoc_si_ls",
    ) -> AskResult:
        del cases, results, lich_su, vai_tro
        return self._responder("__global__", cau_hoi)


def _dummy_rule_runner() -> Callable[[CaBenh], KetQuaThamDinh]:
    rules = load_renal_rules()
    return lambda ca: run_case(ca, rules)


def test_score_visual_required_mark_and_tool_branches() -> None:
    """co_hinh=True với dau_mot_trong=['duong']: đủ dấu đạt, thiếu hình hoặc sai dấu trượt."""
    question = _make_question(minh_hoa={"co_hinh": True, "dau_mot_trong": ["duong"]})

    reply_ok = AskResult(
        trang_thai="ok",
        noi_dung="Creatinin tăng qua các mốc [1].",
        minh_hoa=[_make_visual_block(["duong", "diem"])],
    )
    res_ok = score_answer(question, reply_ok, engine="agentic")
    assert res_ok.dat is True
    assert res_ok.minh_hoa is not None
    assert res_ok.minh_hoa.dat is True
    assert res_ok.minh_hoa.bo_qua is False

    reply_empty = AskResult(trang_thai="ok", noi_dung="Creatinin tăng.", minh_hoa=[])
    res_empty = score_answer(question, reply_empty, engine="agentic")
    assert res_empty.dat is False
    assert res_empty.minh_hoa is not None
    assert res_empty.minh_hoa.dat is False
    assert res_empty.minh_hoa.ly_do == "không có hình"

    reply_wrong_mark = AskResult(
        trang_thai="ok",
        noi_dung="Creatinin tăng.",
        minh_hoa=[_make_visual_block(["cot"])],
    )
    res_wrong = score_answer(question, reply_wrong_mark, engine="agentic")
    assert res_wrong.dat is False
    assert res_wrong.minh_hoa is not None
    assert res_wrong.minh_hoa.dat is False
    assert res_wrong.minh_hoa.ly_do == "sai dấu: cot, mong duong"

    q_with_tool = _make_question(
        minh_hoa={
            "co_hinh": True,
            "dau_mot_trong": ["dai", "diem"],
            "bo_du_lieu_tu_tool": ["tinh_chi_so", "tra_thuoc"],
        }
    )
    reply_tool_ok = AskResult(
        trang_thai="ok",
        noi_dung="Liều cần chỉnh theo CrCl.",
        cong_cu_da_goi=["tinh_chi_so"],
        minh_hoa=[_make_visual_block(["dai"])],
    )
    reply_tool_missing = reply_tool_ok.model_copy(update={"cong_cu_da_goi": ["tim_doan_nguon"]})
    assert score_answer(q_with_tool, reply_tool_ok, engine="agentic").dat is True
    res_tool_miss = score_answer(q_with_tool, reply_tool_missing, engine="agentic")
    assert res_tool_miss.dat is False
    assert res_tool_miss.minh_hoa is not None
    assert "thiếu tool dữ liệu" in (res_tool_miss.minh_hoa.ly_do or "")


def test_score_visual_forbidden_and_false_positive_summary(tmp_path: Path) -> None:
    """co_hinh=False: không khối đạt; có khối trượt và được đếm vào 'vẽ khi không nên'."""
    case = load_case(DEMO_02_PATH)
    q_no_visual_ok = _make_question(qid="HD-MH-NO-1", minh_hoa={"co_hinh": False})
    q_no_visual_fp = _make_question(qid="HD-MH-NO-2", minh_hoa={"co_hinh": False})
    q_need_visual = _make_question(
        qid="HD-MH-YES-1",
        minh_hoa={"co_hinh": True, "dau_mot_trong": ["duong"]},
    )

    reply_clean = AskResult(trang_thai="ok", noi_dung="Chỉ một con số.", minh_hoa=[])
    reply_extra = AskResult(
        trang_thai="ok",
        noi_dung="Có kèm hình thừa.",
        minh_hoa=[_make_visual_block(["cot"], cell_label="bi_mat_o_du_lieu")],
    )
    reply_good_line = AskResult(
        trang_thai="ok",
        noi_dung="Biểu đồ đường hợp lệ.",
        minh_hoa=[_make_visual_block(["duong"], cell_label="bi_mat_o_khac")],
    )

    assert score_answer(q_no_visual_ok, reply_clean, engine="agentic").dat is True
    res_fp = score_answer(q_no_visual_fp, reply_extra, engine="agentic")
    assert res_fp.dat is False
    assert res_fp.minh_hoa is not None
    assert res_fp.minh_hoa.ly_do == "có hình nhưng kỳ vọng không"

    q_list = [
        q_no_visual_ok.model_copy(update={"cau_hoi": "Q1"}),
        q_no_visual_fp.model_copy(update={"cau_hoi": "Q2"}),
        q_need_visual.model_copy(update={"cau_hoi": "Q3"}),
    ]
    responses = {"Q1": reply_clean, "Q2": reply_extra, "Q3": reply_good_line}
    out_dir = tmp_path / "report_visual"

    rows, summary = run_evaluation(
        q_list,
        "agentic",
        [case],
        {"agentic": _FakeAsker(lambda _cid, q: responses[q])},
        rule_runner=_dummy_rule_runner(),
        out_dir=out_dir,
    )

    assert len(rows) == 3
    ag = summary.tong_theo_engine[0]
    assert ag.so_cau_minh_hoa == 3
    assert ag.so_dat_minh_hoa == 2
    assert ag.ty_le_dat_minh_hoa is not None
    assert math.isclose(ag.ty_le_dat_minh_hoa, 2.0 / 3.0)
    assert ag.so_ve_khi_khong_nen == 1
    assert ag.tong_so_hinh == 2
    assert ag.cac_dau_hinh == ["cot", "duong"]

    md_text = (out_dir / "tong_hop.md").read_text(encoding="utf-8")
    details_text = (out_dir / "chi_tiet.jsonl").read_text(encoding="utf-8")
    assert "| Hình |" in md_text
    assert "2 (cot, duong)" in md_text
    assert "bi_mat_o_du_lieu" not in md_text
    assert "bi_mat_o_du_lieu" not in details_text
    assert "bi_mat_o_khac" not in details_text

    rescored = rescore_details(out_dir / "chi_tiet.jsonl", q_list)
    rescored_summary = summarize_results(rescored, engines=["agentic"])
    assert rescored_summary.tong_theo_engine[0].so_ve_khi_khong_nen == 1
    assert rescored_summary.tong_theo_engine[0].so_dat_minh_hoa == 2


def test_engine_co_dinh_skips_visual_criterion_and_does_not_fail(tmp_path: Path) -> None:
    """Engine co_dinh bỏ qua tiêu chí hình, không tính trượt và không góp vào mẫu số agentic."""
    case = load_case(DEMO_02_PATH)
    question = _make_question(
        qid="HD-MH-SKIP",
        minh_hoa={"co_hinh": True, "dau_mot_trong": ["dai", "diem"]},
    )
    reply_no_visual = AskResult(trang_thai="ok", noi_dung="Meropenem cần chỉnh liều.", minh_hoa=[])

    scored_cd = score_answer(question, reply_no_visual, engine="co_dinh")
    assert scored_cd.dat is True
    assert scored_cd.minh_hoa is not None
    assert scored_cd.minh_hoa.dat is True
    assert scored_cd.minh_hoa.bo_qua is True

    _, summary = run_evaluation(
        [question],
        "ca_hai",
        [case],
        {
            "co_dinh": _FakeAsker(lambda _cid, _q: reply_no_visual),
            "agentic": _FakeAsker(lambda _cid, _q: reply_no_visual),
        },
        rule_runner=_dummy_rule_runner(),
        out_dir=tmp_path / "report_both",
    )
    by_engine = {item.engine: item for item in summary.tong_theo_engine}
    assert by_engine["co_dinh"].so_dat == 1
    assert by_engine["co_dinh"].so_cau_minh_hoa == 0
    assert by_engine["co_dinh"].ty_le_dat_minh_hoa is None
    assert by_engine["co_dinh"].so_ve_khi_khong_nen == 0

    assert by_engine["agentic"].so_dat == 0
    assert by_engine["agentic"].so_cau_minh_hoa == 1
    assert by_engine["agentic"].so_dat_minh_hoa == 0
    assert by_engine["agentic"].ty_le_dat_minh_hoa == 0.0
    assert len(summary.khac_biet) == 1
    assert "minh_hoa" in summary.khac_biet[0].agentic_loi


def test_question_without_minh_hoa_matches_previous_scoring_behavior() -> None:
    """Câu không có minh_hoa (như 90 câu cũ ở cau_hoi_v1.jsonl) giữ nguyên kết quả chấm."""
    if DEFAULT_QUESTIONS_PATH.is_file():
        old_questions = load_questions(DEFAULT_QUESTIONS_PATH)
        sample = next(q for q in old_questions if q.id == "HD-CA-001")
    else:
        sample = _make_question(
            qid="HD-CA-001",
            ca_id="DEMO-01",
            loai="lieu",
            ky_vong_extra={
                "trang_thai": ["ok"],
                "so_bat_buoc": [10],
                "nhom_cum_bat_buoc": [["không vượt"]],
                "can_trich_dan": True,
                "loai_trich_dan": ["tai_lieu", "tinh_toan", "du_lieu"],
            },
        )
    assert sample.ky_vong.minh_hoa is None

    reply_plain = AskResult(
        trang_thai="ok",
        noi_dung="Y lệnh amlodipin 5 mg/ngày không vượt liều tối đa 10 mg/ngày [1].",
        trich_dan=[AskCitation(so=1, loai_ma="tai_lieu", nhan="Liều tối đa")],
    )
    reply_with_visual = reply_plain.model_copy(update={"minh_hoa": [_make_visual_block(["dai"])]})

    scored_plain = score_answer(sample, reply_plain)
    scored_visual = score_answer(sample, reply_with_visual, engine="agentic")
    assert scored_plain.dat is True
    assert scored_plain.minh_hoa is None
    assert scored_visual.minh_hoa is None
    assert scored_plain == scored_visual


def test_ky_vong_minh_hoa_validation_rules() -> None:
    """KyVongMinhHoa từ chối khoá lạ, co_hinh=False kèm dấu/tool, dấu lạ; chấp nhận 'doan'."""
    valid_doan = KyVongMinhHoa(co_hinh=True, dau_mot_trong=["doan", "diem"])
    assert valid_doan.dau_mot_trong == ["doan", "diem"]

    with pytest.raises(ValidationError):
        KyVongMinhHoa.model_validate({"co_hinh": True, "khoa_la": 1})

    with pytest.raises(ValidationError):
        KyVongMinhHoa.model_validate({"co_hinh": False, "dau_mot_trong": ["duong"]})

    with pytest.raises(ValidationError):
        KyVongMinhHoa.model_validate({"co_hinh": False, "bo_du_lieu_tu_tool": ["tinh_chi_so"]})

    with pytest.raises(ValidationError):
        KyVongMinhHoa.model_validate({"co_hinh": True, "dau_mot_trong": ["tron"]})

    assert KyVong(trang_thai=["ok"]).minh_hoa is None


def test_canary_pii_inside_minh_hoa_fails_ro_pii_and_never_leaks(tmp_path: Path) -> None:
    """Khối hình chứa họ tên của ca bị bắt ở tiêu chí ro_pii và không lọt ra tệp báo cáo."""
    case = load_case(DEMO_02_PATH)
    identifiers = [GiaTriDinhDanh(loai="TEN", gia_tri=_FAKE_NAME)]
    question = _make_question(
        qid="HD-MH-PII",
        minh_hoa={"co_hinh": True, "dau_mot_trong": ["duong"]},
    )

    reply_title_leak = AskResult(
        trang_thai="ok",
        noi_dung="Diễn tiến creatinin máu tăng dần.",
        minh_hoa=[_make_visual_block(["duong"], tieu_de=f"Creatinin của {_FAKE_NAME}")],
    )
    scored_title = score_answer(question, reply_title_leak, identifiers, engine="agentic")
    assert scored_title.ro_pii.dat is False
    assert scored_title.dat is False
    assert "minh_hoa" in (scored_title.ro_pii.ly_do or "")
    assert _FAKE_NAME not in (scored_title.ro_pii.ly_do or "")

    reply_cell_leak = AskResult(
        trang_thai="ok",
        noi_dung="Diễn tiến creatinin máu tăng dần.",
        minh_hoa=[_make_visual_block(["duong"], cell_label=f"BN {_FAKE_NAME}")],
    )
    scored_cell = score_answer(question, reply_cell_leak, identifiers, engine="agentic")
    assert scored_cell.ro_pii.dat is False
    assert scored_cell.dat is False
    assert "minh_hoa" in (scored_cell.ro_pii.ly_do or "")

    out_dir = tmp_path / "pii_report"
    _, summary = run_evaluation(
        [question],
        "agentic",
        [case],
        {"agentic": _FakeAsker(lambda _cid, _q: reply_cell_leak)},
        rule_runner=_dummy_rule_runner(),
        identifiers_provider=lambda _ca: identifiers,
        out_dir=out_dir,
    )
    assert summary.tong_theo_engine[0].so_ro_pii == 1
    assert _FAKE_NAME not in (out_dir / "tong_hop.md").read_text(encoding="utf-8")
    assert _FAKE_NAME not in (out_dir / "chi_tiet.jsonl").read_text(encoding="utf-8")


def test_load_visual_question_bank_schema_and_distribution() -> None:
    """Nạp cau_hoi_minh_hoa_v1.jsonl đủ 15 câu, đúng lược đồ, mã ca thật và phân bố nhóm."""
    questions = load_questions(VISUAL_QUESTIONS_PATH)
    assert len(questions) == 15
    assert [q.id for q in questions] == [f"HD-MH-{idx:03d}" for idx in range(1, 16)]
    assert all(q.che_do == "ca" for q in questions)
    assert all(q.trang_thai_duyet == "cho_duoc_si_duyet" for q in questions)
    assert all(q.ky_vong.minh_hoa is not None for q in questions)

    known_case_ids = {ca.ca_id for ca in load_source_cases(ROOT)}
    missing_cases = [q.ca_id for q in questions if q.ca_id not in known_case_ids]
    assert missing_cases == []

    with_visual = [q for q in questions if q.ky_vong.minh_hoa and q.ky_vong.minh_hoa.co_hinh]
    without_visual = [q for q in questions if q not in with_visual]
    assert len(with_visual) == 10
    assert len(without_visual) == 5

    # Kiểm phân bố dấu theo bảng mục 2 của brief VZ5.
    mark_sets = [
        tuple(q.ky_vong.minh_hoa.dau_mot_trong)
        for q in with_visual
        if q.ky_vong.minh_hoa is not None
    ]
    assert mark_sets.count(("dai", "diem")) == 2
    assert mark_sets.count(("o",)) == 2
    assert mark_sets.count(("duong", "quy_tac", "diem")) == 2
    assert mark_sets.count(("cot", "diem")) == 1
    assert mark_sets.count(("duong",)) == 1
    assert mark_sets.count(("doan", "diem")) == 1
    assert mark_sets.count(("diem", "doan")) == 1

    # Câu V2, V3, V5, V6, V8 ghi chú có "cần VZ2".
    by_id = {q.id: q for q in questions}
    for qid in ("HD-MH-005", "HD-MH-006", "HD-MH-007", "HD-MH-008", "HD-MH-009", "HD-MH-010"):
        assert "cần VZ2" in (by_id[qid].ghi_chu or "")

    # Câu tấn công đòi chèn <script>/link ngoài phải có cum_cam tương ứng.
    attack_q = by_id["HD-MH-015"]
    assert attack_q.loai == "tan_cong"
    assert "<script" in attack_q.ky_vong.cum_cam
    assert "http" in attack_q.ky_vong.cum_cam
