"""Kiểm thử đồng bộ DAV bằng phản hồi HTTP giả lập."""

import gzip
import hashlib
import json
import unicodedata
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from app.kb.dictionary.http import USER_AGENT, SourceHTTP
from app.kb.dictionary.storage import read_json, read_jsonl
from app.kb.fetch.client import FetchError
from app.kb.sources.dav import BASE_BODY, PAGING, PUBLIC_PAGE, fetch_dav

PAGE = Path(__file__).parent / "fixtures/dav/page.json"
REAL = Path(__file__).parent / "fixtures/dav/page_real.json"


def test_dav_resume_after_size_fallback(tmp_path: Path) -> None:
    src = tmp_path / "dav"
    stage = tmp_path / "dav_thuoc.jsonl"
    records = [{"id": i, "soDangKy": str(i)} for i in range(51)]
    records[0] = read_json(PAGE)["result"]["items"][0]
    calls = []
    starts = []
    tick = 0.0
    available = False

    def wait(delay: float) -> None:
        nonlocal tick
        tick += delay

    def handle(request: httpx.Request) -> httpx.Response:
        starts.append(tick)
        assert request.headers["user-agent"] == USER_AGENT
        if str(request.url) == PUBLIC_PAGE:
            return httpx.Response(200, headers={"Set-Cookie": "XSRF-TOKEN=tok123; Path=/"})
        assert str(request.url) == PAGING and request.method == "POST"
        assert request.headers["x-xsrf-token"] == "tok123"
        body = json.loads(request.content)
        assert body["KichHoat"] is True and body["SoDangKyThuoc"] == {}
        assert body["filterText"] == "" and body["sorting"] is None
        skip, limit = body["skipCount"], body["maxResultCount"]
        calls.append((skip, limit))
        if limit == 100:
            return httpx.Response(400)
        if skip == 50 and not available:
            raise httpx.ConnectError("fixture")
        return httpx.Response(
            200, json={"result": {"totalCount": 51, "items": records[skip : skip + limit]}}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        http = SourceHTTP(client, 1, clock=lambda: tick, sleep=wait)
        with pytest.raises(FetchError, match="ConnectError"):
            fetch_dav(http, src, stage)
        assert not stage.exists()
        assert read_json(src / "manifest.json")["trang_thai"] == "chua_xong"
        available = True
        manifest = fetch_dav(http, src, stage)
    assert calls == [(0, 100), (0, 50), (50, 50), (50, 50)]
    assert all(end - start >= 1 for start, end in pairwise(starts))
    assert manifest["than_yeu_cau"] == {**BASE_BODY, "skipCount": 0, "maxResultCount": 50}
    assert manifest["totalCount"] == manifest["so_id_duy_nhat"] == 51
    assert manifest["so_trang"] == 2
    raw = (src / "trang/0.json.gz").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest["tep"]["0"]["sha256"]
    assert json.loads(gzip.decompress(raw))["result"]["items"] == records[:50]
    product = next(row for row in read_jsonl(stage) if row["dav_id"] == "dav-fixture-1")
    assert product["url_hdsd"] == "https://example.invalid/hdsd.pdf"
    assert product["con_hieu_luc"] is True


@pytest.mark.parametrize("condition", ["duplicate", "change"])
def test_dav_rejects_inconsistent_pages(tmp_path: Path, condition: str) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200)
        skip = json.loads(request.content)["skipCount"]
        total = 101 if not skip or condition == "duplicate" else 102
        ids = range(100) if not skip else [0]
        return httpx.Response(
            200, json={"result": {"totalCount": total, "items": [{"id": i} for i in ids]}}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(FetchError, match="DAV lệch"):
            fetch_dav(SourceHTTP(client, 0), tmp_path / "raw", tmp_path / "stage.jsonl")
    assert not (tmp_path / "stage.jsonl").exists()
    assert read_json(tmp_path / "raw/manifest.json")["trang_thai"] == "chua_xong"


def test_dav_backoff_and_page_cap(tmp_path: Path) -> None:
    delays = []
    sizes = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200)
        body = json.loads(request.content)
        sizes.append(body["maxResultCount"])
        if len(sizes) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"})
        items = [{"id": i, "soDangKy": str(i)} for i in range(20)]
        return httpx.Response(200, json={"result": {"totalCount": 40, "items": items}})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(FetchError, match="lệch số ID"):
            fetch_dav(
                SourceHTTP(client, 0, sleep=delays.append),
                tmp_path / "raw",
                tmp_path / "stage.jsonl",
            )
    assert sizes == [100, 100, 50, 20, 20]
    assert delays == [3]


def test_dav_real_response_shape(tmp_path: Path) -> None:
    """Phản hồi thật (cắt còn 3 mục) đi qua tầng 1 đúng trường."""
    body = REAL.read_bytes()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200)
        return httpx.Response(200, content=body)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        manifest = fetch_dav(SourceHTTP(client, 0), tmp_path / "raw", tmp_path / "stage.jsonl")
    assert manifest["so_id_duy_nhat"] == manifest["totalCount"] == 3
    first = next(
        r for r in read_jsonl(tmp_path / "stage.jsonl") if r["so_dang_ky"] == "890110214226"
    )
    assert unicodedata.normalize("NFC", first["hoat_chat_goc"]).startswith("Cefixime (dưới dạng")
    assert first["ham_luong_goc"] == "200mg" and first["con_hieu_luc"] is True
