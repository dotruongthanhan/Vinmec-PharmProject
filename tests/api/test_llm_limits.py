"""Kiểm thử giới hạn kích thước, tốc độ, ngân sách ngày và tách nguồn hỏi đáp (T88)."""

import threading
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.rate_limit import DailyBudget, LlmRateLimits, SlidingWindowLimiter
from app.api.schemas import DoanNguon
from app.api.service import CaseService
from app.auth.errors import AuthError
from app.auth.principal import Principal
from app.config.settings import load_llm_rate_limits
from app.core.types import Chunk
from app.db.timezone import VN_TZ
from app.domain.loader import load_case
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskCitation, AskResult
from app.pipeline import KetQuaThamDinh

ROOT = Path(__file__).resolve().parents[2]
_DEMO_DIR = ROOT / "data/mock/demo"
_RENAL_PATH = ROOT / "data/kb/quy_tac_lieu_than.json"


class _FakeClock:
    """Đồng hồ giả cho phép tiến thời gian tức thời trong kiểm thử."""

    def __init__(self, initial: float | None = None) -> None:
        if initial is None:
            initial = datetime(2026, 11, 20, 10, 0, 0, tzinfo=VN_TZ).timestamp()
        self.now = initial

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _sample_chunk(chunk_id: str = "DT-LIMIT-01") -> Chunk:
    return Chunk(
        doan_trich_id=chunk_id,
        tai_lieu_id="TL-MERO",
        muc_cha_id=None,
        nhom_nguon="nhan_thuoc",
        nguon="openfda",
        tang_tin_cay=3,
        hoat_chat_ids=["meropenem"],
        muc="lieu_than",
        duong_dan_muc="Dosage and Administration > Renal Impairment",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="20261102",
        url_goc="https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=mero",
        noi_dung_goc="Administer one-half the recommended dose every 12 hours.",
        noi_dung_nhung="[Meropenem | FDA] Administer one-half the recommended dose every 12 hours.",
    )


class _FakeAiRunner:
    """Bộ chạy AI giả đếm số lần chạy và có thể giữ trạng thái đang chạy bằng Event."""

    model_name = "model-test"

    def __init__(
        self,
        *,
        entered: threading.Event | None = None,
        release: threading.Event | None = None,
    ) -> None:
        self.calls = 0
        self._lock = threading.Lock()
        self._entered = entered
        self._release = release

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        del ca
        with self._lock:
            self.calls += 1
        if self._entered is not None:
            self._entered.set()
        if self._release is not None:
            self._release.wait(timeout=2.0)
        return AiRunResult(
            llm=KetQuaLLM(
                trang_thai="ok",
                nhan_dinh=[
                    NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in ket_qua.phat_hien
                ],
                so_lan_goi=1,
                canh_bao=[],
                phien_ban_prompt="tong_hop.v1",
                mo_hinh="model-test",
            ),
            doan=[],
            canh_bao=[],
            thoi_gian_ms=5.0,
        )


class _FakeAsker:
    """Bộ hỏi đáp giả đếm số lượt gọi LLM cho cả theo ca và hỏi đáp chung."""

    def __init__(self, chunks: Sequence[Chunk] | None = None) -> None:
        self.calls = 0
        self.global_calls = 0
        self._chunks = list(chunks) if chunks is not None else []

    def _reply(self, text: str) -> AskResult:
        citations = (
            [
                AskCitation(
                    so=1,
                    loai_ma="tai_lieu",
                    nhan="Nhãn FDA · Liều",
                    doan_trich_id=self._chunks[0].doan_trich_id,
                    trich_nguyen_van="recommended dose every 12 hours.",
                )
            ]
            if self._chunks
            else []
        )
        return AskResult(
            trang_thai="ok",
            noi_dung=text,
            trich_dan=citations,
            cong_cu_da_goi=["du_lieu_ca"],
            thoi_gian_ms=1,
            doan=list(self._chunks),
        )

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
        self.calls += 1
        return self._reply("Trả lời giả lập [1]." if self._chunks else "Trả lời giả lập.")

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        del cases, results, cau_hoi, lich_su
        self.global_calls += 1
        return self._reply("Trả lời chung giả lập [1]." if self._chunks else "Trả lời chung.")


