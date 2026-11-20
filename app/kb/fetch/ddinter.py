"""Tải, phân tích và đối chiếu dữ liệu công khai DDInter 2.0."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
import re
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.kb.fetch.client import FetchError
from app.kb.names import strip_salt
from app.kb.sources.ddinter_web import (
    ATTRIBUTION,
    BASE,
    DRUG_ID,
    TABLE_COLUMN_COUNTS,
    TABLES,
    Document,
    ParseError,
    parse_drug,
    parse_pair,
    parse_row,
    parse_table,
)

ROOT = Path(__file__).resolve().parents[3]
PAIR = "tuong_tac_chi_tiet"
DRUG = "thuoc"
PROBE_IDS = ("DDInter1951", "DDInter83")
PHASES = (DRUG, "cap-uu-tien", "cap-mot-ben", "cap-tat-ca", "phan-tich", "kiem")
COMBINATION = re.compile(r"\s*(?:\+|/|\band\b|&|,)\s*", re.I)
PAGE_SIZE = 1000
Row = dict[str, Any]
Pair = tuple[str, str]


class CrawlStopped(FetchError):
    """Đã vượt ngưỡng lỗi liên tiếp."""


def json_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def print_summary(value: Row) -> None:
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


def read_json(path: Path, fallback: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())


def write_jsonl(path: Path, rows: Iterable[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json_line(row) + "\n")
    temporary.replace(path)


def read_jsonl(path: Path) -> Iterator[Row]:
    if path.is_file():
        with path.open(encoding="utf-8") as stream:
            yield from map(json.loads, stream)


def pair_key(row: Row) -> Pair:
    a, b = row["ddinter_id_a"], row["ddinter_id_b"]
    return (a, b) if a <= b else (b, a)


def catalogue(root: Path) -> tuple[dict[str, str], dict[Pair, set[str]]]:
    drugs: dict[str, str] = {}
    pairs: dict[Pair, set[str]] = defaultdict(set)
    for path in sorted((root / "data/kb_sources/ddinter").glob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                first, second = row["DDInterID_A"], row["DDInterID_B"]
                drugs.setdefault(first, row["Drug_A"])
                drugs.setdefault(second, row["Drug_B"])
                a, b = sorted((first, second))
                pairs[a, b].add(row["Level"])
    return drugs, pairs


def priority(root: Path, drugs: dict[str, str]) -> Row:
    exact: dict[str, set[str]] = defaultdict(set)
    for drug_id, name in drugs.items():
        if len(COMBINATION.split(name)) == 1:
            exact[strip_salt(name)].add(drug_id)
    entries = read_json(root / "data/kb/hoat_chat.json", {})["hoat_chat"]
    by_id = {row["hoat_chat_id"]: row for row in entries}
    components: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in entries:
        key = row["hoat_chat_id"]
        if row.get("thanh_phan"):
            for part in row["thanh_phan"]:
                name = by_id.get(part, {}).get("ten_inn", part)
                components[key, name].update(by_id.get(part, {}).get("dong_nghia", []))
            continue
        inn = row.get("ten_inn") or key
        for name in COMBINATION.split(inn):
            alternatives = components[key, name]
            if inn == name:
                alternatives.update(
                    item
                    for item in [key, *row.get("dong_nghia", [])]
                    if len(COMBINATION.split(item)) == 1
                )
    aliases_by_name: dict[str, set[str]] = defaultdict(set)
    for (_, name), aliases in components.items():
        aliases_by_name[strip_salt(name)].update(aliases)
    for folder in ("demo", "hoso_gia_lap"):
        for path in sorted((root / "data/mock" / folder).glob("*.json")):
            for row in read_json(path, {}).get("danh_muc_hoat_chat", []):
                name = row.get("ten_quoc_te") or row.get("ten_hoat_chat") or ""
                for part in filter(None, COMBINATION.split(name)):
                    components[row["hoat_chat_id"], part].update(aliases_by_name[strip_salt(part)])
    matched, unmatched = [], []
    for (key, name), aliases in sorted(components.items()):
        ids = set().union(*(exact.get(strip_salt(alias), set()) for alias in aliases | {name}))
        record = {"hoat_chat_id": key, "ten": name}
        if ids:
            matched.append({**record, "ddinter_ids": sorted(ids)})
        else:
            unmatched.append(record)
    return {
        **ATTRIBUTION,
        "ddinter_ids": sorted({drug_id for row in matched for drug_id in row["ddinter_ids"]}),
        "da_khop": matched,
        "chua_khop": unmatched,
    }


def raw_url(kind: str, key: str) -> str:
    endpoint = {DRUG: "drug-detail", PAIR: "interact", **TABLES}[kind]
    return f"{BASE}/server/{endpoint}/{key.split('__', 1)[0]}/"


class Archive:
    """Lưu nguyên byte phản hồi và phục hồi từ tệp gzip."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw = root / "data/kb_sources/ddinter_web"
        self.stage = root / "data/kb_staging/ddinter"
        self.reports = root / "data/kb_reports"
        self.state_path = self.raw / "trang_thai.json"
        self.state: Row = read_json(self.state_path, dict(ATTRIBUTION))

    def path(self, kind: str, key: str) -> Path:
        extension = "json" if kind in TABLES else "html"
        return self.raw / kind / f"{key}.{extension}.gz"

    def load(self, kind: str, key: str) -> bytes:
        return gzip.decompress(self.path(kind, key).read_bytes())

    def record(self, kind: str, key: str) -> Row:
        path = self.path(kind, key)
        with path.open("rb") as stream:
            stamp = int.from_bytes(stream.read(8)[4:8], "little")
        return {
            **ATTRIBUTION,
            "url_goc": raw_url(kind, key),
            "tep_tho": path.relative_to(self.root).as_posix(),
            "ngay_lay": datetime.fromtimestamp(stamp, UTC).isoformat(),
        }

    def save(self, kind: str, key: str, body: bytes) -> None:
        write_bytes(self.path(kind, key), gzip.compress(body, mtime=int(time.time())))

    def manifest(self) -> None:
        path = self.raw / "manifest.json"
        files = read_json(path, {}).get("tep", {})
        for kind in (DRUG, PAIR, *TABLES):
            for target in sorted((self.raw / kind).glob("*.gz")):
                key = target.name.split(".", 1)[0]
                record = self.record(kind, key)
                relative = record["tep_tho"]
                if files.get(relative, {}).get("ngay_lay") != record["ngay_lay"]:
                    files[relative] = {
                        **record,
                        "sha256": hashlib.sha256(gzip.decompress(target.read_bytes())).hexdigest(),
                        "byte_gzip": target.stat().st_size,
                    }
        write_json(path, {**ATTRIBUTION, "tep": files})


