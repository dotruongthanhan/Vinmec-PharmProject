"""Kiểm thử lưu phản hồi và hội thoại trên DB giả lập, sở hữu và chế độ CaseService DB."""

from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import ExitStack, closing, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.schemas import MedicalRecord
from app.api.service import CaseService
from app.auth.principal import Principal
from app.auth.roles import ADMIN, CLINICAL_PHARMACIST
from app.db.reader import DatabaseReadError, DbReviewService
from app.domain.loader import load_case
from app.feedback import PhanHoi
from app.orchestration.ask import AskCitation, AskResult
from app.providers.fakes import FakeLLM
from app.storage import feedback_chat as fc_mod
from app.storage.feedback_chat import DbFeedbackChatStore, FileFeedbackChatStore

ROOT = Path(__file__).resolve().parents[2]

_FAKE_RUNTIME_SCHEMA = """
CREATE TABLE phan_hoi (
    thoi_diem TEXT NOT NULL,
    ca_id TEXT NOT NULL,
    ma_luat TEXT NOT NULL,
    yeu_to INTEGER NOT NULL,
    chi_tiet_y_lenh_id TEXT NOT NULL,
    phan_hoi TEXT NOT NULL,
    nhom_ly_do TEXT,
    ly_do TEXT,
    nguoi_dung_id TEXT,
    PRIMARY KEY (ca_id, ma_luat, thoi_diem)
);
CREATE TABLE hoi_thoai (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thoi_diem TEXT NOT NULL,
    ca_id TEXT NOT NULL,
    cau_hoi TEXT NOT NULL,
    tra_loi TEXT NOT NULL,
    nguoi_dung_id TEXT,
    phien_id TEXT
);
"""