class _FakeAuthenticator:
    """Bộ xác thực giả trả hai Principal khác nhau theo token, không gọi mạng."""

    def __init__(self) -> None:
        self.principals = {
            "tok-user-a": Principal(
                nguoi_dung_id="user-aaaa-1111-2222",
                email="a@example.invalid",
                vai_tro="duoc_si_ls",
                phien_id="sess-a",
                het_han_luc=9_999_999_999.0,
            ),
            "tok-user-b": Principal(
                nguoi_dung_id="user-bbbb-3333-4444",
                email="b@example.invalid",
                vai_tro="duoc_si_ls",
                phien_id="sess-b",
                het_han_luc=9_999_999_999.0,
            ),
        }

    def verify(self, token: str) -> Principal:
        principal = self.principals.get(token)
        if principal is None:
            raise AuthError()
        return principal

    def online_check(self, token: str) -> str:
        return self.verify(token).vai_tro


@pytest.fixture(autouse=True)
def _force_file_case_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE_SOURCE", "file")


def _make_service(
    tmp_path: Path,
    *,
    ai_runner: object = None,
    asker: object = None,
    limits: LlmRateLimits | None = None,
    case_dir: Path = _DEMO_DIR,
) -> CaseService:
    return CaseService(
        case_dir,
        _RENAL_PATH,
        tmp_path / "phan_hoi.jsonl",
        ai_runner=ai_runner,
        asker=asker,
        limits=limits,
    )


def test_schema_size_limits_return_422(tmp_path: Path) -> None:
    """Test 4: kiểm tra giới hạn lich_su, noi_dung, ly_do, nhan_dinh_id và dau_vao."""
    asker = _FakeAsker()
    service = _make_service(tmp_path, ai_runner=_FakeAiRunner(), asker=asker)
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        detail = client.get("/api/cases/DEMO-02").json()
        nid = detail["nhan_dinh"]["can_chu_y"][0]["nhan_dinh_id"]

        too_many_history = client.post(
            "/api/cases/DEMO-02/ask",
            json={
                "cau_hoi": "Câu hỏi hợp lệ",
                "lich_su": [{"vai": "nguoi_dung", "noi_dung": "tin"}] * 7,
            },
        )
        assert too_many_history.status_code == 422
        assert too_many_history.json()["loi"]["ma"] == "du_lieu_khong_hop_le"

        too_long_msg = client.post(
            "/api/cases/DEMO-02/ask",
            json={
                "cau_hoi": "Câu hỏi hợp lệ",
                "lich_su": [{"vai": "he_thong", "noi_dung": "x" * 4001}],
            },
        )
        assert too_long_msg.status_code == 422

        too_long_ask_nid = client.post(
            "/api/cases/DEMO-02/ask",
            json={
                "cau_hoi": "Câu hỏi hợp lệ",
                "lich_su": [],
                "nhan_dinh_id": "n" * 129,
            },
        )
        assert too_long_ask_nid.status_code == 422

        too_long_reason = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": nid, "phan_hoi": "dong_y", "ly_do": "r" * 1001},
        )
        assert too_long_reason.status_code == 422

        too_long_group = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": nid, "phan_hoi": "dong_y", "nhom_ly_do": "g" * 65},
        )
        assert too_long_group.status_code == 422

        too_long_fb_nid = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": "n" * 129, "phan_hoi": "dong_y"},
        )
        assert too_long_fb_nid.status_code == 422

        too_many_formula_keys = client.post(
            "/api/cong-thuc/cockcroft_gault",
            json={"dau_vao": {f"k_{idx}": 1 for idx in range(31)}},
        )
        assert too_many_formula_keys.status_code == 422

        too_long_formula_key = client.post(
            "/api/cong-thuc/cockcroft_gault",
            json={"dau_vao": {"k" * 65: 1}},
        )
        assert too_long_formula_key.status_code == 422

        too_long_formula_str = client.post(
            "/api/cong-thuc/cockcroft_gault",
            json={"dau_vao": {"tuoi": "1" * 201}},
        )
        assert too_long_formula_str.status_code == 422

        # Giá trị đúng biên vẫn được chấp nhận.
        ok_ask = client.post(
            "/api/cases/DEMO-02/ask",
            json={
                "cau_hoi": "Câu hỏi hợp lệ",
                "lich_su": [{"vai": "nguoi_dung", "noi_dung": "a" * 4000}] * 6,
            },
        )
        assert ok_ask.status_code == 200
        assert asker.calls == 1

        ok_fb = client.post(
            "/api/cases/DEMO-02/feedback",
            json={"nhan_dinh_id": nid, "phan_hoi": "dong_y", "ly_do": "l" * 1000},
        )
        assert ok_fb.status_code == 200