class DDInterClient:
    """Điều tiết mọi lần gửi, kể cả lần thử lại."""

    def __init__(self, http: httpx.Client, rps: float) -> None:
        if not math.isfinite(rps) or not 0 < rps <= 2:
            raise ValueError("rps phải lớn hơn 0 và tối đa 2")
        self.http = http
        self.interval = 1 / rps
        self.last: float | None = None
        self.count = 0
        self.seconds = 0.0
        self.failures = 0

    def failed(self) -> None:
        self.failures += 1
        if self.failures > 20:
            raise CrawlStopped("Dừng sau 21 yêu cầu HTTP liên tiếp thất bại")

    def request(
        self, url: str, data: dict[str, str] | None = None, referer: str | None = None
    ) -> bytes:
        if not url.startswith(f"{BASE}/server/"):
            raise FetchError("URL ngoài phạm vi DDInter")
        headers = {}
        form = None if data is None else dict(data)
        if form is not None:
            headers.update(
                {
                    "Referer": referer or BASE,
                    "Origin": BASE,
                    "X-Requested-With": "XMLHttpRequest",
                }
            )
            for cookie in self.http.cookies.jar:
                if cookie.name == "csrftoken" and cookie.domain.lstrip(".") == "ddinter2.scbdd.com":
                    headers["X-CSRFToken"] = cookie.value
                    form.setdefault("csrfmiddlewaretoken", cookie.value)
                    break
        for attempt in range(6):
            if self.last is not None:
                time.sleep(max(0.0, self.interval - (time.monotonic() - self.last)))
            start = self.last = time.monotonic()
            self.count += 1
            retry_after = 0.0
            try:
                response = self.http.request(
                    "GET" if form is None else "POST", url, data=form, headers=headers
                )
            except httpx.TimeoutException:
                error = "hết giờ"
            except httpx.RequestError as exc:
                self.failed()
                raise FetchError(f"{type(exc).__name__}: {url}") from None
            else:
                status = response.status_code
                if status == 200:
                    self.failures = 0
                    return response.content
                error = f"HTTP {status}"
                if status != 429 and not 500 <= status < 600:
                    self.failed()
                    raise FetchError(f"{error}: {url}")
                try:
                    retry_after = float(response.headers.get("Retry-After", "0"))
                except ValueError:
                    pass
            finally:
                self.seconds += time.monotonic() - start
            self.failed()
            if attempt < 5:
                time.sleep(max(2**attempt, retry_after))
        raise FetchError(f"{error} sau 5 lần thử lại: {url}")


