"""Kiểm thử tracer JSONL và các điểm móc không gọi mạng."""

import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent.tools.base import ToolContext
from app.api.main import create_app
from app.api.service import CaseService
from app.config.settings import TracerSettings
from app.core.errors import ConfigError
from app.core.progress import ghi_buoc
from app.core.types import ChatMessage
from app.db.timezone import VN_TZ
from app.deid.known import GiaTriDinhDanh
from app.deid.session import DeidSession
from app.domain.loader import load_case
from app.eval.hoi_dap import CauHoiDanhGia, run_evaluation
from app.orchestration.ask import AskResult
from app.providers.fakes import FakeLLM
from app.tracing import (
    JsonlTraceSink,
    Tracer,
    bat_dau_vet,
    dat_tracer_mac_dinh,
    don_vet_qua_han,
    goi_llm_co_vet,
    span,
)
from tests.agent.test_asker import _make_asker
from tests.agent.test_gateway import _setup
from tests.eval.test_cham_hoi_dap import _FakeAsker, _question_dict

ROOT = Path(__file__).resolve().parents[2]


def _read_trace(tracer: Tracer, path: Path) -> dict:
    assert tracer.flush()
    files = list(path.glob("vet-*.jsonl"))
    assert len(files) == 1
    return json.loads(files[0].read_text(encoding="utf-8").splitlines()[0])


class _FakeLLM:
    model = "fake"
    last_usage = {"prompt_tokens": 12, "completion_tokens": 7}

    def complete_json(self, messages: list[ChatMessage], schema: dict) -> dict:
        del messages, schema
        return {"ok": True}


def test_tree_gateway_and_tokens(tmp_path: Path) -> None:
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path)))
    _, gateway = _setup(so_lan_goi_toi_da=3)
    ctx = ToolContext(
        vai_tro="duoc_si_ls", che_do="ca", han_chot=time.monotonic() + 30, cau_hoi_goc="test"
    )
    with tracer.bat_dau_vet("hoi_dap", "agentic", ca_id="CA-GIA") as vet:
        assert vet is not None
        ghi_buoc("bat_dau", "agent_tac_tu", ten="Tác tử")
        goi_llm_co_vet(_FakeLLM(), [ChatMessage(role="user", content="xin chào")], {})
        for _ in range(2):
            assert gateway.goi("cong_cu_thu", {"cau_truy_van": "meropenem"}, ctx).trang_thai == "ok"
        with span("kiem_chung", "kiem_chung", ma_ly_do=["so_khong_co_nguon:0912345678"]):
            pass
        ghi_buoc("xong", "agent_tac_tu")
    record = _read_trace(tracer, tmp_path)
    assert uuid.UUID(record["ma_vet"]).version == 4
    steps = record["cac_buoc"]
    assert [s["loai"] for s in steps] == ["node", "llm", "tool", "tool", "kiem_chung"]
    assert all(s["ma_buoc_cha"] == steps[0]["ma_buoc"] for s in steps[1:])
    assert (record["tong_token_vao"], record["tong_token_ra"], record["so_tool"]) == (12, 7, 2)
    assert steps[-1]["thuoc_tinh"]["ma_ly_do"] == ["so_khong_co_nguon:#10"]
    assert record["ca_bam"] != "CA-GIA"
    tracer.close()


def test_full_queue_does_not_block(tmp_path: Path) -> None:
    sink = JsonlTraceSink(tmp_path, hang_doi_toi_da=1, auto_start=False)
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path)), sink=sink)
    with tracer.bat_dau_vet("hoi_dap", "co_dinh"):
        pass
    with tracer.bat_dau_vet("hoi_dap", "co_dinh"):
        answer = "trả lời bình thường"
    assert answer == "trả lời bình thường"
    assert tracer.so_vet_bi_bo == 1
    tracer.close()


def test_production_rejects_full_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ConfigError, match="day_du"):
        Tracer(TracerSettings(muc_noi_dung="day_du"))


@pytest.mark.parametrize("level", ["sieu_du_lieu", "noi_dung_da_che", "day_du"])
def test_canary_and_unknown_attributes(tmp_path: Path, level: str) -> None:
    tracer = Tracer(
        TracerSettings.model_validate({"thu_muc": str(tmp_path), "muc_noi_dung": level})
    )
    _, gateway = _setup()
    question = (
        "Bệnh nhân Giả Lập Sáu Ba, HN HN998877, SĐT 0912345678 CCCD 012345678901 sk-test-canary-123"
    )
    ctx = ToolContext(
        vai_tro="duoc_si_ls", che_do="ca", han_chot=time.monotonic() + 30, cau_hoi_goc=question
    )
    with tracer.bat_dau_vet("hoi_dap", "agentic"):
        goi_llm_co_vet(_FakeLLM(), [ChatMessage(role="user", content=question)], {})
        gateway.goi("cong_cu_thu", {"cau_truy_van": question}, ctx)
        with span("node", "buoc", truong_la=question):
            pass
    record = _read_trace(tracer, tmp_path)
    raw = json.dumps(record, ensure_ascii=False)
    for item in ("Giả Lập Sáu Ba", "HN998877", "0912345678", "012345678901", "sk-test-canary-123"):
        assert item not in raw
    assert record["so_khoa_la_bi_bo"] == 1
    assert any(s["loai"] == "su_kien_bao_mat" for s in record["cac_buoc"])
    tracer.close()