def test_ask_rate_limit_resets_after_5min_and_logs_without_question(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test 5: LLM_ASK_PER_5MIN=3 chặn lượt 4 với 429 + Retry-After, tiến 5 phút chạy lại."""
    monkeypatch.setenv("LLM_ASK_PER_5MIN", "3")
    clock = _FakeClock()
    limits = LlmRateLimits.from_env(clock=clock)
    asker = _FakeAsker()
    service = _make_service(tmp_path, ai_runner=_FakeAiRunner(), asker=asker, limits=limits)

    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        assert client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Hỏi 1"}).status_code == 200
        assert client.post("/api/ask", json={"cau_hoi": "Hỏi chung 2"}).status_code == 200
        assert client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Hỏi 3"}).status_code == 200
        assert asker.calls + asker.global_calls == 3

        with caplog.at_level("WARNING", logger="app.api.service"):
            blocked = client.post(
                "/api/cases/DEMO-02/ask",
                json={"cau_hoi": "Nội dung câu hỏi nhạy cảm không được log"},
            )
        assert blocked.status_code == 429
        assert "retry-after" in blocked.headers
        assert int(blocked.headers["retry-after"]) == 300
        assert blocked.json()["loi"]["ma"] == "vuot_gioi_han"
        assert asker.calls + asker.global_calls == 3
        assert "vuot_gioi_han" in caplog.text
        assert "/api/cases/{ca_id}/ask" in caplog.text
        assert "dev-loca" in caplog.text
        assert "Nội dung câu hỏi nhạy cảm" not in caplog.text

        clock.advance(300.0)
        resumed = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Hỏi sau 5 phút"})
        assert resumed.status_code == 200
        assert asker.calls + asker.global_calls == 4


def test_different_users_have_independent_rate_limits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 6: hai người dùng khác nhau có hạn mức tốc độ tách biệt."""
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("SUPABASE_URL", "https://auth.example.invalid")
    monkeypatch.setenv("LLM_ASK_PER_5MIN", "2")
    monkeypatch.setenv("LLM_AI_PER_HOUR", "1")
    clock = _FakeClock()
    limits = LlmRateLimits.from_env(clock=clock)
    asker = _FakeAsker()
    service = _make_service(tmp_path, ai_runner=_FakeAiRunner(), asker=asker, limits=limits)
    auth = _FakeAuthenticator()

    headers_a = {"Authorization": "Bearer tok-user-a"}
    headers_b = {"Authorization": "Bearer tok-user-b"}
    with TestClient(create_app(service, auth=auth), raise_server_exceptions=False) as client:
        for _ in range(2):
            assert (
                client.post(
                    "/api/cases/DEMO-02/ask",
                    json={"cau_hoi": "Hỏi A"},
                    headers=headers_a,
                ).status_code
                == 200
            )
        blocked_a = client.post(
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "Hỏi A lần 3"},
            headers=headers_a,
        )
        assert blocked_a.status_code == 429
        assert blocked_a.json()["loi"]["ma"] == "vuot_gioi_han"

        for _ in range(2):
            assert (
                client.post(
                    "/api/cases/DEMO-02/ask",
                    json={"cau_hoi": "Hỏi B"},
                    headers=headers_b,
                ).status_code
                == 200
            )

        ai_a = client.post("/api/cases/DEMO-02/ai", json={}, headers=headers_a)
        assert ai_a.status_code == 200
        # Người B khởi động AI trên ca khác vẫn được trong hạn mức riêng của B.
        ai_b = client.post("/api/cases/DEMO-03/ai", json={}, headers=headers_b)
        assert ai_b.status_code == 200


