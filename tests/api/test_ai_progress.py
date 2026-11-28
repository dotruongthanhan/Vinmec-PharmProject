"""Kiểm thử tiến trình phân tích AI qua API: trạng thái, song song và bảo mật."""

import json
import threading
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.schemas import KetQuaAI
from app.api.service import CaseService
from app.container import build_container
from app.core.errors import ProviderError
from app.core.progress import MAX_PROGRESS_STEPS, MAX_PROGRESS_TEXT_LEN, ghi_buoc
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.domain.models import CaBenh
from app.kb.names import DrugNameIndex
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.evidence import EvidenceCollector
from app.pipeline import KetQuaThamDinh
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from tests.api.test_contract import _check_display_strings
from tests.core.test_types import make_chunk
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/tong_hop.v1.md"
NAMES = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")


class _StaticRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        del query
        return [ScoredChunk(chunk=c, diem=0.9, nguon_diem="xep_hang_lai") for c in self._chunks]


def _poll_until_done(client: TestClient, ca_id: str, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/cases/{ca_id}/ai")
        assert resp.status_code == 200
        body = resp.json()
        if body["trang_thai"] != "dang_chay":
            return body
        time.sleep(0.01)
    raise AssertionError("Quá thời gian chờ AI hoàn tất")


def _all_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_all_strings(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_all_strings(item))
        return out
    return []


def test_api_ai_progress_for_disabled_running_done_and_error(tmp_path: Path) -> None:
    # 1. Trạng thái tat -> cac_buoc=[], da_chay_ms=None, thuong_le_ms=None.
    off_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb_off.jsonl",
        ai_runner=None,
    )
    with TestClient(create_app(off_service)) as client:
        off_body = client.post("/api/cases/DEMO-02/ai").json()
        assert off_body["trang_thai"] == "tat"
        assert off_body["cac_buoc"] == []
        assert off_body["da_chay_ms"] is None
        assert off_body["thuong_le_ms"] is None

    # 2. Trạng thái dang_chay và xong với bước thật.
    entered_synth = threading.Event()
    release_synth = threading.Event()

    class _ControlledRunner:
        model_name = "model-test"

        def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
            del ca
            ghi_buoc("bat_dau", "thu_thap_nguon")
            ghi_buoc("xong", "thu_thap_nguon", chi_tiet="2 đoạn từ 1 nguồn")
            ghi_buoc("bat_dau", "tong_hop_1", chi_tiet="Đang gọi mô hình")
            entered_synth.set()
            release_synth.wait(timeout=2.0)
            ghi_buoc("xong", "tong_hop_1")
            ghi_buoc("bat_dau", "kiem_chung_1")
            ghi_buoc("xong", "kiem_chung_1", chi_tiet="1/1 dòng đạt")
            rule_rows = [NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in ket_qua.phat_hien]
            return AiRunResult(
                llm=KetQuaLLM(
                    trang_thai="ok",
                    nhan_dinh=rule_rows,
                    so_lan_goi=1,
                    canh_bao=[],
                    phien_ban_prompt="tong_hop.v1",
                    mo_hinh="model-test",
                ),
                doan=[],
                canh_bao=[],
                thoi_gian_ms=10.0,
            )

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb_on.jsonl",
        ai_runner=_ControlledRunner(),
    )
    with TestClient(create_app(service)) as client:
        client.post("/api/cases/DEMO-02/ai")
        assert entered_synth.wait(timeout=2.0)

        running = client.get("/api/cases/DEMO-02/ai").json()
        KetQuaAI.model_validate(running, extra="forbid")
        _check_display_strings(running)
        assert running["trang_thai"] == "dang_chay"
        assert running["da_chay_ms"] >= 0.0
        assert running["thuong_le_ms"] is None
        assert [b["ma"] for b in running["cac_buoc"]] == [
            "thu_thap_nguon",
            "tong_hop_1",
            "kiem_chung_1",
        ]
        assert running["cac_buoc"][0]["trang_thai"] == "xong"
        assert running["cac_buoc"][1]["trang_thai"] == "dang_chay"
        assert running["cac_buoc"][1]["thoi_gian_ms"] >= 0.0
        assert running["cac_buoc"][2]["trang_thai"] == "cho"

        release_synth.set()
        done = _poll_until_done(client, "DEMO-02")
        KetQuaAI.model_validate(done, extra="forbid")
        _check_display_strings(done)
        assert done["trang_thai"] == "xong"
        assert done["da_chay_ms"] >= 0.0
        assert all(b["trang_thai"] == "xong" for b in done["cac_buoc"])

        # Chạy thêm 2 ca nữa để đủ 3 mẫu cho thuong_le_ms.
        for cid in ("DEMO-01", "DEMO-03"):
            client.post(f"/api/cases/{cid}/ai")
            _poll_until_done(client, cid)
        third = client.get("/api/cases/DEMO-03/ai").json()
        assert isinstance(third["thuong_le_ms"], float)
        assert third["thuong_le_ms"] >= 0.0

    # 3. Trạng thái loi khi runner ném ngoại lệ: cac_buoc vẫn có và không rò message lỗi.
    class _FailingRunner:
        model_name = "model-test"

        def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
            del ca, ket_qua
            ghi_buoc("bat_dau", "thu_thap_nguon")
            raise RuntimeError("SECRET_STACK_TRACE_LEAK")

    err_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb_err.jsonl",
        ai_runner=_FailingRunner(),
    )
    with TestClient(create_app(err_service)) as client:
        client.post("/api/cases/DEMO-02/ai")
        err_body = _poll_until_done(client, "DEMO-02")
        KetQuaAI.model_validate(err_body, extra="forbid")
        assert err_body["trang_thai"] == "loi"
        assert err_body["da_chay_ms"] >= 0.0
        assert err_body["cac_buoc"][0]["trang_thai"] == "loi"
        assert err_body["cac_buoc"][1]["trang_thai"] == "bo_qua"
        assert "SECRET_STACK_TRACE_LEAK" not in json.dumps(err_body, ensure_ascii=False)


