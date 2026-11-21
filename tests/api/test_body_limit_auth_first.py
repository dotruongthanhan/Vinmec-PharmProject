"""Kiểm thử chặn thân yêu cầu lớn và yêu cầu thiếu Bearer trước khi định tuyến (T1)."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.types import Message

from app.api.main import create_app
from app.api.service import CaseService
from app.auth.errors import AuthError
from app.auth.principal import Principal
from app.domain.models import CaBenh
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskResult
from app.pipeline import KetQuaThamDinh

ROOT = Path(__file__).resolve().parents[2]
_DEMO_DIR = ROOT / "data/mock/demo"
_RENAL_PATH = ROOT / "data/kb/quy_tac_lieu_than.json"


class _FakeAiRunner:
    """Bộ chạy AI giả để bật hỏi đáp trong CaseService mà không gọi LLM thật."""

    model_name = "deepseek-flash"

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult:
        del ca
        return AiRunResult(
            llm=KetQuaLLM(
                trang_thai="ok",
                nhan_dinh=[
                    NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in ket_qua.phat_hien
                ],
                so_lan_goi=1,
                canh_bao=[],
                phien_ban_prompt="tong_hop.v1",
                mo_hinh="deepseek-flash",
            ),
            doan=[],
            canh_bao=[],
            thoi_gian_ms=1.0,
        )


class _FakeAsker:
    """Bộ hỏi đáp giả đếm số lượt gọi khi yêu cầu đi qua được lớp bảo vệ."""

    def __init__(self) -> None:
        self.calls = 0
        self.global_calls = 0

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
        return AskResult(trang_thai="ok", noi_dung="Trả lời giả lập.", thoi_gian_ms=1)

    def ask_global(
        self,
        cases: Any,
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        del cases, results, cau_hoi, lich_su
        self.global_calls += 1
        return AskResult(trang_thai="ok", noi_dung="Trả lời chung giả lập.", thoi_gian_ms=1)


class _FakeAuthenticator:
    """Bộ xác thực giả theo mẫu tests/api/test_auth_ownership.py, không gọi mạng."""

    def __init__(self) -> None:
        self.verify_calls = 0
        self.principals = {
            "valid-token": Principal(
                nguoi_dung_id="simulated-user-a",
                email="account@example.invalid",
                vai_tro="duoc_si_ls",
                phien_id="simulated-session-a",
                het_han_luc=9_999_999_999.0,
            )
        }

    def verify(self, token: str) -> Principal:
        self.verify_calls += 1
        principal = self.principals.get(token)
        if principal is None:
            raise AuthError()
        return principal

    def online_check(self, token: str) -> str:
        return self.verify(token).vai_tro


def _build_app(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    auth_mode: str,
) -> tuple[Any, CaseService, _FakeAsker, _FakeAuthenticator]:
    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.delenv("CDSS_RUNTIME", raising=False)
    monkeypatch.setenv("AUTH_MODE", auth_mode)
    if auth_mode != "off":
        monkeypatch.setenv("SUPABASE_URL", "https://auth.example.invalid")
    asker = _FakeAsker()
    auth = _FakeAuthenticator()
    service = CaseService(
        _DEMO_DIR,
        _RENAL_PATH,
        tmp_path / "phan_hoi.jsonl",
        ai_runner=_FakeAiRunner(),
        asker=asker,
    )
    app = create_app(service, auth=auth)
    return app, service, asker, auth


async def _call_asgi(
    app: Any,
    *,
    method: str,
    path: str,
    headers: list[tuple[bytes, bytes]],
    chunks: list[bytes],
) -> tuple[int, dict[str, Any], int]:
    """Gọi thẳng ASGI để kiểm chứng có đọc receive hay không và hành vi chunked."""
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "app": app,
    }
    receive_calls = 0
    chunk_iter = iter(chunks)

    async def spy_receive() -> Message:
        nonlocal receive_calls
        receive_calls += 1
        data = next(chunk_iter, b"")
        return {"type": "http.request", "body": data, "more_body": bool(data)}

    status = 0
    body_parts: list[bytes] = []

    async def capture_send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = int(message["status"])
        elif message["type"] == "http.response.body":
            body_parts.append(message.get("body", b""))

    await app(scope, spy_receive, capture_send)
    parsed = json.loads(b"".join(body_parts).decode("utf-8"))
    return status, parsed, receive_calls


def test_unauthenticated_malformed_json_returns_401_without_reading_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _, asker, auth = _build_app(tmp_path, monkeypatch, auth_mode="required")
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/api/ask",
            content=b"{hong-json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401
        assert resp.json()["loi"]["ma"] == "chua_dang_nhap"
        assert auth.verify_calls == 0
        assert asker.global_calls == 0

        for bad_header in ("Basic abc", "Bearer", "Bearer ", "Bearer a b"):
            bad_resp = client.post(
                "/api/cases/DEMO-02/ask",
                content=b"{hong-json",
                headers={"Content-Type": "application/json", "Authorization": bad_header},
            )
            assert bad_resp.status_code == 401
            assert bad_resp.json()["loi"]["ma"] == "chua_dang_nhap"
        assert auth.verify_calls == 0

    app2, service2, _, auth2 = _build_app(tmp_path / "asgi", monkeypatch, auth_mode="required")
    try:
        status, body, receive_calls = asyncio.run(
            _call_asgi(
                app2,
                method="POST",
                path="/api/ask",
                headers=[(b"content-type", b"application/json")],
                chunks=[b"{hong-json"],
            )
        )
        assert status == 401
        assert body["loi"]["ma"] == "chua_dang_nhap"
        assert receive_calls == 0
        assert auth2.verify_calls == 0
    finally:
        service2.shutdown()


def test_valid_token_oversized_body_returns_413_and_1kb_body_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _, asker, auth = _build_app(tmp_path, monkeypatch, auth_mode="required")
    auth_headers = {"Authorization": "Bearer valid-token", "Content-Type": "application/json"}
    with TestClient(app, raise_server_exceptions=False) as client:
        too_big = client.post("/api/ask", content=b"x" * 300_000, headers=auth_headers)
        assert too_big.status_code == 413
        assert too_big.json()["loi"]["ma"] == "than_qua_lon"
        assert asker.global_calls == 0
        assert auth.verify_calls == 0

        one_kb_payload = json.dumps(
            {"cau_hoi": "Ca này có cần lưu ý gì? " + ("a" * 965)},
            ensure_ascii=False,
        ).encode("utf-8")
        assert 950 <= len(one_kb_payload) <= 1200

        ok_resp = client.post("/api/ask", content=one_kb_payload, headers=auth_headers)
        assert ok_resp.status_code == 200
        assert ok_resp.json()["trang_thai"] == "ok"
        assert asker.global_calls == 1
        assert auth.verify_calls >= 1

    app2, service2, asker2, _ = _build_app(tmp_path / "chunked", monkeypatch, auth_mode="required")
    try:
        status_413, body_413, reads_413 = asyncio.run(
            _call_asgi(
                app2,
                method="POST",
                path="/api/ask",
                headers=[
                    (b"authorization", b"Bearer valid-token"),
                    (b"content-type", b"application/json"),
                    (b"transfer-encoding", b"chunked"),
                ],
                chunks=[b"x" * 100_000, b"x" * 100_000, b"x" * 100_000, b"x" * 100_000],
            )
        )
        assert status_413 == 413
        assert body_413["loi"]["ma"] == "than_qua_lon"
        assert reads_413 == 3
        assert asker2.global_calls == 0

        small_payload = json.dumps({"cau_hoi": "Hỏi dạng chunked 1 KB?"}).encode("utf-8")
        status_200, body_200, _ = asyncio.run(
            _call_asgi(
                app2,
                method="POST",
                path="/api/ask",
                headers=[
                    (b"authorization", b"Bearer valid-token"),
                    (b"content-type", b"application/json"),
                    (b"transfer-encoding", b"chunked"),
                ],
                chunks=[small_payload[:10], small_payload[10:], b""],
            )
        )
        assert status_200 == 200
        assert body_200["trang_thai"] == "ok"
        assert asker2.global_calls == 1
    finally:
        service2.shutdown()


def test_health_and_cors_preflight_work_without_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _, _, auth = _build_app(tmp_path, monkeypatch, auth_mode="required")
    with TestClient(app, raise_server_exceptions=False) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True
        assert health.json()["xac_thuc"] == "required"

        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            preflight = client.options(
                "/api/ask",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Authorization, Content-Type",
                },
            )
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == origin

        disallowed = client.options(
            "/api/ask",
            headers={
                "Origin": "https://example.invalid",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert disallowed.status_code == 400
        assert "access-control-allow-origin" not in disallowed.headers

        unauth_with_origin = client.post(
            "/api/ask",
            content=b"{broken",
            headers={"Origin": "http://localhost:5173", "Content-Type": "application/json"},
        )
        assert unauth_with_origin.status_code == 401
        assert unauth_with_origin.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert auth.verify_calls == 0


def test_auth_mode_off_allows_no_token_but_still_rejects_oversized_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _, asker, _ = _build_app(tmp_path, monkeypatch, auth_mode="off")
    with TestClient(app, raise_server_exceptions=False) as client:
        ok_resp = client.post("/api/ask", json={"cau_hoi": "Câu hỏi hợp lệ?"})
        assert ok_resp.status_code == 200
        assert ok_resp.json()["trang_thai"] == "ok"
        assert asker.global_calls == 1

        bad_json = client.post(
            "/api/ask",
            content=b"{broken",
            headers={"Content-Type": "application/json"},
        )
        assert bad_json.status_code == 422
        assert bad_json.json()["loi"]["ma"] == "du_lieu_khong_hop_le"

        too_big = client.post(
            "/api/ask",
            content=b"x" * 300_000,
            headers={"Content-Type": "application/json"},
        )
        assert too_big.status_code == 413
        assert too_big.json()["loi"]["ma"] == "than_qua_lon"
        assert asker.global_calls == 1