def test_daily_budget_blocks_on_third_call_and_resets_at_vn_midnight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 7: LLM_DAILY_CALLS=2 -> lượt 3 trả 429 het_ngan_sach_ngay, qua ngày VN đặt lại."""
    monkeypatch.setenv("LLM_DAILY_CALLS", "2")
    late_vn = datetime(2026, 11, 20, 23, 59, 50, tzinfo=VN_TZ).timestamp()
    clock = _FakeClock(late_vn)
    limits = LlmRateLimits.from_env(clock=clock)
    asker = _FakeAsker()
    service = _make_service(tmp_path, ai_runner=_FakeAiRunner(), asker=asker, limits=limits)

    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        assert client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Lượt 1"}).status_code == 200
        assert client.post("/api/ask", json={"cau_hoi": "Lượt 2"}).status_code == 200

        blocked = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Lượt 3"})
        assert blocked.status_code == 429
        assert blocked.json()["loi"]["ma"] == "het_ngan_sach_ngay"
        assert int(blocked.headers["retry-after"]) == 10
        assert asker.calls + asker.global_calls == 2

        # Qua 00:00 giờ Việt Nam (17:00 UTC) -> ngân sách được đặt lại.
        clock.advance(15.0)
        resumed = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Ngày mới"})
        assert resumed.status_code == 200
        assert asker.calls + asker.global_calls == 3


def test_post_ai_restart_20_times_while_running_runs_once_without_429(tmp_path: Path) -> None:
    """Test 8: POST /ai chay_lai=true lặp 20 lần khi đang chạy -> chạy 1 lần, không 429."""
    entered = threading.Event()
    release = threading.Event()
    runner = _FakeAiRunner(entered=entered, release=release)
    limits = LlmRateLimits(ai_per_hour=1, daily_calls=1, clock=_FakeClock())
    service = _make_service(tmp_path, ai_runner=runner, asker=_FakeAsker(), limits=limits)

    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        try:
            started = client.post("/api/cases/DEMO-02/ai", json={"chay_lai": True})
            assert started.status_code == 200
            assert started.json()["trang_thai"] == "dang_chay"
            assert entered.wait(timeout=2.0)

            for _ in range(20):
                resp = client.post("/api/cases/DEMO-02/ai", json={"chay_lai": True})
                assert resp.status_code == 200
                assert resp.json()["trang_thai"] == "dang_chay"

            assert runner.calls == 1
        finally:
            release.set()

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            status = client.get("/api/cases/DEMO-02/ai")
            if status.json()["trang_thai"] == "xong":
                break
            time.sleep(0.01)
        assert runner.calls == 1


def test_disabled_ai_and_missing_case_do_not_consume_limits(tmp_path: Path) -> None:
    """Test 9: khi AI tắt, gọi /ask 50 lần không 429; ca 404 cũng không trừ lượt."""
    limits_off = LlmRateLimits(ask_per_5min=2, ai_per_hour=1, daily_calls=2, clock=_FakeClock())
    disabled_service = _make_service(tmp_path, ai_runner=None, asker=None, limits=limits_off)
    with TestClient(create_app(disabled_service), raise_server_exceptions=False) as client:
        for _ in range(50):
            resp = client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Vì sao?"})
            assert resp.status_code == 200
            assert resp.json()["trang_thai"] == "chua_san_sang"
        assert client.post("/api/ask", json={"cau_hoi": "Hỏi chung?"}).status_code == 200
        assert client.post("/api/cases/DEMO-02/ai").json()["trang_thai"] == "tat"

    limits_on = LlmRateLimits(ask_per_5min=1, ai_per_hour=1, daily_calls=1, clock=_FakeClock())
    asker = _FakeAsker()
    enabled_service = _make_service(
        tmp_path / "on",
        ai_runner=_FakeAiRunner(),
        asker=asker,
        limits=limits_on,
    )
    with TestClient(create_app(enabled_service), raise_server_exceptions=False) as client:
        for _ in range(5):
            missing_ask = client.post(
                "/api/cases/KHONG-CO/ask",
                json={"cau_hoi": "Ca lạ?"},
            )
            assert missing_ask.status_code == 404
            assert client.post("/api/cases/KHONG-CO/ai").status_code == 404
        assert client.post("/api/cases/DEMO-02/ask", json={"cau_hoi": "Ca thật"}).status_code == 200
        assert asker.calls == 1


def test_global_sources_isolated_by_user_and_capped_at_200(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test 10 (L5): nguồn __global__ tách theo user và giữ tối đa 200 đoạn mỗi khoá."""
    monkeypatch.setenv("AUTH_MODE", "required")
    monkeypatch.setenv("SUPABASE_URL", "https://auth.example.invalid")
    auth = _FakeAuthenticator()
    chunk = _sample_chunk("DT-GLOBAL-A1")
    asker = _FakeAsker(chunks=[chunk])
    limits = LlmRateLimits(ask_per_5min=100, daily_calls=100, clock=_FakeClock())
    service = _make_service(tmp_path, ai_runner=_FakeAiRunner(), asker=asker, limits=limits)

    headers_a = {"Authorization": "Bearer tok-user-a"}
    headers_b = {"Authorization": "Bearer tok-user-b"}
    with TestClient(create_app(service, auth=auth), raise_server_exceptions=False) as client:
        ask_resp = client.post("/api/ask", json={"cau_hoi": "Hỏi chung"}, headers=headers_a)
        assert ask_resp.status_code == 200

        own_src = client.get("/api/cases/__global__/sources/DT-GLOBAL-A1", headers=headers_a)
        assert own_src.status_code == 200
        DoanNguon.model_validate(own_src.json(), extra="forbid")

        other_src = client.get("/api/cases/__global__/sources/DT-GLOBAL-A1", headers=headers_b)
        assert other_src.status_code == 404

        # Ghi 201 đoạn vào khoá __global__ của B -> còn 200, đoạn đầu tiên bị bỏ.
        asker._chunks = [_sample_chunk(f"DT-CAP-{idx:03}") for idx in range(201)]
        bulk_resp = client.post("/api/ask", json={"cau_hoi": "Nạp 201 đoạn"}, headers=headers_b)
        assert bulk_resp.status_code == 200
        key_b = "__global__:user-bbbb-3333-4444"
        assert len(service._ask_sources[key_b]) == 200
        for chunk_id, expected in (
            ("DT-CAP-000", 404),
            ("DT-CAP-001", 200),
            ("DT-CAP-200", 200),
        ):
            resp = client.get(f"/api/cases/__global__/sources/{chunk_id}", headers=headers_b)
            assert resp.status_code == expected

        # Kiểm tra cả khoá theo ca giữ tối đa 200 đoạn.
        case_resp = client.post(
            "/api/cases/DEMO-02/ask",
            json={"cau_hoi": "Nạp 201 đoạn ca"},
            headers=headers_a,
        )
        assert case_resp.status_code == 200
        assert len(service._ask_sources["DEMO-02"]) == 200
        for chunk_id, expected in (("DT-CAP-000", 404), ("DT-CAP-200", 200)):
            resp = client.get(f"/api/cases/DEMO-02/sources/{chunk_id}", headers=headers_a)
            assert resp.status_code == expected