def test_api_parallel_cases_do_not_mix_progress_steps(tmp_path: Path) -> None:
    barrier = threading.Barrier(2)

    class _ParallelRunner:
        model_name = "model-test"

        def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
            barrier.wait(timeout=2.0)
            ghi_buoc("bat_dau", "thu_thap_nguon")
            n_lines = len(ca.y_lenh_cho_duyet.chi_tiet)
            ghi_buoc("xong", "thu_thap_nguon", chi_tiet=f"{n_lines} đoạn từ 1 nguồn")
            ghi_buoc(
                "them",
                f"rieng_{ca.ca_id.lower().replace('-', '_')}",
                ten=f"Bước {ca.ca_id}",
            )
            rule_rows = [NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in ket_qua.phat_hien]
            return AiRunResult(
                llm=KetQuaLLM(
                    trang_thai="ok",
                    nhan_dinh=rule_rows,
                    so_lan_goi=1,
                    canh_bao=[],
                    phien_ban_prompt="tong_hop.v1",
                    mo_hinh="model-test",
                ),
                doan=[],
                canh_bao=[],
                thoi_gian_ms=5.0,
            )

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb_par.jsonl",
        ai_runner=_ParallelRunner(),
    )
    with TestClient(create_app(service)) as client:
        client.post("/api/cases/DEMO-01/ai")
        client.post("/api/cases/DEMO-02/ai")
        b1 = _poll_until_done(client, "DEMO-01")
        b2 = _poll_until_done(client, "DEMO-02")

        ma1 = [b["ma"] for b in b1["cac_buoc"]]
        ma2 = [b["ma"] for b in b2["cac_buoc"]]
        assert "rieng_demo_01" in ma1 and "rieng_demo_02" not in ma1
        assert "rieng_demo_02" in ma2 and "rieng_demo_01" not in ma2


