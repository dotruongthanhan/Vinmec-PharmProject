"""Lưu trữ phản hồi dược sĩ và lịch sử hỏi đáp theo tệp JSONL hoặc PostgreSQL."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.auth.principal import Principal
from app.auth.roles import ADMIN
from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.db.read_pool import read_pool
from app.db.reader import DatabaseReadError
from app.feedback import (
    PhanHoi,
    load_feedback,
    load_feedback_from_db,
    save_feedback,
    save_feedback_to_db,
)

_LOGGER = logging.getLogger(__name__)
_CHAT_COLUMNS = ("thoi_diem", "ca_id", "cau_hoi", "tra_loi", "nguoi_dung_id")

_INSERT_CHAT_SQL = """
INSERT INTO nghiep_vu.hoi_thoai (
    thoi_diem, ca_id, cau_hoi, tra_loi, nguoi_dung_id, phien_id
) VALUES (%s, %s, %s, %s, %s, %s)
"""

_SELECT_CHAT_USER_SQL = (
    "SELECT thoi_diem, ca_id, cau_hoi, tra_loi, nguoi_dung_id "
    "FROM nghiep_vu.hoi_thoai "
    "WHERE nguoi_dung_id = %s "
    "ORDER BY thoi_diem ASC, id ASC"
)

_SELECT_CHAT_ADMIN_SQL = (
    "SELECT thoi_diem, ca_id, cau_hoi, tra_loi, nguoi_dung_id "
    "FROM nghiep_vu.hoi_thoai "
    "WHERE nguoi_dung_id = %s OR nguoi_dung_id IS NULL "
    "ORDER BY thoi_diem ASC, id ASC"
)

_DELETE_CHAT_USER_SQL = "DELETE FROM nghiep_vu.hoi_thoai WHERE ca_id = %s AND nguoi_dung_id = %s"

_DELETE_CHAT_ADMIN_SQL = (
    "DELETE FROM nghiep_vu.hoi_thoai "
    "WHERE ca_id = %s AND (nguoi_dung_id = %s OR nguoi_dung_id IS NULL)"
)


def owns_conversation(owner: str | None, principal: Principal) -> bool:
    """Admin chỉ được thêm quyền với dòng cũ không có chủ."""
    return owner == principal.nguoi_dung_id or (owner is None and principal.vai_tro == ADMIN)


class FeedbackAndChatStore(Protocol):
    """Hợp đồng đọc/ghi phản hồi dược sĩ và lịch sử hỏi đáp."""

    def load_feedback(self) -> list[PhanHoi]: ...
    def save_feedback(self, item: PhanHoi) -> None: ...

    def save_chat(
        self,
        ca_id: str,
        cau_hoi: str,
        tra_loi: dict[str, Any],
        thoi_diem: datetime,
        principal: Principal,
    ) -> None: ...

    def list_conversations(self, principal: Principal) -> dict[str, list[dict[str, object]]]: ...
    def clear_conversation(self, ca_id: str, principal: Principal) -> None: ...


class FileFeedbackChatStore:
    """Cài đặt lưu phản hồi và hội thoại bằng tệp JSONL cục bộ."""

    def __init__(self, feedback_path: Path, chat_path: Path | None = None) -> None:
        self._feedback_path = Path(feedback_path)
        self._chat_path = (
            Path(chat_path)
            if chat_path is not None
            else self._feedback_path.parent / "hoi_thoai.jsonl"
        )
        self._lock = RLock()

    def load_feedback(self) -> list[PhanHoi]:
        with self._lock:
            return load_feedback(self._feedback_path)

    def save_feedback(self, item: PhanHoi) -> None:
        with self._lock:
            save_feedback(item, self._feedback_path)

    def save_chat(
        self,
        ca_id: str,
        cau_hoi: str,
        tra_loi: dict[str, Any],
        thoi_diem: datetime,
        principal: Principal,
    ) -> None:
        with self._lock:
            try:
                self._chat_path.parent.mkdir(parents=True, exist_ok=True)
                entry = {
                    "thoi_diem": thoi_diem.isoformat(),
                    "ca_id": ca_id,
                    "cau_hoi": cau_hoi,
                    "tra_loi": tra_loi,
                    "nguoi_dung_id": principal.nguoi_dung_id,
                    "phien_id": principal.phien_id,
                }
                with self._chat_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def list_conversations(self, principal: Principal) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            if not self._chat_path.is_file():
                return {}
            grouped: dict[str, list[dict[str, object]]] = {}
            last_seen: dict[str, str] = {}
            try:
                for raw_line in self._chat_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        continue
                    owner = item.get("nguoi_dung_id")
                    if owner is not None and not isinstance(owner, str):
                        continue
                    if not owns_conversation(owner, principal):
                        continue
                    ca_id = str(item.get("ca_id") or "")
                    cau_hoi = str(item.get("cau_hoi") or "")
                    tra_loi = item.get("tra_loi")
                    thoi_diem = str(item.get("thoi_diem") or "")
                    if ca_id and cau_hoi and isinstance(tra_loi, dict):
                        grouped.setdefault(ca_id, []).append(
                            {"cau_hoi": cau_hoi, "tra_loi": tra_loi, "thoi_diem": thoi_diem}
                        )
                        last_seen[ca_id] = max(last_seen.get(ca_id, ""), thoi_diem)
            except (OSError, ValueError):
                return {}
            ordered = sorted(grouped, key=lambda key: last_seen.get(key, ""), reverse=True)
            return {key: grouped[key] for key in ordered}

    def clear_conversation(self, ca_id: str, principal: Principal) -> None:
        with self._lock:
            if not self._chat_path.is_file():
                return
            try:
                kept: list[str] = []
                for raw_line in self._chat_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except ValueError:
                        kept.append(line)
                        continue
                    owner = item.get("nguoi_dung_id") if isinstance(item, dict) else None
                    if (
                        not isinstance(item, dict)
                        or str(item.get("ca_id") or "") != ca_id
                        or (owner is not None and not isinstance(owner, str))
                        or not owns_conversation(owner, principal)
                    ):
                        kept.append(line)
                content = ("\n".join(kept) + "\n") if kept else ""
                self._chat_path.write_text(content, encoding="utf-8")
            except OSError:
                pass


@contextmanager
def _open_write_connection(url: str) -> Iterator[psycopg.Connection[dict[str, Any]]]:
    """Mở kết nối PostgreSQL ngắn hạn có quyền ghi và đóng ngay sau khi xong."""
    conn = psycopg.connect(url, connect_timeout=10, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def _format_db_timestamp(value: Any) -> str:
    """Chuẩn hoá thời điểm đọc từ DB về chuỗi ISO 8601 UTC."""
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(UTC).isoformat()
    return str(value or "")


class DbFeedbackChatStore:
    """Cài đặt lưu phản hồi và hội thoại trên PostgreSQL qua read_pool và kết nối ghi."""

    def __init__(
        self,
        *,
        url_env: str = "DATABASE_URL",
        read_connection: Callable[[str], AbstractContextManager[Any]] | None = None,
        write_connection: Callable[[str], AbstractContextManager[Any]] | None = None,
    ) -> None:
        self._url_env = url_env
        self._read_connection = read_connection
        self._write_connection = write_connection

    def _database_url(self) -> str:
        try:
            url = get_secret(self._url_env).strip()
            if not url:
                raise ConfigError(self._url_env)
            return url
        except ConfigError:
            raise DatabaseReadError(
                "Chưa cấu hình DATABASE_URL để đọc/ghi phản hồi và hội thoại."
            ) from None

    @contextmanager
    def _read_conn(self) -> Iterator[Any]:
        factory = self._read_connection or read_pool.connection
        with factory(self._database_url()) as conn:
            yield conn

    @contextmanager
    def _write_conn(self) -> Iterator[Any]:
        factory = self._write_connection or _open_write_connection
        with factory(self._database_url()) as conn:
            yield conn

    def load_feedback(self) -> list[PhanHoi]:
        try:
            with self._read_conn() as conn:
                return load_feedback_from_db(conn)
        except DatabaseReadError:
            raise
        except (psycopg.Error, OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Lỗi đọc phản hồi từ DB (%s)", type(exc).__name__)
            raise DatabaseReadError("Không thể đọc phản hồi từ cơ sở dữ liệu.") from None

    def save_feedback(self, item: PhanHoi) -> None:
        try:
            with self._write_conn() as conn, conn.transaction():
                save_feedback_to_db(conn, item)
        except DatabaseReadError:
            raise
        except (psycopg.Error, OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Lỗi ghi phản hồi vào DB (%s)", type(exc).__name__)
            raise DatabaseReadError("Không thể lưu phản hồi vào cơ sở dữ liệu.") from None

    def save_chat(
        self,
        ca_id: str,
        cau_hoi: str,
        tra_loi: dict[str, Any],
        thoi_diem: datetime,
        principal: Principal,
    ) -> None:
        try:
            with self._write_conn() as conn, conn.transaction():
                conn.execute(
                    _INSERT_CHAT_SQL,
                    (
                        thoi_diem,
                        ca_id,
                        cau_hoi,
                        Jsonb(tra_loi),
                        principal.nguoi_dung_id,
                        principal.phien_id,
                    ),
                )
        except (DatabaseReadError, psycopg.Error, OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Không lưu được lịch sử hội thoại vào DB (%s)", type(exc).__name__)

    def list_conversations(self, principal: Principal) -> dict[str, list[dict[str, object]]]:
        query = _SELECT_CHAT_ADMIN_SQL if principal.vai_tro == ADMIN else _SELECT_CHAT_USER_SQL
        try:
            with self._read_conn() as conn:
                cursor = conn.execute(query, (principal.nguoi_dung_id,))
                fetch = getattr(cursor, "fetchall", None)
                rows = fetch() if callable(fetch) else cursor
        except DatabaseReadError:
            raise
        except (psycopg.Error, OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Lỗi đọc hội thoại từ DB (%s)", type(exc).__name__)
            raise DatabaseReadError("Không thể đọc lịch sử hội thoại từ cơ sở dữ liệu.") from None

        grouped: dict[str, list[dict[str, object]]] = {}
        last_seen: dict[str, str] = {}
        for row in rows:
            if isinstance(row, Mapping):
                item = dict(row)
            else:
                item = dict(zip(_CHAT_COLUMNS, row, strict=True))
            owner = item.get("nguoi_dung_id")
            if owner is not None and not isinstance(owner, str):
                continue
            if not owns_conversation(owner, principal):
                continue
            ca_id = str(item.get("ca_id") or "")
            cau_hoi = str(item.get("cau_hoi") or "")
            tra_loi = item.get("tra_loi")
            if isinstance(tra_loi, str):
                try:
                    tra_loi = json.loads(tra_loi)
                except ValueError:
                    continue
            thoi_diem = _format_db_timestamp(item.get("thoi_diem"))
            if ca_id and cau_hoi and isinstance(tra_loi, dict):
                grouped.setdefault(ca_id, []).append(
                    {"cau_hoi": cau_hoi, "tra_loi": tra_loi, "thoi_diem": thoi_diem}
                )
                last_seen[ca_id] = max(last_seen.get(ca_id, ""), thoi_diem)
        ordered = sorted(grouped, key=lambda key: last_seen.get(key, ""), reverse=True)
        return {key: grouped[key] for key in ordered}

    def clear_conversation(self, ca_id: str, principal: Principal) -> None:
        query = _DELETE_CHAT_ADMIN_SQL if principal.vai_tro == ADMIN else _DELETE_CHAT_USER_SQL
        try:
            with self._write_conn() as conn, conn.transaction():
                conn.execute(query, (ca_id, principal.nguoi_dung_id))
        except DatabaseReadError:
            raise
        except (psycopg.Error, OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Lỗi xoá hội thoại trên DB (%s)", type(exc).__name__)
            raise DatabaseReadError("Không thể xoá lịch sử hội thoại trên cơ sở dữ liệu.") from None
