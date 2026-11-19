"""Thu thập chi tiết tương tác DDInter 2.0 và làm giàu trực tiếp 14 tệp CSV nguồn."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx

from app.kb.names import DrugNameIndex
from app.kb.sources.ddinter_index import (
    ALL_CSV_COLUMNS,
    BASE_COLUMNS,
    build_ingredient_bridge,
    canonical_pair_key,
    iter_ddinter_csv_paths,
    load_ddinter_pairs,
)

DEFAULT_DDINTER_DIR = Path("data/kb_sources/ddinter")
DEFAULT_MANIFEST_PATH = Path("data/kb_sources/manifest.json")
DEFAULT_CACHE_NAME = ".fetch_cache.sqlite"
DEFAULT_BASE_URL = "https://ddinter2.scbdd.com"

_MECHANISM_FLAG_LABELS: tuple[tuple[str, str], ...] = (
    ("absorption", "Absorption"),
    ("distribution", "Distribution"),
    ("metabolism", "Metabolism"),
    ("excretion", "Excretion"),
    ("synergistic_effect", "Synergistic effect"),
    ("antagonistic_effect", "Antagonistic effect"),
    ("others", "Others"),
)
_KNOWN_LEVELS = {"Major", "Moderate", "Minor", "Unknown"}
_ATC_BADGE_RE = re.compile(r"^[A-Z]\d{2}[A-Z](?:\d{2})?$")
_EMPTY_VALUES = {"-", "none", "n/a"}
_WS_RE = re.compile(r"\s+")


def _now_iso() -> str:
    """Trả về dấu thời gian UTC hiện tại dạng ISO 8601."""
    return datetime.now(UTC).isoformat()


def _clean_text(text: str) -> str:
    """Chuẩn hóa khoảng trắng thành một dấu cách."""
    return _WS_RE.sub(" ", text).strip()


def _mechanisms_from_json_row(row: dict[str, object]) -> list[str]:
    """Trích nhãn cơ chế từ các cờ 0/1 của endpoint /server/interact-with/<id>/."""
    result: list[str] = []
    for field_name, label in _MECHANISM_FLAG_LABELS:
        val = row.get(field_name)
        if val in (1, "1", True):
            result.append(label)
    return result


class _DetailHtmlParser(HTMLParser):
    """Phân tích HTML trang /server/interact/<interaction_id>/ của DDInter 2.0."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._td_depth = 0
        self._in_tr = False
        self._in_key_td = False
        self._in_value_td = False
        self._in_ref_td = False
        self._current_key = ""
        self._buf: list[str] = []
        self._row_values: list[str] = []

        self._in_badge = False
        self._badge_buf: list[str] = []

        self._in_ref_span = False
        self._ref_buf: list[str] = []

        self.level: str | None = None
        self.mechanisms: list[str] = []
        self.interaction_text: str | None = None
        self.management_text: str | None = None
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        cls = (attr_map.get("class") or "").split()
        elem_id = attr_map.get("id") or ""

        if tag == "tr":
            self._in_tr = True
            self._current_key = ""
            self._row_values = []
        elif tag == "td":
            self._td_depth += 1
            if "key" in cls:
                self._in_key_td = True
                self._buf = []
            else:
                self._in_value_td = True
                self._buf = []
                if elem_id == "reference-text":
                    self._in_ref_td = True
        elif tag == "span":
            if "badge" in cls:
                self._in_badge = True
                self._badge_buf = []
            elif self._in_ref_td and ("d-block" in cls or not cls):
                self._in_ref_span = True
                self._ref_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "span":
            if self._in_badge:
                badge_text = _clean_text("".join(self._badge_buf))
                if badge_text in _KNOWN_LEVELS and self.level is None:
                    self.level = badge_text
                elif badge_text and badge_text not in _KNOWN_LEVELS:
                    if not _ATC_BADGE_RE.match(badge_text) and badge_text not in self.mechanisms:
                        self.mechanisms.append(badge_text)
                self._in_badge = False
                self._badge_buf = []
            if self._in_ref_span:
                ref_text = _clean_text("".join(self._ref_buf))
                if ref_text and ref_text.lower() not in _EMPTY_VALUES:
                    self.references.append(ref_text)
                self._in_ref_span = False
                self._ref_buf = []
        elif tag == "td":
            self._td_depth = max(0, self._td_depth - 1)
            text = _clean_text("".join(self._buf))
            if self._in_key_td:
                self._current_key = text.lower().rstrip(":")
                self._in_key_td = False
            elif self._in_value_td:
                if text and text.lower() not in _EMPTY_VALUES:
                    self._row_values.append(text)
                self._in_value_td = False
                self._in_ref_td = False
            self._buf = []
        elif tag == "tr":
            if self._in_tr and self._row_values:
                joined = _clean_text(" ".join(self._row_values))
                if self._current_key == "interaction" and joined.lower() not in _EMPTY_VALUES:
                    self.interaction_text = joined
                elif self._current_key == "management" and joined.lower() not in _EMPTY_VALUES:
                    self.management_text = joined
                elif self._current_key == "references" and not self.references:
                    if joined.lower() not in _EMPTY_VALUES:
                        self.references.append(joined)
            self._in_tr = False

    def handle_data(self, data: str) -> None:
        if self._in_badge:
            self._badge_buf.append(data)
        if self._in_ref_span:
            self._ref_buf.append(data)
        if self._in_key_td or self._in_value_td:
            self._buf.append(data)