def test_http_ai_queue_full_returns_429_retry_after_30_without_burning_limits(
    tmp_path: Path,
) -> None:
    """Khi 6 ca đang chạy, ca thứ 7 trả 429 hang_doi_day với Retry-After=30."""
    case_dir = tmp_path / "cases"
    case_dir.mkdir()
    template = load_case(_DEMO_DIR / "DEMO-01.json")
    for idx in range(1, 8):
        case = template.model_copy(update={"ca_id": f"CA-{idx:02}"})
        (case_dir / f"CA-{idx:02}.json").write_text(case.model_dump_json(), encoding="utf-8")

    entered_count = 0
    count_lock = threading.Lock()
    two_running = threading.Event()
    release = threading.Event()

    class _SlowRunner(_FakeAiRunner):
        def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
            nonlocal entered_count
            with count_lock:
                entered_count += 1
                if entered_count >= 2:
                    two_running.set()
            return super().run(ca, ket_qua)

    runner = _SlowRunner(release=release)
    limits = LlmRateLimits(ai_per_hour=10, daily_calls=7, clock=_FakeClock())
    service = _make_service(
        tmp_path,
        ai_runner=runner,
        asker=_FakeAsker(),
        limits=limits,
        case_dir=case_dir,
    )
    with TestClient(create_app(service), raise_server_exceptions=False) as client:
        try:
            for idx in range(1, 7):
                resp = client.post(f"/api/cases/CA-{idx:02}/ai")
                assert resp.status_code == 200
                assert resp.json()["trang_thai"] == "dang_chay"
            assert two_running.wait(timeout=2.0)

            full = client.post("/api/cases/CA-07/ai")
            assert full.status_code == 429
            assert full.json()["loi"]["ma"] == "hang_doi_day"
            assert full.headers["retry-after"] == "30"
        finally:
            release.set()

        # Ngân sách ngày (còn 1/7) không bị tiêu tốn bởi lỗi hang_doi_day.
        after = client.post("/api/cases/CA-07/ai")
        assert after.status_code == 200


