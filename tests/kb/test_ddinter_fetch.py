"""Kiểm thử ngoại tuyến bộ thu thập DDInter 2.0 (MockTransport, SQLite resume, CSV & manifest)."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from pathlib import Path

import httpx

from app.kb.sources.ddinter_fetch import (
    discover_interaction_ids,
    export_enriched_csvs,
    fetch_interaction_details,
    parse_interaction_detail_html,
    update_manifest,
)
from app.kb.sources.ddinter_index import ALL_CSV_COLUMNS

_SAMPLE_HTML_MAJOR = """
<html><body>
<table class="table">
  <tr>
    <td class="key">Level</td>
    <td><span class="badge rounded-pill">Major</span></td>
  </tr>
  <tr>
    <td class="key">Mechanism</td>
    <td>
      <span class="badge rounded-pill">Synergistic effect</span>
      <span class="badge rounded-pill">Metabolism</span>
    </td>
  </tr>
  <tr>
    <td class="key">Interaction</td>
    <td>Coadministration may increase bleeding risk.</td>
  </tr>
  <tr>
    <td class="key">Management</td>
    <td>Monitor INR closely and adjust warfarin dose.</td>
  </tr>
  <tr>
    <td class="key">References</td>
    <td id="reference-text">
      <span class="d-block my-2">
        [1] Holbrook AM et al. Arch Intern Med. 2005;165(10):1095-1106.
      </span>
      <span class="d-block my-2">[2] FDA Label: Coumadin.</span>
    </td>
  </tr>
</table>
</body></html>
"""

_SAMPLE_HTML_UNKNOWN = """
<html><body>
<table>
  <tr><td class="key">Level</td><td><span class="badge rounded-pill">Unknown</span></td></tr>
  <tr><td class="key">Interaction</td><td>-</td></tr>
  <tr><td class="key">Management</td><td>-</td></tr>
  <tr>
    <td class="key">References</td>
    <td id="reference-text"><span class="d-block">-</span></td>
  </tr>
</table>
</body></html>
"""


def test_parse_interaction_detail_html_major_and_unknown() -> None:
    major = parse_interaction_detail_html(_SAMPLE_HTML_MAJOR)
    assert major["level"] == "Major"
    assert major["mechanism"] == ["Synergistic effect", "Metabolism"]
    assert major["interaction_text"] == "Coadministration may increase bleeding risk."
    assert major["management_text"] == "Monitor INR closely and adjust warfarin dose."
    assert len(major["references"]) == 2  # type: ignore[arg-type]

    unk = parse_interaction_detail_html(_SAMPLE_HTML_UNKNOWN)
    assert unk["level"] == "Unknown"
    assert unk["interaction_text"] is None
    assert unk["management_text"] is None
    assert unk["references"] == []


def test_fetch_pipeline_resume_csv_export_and_manifest(tmp_path: Path) -> None:
    ddinter_dir = tmp_path / "ddinter"
    ddinter_dir.mkdir()
    csv_path = ddinter_dir / "ddinter_downloads_code_B.csv"
    csv_path.write_text(
        "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"
        "DDInter1951,Warfarin,DDInter138,Aspirin,Major\n"
        "DDInter79,Amlodipine,DDInter1951,Warfarin,Unknown\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tep": [
                    {
                        "duong_dan": "data/kb_sources/ddinter/ddinter_downloads_code_B.csv",
                        "nguon": "ddinter_2.0",
                        "sha256": "oldhash",
                        "kich_thuoc": 10,
                        "so_dong": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/server/interact-with/DDInter1951/":
            body = request.content.decode("utf-8")
            start = 0
            for part in body.split("&"):
                if part.startswith("start="):
                    start = int(part.split("=")[1])
            page_0 = [
                {
                    "drug_id": "DDInter138",
                    "drug_name": "Aspirin",
                    "interaction_id": "DDInter216310",
                    "level": "Major",
                    "synergistic_effect": 1,
                    "metabolism": 1,
                }
            ]
            page_1 = [
                {
                    "drug_id": "DDInter79",
                    "drug_name": "Amlodipine",
                    "interaction_id": "DDInter216311",
                    "level": "Unknown",
                }
            ]
            return httpx.Response(
                200,
                json={
                    "draw": 1,
                    "recordsTotal": 2,
                    "recordsFiltered": 2,
                    "data": page_0 if start == 0 else page_1,
                },
            )
        if request.url.path == "/server/interact/DDInter216310/":
            return httpx.Response(200, text=_SAMPLE_HTML_MAJOR)
        if request.url.path == "/server/interact/DDInter216311/":
            return httpx.Response(200, text=_SAMPLE_HTML_UNKNOWN)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    db_path = ddinter_dir / ".fetch_cache.sqlite"

    # Giai đoạn 1 + thử tiếp tục từ SQLite cache (lần 2 bỏ qua thuốc đã lấy)
    p1 = discover_interaction_ids(
        ["DDInter1951"],
        db_path,
        workers=2,
        page_size=1,
        transport=transport,
    )
    assert p1["drugs_requested"] == 1
    assert p1["unique_pairs_cached"] == 2
    p1_resume = discover_interaction_ids(
        ["DDInter1951"],
        db_path,
        workers=2,
        page_size=1,
        transport=transport,
    )
    assert p1_resume["drugs_requested"] == 0
    assert p1_resume["drugs_skipped_cached"] == 1

    # Giai đoạn 2: tải 1 bản ghi với skip_unknown=True, sau đó tiếp tục tải Unknown còn lại
    p2_known = fetch_interaction_details(
        db_path,
        skip_unknown=True,
        workers=2,
        transport=transport,
    )
    assert p2_known["details_fetched_ok"] == 1
    assert "GET /server/interact/DDInter216311/" not in calls

    p2_all = fetch_interaction_details(
        db_path,
        skip_unknown=False,
        workers=2,
        transport=transport,
    )
    assert p2_all["details_fetched_ok"] == 1
    assert p2_all["details_total_cached"] == 2

    # Kiểm tra trạng thái SQLite
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM interaction_detail WHERE status='done'").fetchone()
        count = row[0]
        assert count == 2
    finally:
        conn.close()

    # Giai đoạn 3 & 4: ghi CSV 10 cột + cập nhật sha256/kich_thuoc trong manifest
    export_res = export_enriched_csvs(ddinter_dir, db_path)
    assert export_res["files_updated"] == 1
    assert export_res["rows_total"] == 2
    assert export_res["rows_with_interaction_id"] == 2
    assert export_res["rows_with_interaction_text"] == 1

    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert tuple(reader.fieldnames or ()) == ALL_CSV_COLUMNS
        rows = list(reader)
        assert rows[0]["InteractionID"] == "DDInter216310"
        assert rows[0]["Mechanism"] == "Synergistic effect; Metabolism"
        assert "bleeding risk" in rows[0]["Interaction"]
        assert "INR closely" in rows[0]["Management"]
        assert "[1] Holbrook AM" in rows[0]["References"]
        assert rows[1]["InteractionID"] == "DDInter216311"
        assert rows[1]["Interaction"] == ""

    updated_count = update_manifest(manifest_path, ddinter_dir)
    assert updated_count == 1
    manifest_after = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    assert manifest_after["tep"][0]["sha256"] == expected_sha
    assert manifest_after["tep"][0]["kich_thuoc"] == csv_path.stat().st_size
    assert manifest_after["tep"][0]["so_dong"] == 2