def parse_interaction_detail_html(html: str) -> dict[str, object]:
    """Phân tích HTML chi tiết tương tác DDInter thành cấu trúc chuẩn."""
    parser = _DetailHtmlParser()
    parser.feed(html)
    parser.close()
    return {
        "level": parser.level,
        "mechanism": parser.mechanisms,
        "interaction_text": parser.interaction_text,
        "management_text": parser.management_text,
        "references": parser.references,
    }


def _init_cache_db(db_path: Path) -> sqlite3.Connection:
    """Khởi tạo SQLite checkpoint dùng WAL để tiếp tục khi bị ngắt quãng."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS drug_discovery (
            ddinter_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            total_records INTEGER NOT NULL DEFAULT 0,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pair_index (
            pair_key TEXT PRIMARY KEY,
            ddinter_id_1 TEXT NOT NULL,
            ddinter_id_2 TEXT NOT NULL,
            interaction_id TEXT NOT NULL,
            level TEXT NOT NULL,
            mechanism_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS interaction_detail (
            interaction_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            http_status INTEGER,
            level TEXT,
            mechanism_json TEXT NOT NULL,
            interaction_text TEXT,
            management_text TEXT,
            references_json TEXT NOT NULL,
            error TEXT,
            fetched_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_pair_iid ON pair_index(interaction_id);
        """
    )
    conn.commit()
    return conn


def _post_with_retry(
    client: httpx.Client,
    url: str,
    *,
    data: dict[str, str],
    headers: dict[str, str],
    max_retries: int = 3,
) -> httpx.Response:
    """Gửi POST với thử lại theo cấp số nhân cho lỗi mạng hoặc 429/5xx."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.post(url, data=data, headers=headers)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(0.5 * (2**attempt))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(0.5 * (2**attempt))
    assert last_exc is not None
    raise last_exc


def _get_with_retry(
    client: httpx.Client,
    url: str,
    *,
    max_retries: int = 3,
) -> httpx.Response:
    """Gửi GET với thử lại theo cấp số nhân cho lỗi mạng hoặc 429/5xx."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.get(url)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(0.5 * (2**attempt))
                continue
            resp.raise_for_status()
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(0.5 * (2**attempt))
    assert last_exc is not None
    raise last_exc


def _discover_single_drug(
    client: httpx.Client,
    base_url: str,
    ddinter_id: str,
    *,
    page_size: int,
    delay: float,
) -> tuple[list[tuple[str, str, str, str, str, str]], int]:
    """Truy vấn toàn bộ trang /server/interact-with/<ddinter_id>/ để lấy InteractionID."""
    url = f"{base_url.rstrip('/')}/server/interact-with/{ddinter_id}/"
    headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{base_url.rstrip('/')}/ddinter/drug-detail/{ddinter_id}/",
    }
    rows: list[tuple[str, str, str, str, str, str]] = []
    start = 0
    total_records = 0
    draw = 1
    while True:
        resp = _post_with_retry(
            client,
            url,
            data={"draw": str(draw), "start": str(start), "length": str(page_size)},
            headers=headers,
        )
        payload = resp.json()
        total_records = int(payload.get("recordsTotal") or 0)
        data = payload.get("data") or []
        if not data:
            break
        for item in data:
            other_id = str(item.get("drug_id") or "").strip()
            iid = str(item.get("interaction_id") or "").strip()
            if not other_id or not iid:
                continue
            id1, id2, pkey = canonical_pair_key(ddinter_id, other_id)
            level = str(item.get("level") or "Unknown").strip()
            mechs = _mechanisms_from_json_row(item)
            rows.append((pkey, id1, id2, iid, level, json.dumps(mechs, ensure_ascii=False)))
        start += len(data)
        draw += 1
        if start >= total_records:
            break
        if delay > 0:
            time.sleep(delay)
    return rows, total_records