def test_invalid_env_limits_fallback_to_defaults_with_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Biến môi trường LLM_* rỗng hoặc sai -> dùng mặc định và chỉ cảnh báo khi sai."""
    monkeypatch.setenv("LLM_ASK_PER_5MIN", "   ")
    monkeypatch.setenv("LLM_AI_PER_HOUR", "")
    monkeypatch.delenv("LLM_DAILY_CALLS", raising=False)
    with caplog.at_level("WARNING", logger="app.config.settings"):
        assert load_llm_rate_limits() == (20, 15, 600)
    assert caplog.records == []

    monkeypatch.setenv("LLM_ASK_PER_5MIN", "abc")
    monkeypatch.setenv("LLM_AI_PER_HOUR", "0")
    monkeypatch.setenv("LLM_DAILY_CALLS", "-10")
    with caplog.at_level("WARNING", logger="app.config.settings"):
        limits = LlmRateLimits.from_env(clock=_FakeClock())
    assert limits.ask_limiter._limit == 20
    assert limits.ai_limiter._limit == 15
    assert limits.daily_budget._limit == 600
    assert "LLM_ASK_PER_5MIN" in caplog.text
    assert "LLM_AI_PER_HOUR" in caplog.text
    assert "LLM_DAILY_CALLS" in caplog.text
    assert "abc" not in caplog.text
    assert "-10" not in caplog.text


def test_sliding_window_and_daily_budget_thread_safety_and_header_preservation(
    tmp_path: Path,
) -> None:
    """Kiểm tra an toàn luồng trực tiếp và trình xử lý HTTPException giữ exc.headers."""
    clock = _FakeClock()
    limiter = SlidingWindowLimiter(5, 60.0, clock=clock)
    results: list[float | None] = []
    res_lock = threading.Lock()

    def worker() -> None:
        outcome = limiter.hit("shared-user")
        with res_lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
    assert results.count(None) == 5
    assert sum(1 for item in results if item is not None) == 5

    budget = DailyBudget(2, clock=clock)
    assert budget.take() is True
    assert budget.take() is True
    assert budget.take() is False

    service = _make_service(tmp_path, ai_runner=None, asker=None)
    app = create_app(service)
    test_router = APIRouter()

    @test_router.get("/api/test-retry-after")
    def raise_retry_after() -> None:
        raise HTTPException(
            429,
            detail={"ma": "vuot_gioi_han", "thong_bao": "Thử lại sau."},
            headers={"Retry-After": "42"},
        )

    app.router.routes.insert(0, test_router.routes[0])

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/test-retry-after")
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "42"
        assert resp.json()["loi"]["ma"] == "vuot_gioi_han"