def test_retention_and_noop(tmp_path: Path) -> None:
    now = datetime(2026, 11, 27, tzinfo=VN_TZ)
    old = tmp_path / f"vet-{(now - timedelta(days=31)).date()}.jsonl"
    recent = tmp_path / f"vet-{(now - timedelta(days=30)).date()}.jsonl"
    old.touch()
    recent.touch()
    assert don_vet_qua_han(30, thu_muc=tmp_path, dong_ho=lambda: now) == 1
    assert not old.exists() and recent.exists()
    with span("node", "khong_co_vet") as s:
        s.dat_thuoc_tinh(so_vong=1)


def test_content_masks_known_name_without_altering_session(tmp_path: Path) -> None:
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="noi_dung_da_che"))
    session = DeidSession([GiaTriDinhDanh(loai="TEN", gia_tri="Giả Lập 63")])
    with tracer.bat_dau_vet("hoi_dap", "agentic") as vet:
        assert vet is not None
        vet.dat_phien_che(session)
        goi_llm_co_vet(_FakeLLM(), [ChatMessage(role="user", content="Giả Lập 63")], {})
    record = _read_trace(tracer, tmp_path)
    assert "Giả Lập 63" not in json.dumps(record, ensure_ascii=False)
    assert record["cac_buoc"][0]["noi_dung"] is not None
    assert session.anh_xa == {}
    tracer.close()


def test_agent_graph_uses_trace_and_deid_session(tmp_path: Path) -> None:
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path), muc_noi_dung="noi_dung_da_che"))
    llm = FakeLLM([{"hanh_dong": "tra_loi", "tra_loi": {"pham_vi": "trong", "tra_loi": "ok"}}])
    asker = _make_asker(llm)
    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    with tracer.bat_dau_vet("hoi_dap", "agentic", ca_id=case.ca_id) as vet:
        assert vet is not None
        result = asker.ask(case, "Có nguồn không?")
        assert result.ma_vet == vet.ma_vet
    record = _read_trace(tracer, tmp_path)
    assert any(step["loai"] == "che_pii" for step in record["cac_buoc"])
    assert any(step["loai"] == "llm" for step in record["cac_buoc"])
    tracer.close()


def test_limits_and_exception_do_not_record_message(tmp_path: Path) -> None:
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path)))
    with tracer.bat_dau_vet("hoi_dap", "co_dinh"):
        with pytest.raises(ValueError):
            with span("node", "loi"):
                raise ValueError("thong_diep_bi_mat")
        with span("kiem_chung", "dai", ma_ly_do=["x:" + "1" * 6000] * 30):
            pass
        for _ in range(205):
            with span("node", "buoc"):
                pass
    record = _read_trace(tracer, tmp_path)
    assert record["vet_bi_cat"] is True
    assert len(record["cac_buoc"]) == 200
    assert record["cac_buoc"][0]["trang_thai"] == "loi"
    assert record["cac_buoc"][0]["thuoc_tinh"]["loai_ngoai_le"] == "ValueError"
    assert "thong_diep_bi_mat" not in json.dumps(record)
    assert len(json.dumps(record["cac_buoc"][1]["thuoc_tinh"], ensure_ascii=False).encode()) <= 4096
    assert len(json.dumps(record, ensure_ascii=False).encode()) <= 256 * 1024
    tracer.close()


def test_disabled_explicit_tracer_ignores_global(tmp_path: Path) -> None:
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path)))
    previous = dat_tracer_mac_dinh(tracer)
    try:
        with bat_dau_vet("hoi_dap", "co_dinh", tracer=None) as vet:
            assert vet is None
    finally:
        dat_tracer_mac_dinh(previous)
        tracer.close()


def test_eval_trace_matches_detail(tmp_path: Path) -> None:
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path / "vet")))
    previous = dat_tracer_mac_dinh(tracer)
    question = CauHoiDanhGia.model_validate(
        _question_dict(id="HD-CH-001", che_do="chung", ca_id=None)
    )

    def respond(_case_id: str, question_text: str) -> AskResult:
        goi_llm_co_vet(_FakeLLM(), [ChatMessage(role="user", content=question_text)], {})
        return AskResult(trang_thai="ok", noi_dung="Câu trả lời giả lập")

    try:
        rows, _ = run_evaluation(
            [question],
            "co_dinh",
            [],
            {"co_dinh": _FakeAsker(respond)},
            out_dir=tmp_path / "report",
        )
        record = _read_trace(tracer, tmp_path / "vet")
        detail = json.loads((tmp_path / "report/chi_tiet.jsonl").read_text(encoding="utf-8"))
        assert record["loai"] == "danh_gia"
        assert record["tong_token_vao"] == 12
        assert rows[0].ma_vet == detail["ma_vet"] == record["ma_vet"]
    finally:
        dat_tracer_mac_dinh(previous)
        tracer.close()


def test_api_header_matches_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_MODE", "off")
    tracer = Tracer(TracerSettings(thu_muc=str(tmp_path / "vet")))

    class FakeAsker:
        def ask(self, *args: object, **kwargs: object) -> AskResult:
            return AskResult(trang_thai="ok", noi_dung="Trả lời giả lập")

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
        ai_runner=lambda: None,
        asker=FakeAsker(),
        tracer=tracer,
    )
    with TestClient(create_app(service)) as client:
        response = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Xin chào"})
        assert response.status_code == 200
        record = _read_trace(tracer, tmp_path / "vet")
        assert response.headers["X-Ma-Vet"] == response.json()["ma_vet"] == record["ma_vet"]


def test_langsmith_remains_disabled() -> None:
    for path in ("app/agent/asker.py", "app/orchestration/ai_review.py"):
        assert "tracing_context(enabled=False)" in (ROOT / path).read_text(encoding="utf-8")