def test_security_no_patient_drug_prompt_or_exception_leaks_in_cac_buoc(
    tmp_path: Path,
) -> None:
    raw_case = json.loads((ROOT / "data/mock/demo/DEMO-02.json").read_text(encoding="utf-8"))
    raw_case["dien_bien"][0]["noi_dung"] = (
        "Bệnh nhân Nguyen Van Bi Mat 999 đang dùng ThuocBiMatXYZ, SĐT 0912345678."
    )
    raw_case["dot_dieu_tri"]["quan_ly"]["bac_si_dieu_tri"] = "BS Tran Thi Giau Ten"
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    case_file = case_dir / "DEMO-02.json"
    case_file.write_text(json.dumps(raw_case, ensure_ascii=False), encoding="utf-8")

    container = build_container("test")
    chunk = make_chunk(
        "DT-MERO-01",
        "administer one-half the recommended dose every 12 hours.",
        nguon="openfda",
    )
    collector = EvidenceCollector(
        _StaticRetriever([chunk]),
        QueryBuilder(container.settings.retrieval),
        NAMES.resolve,
    )
    fake_llm = FakeLLM(
        [
            {
                "nhan_dinh": [
                    {
                        "chi_tiet_y_lenh_id": [temp_id("DEMO-02", "CT-DEMO02-01")],
                        "yeu_to": 5,
                        "ket_luan": "can_xem",
                        "muc_do": "can_luu_y",
                        "nhan_xet": "AI_RAW_OUTPUT_SECRET Creatinin 212 umol/L.",
                        "ban_ghi_ids": [temp_id("DEMO-02", "XN-DEMO02-01")],
                        "trich_dan": [],
                        "thong_tin_con_thieu": [],
                        "de_xuat": None,
                        "bo_sung_cho_ma_luat": None,
                    }
                ]
            }
        ]
    )
    synth = Synthesizer(
        llm=fake_llm,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=2,
        model_name="model-test",
    )
    reviewer = AiReviewer(collector, synth, engine="langgraph")

    service = CaseService(
        case_dir,
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb_sec.jsonl",
        ai_runner=reviewer,
    )
    with TestClient(create_app(service)) as client:
        client.post("/api/cases/DEMO-02/ai")
        body = _poll_until_done(client, "DEMO-02")
        steps_json = json.dumps(body["cac_buoc"], ensure_ascii=False)
        for sensitive in (
            "Nguyen Van Bi Mat 999",
            "ThuocBiMatXYZ",
            "0912345678",
            "Tran Thi Giau Ten",
            "AI_RAW_OUTPUT_SECRET",
            "NB-DEMO-02",
        ):
            assert sensitive not in steps_json
        assert len(body["cac_buoc"]) <= MAX_PROGRESS_STEPS
        for s in _all_strings(body["cac_buoc"]):
            assert len(s) <= MAX_PROGRESS_TEXT_LEN

    # Trường hợp lỗi nhà cung cấp có chuỗi nhạy cảm trong exception message.
    class _LeakyProviderLLM:
        def complete_json(self, messages: list[Any], schema: dict) -> dict:
            del messages, schema
            raise ProviderError("HTTP 500: Nguyen Van Bi Mat 999 SECRET_EXC_MSG")

    leaky_synth = Synthesizer(
        llm=_LeakyProviderLLM(),  # type: ignore[arg-type]
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=12000,
        max_synthesis_attempts=1,
        model_name="model-test",
    )
    leaky_service = CaseService(
        case_dir,
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "fb_sec2.jsonl",
        ai_runner=AiReviewer(collector, leaky_synth, engine="langgraph"),
    )
    with TestClient(create_app(leaky_service)) as client:
        client.post("/api/cases/DEMO-02/ai")
        err_body = _poll_until_done(client, "DEMO-02")
        steps_json = json.dumps(err_body["cac_buoc"], ensure_ascii=False)
        assert "Nguyen Van Bi Mat 999" not in steps_json
        assert "SECRET_EXC_MSG" not in steps_json
        assert len(err_body["cac_buoc"]) <= MAX_PROGRESS_STEPS
        for s in _all_strings(err_body["cac_buoc"]):
            assert len(s) <= MAX_PROGRESS_TEXT_LEN
