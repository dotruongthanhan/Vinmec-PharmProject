"""Lưu và đọc kết quả thẩm định của hệ thống trên PostgreSQL (chế độ DB)."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

import psycopg
from psycopg.types.json import Jsonb

from app.api import schemas as s
from app.config.settings import get_secret, load_kb_source
from app.core.errors import ConfigError
from app.db.bang_luat_store import RULE_DOCUMENTS
from app.db.read_pool import read_pool
from app.db.reader import DatabaseReadError
from app.db.timezone import VN_TZ
from app.rules import renal_dose as renal_dose_mod
from app.rules.renal_dose import RenalRuleBook
from app.storage import feedback_chat as fc_mod
from app.ui import view_model as vm

_ROOT = Path(__file__).resolve().parents[2]
_LOGGER = logging.getLogger(__name__)

_HISTORY_COLUMNS = (
    "ket_qua_id",
    "ca_id",
    "thoi_diem",
    "phien_ban_luat",
    "so_luat_da_chay",
    "che_do",
    "tom_tat",
)

_INSERT_REVIEW_SQL = """
INSERT INTO nghiep_vu.ket_qua_tham_dinh (
    ket_qua_id, ca_id, thoi_diem, phien_ban_luat,
    so_luat_da_chay, che_do, tom_tat
) VALUES (%s, %s, %s, %s, %s, %s, %s)
"""

_INSERT_FINDING_SQL = """
INSERT INTO nghiep_vu.ket_qua_nhan_dinh (
    ket_qua_id, thu_tu, nhom, nhan_dinh_id, thuoc, ma_luat,
    yeu_to, yeu_to_nhan, ket_luan, ket_luan_nhan, muc_do, muc_do_nhan,
    nguon_goc_ma, nguon_goc_nhan, chi_tiet_y_lenh_id, nhan_xet,
    can_cu, du_lieu_thieu
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s
)
"""

_SELECT_HISTORY_SQL = (
    "SELECT ket_qua_id, ca_id, thoi_diem, phien_ban_luat, "
    "so_luat_da_chay, che_do, tom_tat "
    "FROM nghiep_vu.ket_qua_tham_dinh "
    "WHERE ca_id = %s "
    "ORDER BY thoi_diem DESC, ket_qua_id DESC"
)

_SELECT_RULE_META_SQL = (
    "SELECT ma, phien_ban, sha256_tep FROM tri_thuc.bang_luat_meta ORDER BY ma ASC"
)


@contextmanager
def _open_write_connection(url: str) -> Iterator[Any]:
    """Mở kết nối ghi PostgreSQL ngắn hạn dùng chung với bộ lưu phản hồi/hội thoại."""
    with fc_mod._open_write_connection(url) as conn:
        yield conn


def _has_database_url(url_env: str = "DATABASE_URL") -> bool:
    """Kiểm tra biến môi trường DATABASE_URL có giá trị không rỗng."""
    try:
        return bool(get_secret(url_env).strip())
    except ConfigError:
        return False


def parse_factor_number(label: str) -> int:
    """Tách số thứ tự yếu tố (1–7) từ chuỗi hiển thị dạng '6. Cơ địa...'."""
    prefix = label.split(".", 1)[0].strip()
    value = int(prefix)
    if not 1 <= value <= 7:
        raise ValueError(f"Số yếu tố ngoài khoảng 1..7: {label}")
    return value


def build_review_summary(detail: s.ChiTietCa) -> s.TomTatThamDinh:
    """Tổng hợp số mục theo kết luận, mức độ và yếu tố từ chi tiết ca trả API."""
    all_rows = [*detail.nhan_dinh.can_chu_y, *detail.nhan_dinh.dat]
    by_conclusion = Counter(row.ket_luan_ma for row in all_rows)
    by_factor = Counter(parse_factor_number(row.yeu_to) for row in all_rows)
    return s.TomTatThamDinh(
        tong_nhan_dinh=len(all_rows),
        dem=detail.dinh_danh.dem.model_copy(deep=True),
        theo_ket_luan=s.KetLuanCounts(
            dat=by_conclusion["dat"],
            can_xem=by_conclusion["can_xem"],
            khong_du_du_lieu=by_conclusion["khong_du_du_lieu"],
            ngoai_hdsd=by_conclusion["ngoai_hdsd"],
        ),
        theo_yeu_to={str(factor): by_factor[factor] for factor in sorted(by_factor)},
    )


def build_finding_rows(detail: s.ChiTietCa) -> list[dict[str, Any]]:
    """Chuyển danh sách nhận định trả API sang các dòng ghi bảng ket_qua_nhan_dinh."""
    tagged: list[tuple[Literal["can_chu_y", "dat"], s.NhanDinh]] = [
        *[("can_chu_y", row) for row in detail.nhan_dinh.can_chu_y],
        *[("dat", row) for row in detail.nhan_dinh.dat],
    ]
    rows: list[dict[str, Any]] = []
    for thu_tu, (nhom, row) in enumerate(tagged):
        rows.append(
            {
                "thu_tu": thu_tu,
                "nhom": nhom,
                "nhan_dinh_id": row.nhan_dinh_id,
                "thuoc": row.thuoc,
                "ma_luat": row.ma_luat,
                "yeu_to": parse_factor_number(row.yeu_to),
                "yeu_to_nhan": row.yeu_to,
                "ket_luan": row.ket_luan_ma,
                "ket_luan_nhan": row.ket_luan_nhan,
                "muc_do": row.muc_do_ma,
                "muc_do_nhan": row.muc_do_nhan,
                "nguon_goc_ma": row.nguon_goc_ma,
                "nguon_goc_nhan": row.nguon_goc_nhan,
                "chi_tiet_y_lenh_id": list(row.chi_tiet_y_lenh_id),
                "nhan_xet": row.nhan_xet,
                "can_cu": [item.model_dump(mode="json") for item in row.can_cu],
                "du_lieu_thieu": list(row.thong_tin_con_thieu),
            }
        )
    return rows


def resolve_rule_source_mode(
    renal_rules_path: Path,
    *,
    url_env: str = "DATABASE_URL",
) -> Literal["file", "db"]:
    """Xác định nguồn bảng luật đang dùng là 'file' hay 'db' theo KB_SOURCE."""
    kb_source = load_kb_source()
    if kb_source == "db":
        return "db"
    if kb_source == "file":
        return "file"
    default_renal = renal_dose_mod.DEFAULT_RENAL_RULES_PATH
    try:
        is_custom = Path(renal_rules_path).resolve() != default_renal.resolve()
    except OSError:
        is_custom = renal_rules_path != default_renal
    if is_custom:
        if Path(renal_rules_path).is_file():
            return "file"
        return "db" if _has_database_url(url_env) else "file"
    if default_renal.is_file():
        return "file"
    return "db" if _has_database_url(url_env) else "file"


def _digest_rule_hashes(pairs: Iterable[tuple[str, str]]) -> str:
    """Tính SHA-256 ổn định từ danh sách cặp (ma, sha256) đã sắp xếp theo ma."""
    ordered = sorted((ma, digest) for ma, digest in pairs if ma and digest)
    payload = "\n".join(f"{ma}:{digest}" for ma, digest in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hash_rule_files(
    renal_rules_path: Path,
    renal_rules: RenalRuleBook | None,
    *,
    root: Path = _ROOT,
) -> str:
    """Tính SHA-256 ổn định của bộ bảng luật cục bộ hoặc quy tắc thận hiện hành."""
    default_renal = renal_dose_mod.DEFAULT_RENAL_RULES_PATH
    try:
        is_custom = Path(renal_rules_path).resolve() != default_renal.resolve()
    except OSError:
        is_custom = renal_rules_path != default_renal

    pairs: list[tuple[str, str]] = []
    for spec in RULE_DOCUMENTS:
        target = (
            Path(renal_rules_path)
            if spec.ma == "quy_tac_lieu_than" and is_custom
            else root / spec.tep
        )
        if target.is_file():
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            pairs.append((spec.ma, digest))
    if pairs:
        return _digest_rule_hashes(pairs)
    if renal_rules is not None:
        return hashlib.sha256(renal_rules.model_dump_json().encode("utf-8")).hexdigest()
    return hashlib.sha256(b"unknown").hexdigest()


def compute_rule_version(
    renal_rules_path: Path,
    renal_rules: RenalRuleBook | None,
    *,
    read_conn_factory: Callable[[], AbstractContextManager[Any]] | None = None,
    url_env: str = "DATABASE_URL",
    root: Path = _ROOT,
) -> tuple[Literal["file", "db"], str]:
    """Trả về (che_do, phien_ban_luat) từ siêu dữ liệu DB hoặc tệp luật cục bộ."""
    mode = resolve_rule_source_mode(renal_rules_path, url_env=url_env)
    if mode == "db":
        try:
            if read_conn_factory is not None:
                ctx = read_conn_factory()
            else:
                url = get_secret(url_env).strip()
                if not url:
                    raise ConfigError(url_env)
                ctx = read_pool.connection(url)
            with ctx as conn:
                cursor = conn.execute(_SELECT_RULE_META_SQL)
                fetch = getattr(cursor, "fetchall", None)
                rows = fetch() if callable(fetch) else list(cursor)
            pairs: list[tuple[str, str]] = []
            for row in rows:
                if isinstance(row, Mapping):
                    ma = str(row.get("ma") or "")
                    digest = str(row.get("sha256_tep") or row.get("phien_ban") or "")
                else:
                    ma = str(row[0] or "")
                    digest = str(row[2] or row[1] or "")
                if ma and digest:
                    pairs.append((ma, digest))
            if pairs:
                return "db", _digest_rule_hashes(pairs)
        except (
            DatabaseReadError,
            ConfigError,
            psycopg.Error,
            sqlite3.Error,
            OSError,
            ValueError,
            TypeError,
        ) as exc:
            _LOGGER.debug("Dùng bản băm dự phòng cho phien_ban_luat (%s)", type(exc).__name__)
    return mode, _hash_rule_files(renal_rules_path, renal_rules, root=root)


def _parse_db_datetime(value: Any) -> datetime:
    """Chuẩn hoá timestamptz đọc từ DB về datetime có múi giờ VN."""
    if isinstance(value, datetime):
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        aware = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    else:
        raise ValueError("thoi_diem không hợp lệ")
    return aware.astimezone(VN_TZ)


class ReviewResultStore(Protocol):
    """Hợp đồng lưu và đọc lịch sử kết quả thẩm định của hệ thống."""

    def save_review(
        self,
        *,
        ca_id: str,
        detail: s.ChiTietCa,
        phien_ban_luat: str,
        che_do: Literal["file", "db"],
        thoi_diem: datetime | None = None,
    ) -> str | None: ...

    def list_history(self, ca_id: str) -> list[s.LanThamDinhLichSu]: ...


class NoopReviewResultStore:
    """Bộ lưu rỗng cho chế độ tệp: giữ nguyên không ghi DB và trả lịch sử rỗng."""

    def save_review(
        self,
        *,
        ca_id: str,
        detail: s.ChiTietCa,
        phien_ban_luat: str,
        che_do: Literal["file", "db"],
        thoi_diem: datetime | None = None,
    ) -> str | None:
        del ca_id, detail, phien_ban_luat, che_do, thoi_diem
        return None

    def list_history(self, ca_id: str) -> list[s.LanThamDinhLichSu]:
        del ca_id
        return []


class DbReviewResultStore:
    """Lưu kết quả thẩm định qua kết nối ghi và đọc lịch sử qua read_pool."""

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
                "Chưa cấu hình DATABASE_URL để đọc/ghi kết quả thẩm định."
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

    def save_review(
        self,
        *,
        ca_id: str,
        detail: s.ChiTietCa,
        phien_ban_luat: str,
        che_do: Literal["file", "db"],
        thoi_diem: datetime | None = None,
    ) -> str | None:
        """Ghi một lần thẩm định và toàn bộ nhận định tương ứng trong một giao dịch."""
        ket_qua_id = str(uuid.uuid4())
        recorded_at = (thoi_diem or datetime.now(UTC)).astimezone(UTC)
        summary = build_review_summary(detail).model_dump(mode="json")
        finding_rows = build_finding_rows(detail)
        try:
            with self._write_conn() as conn, conn.transaction():
                conn.execute(
                    _INSERT_REVIEW_SQL,
                    (
                        ket_qua_id,
                        ca_id,
                        recorded_at,
                        phien_ban_luat,
                        detail.nhan_dinh.so_luat_da_chay,
                        che_do,
                        Jsonb(summary),
                    ),
                )
                if finding_rows:
                    payload = [
                        (
                            ket_qua_id,
                            row["thu_tu"],
                            row["nhom"],
                            row["nhan_dinh_id"],
                            row["thuoc"],
                            row["ma_luat"],
                            row["yeu_to"],
                            row["yeu_to_nhan"],
                            row["ket_luan"],
                            row["ket_luan_nhan"],
                            row["muc_do"],
                            row["muc_do_nhan"],
                            row["nguon_goc_ma"],
                            row["nguon_goc_nhan"],
                            Jsonb(row["chi_tiet_y_lenh_id"]),
                            row["nhan_xet"],
                            Jsonb(row["can_cu"]),
                            Jsonb(row["du_lieu_thieu"]),
                        )
                        for row in finding_rows
                    ]
                    executemany = getattr(conn, "executemany", None)
                    if callable(executemany):
                        executemany(_INSERT_FINDING_SQL, payload)
                    else:
                        for params in payload:
                            conn.execute(_INSERT_FINDING_SQL, params)
            return ket_qua_id
        except (
            DatabaseReadError,
            ConfigError,
            psycopg.Error,
            sqlite3.Error,
            OSError,
            ValueError,
            TypeError,
        ) as exc:
            _LOGGER.warning("Không lưu được kết quả thẩm định vào DB (%s)", type(exc).__name__)
            return None

    def list_history(self, ca_id: str) -> list[s.LanThamDinhLichSu]:
        """Đọc danh sách lần thẩm định đã lưu cho một ca bệnh, mới nhất trước."""
        try:
            with self._read_conn() as conn:
                cursor = conn.execute(_SELECT_HISTORY_SQL, (ca_id,))
                fetch = getattr(cursor, "fetchall", None)
                rows = fetch() if callable(fetch) else cursor
        except DatabaseReadError:
            raise
        except (psycopg.Error, sqlite3.Error, OSError, ValueError, TypeError) as exc:
            _LOGGER.warning("Lỗi đọc lịch sử thẩm định từ DB (%s)", type(exc).__name__)
            raise DatabaseReadError("Không thể đọc lịch sử thẩm định từ cơ sở dữ liệu.") from None

        items: list[s.LanThamDinhLichSu] = []
        for row in rows:
            if isinstance(row, Mapping):
                values = dict(row)
            else:
                values = dict(zip(_HISTORY_COLUMNS, row, strict=True))
            raw_summary = values.get("tom_tat")
            if isinstance(raw_summary, str):
                values["tom_tat"] = json.loads(raw_summary)
            dt_vn = _parse_db_datetime(values.get("thoi_diem"))
            values["thoi_diem"] = dt_vn
            values["thoi_diem_text"] = vm.format_dt(dt_vn)
            items.append(s.LanThamDinhLichSu.model_validate(values))
        return items
