"""Kiểm thử từ tầng thô tới báo cáo bằng nguồn giả lập."""

import json
from pathlib import Path

import httpx

from app.kb.dictionary.axis import Inputs, resolve_names
from app.kb.dictionary.build import build_dictionary
from app.kb.dictionary.http import SourceHTTP
from app.kb.dictionary.report import report_dictionary
from app.kb.dictionary.storage import read_json, read_jsonl, write_json
from app.kb.sources.dav import fetch_dav
from app.kb.sources.rxnav import RxNav
from tests.kb.test_rxnav_source import rx_transport as rx_transport  # noqa: F401


def test_dictionary_keeps_sources_and_queues_whole_product(
    tmp_path: Path,
    rx_transport: httpx.MockTransport,  # noqa: F811
) -> None:
    dav = tmp_path / "kb_sources/dav"
    rxnav_path = tmp_path / "kb_sources/rxnav"
    fixture = read_json(Path(__file__).parent / "fixtures/dav/page.json")
    fixture["result"]["items"].extend(
        [
            {"id": "duplicate-1", "soDangKy": "DUP", "tenThuoc": "Ceftriaxon trùng"},
            {"id": "duplicate-2", "soDangKy": "DUP", "tenThuoc": "Ceftriaxon trùng"},
            {"id": "missing-reg", "tenThuoc": "Fixture thiếu số đăng ký"},
        ]
    )
    fixture["result"]["totalCount"] = 6

    def dav_response(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200)
        return httpx.Response(200, json=fixture)

    write_json(
        tmp_path / "kb/hoat_chat.json",
        {
            "hoat_chat": [
                {
                    "hoat_chat_id": "ceftriaxone",
                    "ten_inn": "ceftriaxone",
                    "ten_viet": "ceftriaxon",
                    "dong_nghia": ["ceftriaxon natri"],
                }
            ],
            "nhan": {},
        },
    )
    write_json(
        tmp_path / "mock/demo/DEMO-fixture.json",
        {
            "danh_muc_hoat_chat": [
                {
                    "hoat_chat_id": "HC-ELECTROLYTE",
                    "ten_quoc_te": "sodium chloride",
                    "ten_hoat_chat": "Natri clorid",
                },
                {"hoat_chat_id": "HC-NO-ANCHOR", "ten_quoc_te": "ceftriaxone sodium"},
            ],
            "danh_muc_thuoc": [
                {"thuoc_id": "T-ELECTROLYTE", "thanh_phan": [{"hoat_chat_id": "HC-ELECTROLYTE"}]}
            ],
        },
    )
    with httpx.Client(transport=httpx.MockTransport(dav_response)) as client:
        fetch_dav(SourceHTTP(client, 0), dav, tmp_path / "kb_staging/tu_dien/dav_thuoc.jsonl")
    with httpx.Client(transport=rx_transport) as client:
        rxnav = RxNav(rxnav_path, SourceHTTP(client, 0))
        resolve_names(Inputs(tmp_path), rxnav)
        rxnav.manifest("xong", {})

    build_dictionary(tmp_path)
    out = tmp_path / "kb_curated/tu_dien"
    assert len(list(out.glob("*.jsonl"))) == 6
    for path in out.glob("*.jsonl"):
        for row in read_jsonl(path):
            assert row["nguon_ban_ghi_ids"] and row["phien_ban"] and row["ngay_dung"]

    axis = {row["hoat_chat_id"]: row for row in read_jsonl(out / "hoat_chat.jsonl")}
    assert set(axis) == {"ceftriaxone", "sodium_chloride"}
    for row in axis.values():
        refs = row["nguon_ban_ghi_ids"]
        assert any(ref.startswith("kb:") for ref in refs) or (
            any(ref.startswith("dav:") for ref in refs)
            and any(ref.startswith("rxnav:") for ref in refs)
        )
    assert axis["sodium_chloride"]["loai"] == "dich_truyen_dien_giai"
    edges = read_jsonl(out / "thuoc_thanh_phan.jsonl")
    assert {row["hoat_chat_id"] for row in edges} <= set(axis)
    assert {row["thuoc_id"] for row in edges} == {"dav:SDK-FIXTURE-1", "dav:SDK-FIXTURE-2"}
    cef = next(row for row in edges if row["thuoc_id"] == "dav:SDK-FIXTURE-1")
    assert (cef["ham_luong"], cef["don_vi"], cef["dang_muoi"]) == (1, "g", "natri")
    reviews = read_jsonl(out / "cho_duyet.jsonl")
    assert any(row.get("thuoc_id") == "dav:SDK-FIXTURE-3" and row["goi_y"] for row in reviews)
    assert any(
        row.get("thuoc_id") == "dav:DUP" and len(row["nguon_ban_ghi_ids"]) == 2 for row in reviews
    )
    assert any(row["ly_do"] == "thieu_so_dang_ky" for row in reviews)
    assert "natri clorit" not in {
        row["khoa_chuan_hoa"] for row in read_jsonl(out / "dong_nghia.jsonl")
    }

    summary = report_dictionary(tmp_path)
    assert summary["tong_ban_ghi_dav"] == 6 and summary["so_che_pham_dav"] == 4
    assert summary["hoat_chat_ca_gia_lap_chua_khop"] == []
    reports = tmp_path / "kb_reports"
    samples = (reports / "T50_mau_kiem.jsonl").read_bytes()
    assert len(samples.splitlines()) == 6
    assert report_dictionary(tmp_path) == json.loads((reports / "T50_tom_tat.json").read_bytes())
    assert (reports / "T50_mau_kiem.jsonl").read_bytes() == samples