def discover_interaction_ids(
    ddinter_ids: Sequence[str],
    db_path: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    workers: int = 8,
    delay: float = 0.0,
    page_size: int = 500,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Giai đoạn 1: lấy InteractionID cho mọi DDInterID chưa có trong SQLite cache."""
    conn = _init_cache_db(db_path)
    lock = threading.Lock()
    try:
        done_ids = {
            row[0]
            for row in conn.execute(
                "SELECT ddinter_id FROM drug_discovery WHERE status = 'done'"
            ).fetchall()
        }
        pending = [did for did in ddinter_ids if did not in done_ids]
        discovered_pairs = 0
        failed_drugs = 0
        thread_local = threading.local()
        clients: list[httpx.Client] = []
        clients_lock = threading.Lock()

        def get_client() -> httpx.Client:
            cli = getattr(thread_local, "client", None)
            if cli is None:
                cli = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)
                thread_local.client = cli
                with clients_lock:
                    clients.append(cli)
            return cli

        def worker(did: str) -> tuple[str, list[tuple[str, str, str, str, str, str]], int]:
            pair_rows, total = _discover_single_drug(
                get_client(),
                base_url,
                did,
                page_size=page_size,
                delay=delay,
            )
            if delay > 0:
                time.sleep(delay)
            return did, pair_rows, total

        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = {pool.submit(worker, did): did for did in pending}
                for idx, fut in enumerate(as_completed(futures), start=1):
                    did = futures[fut]
                    try:
                        _, pair_rows, total = fut.result()
                    except Exception:
                        failed_drugs += 1
                        with lock:
                            conn.execute(
                                """
                                INSERT INTO drug_discovery (
                                    ddinter_id, status, total_records, fetched_at
                                )
                                VALUES (?, 'error', 0, ?)
                                ON CONFLICT(ddinter_id) DO UPDATE SET
                                    status='error', fetched_at=excluded.fetched_at
                                """,
                                (did, _now_iso()),
                            )
                            conn.commit()
                        continue

                    with lock:
                        conn.executemany(
                            """
                            INSERT INTO pair_index (
                                pair_key, ddinter_id_1, ddinter_id_2,
                                interaction_id, level, mechanism_json
                            ) VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(pair_key) DO UPDATE SET
                                interaction_id=excluded.interaction_id,
                                level=excluded.level,
                                mechanism_json=CASE
                                    WHEN excluded.mechanism_json != '[]'
                                        THEN excluded.mechanism_json
                                    ELSE pair_index.mechanism_json
                                END
                            """,
                            pair_rows,
                        )
                        conn.execute(
                            """
                            INSERT INTO drug_discovery (
                                ddinter_id, status, total_records, fetched_at
                            )
                            VALUES (?, 'done', ?, ?)
                            ON CONFLICT(ddinter_id) DO UPDATE SET
                                status='done',
                                total_records=excluded.total_records,
                                fetched_at=excluded.fetched_at
                            """,
                            (did, total, _now_iso()),
                        )
                        if idx % 50 == 0 or idx == len(pending):
                            conn.commit()
                            print(
                                f"[Phase 1] {idx}/{len(pending)} drugs (failed={failed_drugs})",
                                file=sys.stderr,
                                flush=True,
                            )
                        discovered_pairs += len(pair_rows)
        finally:
            for cli in clients:
                cli.close()

        conn.commit()
        total_pairs = conn.execute("SELECT COUNT(*) FROM pair_index").fetchone()[0]
        return {
            "drugs_requested": len(pending),
            "drugs_skipped_cached": len(ddinter_ids) - len(pending),
            "drugs_failed": failed_drugs,
            "pair_rows_upserted": discovered_pairs,
            "unique_pairs_cached": int(total_pairs),
        }
    finally:
        conn.close()


def _target_interaction_ids_from_cache(
    conn: sqlite3.Connection,
    *,
    pair_keys: Iterable[str] | None = None,
    skip_unknown: bool = False,
) -> list[str]:
    """Lấy danh sách InteractionID duy nhất cần tải HTML chi tiết."""
    clauses = ["interaction_id != ''"]
    if skip_unknown:
        clauses.append("level != 'Unknown'")
    query = f"SELECT pair_key, interaction_id FROM pair_index WHERE {' AND '.join(clauses)}"
    rows = conn.execute(query).fetchall()
    allowed = set(pair_keys) if pair_keys is not None else None
    seen: set[str] = set()
    ordered: list[str] = []
    for pkey, iid in rows:
        if allowed is not None and pkey not in allowed:
            continue
        if iid not in seen:
            seen.add(iid)
            ordered.append(iid)
    return sorted(ordered)


def fetch_interaction_details(
    db_path: Path,
    *,
    pair_keys: Iterable[str] | None = None,
    skip_unknown: bool = False,
    limit: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    workers: int = 8,
    delay: float = 0.0,
    transport: httpx.BaseTransport | None = None,
    timeout: float = 30.0,
) -> dict[str, int]:
    """Giai đoạn 2: tải HTML /server/interact/<interaction_id>/ và lưu vào SQLite cache."""
    conn = _init_cache_db(db_path)
    lock = threading.Lock()
    try:
        all_ids = _target_interaction_ids_from_cache(
            conn,
            pair_keys=pair_keys,
            skip_unknown=skip_unknown,
        )
        done_ids = {
            row[0]
            for row in conn.execute(
                "SELECT interaction_id FROM interaction_detail WHERE status = 'done'"
            ).fetchall()
        }
        pending = [iid for iid in all_ids if iid not in done_ids]
        if limit is not None and limit >= 0:
            pending = pending[:limit]

        fetched_ok = 0
        failed = 0
        thread_local = threading.local()
        clients: list[httpx.Client] = []
        clients_lock = threading.Lock()

        def get_client() -> httpx.Client:
            cli = getattr(thread_local, "client", None)
            if cli is None:
                cli = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)
                thread_local.client = cli
                with clients_lock:
                    clients.append(cli)
            return cli

        def worker(iid: str) -> tuple[str, int, dict[str, object]]:
            url = f"{base_url.rstrip('/')}/server/interact/{iid}/"
            resp = _get_with_retry(get_client(), url)
            parsed = parse_interaction_detail_html(resp.text)
            if delay > 0:
                time.sleep(delay)
            return iid, resp.status_code, parsed

        try:
            with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
                futures = {pool.submit(worker, iid): iid for iid in pending}
                for idx, fut in enumerate(as_completed(futures), start=1):
                    iid = futures[fut]
                    try:
                        _, status_code, parsed = fut.result()
                    except Exception as exc:
                        failed += 1
                        with lock:
                            conn.execute(
                                """
                                INSERT INTO interaction_detail (
                                    interaction_id, status, http_status, level, mechanism_json,
                                    interaction_text, management_text, references_json,
                                    error, fetched_at
                                ) VALUES (?, 'error', NULL, NULL, '[]', NULL, NULL, '[]', ?, ?)
                                ON CONFLICT(interaction_id) DO UPDATE SET
                                    status='error',
                                    error=excluded.error,
                                    fetched_at=excluded.fetched_at
                                """,
                                (iid, str(exc), _now_iso()),
                            )
                            conn.commit()
                        continue

                    with lock:
                        conn.execute(
                            """
                            INSERT INTO interaction_detail (
                                interaction_id, status, http_status, level, mechanism_json,
                                interaction_text, management_text, references_json,
                                error, fetched_at
                            ) VALUES (?, 'done', ?, ?, ?, ?, ?, ?, NULL, ?)
                            ON CONFLICT(interaction_id) DO UPDATE SET
                                status='done',
                                http_status=excluded.http_status,
                                level=excluded.level,
                                mechanism_json=excluded.mechanism_json,
                                interaction_text=excluded.interaction_text,
                                management_text=excluded.management_text,
                                references_json=excluded.references_json,
                                error=NULL,
                                fetched_at=excluded.fetched_at
                            """,
                            (
                                iid,
                                status_code,
                                parsed["level"],
                                json.dumps(parsed["mechanism"], ensure_ascii=False),
                                parsed["interaction_text"],
                                parsed["management_text"],
                                json.dumps(parsed["references"], ensure_ascii=False),
                                _now_iso(),
                            ),
                        )
                        fetched_ok += 1
                        if idx % 200 == 0 or idx == len(pending):
                            conn.commit()
                            print(
                                f"[Phase 2] {idx}/{len(pending)} details "
                                f"(ok={fetched_ok}, failed={failed})",
                                file=sys.stderr,
                                flush=True,
                            )
        finally:
            for cli in clients:
                cli.close()

        conn.commit()
        total_done = conn.execute(
            "SELECT COUNT(*) FROM interaction_detail WHERE status = 'done'"
        ).fetchone()[0]
        skipped = len(all_ids) - len(pending) if limit is None else len(done_ids)
        return {
            "details_targeted": len(all_ids),
            "details_skipped_cached": skipped,
            "details_fetched_ok": fetched_ok,
            "details_failed": failed,
            "details_total_cached": int(total_done),
        }
    finally:
        conn.close()


def export_enriched_csvs(ddinter_dir: Path, db_path: Path) -> dict[str, int]:
    """Giai đoạn 3: ghi đè an toàn 14 tệp CSV DDInter với đủ 10 cột từ SQLite cache."""
    paths = iter_ddinter_csv_paths(ddinter_dir)
    if not paths:
        raise FileNotFoundError(f"Không tìm thấy tệp CSV DDInter nào trong {ddinter_dir}")
    conn = _init_cache_db(db_path)
    try:
        pair_rows = conn.execute(
            "SELECT pair_key, interaction_id, mechanism_json FROM pair_index"
        ).fetchall()
        pair_map = {
            pkey: (iid, json.loads(mech_json) if mech_json else [])
            for pkey, iid, mech_json in pair_rows
        }
        detail_rows = conn.execute(
            """
            SELECT
                interaction_id, mechanism_json, interaction_text,
                management_text, references_json
            FROM interaction_detail
            WHERE status = 'done'
            """
        ).fetchall()
        detail_map = {
            iid: (
                [
                    m
                    for m in (json.loads(mech_json) if mech_json else [])
                    if not _ATC_BADGE_RE.match(str(m))
                ],
                ""
                if (interaction_text or "").strip().lower() in _EMPTY_VALUES
                else (interaction_text or "").strip(),
                ""
                if (management_text or "").strip().lower() in _EMPTY_VALUES
                else (management_text or "").strip(),
                json.loads(refs_json) if refs_json else [],
            )
            for iid, mech_json, interaction_text, management_text, refs_json in detail_rows
        }
    finally:
        conn.close()

    rows_total = 0
    rows_with_iid = 0
    rows_with_text = 0
    for path in paths:
        tmp_path = path.with_suffix(".csv.tmp")
        with path.open("r", encoding="utf-8", newline="") as fin:
            reader = csv.DictReader(fin)
            if reader.fieldnames is None:
                continue
            missing_cols = [col for col in BASE_COLUMNS if col not in reader.fieldnames]
            if missing_cols:
                raise ValueError(f"Tệp {path.name} thiếu cột gốc: {missing_cols}")

            with tmp_path.open("w", encoding="utf-8", newline="") as fout:
                writer = csv.DictWriter(fout, fieldnames=list(ALL_CSV_COLUMNS))
                writer.writeheader()
                for raw in reader:
                    rows_total += 1
                    id_a = (raw["DDInterID_A"] or "").strip()
                    id_b = (raw["DDInterID_B"] or "").strip()
                    _, _, pkey = canonical_pair_key(id_a, id_b)
                    iid, p_mechs = pair_map.get(pkey, ("", []))
                    if not iid:
                        iid = (raw.get("InteractionID") or "").strip()

                    d_mechs, inter_txt, mgmt_txt, refs = detail_map.get(iid, ([], "", "", []))
                    mechs = d_mechs or p_mechs
                    raw_mech = "; ".join(
                        part.strip()
                        for part in (raw.get("Mechanism") or "").split(";")
                        if part.strip() and not _ATC_BADGE_RE.match(part.strip())
                    )
                    raw_inter = (raw.get("Interaction") or "").strip()
                    if raw_inter.lower() in _EMPTY_VALUES:
                        raw_inter = ""
                    raw_mgmt = (raw.get("Management") or "").strip()
                    if raw_mgmt.lower() in _EMPTY_VALUES:
                        raw_mgmt = ""

                    mech_cell = "; ".join(mechs) if mechs else raw_mech
                    inter_cell = inter_txt or raw_inter
                    mgmt_cell = mgmt_txt or raw_mgmt
                    refs_cell = "\n".join(refs) if refs else (raw.get("References") or "").strip()

                    if iid:
                        rows_with_iid += 1
                    if inter_cell and inter_cell.lower() not in _EMPTY_VALUES:
                        rows_with_text += 1

                    writer.writerow(
                        {
                            "DDInterID_A": id_a,
                            "Drug_A": (raw["Drug_A"] or "").strip(),
                            "DDInterID_B": id_b,
                            "Drug_B": (raw["Drug_B"] or "").strip(),
                            "Level": (raw["Level"] or "").strip(),
                            "InteractionID": iid,
                            "Mechanism": mech_cell,
                            "Interaction": inter_cell,
                            "Management": mgmt_cell,
                            "References": refs_cell,
                        }
                    )
        os.replace(tmp_path, path)

    return {
        "files_updated": len(paths),
        "rows_total": rows_total,
        "rows_with_interaction_id": rows_with_iid,
        "rows_with_interaction_text": rows_with_text,
    }


def _sha256_file(path: Path) -> str:
    """Tính mã băm SHA-256 của tệp."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def update_manifest(manifest_path: Path, ddinter_dir: Path) -> int:
    """Cập nhật sha256 và kich_thuoc của các tệp DDInter trong data/kb_sources/manifest.json."""
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_name = {p.name: p for p in iter_ddinter_csv_paths(ddinter_dir)}
    updated = 0
    for entry in payload.get("tep", []):
        if entry.get("nguon") != "ddinter_2.0":
            continue
        rel = str(entry.get("duong_dan") or "")
        csv_path = by_name.get(Path(rel).name)
        if csv_path is None or not csv_path.is_file():
            continue
        entry["sha256"] = _sha256_file(csv_path)
        entry["kich_thuoc"] = csv_path.stat().st_size
        updated += 1

    tmp_path = manifest_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, manifest_path)
    return updated


