"""Kho DDInter mở chỉ đọc một lần rồi tra cứu trong bộ nhớ hoặc theo cặp trên PostgreSQL."""

import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping
from contextlib import closing, nullcontext
from itertools import combinations
from pathlib import Path
from threading import Lock
from typing import Any

from app.db.read_pool import read_pool
from app.kb.interactions.models import FoodRecord, PairRecord

_PAIR_COLUMNS = (
    "ddinter_id_a",
    "ddinter_id_b",
    "muc_do",
    "muc_do_so",
    "co_che_json",
    "co_lech_muc",
    "cac_muc_nguon_json",
    "ma_trang_cap_json",
    "hau_qua",
    "xu_tri",
    "tai_lieu_json",
    "url_goc",
)
_DRUG_COLUMNS = ("ddinter_id", "da_cao_du")
_FOOD_COLUMNS = ("ddinter_id", "thuc_an", "muc_do", "mo_ta", "xu_tri", "co_che_json")

_PAIR_SELECT_FIELDS = (
    "SELECT ddinter_id_a, ddinter_id_b, muc_do, muc_do_so, co_che_json, "
    "co_lech_muc, cac_muc_nguon_json, ma_trang_cap_json, hau_qua, xu_tri, "
    "tai_lieu_json, url_goc FROM {table}"
)
_SELECT_PAIRS = f"{_PAIR_SELECT_FIELDS} ORDER BY ddinter_id_a, ddinter_id_b"
_SELECT_PAIR_BY_KEY = (
    f"{_PAIR_SELECT_FIELDS.format(table='tri_thuc.ddinter_cap')} "
    "WHERE ddinter_id_a = %s AND ddinter_id_b = %s"
)
_SELECT_PAIRS_IN = (
    f"{_PAIR_SELECT_FIELDS.format(table='tri_thuc.ddinter_cap')} "
    "WHERE (ddinter_id_a, ddinter_id_b) IN ({placeholders})"
)
_SELECT_DRUGS = "SELECT ddinter_id, da_cao_du FROM {table}"
_SELECT_FOODS = (
    "SELECT ddinter_id, thuc_an, muc_do, mo_ta, xu_tri, co_che_json "
    "FROM {table} ORDER BY ddinter_id, thuc_an, muc_do"
)
_PAIR_BATCH_SIZE = 1000