def table_form(kind: str, start: int, draw: int, html: bytes, drug_id: str) -> dict[str, str]:
    """Chuẩn bị yêu cầu DataTables không lọc."""
    form = {
        "draw": str(draw),
        "start": str(start),
        "length": str(PAGE_SIZE),
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
    }
    doc = Document(html.decode("utf-8")).root
    token = next(
        (
            item.attrs.get("value")
            for item in doc.walk("input")
            if item.attrs.get("name") == "csrfmiddlewaretoken"
        ),
        None,
    )
    if token:
        form["csrfmiddlewaretoken"] = token

    # Lấy tên cột khai báo trong đoạn khởi tạo inline nếu có điểm POST tương ứng.
    endpoint = f"/server/{TABLES[kind]}/{drug_id}/"
    names: list[str] = []
    for item in doc.walk("script"):
        script = "".join(child for child in item.children if isinstance(child, str))
        if endpoint in script:
            tail = script.split(endpoint, 1)[1]
            tail = re.split(r"\.DataTable\s*\(", tail, maxsplit=1)[0]
            columns = re.search(r"\bcolumns\s*:\s*\[(.*?)\]", tail, re.S)
            if columns:
                names = re.findall(r"""\bdata\s*:\s*['"]?([\w.]+)""", columns[1])
            break
    for index in range(TABLE_COLUMN_COUNTS[kind]):
        prefix = f"columns[{index}]"
        form.update(
            {
                f"{prefix}[data]": names[index] if index < len(names) else str(index),
                f"{prefix}[name]": "",
                f"{prefix}[searchable]": "true",
                f"{prefix}[orderable]": "true",
                f"{prefix}[search][value]": "",
                f"{prefix}[search][regex]": "false",
            }
        )
    return form