def run_fetch(
    *,
    ddinter_dir: Path = DEFAULT_DDINTER_DIR,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    names_path: Path = Path("data/kb/hoat_chat.json"),
    db_path: Path | None = None,
    workers: int = 8,
    delay: float = 0.0,
    skip_unknown: bool = False,
    only_in_scope: bool = False,
    limit: int | None = None,
    phase1_only: bool = False,
    export_only: bool = False,
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, object]:
    """Chạy 2 pha thu thập DDInter 2.0 (1,971 thuốc / 234,981 cặp), xuất CSV & manifest."""
    resolved_db = db_path if db_path is not None else Path(ddinter_dir) / DEFAULT_CACHE_NAME
    pairs, drug_names, _ = load_ddinter_pairs(ddinter_dir)

    target_drug_ids = sorted(drug_names)
    target_pair_keys: list[str] = [p.pair_key for p in pairs]
    if only_in_scope:
        names = DrugNameIndex.load(names_path)
        bridge = build_ingredient_bridge(names, drug_names)
        in_scope = set(bridge.in_scope_ddinter_ids)
        target_drug_ids = sorted(in_scope)
        target_pair_keys = [
            p.pair_key for p in pairs if p.ddinter_id_1 in in_scope and p.ddinter_id_2 in in_scope
        ]

    summary: dict[str, object] = {}
    if not export_only:
        summary["phase1_discovery"] = discover_interaction_ids(
            target_drug_ids,
            resolved_db,
            base_url=base_url,
            workers=workers,
            delay=delay,
        )
        if not phase1_only:
            summary["phase2_details"] = fetch_interaction_details(
                resolved_db,
                pair_keys=target_pair_keys,
                skip_unknown=skip_unknown,
                limit=limit,
                base_url=base_url,
                workers=workers,
                delay=delay,
            )
    summary["phase3_export"] = export_enriched_csvs(ddinter_dir, resolved_db)
    if manifest_path.is_file():
        summary["manifest_updated"] = update_manifest(manifest_path, ddinter_dir)
    return summary


def main() -> int:
    """Điểm vào CLI làm giàu 14 tệp CSV DDInter 2.0."""
    parser = argparse.ArgumentParser(
        description="Thu thập chi tiết tương tác DDInter 2.0 và cập nhật 14 tệp CSV."
    )
    parser.add_argument("--ddinter-dir", type=Path, default=DEFAULT_DDINTER_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--names", type=Path, default=Path("data/kb/hoat_chat.json"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--skip-unknown", action="store_true")
    parser.add_argument("--only-in-scope", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--phase1-only", action="store_true")
    parser.add_argument("--export-only", action="store_true")
    args = parser.parse_args()

    result = run_fetch(
        ddinter_dir=args.ddinter_dir,
        manifest_path=args.manifest,
        names_path=args.names,
        workers=args.workers,
        delay=args.delay,
        skip_unknown=args.skip_unknown,
        only_in_scope=args.only_in_scope,
        limit=args.limit,
        phase1_only=args.phase1_only,
        export_only=args.export_only,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
