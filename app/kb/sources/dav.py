"""Đồng bộ công bố số đăng ký của Cục Quản lý Dược."""

from __future__ import annotations

import gzip
import hashlib
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.kb.dictionary.http import SourceHTTP
from app.kb.dictionary.storage import Row, read_json, store, write_json, write_jsonl
from app.kb.fetch.client import FetchError, MalformedResponseError

SITE = "https://dichvucong.dav.gov.vn"
PUBLIC_PAGE = SITE + "/congbothuoc/index"
PAGING = SITE + "/api/services/app/soDangKy/GetAllPublicServerPaging"
PAGE_SIZES = (100, 50, 20)


BASE_BODY = {"filterText": "", "SoDangKyThuoc": {}, "KichHoat": True, "sorting": None}
SKIP_FIELD = "skipCount"
LIMIT_FIELD = "maxResultCount"


def _open_session(http: SourceHTTP) -> dict[str, str]:
    """GET trang công bố để nhận cookie; máy chủ đòi header X-XSRF-TOKEN lấy từ cookie."""
    page = http.request("GET", PUBLIC_PAGE)
    if page.status_code != 200:
        raise FetchError(f"Trang công bố DAV trả HTTP {page.status_code}")
    token = http.http.cookies.get("XSRF-TOKEN")
    return {"X-XSRF-TOKEN": token} if token else {}


def _page(raw: bytes) -> tuple[int, list[Row]]:
    try:
        result = json.loads(raw)["result"]
        total, items = result["totalCount"], result["items"]
        if type(total) is not int or total < 0 or not isinstance(items, list):
            raise TypeError
        if any(not isinstance(item, dict) for item in items):
            raise TypeError
    except (KeyError, TypeError, ValueError) as exc:
        raise MalformedResponseError(
            "DAV thiếu result.totalCount hoặc result.items hợp lệ"
        ) from exc
    return total, items


def _record_id(row: Row) -> str | None:
    value = row.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return str(value) if type(value) is int else None


def _stage(items: list[Row]) -> tuple[list[Row], list[str], dict[str, list[str]]]:
    groups: dict[str, list[Row]] = defaultdict(list)
    missing = []
    for item in items:
        reg = item.get("soDangKy")
        if isinstance(reg, str) and reg.strip():
            groups[reg.strip()].append(item)
        else:
            missing.append(_record_id(item))
    rows = []
    conflicts = {}
    for reg, group in sorted(groups.items()):
        item = min(group, key=lambda row: _record_id(row) or "")
        basic = item.get("thongTinThuocCoBan") or {}
        docs = item.get("thongTinTaiLieu") or {}
        registration = item.get("thongTinDangKyThuoc") or {}
        if len(group) > 1:
            conflicts[reg] = sorted(_record_id(row) for row in group)
        active, expired = item.get("isActive"), item.get("isHetHan")
        effective = (
            False
            if active is False or expired is True
            else (True if active is True and expired is False else None)
        )
        rows.append(
            {
                "so_dang_ky": reg,
                "ten_thuoc": item.get("tenThuoc"),
                "hoat_chat_goc": basic.get("hoatChatChinh"),
                "ham_luong_goc": basic.get("hamLuong"),
                "dang_bao_che": basic.get("dangBaoChe"),
                "dong_goi": basic.get("dongGoi"),
                "duong_dung_goc": basic.get("tenDuongDung"),
                "con_hieu_luc": effective,
                "url_hdsd": docs.get("urlHuongDanSuDung") or docs.get("urlNhanVaHDSD"),
                "url_nhan": docs.get("urlNhan") or docs.get("urlNhanVaHDSD"),
                "dav_id": _record_id(item),
                "ngay_het_han": registration.get("ngayHetHanSoDangKy"),
            }
        )
    return rows, sorted(missing), conflicts