class Crawl:
    def __init__(self, archive: Archive, client: DDInterClient, refresh: bool) -> None:
        self.archive = archive
        self.client = client
        self.refresh = refresh
        self.errors: list[Row] = []
        self.consecutive = 0
        self.saved = 0
        self.cached = 0

    def fetch(
        self,
        kind: str,
        key: str,
        validate: Callable[[bytes], Any],
        form: dict[str, str] | None = None,
        referer: str | None = None,
    ) -> tuple[bytes, Any]:
        if not self.refresh and self.archive.path(kind, key).is_file():
            body = self.archive.load(kind, key)
            value = validate(body)
            self.cached += 1
            return body, value
        url = raw_url(kind, key)
        body = (
            self.client.request(url, form, referer)
            if form is not None
            else self.client.request(url)
        )
        value = validate(body)
        self.archive.save(kind, key, body)
        self.saved += 1
        self.consecutive = 0
        return body, value

    def error(self, key: str, exc: Exception) -> None:
        self.consecutive += 1
        self.errors.append({"khoa": key, "loi": str(exc)})
        if isinstance(exc, CrawlStopped):
            raise exc
        if self.consecutive > 20:
            raise CrawlStopped("Dừng sau 21 lỗi liên tiếp")

    def drugs(self, ids: Iterable[str]) -> None:
        for drug_id in ids:
            try:
                html, drug = self.fetch(
                    DRUG, drug_id, lambda body, current_id=drug_id: parse_drug(body, current_id)
                )
            except (FetchError, ParseError, UnicodeError, OSError) as exc:
                self.error(drug_id, exc)
                continue
            for kind in TABLES:
                try:
                    self.table(kind, drug_id, drug["ten"], html)
                except (FetchError, ParseError, UnicodeError, OSError) as exc:
                    self.error(f"{kind}/{drug_id}", exc)

    def table(self, kind: str, drug_id: str, name: str | None, html: bytes) -> None:
        offset, draw, expected = 0, 1, None
        previous_pages: set[str] = set()
        while expected is None or offset < expected:

            def validate(body: bytes, expected: int | None = expected, offset: int = offset) -> Any:
                page = parse_table(body)
                signature = json_line(page.data)
                if (
                    (expected is not None and page.recordsTotal != expected)
                    or offset + len(page.data) > page.recordsTotal
                    or (not page.data and offset < page.recordsTotal)
                    or signature in previous_pages
                ):
                    raise ParseError(f"{kind}/{drug_id}: phân trang không nhất quán tại {offset}")
                for row in page.data:
                    parse_row(kind, row, drug_id, name)
                previous_pages.add(signature)
                return page

            key = page_key(drug_id, offset)
            _, page = self.fetch(
                kind,
                key,
                validate,
                table_form(kind, offset, draw, html, drug_id),
                raw_url(DRUG, drug_id),
            )
            expected = page.recordsTotal
            offset += len(page.data)
            draw += 1

    def pairs(self, rows: Iterable[Row]) -> None:
        for row in rows:
            key = str(row["ma_trang_cap"])
            try:
                self.fetch(PAIR, key, lambda body, pair=row: parse_pair(body, pair))
            except (FetchError, ParseError, UnicodeError, OSError) as exc:
                self.error(key, exc)


def page_key(drug_id: str, offset: int) -> str:
    return f"{drug_id}__{offset}" if offset else drug_id


def stage_drugs(archive: Archive) -> Row:
    """Dựng lại tầng 1 từ các trang thô đã lưu."""
    drugs: list[Row] = []
    tables: dict[str, list[Row]] = {kind: [] for kind in TABLES}
    counts: list[Row] = []
    truncated: list[Row] = []
    errors: list[Row] = []
    for path in sorted((archive.raw / DRUG).glob("*.html.gz")):
        drug_id = path.name.split(".", 1)[0]
        drug = parse_drug(archive.load(DRUG, drug_id), drug_id)
        drugs.append({**drug, **archive.record(DRUG, drug_id)})
        for kind in TABLES:
            offset, count, total = 0, 0, None
            while total is None or offset < total:
                key = page_key(drug_id, offset)
                if not archive.path(kind, key).is_file():
                    break
                record = archive.record(kind, key)
                page = parse_table(archive.load(kind, key))
                if total is not None and total != page.recordsTotal:
                    break
                total = page.recordsTotal
                for position, row in enumerate(page.data, start=offset):
                    try:
                        parsed = parse_row(kind, row, drug_id, drug["ten"])
                    except ParseError as exc:
                        errors.append(
                            {"tep_tho": record["tep_tho"], "vi_tri": position, "loi": str(exc)}
                        )
                        continue
                    tables[kind].append({**parsed, **record})
                    count += 1
                    if kind == "tuong_tac_benh" and (parsed["noi_dung"] or "").endswith(
                        ("...", "…")
                    ):
                        truncated.append(
                            {
                                "ddinter_id": drug_id,
                                "ten_benh": parsed["ten_benh"],
                                "tep_tho": record["tep_tho"],
                            }
                        )
                offset += len(page.data)
                if not page.data:
                    break
            drug["tong_tuong_tac_tren_trang"][kind] = total
            counts.append({"ddinter_id": drug_id, "bang": kind, "so_dong": count, "tong": total})
    write_jsonl(archive.stage / "thuoc.jsonl", drugs)
    for kind, rows in tables.items():
        write_jsonl(archive.stage / f"{kind}.jsonl", rows)
    return {"dem": counts, "benh_bi_cat": truncated, "loi_phan_tich": errors}