def _row_to_dict(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    """Chuyển hàng tuple, dict hoặc sqlite3.Row thành ánh xạ cột."""
    if isinstance(row, Mapping):
        return dict(row)
    if isinstance(row, sqlite3.Row):
        return dict(row)
    return dict(zip(columns, row, strict=True))


def _fetch_rows(cursor: Any) -> Iterable[Any]:
    """Lấy toàn bộ hàng từ con trỏ psycopg hoặc đối tượng giả tương đương."""
    if hasattr(cursor, "fetchall") and callable(cursor.fetchall):
        return cursor.fetchall()
    return cursor


def _parse_pair_row(row: Any) -> PairRecord:
    """Chuyển một dòng nguồn thành PairRecord bất biến."""
    values = _row_to_dict(row, _PAIR_COLUMNS)
    for key in ("co_che", "cac_muc_nguon", "ma_trang_cap", "tai_lieu"):
        raw = values.pop(f"{key}_json")
        values[key] = json.loads(raw) if isinstance(raw, str) else raw
    return PairRecord.model_validate(values)


class InteractionStore:
    """Nạp chỉ mục bất biến, không giữ kết nối SQLite hoặc PostgreSQL khi tra cứu."""

    def __init__(self) -> None:
        self._pairs: dict[tuple[str, str], PairRecord | None] = {}
        self._complete: dict[str, bool] = {}
        self._foods: dict[str, list[FoodRecord]] = defaultdict(list)
        self._from_db = False
        self._db_url: str | None = None
        self._fallback_conn: Any | None = None
        self._lock = Lock()

    @classmethod
    def _build(
        cls,
        pair_rows: Iterable[Any],
        drug_rows: Iterable[Any],
        food_rows: Iterable[Any],
    ) -> "InteractionStore":
        """Dựng cấu trúc tra cứu trong bộ nhớ từ ba luồng hàng nguồn."""
        store = cls()
        for row in pair_rows:
            pair = _parse_pair_row(row)
            store._pairs[(pair.ddinter_id_a, pair.ddinter_id_b)] = pair

        for row in drug_rows:
            values = _row_to_dict(row, _DRUG_COLUMNS)
            store._complete[values["ddinter_id"]] = bool(values["da_cao_du"])

        for row in food_rows:
            values = _row_to_dict(row, _FOOD_COLUMNS)
            raw = values.pop("co_che_json")
            values["co_che"] = json.loads(raw) if isinstance(raw, str) else raw
            food = FoodRecord.model_validate(values)
            store._foods[food.ddinter_id].append(food)
        return store

    @classmethod
    def from_path(cls, path: Path) -> "InteractionStore":
        """Nạp từ tệp SQLite cục bộ ở chế độ chỉ đọc rồi đóng kết nối."""
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            return cls._build(
                db.execute(_SELECT_PAIRS.format(table="cap")),
                db.execute(_SELECT_DRUGS.format(table="thuoc")),
                db.execute(_SELECT_FOODS.format(table="thuc_an")),
            )

    @classmethod
    def from_db(cls, conn: Any, *, db_url: str | None = None) -> "InteractionStore":
        """Nạp sẵn bảng thuốc và thức ăn từ PostgreSQL; cặp thuốc tra theo khoá chính."""
        store = cls._build(
            (),
            _fetch_rows(conn.execute(_SELECT_DRUGS.format(table="tri_thuc.ddinter_thuoc"))),
            _fetch_rows(conn.execute(_SELECT_FOODS.format(table="tri_thuc.ddinter_thuc_an"))),
        )
        store._from_db = True
        store._db_url = db_url
        store._fallback_conn = conn if db_url is None else None
        return store

    def _query_pairs(self, keys: list[tuple[str, str]]) -> dict[tuple[str, str], PairRecord]:
        """Truy vấn theo khoá chính trên tri_thuc.ddinter_cap (mỗi lô tối đa 1.000 cặp)."""
        if not keys:
            return {}
        conn_ctx = (
            read_pool.connection(self._db_url)
            if self._db_url is not None
            else nullcontext(self._fallback_conn)
        )
        found: dict[tuple[str, str], PairRecord] = {}
        with conn_ctx as conn:
            for start in range(0, len(keys), _PAIR_BATCH_SIZE):
                batch = keys[start : start + _PAIR_BATCH_SIZE]
                if len(batch) == 1:
                    cursor = conn.execute(_SELECT_PAIR_BY_KEY, batch[0])
                else:
                    placeholders = ", ".join("(%s, %s)" for _ in batch)
                    params = tuple(item for pair in batch for item in pair)
                    sql_text = _SELECT_PAIRS_IN.format(placeholders=placeholders)
                    cursor = conn.execute(sql_text, params)
                for row in _fetch_rows(cursor):
                    pair = _parse_pair_row(row)
                    found[(pair.ddinter_id_a, pair.ddinter_id_b)] = pair
        return found

    def pair(self, id_a: str, id_b: str) -> PairRecord | None:
        """Cùng kết quả cho hai chiều của cặp."""
        a, b = sorted((id_a, id_b))
        if a == b:
            return None
        key = (a, b)
        with self._lock:
            if key in self._pairs:
                cached = self._pairs[key]
                return cached.model_copy(deep=True) if cached is not None else None
        if not self._from_db:
            return None
        fetched = self._query_pairs([key])
        with self._lock:
            row = self._pairs.setdefault(key, fetched.get(key))
        return row.model_copy(deep=True) if row is not None else None

    def pairs(self, ids: Iterable[str | tuple[str, str]]) -> dict[tuple[str, str], PairRecord]:
        """Tra nhiều cặp hoặc tập mã DDInter trong một truy vấn DB và ghi vào bộ đệm."""
        single_ids: list[str] = []
        raw_pairs: list[tuple[str, str]] = []
        for item in ids:
            if isinstance(item, str):
                single_ids.append(item)
            else:
                a, b = item
                raw_pairs.append((a, b))
        if single_ids:
            raw_pairs.extend(combinations(sorted(dict.fromkeys(single_ids)), 2))

        requested: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for id_a, id_b in raw_pairs:
            a, b = sorted((id_a, id_b))
            if a == b or (a, b) in seen:
                continue
            seen.add((a, b))
            requested.append((a, b))
        if not requested:
            return {}

        with self._lock:
            missing = [key for key in requested if key not in self._pairs]
        if self._from_db and missing:
            fetched = self._query_pairs(missing)
            with self._lock:
                for key in missing:
                    self._pairs.setdefault(key, fetched.get(key))

        with self._lock:
            return {
                key: row.model_copy(deep=True)
                for key in requested
                if (row := self._pairs.get(key)) is not None
            }

    def drug_complete(self, identifier: str) -> bool:
        """Không coi mã chưa có hoặc chưa rõ tổng nguồn là đã cào đủ."""
        return self._complete.get(identifier, False)

    def foods(self, identifier: str) -> list[FoodRecord]:
        """Trả bản sao để người gọi không sửa dữ liệu dùng chung."""
        return [row.model_copy(deep=True) for row in self._foods.get(identifier, [])]
