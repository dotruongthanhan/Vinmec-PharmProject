"""Kiểm thử recent_turns ở cả FileFeedbackChatStore và DbFeedbackChatStore (T91)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg
import pytest

from app.auth.principal import Principal
from app.auth.roles import ADMIN, CLINICAL_PHARMACIST
from app.db.reader import DatabaseReadError
from app.storage.feedback_chat import DbFeedbackChatStore, FileFeedbackChatStore

_FAKE_CHAT_SCHEMA = """
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


class _FakeCursor:
    """Con trỏ giả trả dict hoặc tuple tương thích psycopg 3."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def fetchall(self) -> list[Any]:
        return list(self._rows)


class _FakeChatPgConnection:
    """Kết nối SQLite giả lập bảng nghiep_vu.hoi_thoai."""

    def __init__(self, *, as_dicts: bool = True) -> None:
        self._db = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
        self._db.executescript(_FAKE_CHAT_SCHEMA)
        self.as_dicts = as_dicts
        self.statements: list[tuple[str, tuple[Any, ...]]] = []

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

    def execute(self, query: str, params: Any = None) -> _FakeCursor:
        bound = tuple(self._convert_param(item) for item in (params or ()))
        self.statements.append((query, bound))
        sql = query.replace("nghiep_vu.", "").replace("%s", "?")
        cur = self._db.execute(sql, bound)
        columns = [desc[0] for desc in cur.description or ()]
        raw_rows = cur.fetchall()
        if not columns:
            return _FakeCursor([])
        parsed: list[Any] = []
        for row in raw_rows:
            converted = [
                datetime.fromisoformat(val) if col == "thoi_diem" and isinstance(val, str) else val
                for col, val in zip(columns, row, strict=True)
            ]
            if self.as_dicts:
                parsed.append(dict(zip(columns, converted, strict=True)))
            else:
                parsed.append(tuple(converted))
        return _FakeCursor(parsed)


def _principal(user_id: str, role: str = CLINICAL_PHARMACIST) -> Principal:
    return Principal(nguoi_dung_id=user_id, vai_tro=role, phien_id=f"sess-{user_id}")


def _reply(text: str) -> dict[str, Any]:
    return {
        "trang_thai": "ok",
        "noi_dung": text,
        "trich_dan": [],
        "cong_cu_da_goi": ["du_lieu_ca"],
        "thoi_gian_ms": 5,
    }


def _make_store(
    backend: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    conn: _FakeChatPgConnection | None = None,
) -> FileFeedbackChatStore | DbFeedbackChatStore:
    if backend == "file":
        return FileFeedbackChatStore(tmp_path / "phan_hoi.jsonl")
    assert conn is not None
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:secret@db.invalid/prod")

    @contextmanager
    def fake_conn(_url: str) -> Iterator[_FakeChatPgConnection]:
        yield conn

    return DbFeedbackChatStore(read_connection=fake_conn, write_connection=fake_conn)


@pytest.mark.parametrize("backend", ["file", "db_dict", "db_tuple"])
@pytest.mark.parametrize("scope", ["DEMO-02", "__global__"])
def test_recent_turns_isolation_limit_order_and_clear(
    backend: str,
    scope: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ds_a = _principal("user-a")
    ds_b = _principal("user-b")
    admin = _principal("admin-1", role=ADMIN)
    base = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)

    conn = _FakeChatPgConnection(as_dicts=(backend == "db_dict")) if backend != "file" else None
    try:
        store_kind = "file" if backend == "file" else "db"
        store = _make_store(store_kind, tmp_path, monkeypatch, conn=conn)

        assert store.recent_turns(scope, ds_a) == []
        assert store.recent_turns(scope, ds_a, limit=0) == []

        for idx in range(1, 6):
            store.save_chat(
                scope,
                f"Hỏi A{idx}",
                _reply(f"Đáp A{idx}"),
                base + timedelta(minutes=idx),
                ds_a,
            )
        store.save_chat(
            "DEMO-99",
            "Hỏi ca khác",
            _reply("Đáp ca khác"),
            base + timedelta(minutes=10),
            ds_a,
        )
        store.save_chat(
            scope,
            "Hỏi B1",
            _reply("Đáp B1"),
            base + timedelta(minutes=11),
            ds_b,
        )

        # Dòng cũ không có chủ: chỉ admin thấy, dược sĩ thường không thấy.
        if conn is not None:
            conn._db.execute(
                "INSERT INTO hoi_thoai (thoi_diem, ca_id, cau_hoi, tra_loi, nguoi_dung_id) "
                "VALUES (?, ?, ?, ?, NULL)",
                (
                    (base + timedelta(minutes=12)).isoformat(),
                    scope,
                    "Hỏi cũ",
                    json.dumps(_reply("Cũ")),
                ),
            )
        else:
            with (tmp_path / "hoi_thoai.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "thoi_diem": (base + timedelta(minutes=12)).isoformat(),
                            "ca_id": scope,
                            "cau_hoi": "Hỏi cũ",
                            "tra_loi": _reply("Cũ"),
                            "nguoi_dung_id": None,
                            "phien_id": None,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        assert store.recent_turns(scope, ds_a, limit=3) == [
            ("Hỏi A3", "Đáp A3"),
            ("Hỏi A4", "Đáp A4"),
            ("Hỏi A5", "Đáp A5"),
        ]
        assert store.recent_turns(scope, ds_b, limit=3) == [("Hỏi B1", "Đáp B1")]
        assert store.recent_turns(scope, admin, limit=3) == [("Hỏi cũ", "Cũ")]

        store.clear_conversation(scope, ds_a)
        assert store.recent_turns(scope, ds_a) == []
        assert store.recent_turns("DEMO-99", ds_a) == [("Hỏi ca khác", "Đáp ca khác")]
        assert store.recent_turns(scope, ds_b) == [("Hỏi B1", "Đáp B1")]

        if conn is not None:
            select_stmts = [
                stmt
                for stmt, _ in conn.statements
                if "ORDER BY thoi_diem DESC" in stmt and "LIMIT %s" in stmt
            ]
            assert select_stmts
            assert all(scope not in stmt and "user-a" not in stmt for stmt in select_stmts)
    finally:
        if conn is not None:
            conn.close()


def test_db_recent_turns_sanitizes_errors_without_leaking_dsn(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_dsn = "postgresql://demo:mat-khau-tuyet-mat@db.invalid/prod"
    monkeypatch.setenv("DATABASE_URL", secret_dsn)

    @contextmanager
    def broken_conn(url: str) -> Iterator[Any]:
        raise psycopg.OperationalError(url)
        yield  # pragma: no cover

    store = DbFeedbackChatStore(read_connection=broken_conn, write_connection=broken_conn)
    principal = _principal("user-a")
    with caplog.at_level("WARNING", logger="app.storage.feedback_chat"):
        with pytest.raises(DatabaseReadError) as exc:
            store.recent_turns("DEMO-02", principal)
    assert "mat-khau-tuyet-mat" not in str(exc.value)
    assert "mat-khau-tuyet-mat" not in caplog.text


def test_file_recent_turns_sorts_by_timestamp_even_if_out_of_order(tmp_path: Path) -> None:
    store = FileFeedbackChatStore(tmp_path / "phan_hoi.jsonl")
    ds_a = _principal("user-a")
    t1 = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
    store.save_chat("DEMO-02", "Hỏi muộn", _reply("Đáp muộn"), t1 + timedelta(minutes=5), ds_a)
    store.save_chat("DEMO-02", "Hỏi sớm", _reply("Đáp sớm"), t1, ds_a)
    assert store.recent_turns("DEMO-02", ds_a, limit=3) == [
        ("Hỏi sớm", "Đáp sớm"),
        ("Hỏi muộn", "Đáp muộn"),
    ]
