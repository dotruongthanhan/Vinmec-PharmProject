"""Kiểm thử API tiến trình hỏi đáp: luồng ca/chung, hết hạn 60s, 429, token và bảo mật."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.rate_limit import LlmRateLimits
from app.api.schemas import TienTrinhHoiDap, TraLoi
from app.api.service import CaseService
from app.auth.principal import Principal
from app.auth.roles import CLINICAL_PHARMACIST
from app.container import build_container
from app.core.errors import ProviderError
from app.core.progress import MAX_PROGRESS_STEPS, MAX_PROGRESS_TEXT_LEN, ghi_buoc
from app.domain.models import CaBenh
from app.kb.names import DrugNameIndex
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskCitation, AskResult, CaseAsker
from app.pipeline import KetQuaThamDinh
from app.providers.fakes import FakeLLM
from app.retrieval.query_builder import QueryBuilder
from tests.api.test_contract import _check_display_strings
from tests.deid_support import temp_id

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/hoi_them.v1.md"
NAMES = DrugNameIndex.load(ROOT / "data/kb/hoat_chat.json")


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


class _ControlledAsker:
    """Bộ hỏi đáp giả cho phép chặn ở bước đang chạy để kiểm tra GET tiến trình."""

    def __init__(self, entered: threading.Event, release: threading.Event) -> None:
        self._entered = entered
        self._release = release

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult:
        del ca, cau_hoi, lich_su, ket_qua, ai_result, nhan_dinh_id
        ghi_buoc("bat_dau", "chuan_bi", ten="Đọc hồ sơ ca và chạy bộ luật")
        ghi_buoc("xong", "chuan_bi")
        ghi_buoc("bat_dau", "truy_xuat", ten="Tra cứu nhãn thuốc và hướng dẫn")
        ghi_buoc("xong", "truy_xuat", chi_tiet="Không dùng tra cứu nguồn")
        ghi_buoc("bat_dau", "goi_mo_hinh", chi_tiet="Đang gọi mô hình", ten="Soạn câu trả lời")
        self._entered.set()
        assert self._release.wait(timeout=3.0)
        ghi_buoc("xong", "goi_mo_hinh")
        ghi_buoc("bat_dau", "kiem_chung", ten="Kiểm chứng trích dẫn và số liệu")
        ghi_buoc("xong", "kiem_chung", chi_tiet="Đạt")
        return AskResult(
            trang_thai="ok",
            noi_dung="Creatinin 212 umol/L [1].",
            trich_dan=[
                AskCitation(
                    so=1,
                    loai_ma="du_lieu",
                    nhan="Xét nghiệm",
                    ban_ghi_id="XN-DEMO02-01",
                )
            ],
            cong_cu_da_goi=["du_lieu_ca", "bo_luat"],
            thoi_gian_ms=12,
        )

    def ask_global(
        self,
        cases: list[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        del results, cau_hoi, lich_su
        ghi_buoc("bat_dau", "chuan_bi", ten="Tổng hợp danh sách y lệnh")
        ghi_buoc("xong", "chuan_bi", chi_tiet=f"{len(cases)} ca")
        ghi_buoc("bat_dau", "goi_mo_hinh", chi_tiet="Đang gọi mô hình", ten="Soạn câu trả lời")
        self._entered.set()
        assert self._release.wait(timeout=3.0)
        ghi_buoc("xong", "goi_mo_hinh")
        ghi_buoc("bat_dau", "kiem_chung", ten="Kiểm chứng trích dẫn và số liệu")
        ghi_buoc("xong", "kiem_chung", chi_tiet="Đạt")
        return AskResult(
            trang_thai="ok",
            noi_dung="Có 6 ca trong hàng đợi.",
            trich_dan=[],
            cong_cu_da_goi=["danh_sach_y_lenh", "bo_luat"],
            thoi_gian_ms=9,
        )


def _make_service(
    tmp_path: Path,
    *,
    case_dir: Path | None = None,
    asker: Any = None,
    limits: LlmRateLimits | None = None,
) -> CaseService:
    return CaseService(
        case_dir if case_dir is not None else (ROOT / "data/mock/demo"),
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=object(),
        asker=asker,
        limits=limits,
    )


def test_ask_progress_empty_for_unknown_case_and_validates_case_id_length(
    tmp_path: Path,
) -> None:
    service = _make_service(tmp_path)
    with TestClient(create_app(service)) as client:
        case_resp = client.get("/api/cases/KHONG-TON-TAI/ask/tien-trinh")
        assert case_resp.status_code == 200
        assert case_resp.json() == {"dang_chay": False, "cac_buoc": [], "da_chay_ms": None}
        TienTrinhHoiDap.model_validate(case_resp.json(), extra="forbid")

        global_resp = client.get("/api/ask/tien-trinh")
        assert global_resp.status_code == 200
        assert global_resp.json() == {"dang_chay": False, "cac_buoc": [], "da_chay_ms": None}

        max_ok = client.get(f"/api/cases/{'A' * 128}/ask/tien-trinh")
        assert max_ok.status_code == 200

        too_long = client.get(f"/api/cases/{'A' * 129}/ask/tien-trinh")
        assert too_long.status_code == 422
        assert too_long.json()["loi"]["ma"] == "du_lieu_khong_hop_le"


def test_ask_progress_case_and_global_lifecycle_retention_and_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock_now = [1000.0]
    entered = threading.Event()
    release = threading.Event()
    service = _make_service(tmp_path, asker=_ControlledAsker(entered, release))
    monkeypatch.setattr(service._ask_progress, "_clock", lambda: clock_now[0])

    with (
        TestClient(create_app(service)) as client,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        # 1. Hỏi đáp theo ca: đang chạy -> xong (đọc lại trong 60s) -> hết hạn sau 60s.
        future = pool.submit(
            client.post,
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "Creatinin thế nào?"},
        )
        assert entered.wait(timeout=10.0)

        mid_resp = client.get("/api/cases/DEMO-02/ask/tien-trinh")
        assert mid_resp.status_code == 200
        mid = mid_resp.json()
        TienTrinhHoiDap.model_validate(mid, extra="forbid")
        _check_display_strings(mid)
        assert mid["dang_chay"] is True
        assert mid["da_chay_ms"] >= 0.0
        # Bước chỉ xuất hiện khi thật sự bắt đầu: chưa tới kiểm chứng thì chưa có bước đó.
        assert [b["ma"] for b in mid["cac_buoc"]] == [
            "chuan_bi",
            "truy_xuat",
            "goi_mo_hinh",
        ]
        assert [b["ten"] for b in mid["cac_buoc"]] == [
            "Đọc hồ sơ ca và chạy bộ luật",
            "Tra cứu nhãn thuốc và hướng dẫn",
            "Soạn câu trả lời",
        ]
        assert mid["cac_buoc"][0]["trang_thai"] == "xong"
        assert mid["cac_buoc"][1]["trang_thai"] == "xong"
        assert mid["cac_buoc"][2]["trang_thai"] == "dang_chay"
        assert not any(b["trang_thai"] == "cho" for b in mid["cac_buoc"])

        release.set()
        post_resp = future.result(timeout=3.0)
        assert post_resp.status_code == 200
        TraLoi.model_validate(post_resp.json(), extra="forbid")
        assert post_resp.json()["trang_thai"] == "ok"

        done_resp = client.get("/api/cases/DEMO-02/ask/tien-trinh")
        assert done_resp.status_code == 200
        done = done_resp.json()
        TienTrinhHoiDap.model_validate(done, extra="forbid")
        assert done["dang_chay"] is False
        assert done["da_chay_ms"] >= 0.0
        assert all(b["trang_thai"] == "xong" for b in done["cac_buoc"])
        assert done["cac_buoc"][3]["chi_tiet"] == "Đạt"

        clock_now[0] += 61.0
        expired = client.get("/api/cases/DEMO-02/ask/tien-trinh").json()
        assert expired == {"dang_chay": False, "cac_buoc": [], "da_chay_ms": None}

        # 2. Hỏi đáp chung (/api/ask và /api/ask/tien-trinh).
        entered.clear()
        release.clear()
        g_future = pool.submit(client.post, "/api/ask", json={"cau_hoi": "Tổng quan hàng đợi?"})
        assert entered.wait(timeout=10.0)

        g_mid = client.get("/api/ask/tien-trinh").json()
        TienTrinhHoiDap.model_validate(g_mid, extra="forbid")
        assert g_mid["dang_chay"] is True
        assert [b["ma"] for b in g_mid["cac_buoc"]] == ["chuan_bi", "goi_mo_hinh"]
        assert g_mid["cac_buoc"][0]["ten"] == "Tổng hợp danh sách y lệnh"
        assert g_mid["cac_buoc"][1]["trang_thai"] == "dang_chay"

        release.set()
        g_post = g_future.result(timeout=3.0)
        assert g_post.status_code == 200
        TraLoi.model_validate(g_post.json(), extra="forbid")

        g_done = client.get("/api/ask/tien-trinh").json()
        assert g_done["dang_chay"] is False
        assert all(b["trang_thai"] == "xong" for b in g_done["cac_buoc"])


def test_ask_progress_isolates_between_users(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")

    class _TokenAuth:
        _users = {
            "tok-a": Principal(nguoi_dung_id="user-a", vai_tro=CLINICAL_PHARMACIST, phien_id="s-a"),
            "tok-b": Principal(nguoi_dung_id="user-b", vai_tro=CLINICAL_PHARMACIST, phien_id="s-b"),
        }

        def verify(self, token: str) -> Principal:
            return self._users[token]

        def online_check(self, token: str) -> str:
            return self._users[token].vai_tro

    entered = threading.Event()
    release = threading.Event()
    service = _make_service(tmp_path, asker=_ControlledAsker(entered, release))
    headers_a = {"Authorization": "Bearer tok-a"}
    headers_b = {"Authorization": "Bearer tok-b"}

    with (
        TestClient(create_app(service, auth=_TokenAuth())) as client,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        assert client.get("/api/cases/DEMO-02/ask/tien-trinh").status_code == 401

        future = pool.submit(
            client.post,
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "Câu hỏi của A"},
            headers=headers_a,
        )
        assert entered.wait(timeout=10.0)

        # User B cùng ca_id không thấy tiến trình của user A.
        b_mid = client.get("/api/cases/DEMO-02/ask/tien-trinh", headers=headers_b)
        assert b_mid.status_code == 200
        assert b_mid.json() == {"dang_chay": False, "cac_buoc": [], "da_chay_ms": None}

        a_mid = client.get("/api/cases/DEMO-02/ask/tien-trinh", headers=headers_a)
        assert a_mid.status_code == 200
        assert a_mid.json()["dang_chay"] is True

        release.set()
        assert future.result(timeout=3.0).status_code == 200

        assert client.get("/api/cases/DEMO-02/ask/tien-trinh", headers=headers_b).json() == {
            "dang_chay": False,
            "cac_buoc": [],
            "da_chay_ms": None,
        }
        a_done = client.get("/api/cases/DEMO-02/ask/tien-trinh", headers=headers_a).json()
        assert a_done["dang_chay"] is False


def test_ask_progress_security_no_leak_and_no_step_logging(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_case = json.loads((ROOT / "data/mock/demo/DEMO-02.json").read_text(encoding="utf-8"))
    raw_case["dien_bien"][0]["noi_dung"] = "Hồ sơ BENHNHAN-XYZ dùng Meropenem, SĐT 0912345678."
    raw_case["dot_dieu_tri"]["quan_ly"]["bac_si_dieu_tri"] = "BS BENHNHAN-XYZ"
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    (case_dir / "DEMO-02.json").write_text(
        json.dumps(raw_case, ensure_ascii=False),
        encoding="utf-8",
    )

    container = build_container("test")
    ok_llm = FakeLLM(
        [
            {
                "pham_vi": "trong",
                "tra_loi": "Creatinin 212 umol/L [1].",
                "trich_dan": [
                    {
                        "so": 1,
                        "loai": "du_lieu_ca",
                        "ma": temp_id("DEMO-02", "XN-DEMO02-01"),
                    }
                ],
            }
        ]
    )
    asker_ok = CaseAsker(
        llm=ok_llm,
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    service_ok = _make_service(tmp_path / "ok", case_dir=case_dir, asker=asker_ok)
    with caplog.at_level("INFO"), TestClient(create_app(service_ok)) as client:
        resp = client.post(
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "BENHNHAN-XYZ có creatinin bao nhiêu?"},
        )
        assert resp.status_code == 200
        progress = client.get("/api/cases/DEMO-02/ask/tien-trinh").json()
        TienTrinhHoiDap.model_validate(progress, extra="forbid")
        serialized = json.dumps(progress, ensure_ascii=False)
        for sensitive in ("BENHNHAN-XYZ", "NB-DEMO-02", "0912345678", "Meropenem"):
            assert sensitive not in serialized
        assert len(progress["cac_buoc"]) <= MAX_PROGRESS_STEPS
        for text in _all_strings(progress["cac_buoc"]):
            assert len(text) <= MAX_PROGRESS_TEXT_LEN
        assert "Chuẩn bị ngữ cảnh ca" not in caplog.text
        assert "Kiểm chứng trích dẫn và số liệu" not in caplog.text

    class _LeakyProviderLLM:
        def complete_json(self, messages: list[Any], schema: dict) -> dict:
            del messages, schema
            raise ProviderError("HTTP 500: BENHNHAN-XYZ SECRET_ERR_MSG")

    asker_err = CaseAsker(
        llm=_LeakyProviderLLM(),  # type: ignore[arg-type]
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    service_err = _make_service(tmp_path / "err", case_dir=case_dir, asker=asker_err)
    with TestClient(create_app(service_err)) as client:
        resp = client.post(
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "BENHNHAN-XYZ hỏi khi lỗi?"},
        )
        assert resp.status_code == 200
        assert resp.json()["trang_thai"] == "loi"
        err_progress = client.get("/api/cases/DEMO-02/ask/tien-trinh").json()
        serialized_err = json.dumps(err_progress, ensure_ascii=False)
        assert "BENHNHAN-XYZ" not in serialized_err
        assert "SECRET_ERR_MSG" not in serialized_err
        assert err_progress["dang_chay"] is False
        assert len(err_progress["cac_buoc"]) <= MAX_PROGRESS_STEPS
        for text in _all_strings(err_progress["cac_buoc"]):
            assert len(text) <= MAX_PROGRESS_TEXT_LEN


def test_ask_progress_rate_limit_429_still_closes_entry(tmp_path: Path) -> None:
    container = build_container("test")
    ok_llm = FakeLLM(
        [
            {
                "pham_vi": "trong",
                "tra_loi": "Creatinin 212 umol/L [1].",
                "trich_dan": [
                    {
                        "so": 1,
                        "loai": "du_lieu_ca",
                        "ma": temp_id("DEMO-02", "XN-DEMO02-01"),
                    }
                ],
            }
        ]
    )
    asker = CaseAsker(
        llm=ok_llm,
        retriever=None,
        query_builder=QueryBuilder(container.settings.retrieval),
        resolve_name=NAMES.resolve,
        prompt_path=PROMPT_PATH,
        case_settings=container.settings.case_context,
        evidence_max_chars=container.settings.evidence.max_chars,
        model_name="deepseek-flash",
        renal_rules=container.renal_rules,
    )
    limits = LlmRateLimits(ask_per_5min=1, ai_per_hour=10, daily_calls=100)
    service = _make_service(tmp_path, asker=asker, limits=limits)
    with TestClient(create_app(service)) as client:
        first = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Creatinin?"})
        assert first.status_code == 200

        second = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Hỏi tiếp?"})
        assert second.status_code == 429

        progress = client.get("/api/cases/DEMO-02/ask/tien-trinh").json()
        TienTrinhHoiDap.model_validate(progress, extra="forbid")
        assert progress["dang_chay"] is False
        assert progress["cac_buoc"][0]["trang_thai"] == "loi"
        assert progress["cac_buoc"][0]["ly_do"] == "Vượt giới hạn lượt hỏi"
        assert progress["cac_buoc"][0]["goi_y"] == "Chờ ít giây rồi hỏi lại"
        assert all(b["trang_thai"] == "bo_qua" for b in progress["cac_buoc"][1:])


def test_ask_progress_consecutive_requests_do_not_let_old_clear_new(
    tmp_path: Path,
) -> None:
    entered_1 = threading.Event()
    entered_2 = threading.Event()
    gate_1 = threading.Event()
    gate_2 = threading.Event()

    class _TwoRoundAsker:
        def __init__(self) -> None:
            self._lock = threading.Lock()
            self._call = 0

        def ask(
            self,
            ca: CaBenh,
            cau_hoi: str,
            lich_su: list[tuple[str, str]] | None = None,
            *,
            ket_qua: KetQuaThamDinh | None = None,
            ai_result: AiRunResult | None = None,
            nhan_dinh_id: str | None = None,
        ) -> AskResult:
            del ca, cau_hoi, lich_su, ket_qua, ai_result, nhan_dinh_id
            with self._lock:
                self._call += 1
                turn = self._call
            ghi_buoc("bat_dau", "chuan_bi")
            ghi_buoc("xong", "chuan_bi", chi_tiet=f"Lượt {turn}")
            ghi_buoc("bat_dau", "goi_mo_hinh")
            if turn == 1:
                entered_1.set()
                assert gate_1.wait(timeout=3.0)
            else:
                entered_2.set()
                assert gate_2.wait(timeout=3.0)
            ghi_buoc("xong", "goi_mo_hinh")
            return AskResult(
                trang_thai="ok",
                noi_dung=f"Xong lượt {turn}",
                trich_dan=[],
                cong_cu_da_goi=["du_lieu_ca"],
                thoi_gian_ms=5,
            )

    service = _make_service(tmp_path, asker=_TwoRoundAsker())
    with (
        TestClient(create_app(service)) as client,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        f1 = pool.submit(client.post, "/api/cases/DEMO-02/ask", json={"cau_hoi": "Lượt 1"})
        assert entered_1.wait(timeout=10.0)

        f2 = pool.submit(client.post, "/api/cases/DEMO-02/ask", json={"cau_hoi": "Lượt 2"})
        assert entered_2.wait(timeout=10.0)

        # Lượt 1 kết thúc sau khi lượt 2 đã bắt đầu -> không được chốt hay xoá mục lượt 2.
        gate_1.set()
        assert f1.result(timeout=3.0).status_code == 200

        during_2 = client.get("/api/cases/DEMO-02/ask/tien-trinh").json()
        assert during_2["dang_chay"] is True
        assert during_2["cac_buoc"][0]["chi_tiet"] == "Lượt 2"
        assert during_2["cac_buoc"][1]["trang_thai"] == "dang_chay"

        gate_2.set()
        assert f2.result(timeout=3.0).status_code == 200

        after_2 = client.get("/api/cases/DEMO-02/ask/tien-trinh").json()
        assert after_2["dang_chay"] is False
        assert after_2["cac_buoc"][0]["chi_tiet"] == "Lượt 2"