def fetch_dav(http: SourceHTTP, source: Path, staging: Path, *, refresh: bool = False) -> Row:
    """Lưu từng trang và từ chối xuất tầng 1 nếu lượt tải thiếu hoặc trùng ID."""
    started = time.monotonic()
    path = source / "manifest.json"
    if path.exists() and not refresh:
        manifest = read_json(path)
    else:
        manifest = {
            "ngay_lay": datetime.now(UTC).isoformat(),
            "url": PAGING,
            "than_yeu_cau": {**BASE_BODY, SKIP_FIELD: 0, LIMIT_FIELD: PAGE_SIZES[0]},
            "header_toi_thieu": [
                "Content-Type: application/json",
                "Cookie (GET trang)",
                "X-XSRF-TOKEN",
            ],
            "giay_phep": "dữ liệu công bố của Cục Quản lý Dược – Bộ Y tế",
            "thu_kich_thuoc_trang": [],
            "totalCount": None,
            "tep": {},
            "trang_thai": "dang_lay",
        }
        write_json(path, manifest)

    total = manifest["totalCount"]
    entries = manifest["tep"]
    items: list[Row] = []
    ids: set[str] = set()
    skip = 0
    missing_ids = 0

    def checkpoint(status: str) -> None:
        manifest.update(
            trang_thai=status,
            so_trang=len(entries),
            so_id_duy_nhat=len(ids),
            so_ban_ghi_thieu_id=missing_ids,
            thoi_gian_giay=round(time.monotonic() - started, 3),
        )
        write_json(path, manifest)

    try:
        headers: dict[str, str] | None = None
        limit = manifest["than_yeu_cau"][LIMIT_FIELD]
        while total is None or skip < total or (total == 0 and not items and skip == 0):
            key = str(skip)
            file = source / "trang" / f"{key}.json.gz"
            old = entries.get(key)
            compressed = file.read_bytes() if old and file.exists() else None
            cached = (
                compressed is not None and hashlib.sha256(compressed).hexdigest() == old["sha256"]
            )
            if cached:
                raw = gzip.decompress(compressed)
            else:
                if headers is None:
                    headers = _open_session(http)
                response = http.request(
                    "POST",
                    PAGING,
                    headers=headers,
                    json={**manifest["than_yeu_cau"], SKIP_FIELD: skip, LIMIT_FIELD: limit},
                )
                if response.status_code in {400, 413, 422} and skip == 0 and total is None:
                    batch_total, batch = None, []
                elif response.status_code != 200:
                    raise FetchError(f"DAV trả HTTP {response.status_code} tại skip={skip}")
                else:
                    batch_total, batch = _page(response.content)
                shortened = batch_total is None or len(batch) < min(limit, batch_total)
                if shortened and skip == 0 and total is None:
                    manifest["thu_kich_thuoc_trang"].append(
                        {"kich_thuoc": limit, "http": response.status_code, "so_muc": len(batch)}
                    )
                    if limit != PAGE_SIZES[-1]:
                        limit = PAGE_SIZES[PAGE_SIZES.index(limit) + 1]
                        manifest["than_yeu_cau"][LIMIT_FIELD] = limit
                        checkpoint("dang_lay")
                        continue
                    raise FetchError(f"DAV từ chối hoặc trả thiếu với trang {limit}")
                raw = response.content
                compressed = gzip.compress(raw, mtime=0)
            batch_total, batch = _page(raw)
            if total is None:
                total = manifest["totalCount"] = batch_total
            if batch_total != total or len(batch) != min(limit, total - skip):
                raise FetchError(
                    f"DAV lệch tại skip={skip}: totalCount={batch_total} (dự kiến {total}), "
                    f"số mục={len(batch)} (dự kiến {min(limit, total - skip)})"
                )
            if not cached:
                entries[key] = {
                    "duong_dan": f"trang/{file.name}",
                    "sha256": hashlib.sha256(compressed).hexdigest(),
                }
                checkpoint("dang_lay")
                store(file, compressed)
            items.extend(batch)
            for item in batch:
                identifier = _record_id(item)
                if identifier is None:
                    missing_ids += 1
                else:
                    ids.add(identifier)
            checkpoint("dang_lay")
            if total == 0:
                break
            skip += limit
        if len(ids) != total or missing_ids:
            raise FetchError(
                f"DAV lệch số ID: {len(ids)} duy nhất, {missing_ids} thiếu, totalCount={total}"
            )
        rows, missing_regs, conflicts = _stage(items)
        manifest.update(
            so_dang_ky_duy_nhat=len(rows),
            id_thieu_so_dang_ky=missing_regs,
            so_dang_ky_trung=conflicts,
        )
        write_jsonl(staging, rows)
    except (FetchError, OSError, ValueError, TypeError, AttributeError) as exc:
        manifest["loi"] = str(exc)
        checkpoint("chua_xong")
        raise
    manifest.pop("loi", None)
    checkpoint("xong")
    return manifest