def pair_index(archive: Archive) -> dict[int, Row]:
    rows: dict[int, Row] = {}
    for row in read_jsonl(archive.stage / "tuong_tac_thuoc.jsonl"):
        number = row["ma_trang_cap"]
        if number is None:
            continue
        old = rows.setdefault(number, row)
        if pair_key(old) != pair_key(row):
            raise ParseError(f"Trang cặp {number} trỏ đến nhiều cặp thuốc")
    return rows


def stage_pairs(archive: Archive, index: dict[int, Row]) -> list[int]:
    missing: list[int] = []
    archived = {
        int(path.name.removesuffix(".html.gz")): path
        for path in (archive.raw / PAIR).glob("*.html.gz")
    }
    samples = {
        int(match[1]): path
        for path in (archive.raw / "mau_that").glob("interact_*.html")
        if (match := re.fullmatch(r"interact_([0-9]+)\.html", path.name))
    }

    def rows() -> Iterator[Row]:
        for number, path in sorted((samples | archived).items()):
            if number not in index:
                missing.append(number)
                continue
            key = str(number)
            if number in archived:
                body = archive.load(PAIR, key)
                record = archive.record(PAIR, key)
            else:
                body = path.read_bytes()
                record = {
                    **ATTRIBUTION,
                    "url_goc": raw_url(PAIR, key),
                    "tep_tho": path.relative_to(archive.root).as_posix(),
                    "ngay_lay": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                }
            yield {**parse_pair(body, index[number]), **record}

    write_jsonl(archive.stage / f"{PAIR}.jsonl", rows())
    return missing


def candidates(index: dict[int, Row], ids: set[str], phase: str) -> Iterator[Row]:
    for number in sorted(index):
        row = index[number]
        overlap = sum(item in ids for item in pair_key(row))
        if phase == "cap-tat-ca" or overlap >= (2 if phase == "cap-uu-tien" else 1):
            yield row