class FakeRuntimeCursor:
    """Con trỏ giả trả dict hoặc tuple giống psycopg 3."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Any]:
        return list(self._rows)

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None


class FakeRuntimePgConnection:
    """Kết nối SQLite giả lập bảng nghiep_vu.phan_hoi và nghiep_vu.hoi_thoai."""

    def __init__(self, *, as_dicts: bool = True) -> None:
        self._db = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self._db.executescript(_FAKE_RUNTIME_SCHEMA)
        self.as_dicts = as_dicts
        self.statements: list[str] = []

    def close(self) -> None:
        self._db.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        self._db.execute("BEGIN")
        try:
            yield
        except Exception:
            self._db.rollback()
            raise
        else:
            self._db.commit()

    def _convert_param(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if hasattr(value, "obj"):
            return json.dumps(value.obj, ensure_ascii=False)
        return value

    def execute(self, query: str, params: Any = None) -> FakeRuntimeCursor:
        self.statements.append(query)
        sql = query.replace("nghiep_vu.", "").replace("%s", "?")
        bound = tuple(self._convert_param(item) for item in (params or ()))
        cur = self._db.execute(sql, bound)
        columns = [desc[0] for desc in cur.description or ()]
        raw_rows = cur.fetchall()
        if not columns:
            return FakeRuntimeCursor([])
        parsed_rows: list[Any] = []
        for row in raw_rows:
            converted = []
            for col, val in zip(columns, row, strict=True):
                if col == "thoi_diem" and isinstance(val, str):
                    converted.append(datetime.fromisoformat(val))
                else:
                    converted.append(val)
            if self.as_dicts:
                parsed_rows.append(dict(zip(columns, converted, strict=True)))
            else:
                parsed_rows.append(tuple(converted))
        return FakeRuntimeCursor(parsed_rows)


def _principal(user_id: str, role: str = CLINICAL_PHARMACIST, session_id: str = "s1") -> Principal:
    return Principal(nguoi_dung_id=user_id, vai_tro=role, phien_id=session_id)


def _sample_reply(text: str = "Trả lời giả lập") -> dict[str, Any]:
    return {
        "trang_thai": "ok",
        "noi_dung": text,
        "trich_dan": [],
        "cong_cu_da_goi": ["du_lieu_ca"],
        "thoi_gian_ms": 12,
    }


@pytest.mark.parametrize("as_dicts", [True, False])
def test_db_feedback_roundtrip_and_upsert(monkeypatch: pytest.MonkeyPatch, as_dicts: bool) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    with closing(FakeRuntimePgConnection(as_dicts=as_dicts)) as conn:

        @contextmanager
        def fake_conn(_url: str) -> Iterator[FakeRuntimePgConnection]:
            yield conn

        store = DbFeedbackChatStore(read_connection=fake_conn, write_connection=fake_conn)
        t1 = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)
        t2 = t1 + timedelta(minutes=5)
        item_1 = PhanHoi(
            thoi_diem=t1,
            ca_id="DEMO-02",
            ma_luat="lieu_than_can_chinh",
            yeu_to=6,
            chi_tiet_y_lenh_id=["CT-DEMO02-01"],
            phan_hoi="dong_y",
            ly_do="Đồng ý giảm liều theo CrCl",
            nguoi_dung_id="ds-1",
        )
        item_2 = PhanHoi(
            thoi_diem=t2,
            ca_id="DEMO-02",
            ma_luat="khang_sinh_can_phe_duyet",
            yeu_to=7,
            chi_tiet_y_lenh_id=["CT-DEMO02-01"],
            phan_hoi="bac_bo",
            nhom_ly_do="khac",
            ly_do="Đã hội chẩn khoa",
            nguoi_dung_id="ds-2",
        )
        store.save_feedback(item_1)
        store.save_feedback(item_2)
        store.save_feedback(item_1.model_copy(update={"phan_hoi": "can_sua", "nhom_ly_do": "khac"}))

        loaded = store.load_feedback()
        assert len(loaded) == 2
        assert loaded[0].phan_hoi == "can_sua"
        assert loaded[0].nguoi_dung_id == "ds-1"
        assert loaded[1].ly_do == "Đã hội chẩn khoa"
        assert loaded[1].nguoi_dung_id == "ds-2"


@pytest.mark.parametrize("as_dicts", [True, False])
def test_db_chat_ownership_sorting_and_clear_delete(
    monkeypatch: pytest.MonkeyPatch, as_dicts: bool
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    ds_a = _principal("ds-a")
    ds_b = _principal("ds-b")
    admin = _principal("admin-1", role=ADMIN)

    with closing(FakeRuntimePgConnection(as_dicts=as_dicts)) as conn:

        @contextmanager
        def fake_conn(_url: str) -> Iterator[FakeRuntimePgConnection]:
            yield conn

        store = DbFeedbackChatStore(read_connection=fake_conn, write_connection=fake_conn)
        base = datetime(2026, 11, 19, 8, 0, tzinfo=UTC)
        store.save_chat("DEMO-01", "Câu hỏi 1", _sample_reply("Đáp 1"), base, ds_a)
        store.save_chat(
            "DEMO-02", "Câu hỏi 2", _sample_reply("Đáp 2"), base + timedelta(minutes=2), ds_a
        )
        store.save_chat(
            "DEMO-01", "Câu hỏi B", _sample_reply("Đáp B"), base + timedelta(minutes=3), ds_b
        )
        conn._db.execute(
            "INSERT INTO hoi_thoai (thoi_diem, ca_id, cau_hoi, tra_loi, nguoi_dung_id, phien_id) "
            "VALUES (?, ?, ?, ?, NULL, NULL)",
            (
                (base + timedelta(minutes=1)).isoformat(),
                "__global__",
                "Câu hỏi cũ",
                json.dumps(_sample_reply("Đáp cũ")),
            ),
        )
        store.save_chat(
            "DEMO-03",
            "Câu hỏi admin",
            _sample_reply("Đáp admin"),
            base + timedelta(minutes=4),
            admin,
        )

        conv_a = store.list_conversations(ds_a)
        assert list(conv_a) == ["DEMO-02", "DEMO-01"]
        assert [row["cau_hoi"] for row in conv_a["DEMO-01"]] == ["Câu hỏi 1"]

        conv_b = store.list_conversations(ds_b)
        assert list(conv_b) == ["DEMO-01"]
        assert [row["cau_hoi"] for row in conv_b["DEMO-01"]] == ["Câu hỏi B"]

        conv_admin = store.list_conversations(admin)
        assert list(conv_admin) == ["DEMO-03", "__global__"]

        conn.statements.clear()
        store.clear_conversation("DEMO-01", ds_a)
        assert any("DELETE FROM nghiep_vu.hoi_thoai" in stmt for stmt in conn.statements)
        assert list(store.list_conversations(ds_a)) == ["DEMO-02"]
        assert list(store.list_conversations(ds_b)) == ["DEMO-01"]

        store.clear_conversation("__global__", admin)
        assert list(store.list_conversations(admin)) == ["DEMO-03"]


def test_db_store_sanitizes_errors_without_leaking_dsn(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret_dsn = "postgresql://demo:mat-khau-tuyet-mat@db.invalid/prod"
    monkeypatch.setenv("DATABASE_URL", secret_dsn)

    @contextmanager
    def broken_conn(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    store = DbFeedbackChatStore(read_connection=broken_conn, write_connection=broken_conn)
    principal = _principal("ds-1")
    item = PhanHoi(
        thoi_diem=datetime.now(UTC),
        ca_id="DEMO-02",
        ma_luat="lieu_than_can_chinh",
        yeu_to=6,
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        phan_hoi="dong_y",
    )

    for call in (
        store.load_feedback,
        lambda: store.save_feedback(item),
        lambda: store.list_conversations(principal),
        lambda: store.clear_conversation("DEMO-02", principal),
    ):
        with pytest.raises(DatabaseReadError) as exc:
            call()
        assert "mat-khau-tuyet-mat" not in str(exc.value)

    with caplog.at_level("WARNING", logger="app.storage.feedback_chat"):
        store.save_chat("DEMO-02", "Hỏi", _sample_reply(), datetime.now(UTC), principal)
    assert "mat-khau-tuyet-mat" not in caplog.text


class _StubAsker:
    def ask(
        self,
        ca: Any,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: Any = None,
        ai_result: Any = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult:
        del ca, lich_su, ket_qua, ai_result, nhan_dinh_id
        return AskResult(
            trang_thai="ok",
            noi_dung=f"Đã trả lời: {cau_hoi}",
            trich_dan=[AskCitation(so=1, loai_ma="du_lieu", nhan="Xét nghiệm", ban_ghi_id="XN-1")],
            cong_cu_da_goi=["du_lieu_ca"],
            thoi_gian_ms=5,
            doan=[],
        )

    def ask_global(
        self,
        cases: Any,
        results: Any,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        del cases, results, lich_su
        return AskResult(
            trang_thai="ok",
            noi_dung=f"Chung: {cau_hoi}",
            trich_dan=[],
            cong_cu_da_goi=["danh_sach_y_lenh"],
            thoi_gian_ms=4,
            doan=[],
        )


class _StubAiRunner:
    model_name = "stub"

    def run(self, ca: Any, ket_qua: Any) -> Any:
        raise AssertionError("Không dùng trong test hỏi đáp")


def test_case_service_db_mode_uses_db_store_and_db_corpus_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import container as container_mod
    from app.api import service as service_mod
    from app.db.bang_luat_store import clear_all_caches
    from app.rules.renal_dose import RenalRuleBook

    case = load_case(ROOT / "data/mock/demo/DEMO-02.json")
    renal_rules = RenalRuleBook.model_validate_json(
        (ROOT / "data/kb/quy_tac_lieu_than.json").read_text(encoding="utf-8")
    )
    monkeypatch.setenv("CASE_SOURCE", "db")
    monkeypatch.setenv("KB_SOURCE", "db")
    monkeypatch.setenv("AUTH_MODE", "off")
    monkeypatch.setenv("ACCESS_LOG", "off")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    monkeypatch.setattr(service_mod, "load_renal_rules", lambda _path=None: renal_rules)
    monkeypatch.setattr(container_mod, "_SHARED_RULE_CONTEXT", None)
    monkeypatch.setattr(DbReviewService, "list_cases", lambda self: ([case], []))
    monkeypatch.setattr(CaseService, "_administrative", lambda self, cases: {})
    monkeypatch.setattr(
        CaseService,
        "_read_medical_record",
        lambda self, c: MedicalRecord(),
    )

    with ExitStack() as stack:
        stack.callback(clear_all_caches)
        conn = stack.enter_context(closing(FakeRuntimePgConnection(as_dicts=True)))

        @contextmanager
        def fake_pool(_url: str) -> Iterator[FakeRuntimePgConnection]:
            yield conn

        monkeypatch.setattr(fc_mod.read_pool, "connection", fake_pool)
        monkeypatch.setattr(fc_mod, "_open_write_connection", fake_pool)

        def build_service() -> CaseService:
            return CaseService(
                ROOT / "data/mock/demo",
                ROOT / "data/kb/quy_tac_lieu_than.json",
                tmp_path / "unused_feedback.jsonl",
                ai_runner=_StubAiRunner(),
                asker=_StubAsker(),
            )

        service = build_service()
        assert isinstance(service._store, DbFeedbackChatStore)
        with TestClient(create_app(service)) as client:
            health = client.get("/api/health").json()
            assert health["che_do"]["truy_xuat"] == "san_sang"

            finding_id = client.get("/api/cases/DEMO-02").json()["nhan_dinh"]["can_chu_y"][0][
                "nhan_dinh_id"
            ]
            fb_resp = client.post(
                "/api/cases/DEMO-02/feedback",
                json={"nhan_dinh_id": finding_id, "phan_hoi": "dong_y"},
            )
            assert fb_resp.status_code == 200
            ask_resp = client.post(
                "/api/cases/DEMO-02/ask", json={"cau_hoi": "Hỏi về ca?", "lich_su": []}
            )
            assert ask_resp.status_code == 200
            global_resp = client.post("/api/ask", json={"cau_hoi": "Hỏi chung?", "lich_su": []})
            assert global_resp.status_code == 200

        # Mô phỏng khởi động lại backend với thực thể CaseService mới hoàn toàn.
        restarted = build_service()
        with TestClient(create_app(restarted)) as client:
            detail = client.get("/api/cases/DEMO-02").json()
            assert detail["nhan_dinh"]["can_chu_y"][0]["phan_hoi"]["phan_hoi"] == "dong_y"
            convs = client.get("/api/conversations").json()
            assert set(convs) == {"DEMO-02", "__global__"}
            assert convs["DEMO-02"][0]["cau_hoi"] == "Hỏi về ca?"
            clear_resp = client.post("/api/conversations/DEMO-02/clear")
            assert clear_resp.status_code == 200
            assert set(client.get("/api/conversations").json()) == {"__global__"}

        assert not (tmp_path / "unused_feedback.jsonl").exists()
        assert not (tmp_path / "hoi_thoai.jsonl").exists()


def test_case_service_default_ai_runner_uses_db_corpus_without_chunks_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app import container as container_mod
    from app.api import service as service_mod
    from app.config.settings import load_settings
    from app.container import Container

    monkeypatch.setenv("CASE_SOURCE", "file")
    monkeypatch.setenv("KB_SOURCE", "auto")
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")
    monkeypatch.delenv("CDSS_AI", raising=False)

    settings = load_settings("test")
    container = Container(settings)
    container.__dict__["llm"] = FakeLLM([])
    monkeypatch.setattr(service_mod.container_mod, "build_container", lambda: container)
    monkeypatch.setattr(service_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(container_mod, "_ROOT", tmp_path)
    (tmp_path / "data/kb").mkdir(parents=True)
    for kb_file in ("hoat_chat.json", "quy_tac_lieu_than.json"):
        (tmp_path / "data/kb" / kb_file).write_text(
            (ROOT / "data/kb" / kb_file).read_text(encoding="utf-8"), encoding="utf-8"
        )
    (tmp_path / "config/prompts").mkdir(parents=True)
    (tmp_path / "config/prompts/tong_hop.v1.md").write_text(
        (ROOT / "config/prompts/tong_hop.v1.md").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "config/prompts/hoi_them.v1.md").write_text(
        (ROOT / "config/prompts/hoi_them.v1.md").read_text(encoding="utf-8"), encoding="utf-8"
    )

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "feedback.jsonl",
    )
    try:
        assert service._retriever_factory is not None
        assert service._retriever_factory._should_use_db() is True
        assert service._asker_impl is not None
        asker_retriever = service._asker_impl._retriever  # type: ignore[attr-defined]
        assert asker_retriever is not None
        assert asker_retriever._should_use_db() is True
        assert service.mode().truy_xuat == "san_sang"
    finally:
        service.shutdown()


def test_file_feedback_chat_store_preserves_legacy_behavior(tmp_path: Path) -> None:
    store = FileFeedbackChatStore(tmp_path / "phan_hoi.jsonl")
    ds = _principal("ds-1")
    admin = _principal("admin-1", role=ADMIN)
    t1 = datetime(2026, 11, 19, 9, 0, tzinfo=UTC)
    store.save_chat("DEMO-01", "Hỏi 1", _sample_reply("Đáp 1"), t1, ds)
    (tmp_path / "hoi_thoai.jsonl").write_text(
        (tmp_path / "hoi_thoai.jsonl").read_text(encoding="utf-8")
        + json.dumps(
            {
                "thoi_diem": (t1 + timedelta(minutes=1)).isoformat(),
                "ca_id": "__global__",
                "cau_hoi": "Cũ",
                "tra_loi": _sample_reply("Đáp cũ"),
                "nguoi_dung_id": None,
                "phien_id": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert list(store.list_conversations(ds)) == ["DEMO-01"]
    assert list(store.list_conversations(admin)) == ["__global__"]
    store.clear_conversation("DEMO-01", ds)
    assert store.list_conversations(ds) == {}
    assert list(store.list_conversations(admin)) == ["__global__"]


@pytest.mark.skipif(
    not (os.getenv("CDSS_TEST_PG_INTEGRATION") == "1" and os.getenv("DATABASE_URL")),
    reason="Bỏ qua kiểm tích hợp PostgreSQL khi không bật CDSS_TEST_PG_INTEGRATION=1",
)
def test_postgres_real_db_feedback_and_chat_optional() -> None:
    store = DbFeedbackChatStore()
    principal = _principal("test-t76-integration")
    store.save_chat("__t76_test__", "Kiểm thử?", _sample_reply("OK"), datetime.now(UTC), principal)
    try:
        convs = store.list_conversations(principal)
        assert "__t76_test__" in convs
    finally:
        store.clear_conversation("__t76_test__", principal)