def check(
    archive: Archive,
    legacy: dict[Pair, set[str]],
    counts: Row,
    raw_orphans: list[int],
    *,
    save_report: bool = True,
) -> Row:
    direction: dict[Pair, dict[str, set[str | None]]] = defaultdict(lambda: defaultdict(set))
    for row in read_jsonl(archive.stage / "tuong_tac_thuoc.jsonl"):
        direction[pair_key(row)][row["tu_trang_cua"]].add(row["muc_do"])
    complete = {
        row["ddinter_id"]
        for row in counts["dem"]
        if row["bang"] == "tuong_tac_thuoc" and row["so_dong"] == row["tong"]
    }
    web = set(direction)
    mismatches, asymmetry = [], []
    for key, sides in sorted(direction.items()):
        old_levels = legacy.get(key)
        if old_levels is not None:
            for drug_id, levels in sorted(sides.items()):
                if levels != old_levels:
                    mismatches.append(
                        {
                            "cap": key,
                            "tu_trang_cua": drug_id,
                            "csv": sorted(old_levels),
                            "web": sorted(levels, key=str),
                        }
                    )
        a, b = key
        if a != b and a in sides and b in sides and sides[a] != sides[b]:
            asymmetry.append(
                {"cap": key, "muc_do": {k: sorted(v, key=str) for k, v in sides.items()}}
            )
    details = list(read_jsonl(archive.stage / f"{PAIR}.jsonl"))
    rng = random.Random(51)  # noqa: S311  # mẫu kiểm dữ liệu tất định
    sample = rng.sample(details, min(40, len(details)))
    report = {
        **ATTRIBUTION,
        **counts,
        "lech_dem": [row for row in counts["dem"] if row["tong"] != row["so_dong"]],
        "csv_thieu_tren_web": sorted(
            key for key in legacy.keys() - web if complete.intersection(key)
        ),
        "web_thieu_trong_csv": sorted(web - legacy.keys()),
        "lech_muc_do": mismatches,
        "lech_doi_xung": asymmetry,
        "chi_tiet_mo_coi": [row["ma_trang_cap"] for row in details if pair_key(row) not in web],
        "tep_tho_chi_tiet_mo_coi": raw_orphans,
        "so_thuoc_da_kiem": len(complete),
        "so_mau": len(sample),
    }
    if save_report:
        write_jsonl(archive.reports / "T51_mau_kiem.jsonl", sample)
        write_json(archive.reports / "T51_kiem.json", report)
    return {key: len(value) if isinstance(value, list) else value for key, value in report.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pha", choices=PHASES)
    parser.add_argument("--rps", type=float, default=2.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", type=lambda value: value.split(","))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument(
        "--khong-ghi-bao-cao", action="store_true", help="Chỉ in kết quả của pha kiem"
    )
    args = parser.parse_args(argv)
    if not math.isfinite(args.rps) or not 0 < args.rps <= 2:
        parser.error("--rps phải lớn hơn 0 và tối đa 2")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit phải lớn hơn 0")
    if args.ids is not None and any(not DRUG_ID.fullmatch(item) for item in args.ids):
        parser.error("--ids phải gồm các DDInterID hợp lệ, cách nhau bằng dấu phẩy")
    archive = Archive(ROOT)
    drugs, legacy = catalogue(ROOT)
    if args.ids is not None and set(args.ids) - drugs.keys():
        parser.error("--ids chứa mã không có trong CSV")
    selected = priority(ROOT, drugs)
    write_json(archive.stage / "uu_tien.json", selected)
    if args.pha in {"phan-tich", "kiem"}:
        counts = stage_drugs(archive)
        missing = stage_pairs(archive, pair_index(archive))
        if args.pha == "kiem":
            print_summary(
                check(archive, legacy, counts, missing, save_report=not args.khong_ghi_bao_cao)
            )
        else:
            print_summary({**ATTRIBUTION, **counts, "tep_tho_chi_tiet_mo_coi": missing})
        return int(bool(counts["loi_phan_tich"]))
    preferred = dict.fromkeys([*PROBE_IDS, *selected["ddinter_ids"], *sorted(drugs)])
    stopped = None
    target_count = 0
    with httpx.Client(
        headers={"User-Agent": "BvienxPharmProject-kb/1.0"},
        timeout=30.0,
        follow_redirects=False,
    ) as http:
        client = DDInterClient(http, args.rps)
        crawl = Crawl(archive, client, args.refresh)
        counts = None
        try:
            if args.pha == DRUG:
                ids = list(dict.fromkeys(args.ids or preferred))[: args.limit]
                target_count = len(ids)
                crawl.drugs(ids)
            else:
                counts = stage_drugs(archive)
                index = pair_index(archive)
                ids = set(selected["ddinter_ids"])
                rows = [
                    row
                    for row in candidates(index, ids, args.pha)
                    if args.ids is None or set(args.ids).intersection(pair_key(row))
                ][: args.limit]
                target_count = len(rows)
                crawl.pairs(rows)
        except CrawlStopped as exc:
            stopped = str(exc)
        except KeyboardInterrupt:
            stopped = "Đã dừng bằng bàn phím"
        finally:
            if counts is None:
                counts = stage_drugs(archive)
            stage_pairs(archive, pair_index(archive))
            archive.manifest()
        no_candidates = args.pha != DRUG and not target_count
        report = {
            **ATTRIBUTION,
            "pha": args.pha,
            "so_muc": target_count,
            "yeu_cau": client.count,
            "giay_moi_yeu_cau": client.seconds / client.count if client.count else None,
            "da_luu": crawl.saved,
            "bo_qua_da_co": crawl.cached,
            "loi": crawl.errors,
            "ly_do_dung": stopped
            or ("Chưa có cặp phù hợp trong tầng 1" if no_candidates else None),
            "loai_loi": dict(Counter(row["loi"].split(":", 1)[0] for row in crawl.errors)),
        }
        archive.state[args.pha] = report
        write_json(archive.state_path, archive.state)
        write_json(archive.reports / f"T51_{args.pha}.json", report)
        print_summary(report)
        return int(bool(stopped or crawl.errors or no_candidates))


if __name__ == "__main__":
    raise SystemExit(main())
