"""Kiểm thử tải openFDA bằng phản hồi giả lập, không gọi mạng."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import yaml

from app.kb import build as kb_build
from app.kb.fetch import __main__ as fetch_cli
from app.kb.fetch.client import FDAClient, FetchError
from app.kb.fetch.labels import DrugSpec, build_queries, build_query, select_label
from app.kb.fetch.report import label_coverage, write_coverage_report
from app.kb.fetch.runner import fetch_sources, load_config

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).parent / "fixtures"
_API_MAU = _ROOT / "data" / "kb_sources" / "openfda_api_mau"


def fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def api_sample(name: str) -> dict:
    return json.loads((_API_MAU / name).read_text(encoding="utf-8"))


def drug(**kwargs: object) -> DrugSpec:
    return DrugSpec(hoat_chat="meropenem", ma="meropenem", duong_dung=["INTRAVENOUS"], **kwargs)


def _minimal_label(
    *,
    set_id: str,
    generic_name: list[str],
    substance_name: list[str],
    route: list[str],
    product_type: list[str] | None = None,
    effective_time: str = "20261110",
    indication: str = (
        "Indicated for complicated bacterial infections in adult hospitalized patients."
    ),
) -> dict:
    return {
        "set_id": set_id,
        "effective_time": effective_time,
        "openfda": {
            "generic_name": generic_name,
            "substance_name": substance_name,
            "route": route,
            "product_type": product_type or ["HUMAN PRESCRIPTION DRUG"],
        },
        "indications_and_usage": [indication],
    }


def test_selection_rejects_combinations_and_uses_coverage_date_then_id() -> None:
    candidates = fixture("openfda_fetch_labels.json")["results"]
    for order in itertools.permutations(candidates):
        assert select_label(list(order), drug(), "INTRAVENOUS")["set_id"] == "a"
    assert select_label([candidates[0]], drug(), "INTRAVENOUS") is None
    assert select_label(candidates[1:3], drug(), "INTRAVENOUS")["set_id"] == "older"
    assert select_label(candidates[2:4], drug(), "INTRAVENOUS")["set_id"] == "b"


def test_selection_checks_generic_route_product_type_and_substance() -> None:
    entry = fixture("openfda_fetch_labels.json")["results"][-1]
    for field, value in [
        ("generic_name", ["MEROPENEM AND VABORBACTAM"]),
        ("substance_name", ["OTHER"]),
        ("route", ["ORAL"]),
        ("product_type", ["HUMAN OTC DRUG"]),
    ]:
        bad = copy.deepcopy(entry)
        bad["openfda"][field] = value
        assert select_label([bad], drug(), "INTRAVENOUS") is None
    combo = copy.deepcopy(entry)
    combo["openfda"]["generic_name"] = ["IMIPENEM AND CILASTATIN"]
    combo["openfda"]["substance_name"] = ["IMIPENEM ANHYDROUS", "CILASTATIN SODIUM"]
    spec = DrugSpec(
        hoat_chat="imipenem and cilastatin",
        ma="combo",
        duong_dung=["INTRAVENOUS"],
        thanh_phan=["imipenem anhydrous", "cilastatin sodium"],
    )
    assert select_label([combo], spec, "INTRAVENOUS") == combo


def test_query_encodes_spaces_and_special_characters_without_injection() -> None:
    name = 'alpha + beta/"gamma" (salt) & acid'
    spec = DrugSpec(hoat_chat=name, ma="special", duong_dung=["ORAL"])
    query = build_query(spec, "ORAL")
    assert query == (
        'openfda.generic_name.exact:"ALPHA + BETA/\\"GAMMA\\" (SALT) & ACID" AND '
        'openfda.product_type:"HUMAN PRESCRIPTION DRUG" AND openfda.route:"ORAL"'
    )
    urls: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json=fixture("openfda_fetch_labels.json"))

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        FDAClient(http, api_key="synthetic-secret").get("label", query, limit=25)
    assert parse_qs(urlsplit(urls[0]).query)["search"] == [query]
    assert "%26" in urls[0] and "%2B" in urls[0] and "%22" in urls[0]


def test_build_queries_multi_tier_for_openfda_and_ndc() -> None:
    levo = DrugSpec(hoat_chat="levofloxacin", ma="levofloxacin", duong_dung=["INTRAVENOUS"])
    assert build_queries(levo, "INTRAVENOUS") == [
        (
            1,
            'openfda.generic_name.exact:"LEVOFLOXACIN" AND '
            'openfda.product_type:"HUMAN PRESCRIPTION DRUG" AND openfda.route:"INTRAVENOUS"',
        ),
        (
            2,
            'openfda.substance_name.exact:"LEVOFLOXACIN" AND '
            'openfda.product_type:"HUMAN PRESCRIPTION DRUG" AND openfda.route:"INTRAVENOUS"',
        ),
        (
            3,
            'openfda.generic_name:"levofloxacin" AND '
            'openfda.product_type:"HUMAN PRESCRIPTION DRUG" AND openfda.route:"INTRAVENOUS"',
        ),
    ]

    warfarin = DrugSpec(hoat_chat="warfarin sodium", ma="warfarin", duong_dung=["ORAL"])
    assert build_queries(warfarin, None, ndc=True) == [
        (1, 'generic_name.exact:"WARFARIN SODIUM" AND product_type:"HUMAN PRESCRIPTION DRUG"'),
        (
            2,
            'active_ingredients.name.exact:"WARFARIN SODIUM" AND '
            'product_type:"HUMAN PRESCRIPTION DRUG"',
        ),
        (3, 'generic_name:"warfarin sodium" AND product_type:"HUMAN PRESCRIPTION DRUG"'),
        (4, 'generic_name:"warfarin" AND product_type:"HUMAN PRESCRIPTION DRUG"'),
    ]

    combo = DrugSpec(
        hoat_chat="imipenem and cilastatin",
        ma="imipenem_and_cilastatin",
        duong_dung=["INTRAVENOUS"],
        thanh_phan=["imipenem anhydrous", "cilastatin sodium"],
    )
    combo_queries = build_queries(combo, None, ndc=True)
    assert combo_queries[1] == (
        2,
        'active_ingredients.name.exact:"IMIPENEM ANHYDROUS" AND '
        'active_ingredients.name.exact:"CILASTATIN SODIUM" AND '
        'product_type:"HUMAN PRESCRIPTION DRUG"',
    )


def test_fetch_skips_matching_hash_refreshes_and_is_byte_stable(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=fixture("openfda_fetch_labels.json"))

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = FDAClient(http, sleep=lambda _: None)
        first = fetch_sources("openfda", [drug()], tmp_path, client)
        before = (tmp_path / "manifest.json").read_bytes()
        assert first[0]["trang_thai"] == "da_lay"
        assert first[0]["bac_truy_van"] == 1
        second = fetch_sources("openfda", [drug()], tmp_path, client)
        assert second[0]["trang_thai"] == "bo_qua"
        assert len(requests) == 1
        assert (tmp_path / "manifest.json").read_bytes() == before
        fetch_sources("openfda", [drug()], tmp_path, client, refresh=True)
        assert len(requests) == 2
        assert (tmp_path / "manifest.json").read_bytes() == before
        path = tmp_path / "openfda/meropenem.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved["results"] == [fixture("openfda_fetch_labels.json")["results"][-1]]
        manifest = json.loads(before)["tep"][0]
        assert manifest["so_ung_vien"] == 5
        assert manifest["bac_truy_van"] == 1
        assert manifest["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_text("{}", encoding="utf-8")
        fetch_sources("openfda", [drug()], tmp_path, client)
        assert len(requests) == 3


def test_retry_and_failure_continue_with_next_drug(tmp_path: Path) -> None:
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        if "meropenem" in request.url.params["search"].lower():
            attempts += 1
            return httpx.Response(429, json=fixture("openfda_fetch_429.json"))
        return httpx.Response(404, json=api_sample("err_404.json"))

    other = DrugSpec(hoat_chat="other", ma="other", duong_dung=["ORAL"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        outcomes = fetch_sources(
            "openfda",
            [drug(), other],
            tmp_path,
            FDAClient(http, api_key="synthetic-secret", sleep=lambda _: None),
        )
    assert attempts == 5
    assert [r["trang_thai"] for r in outcomes] == ["loi_ket_noi", "khong_tim_thay"]
    assert "synthetic-secret" not in json.dumps(outcomes)
    assert not (tmp_path / "openfda/meropenem.json").exists()


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_eventually_succeeds(status: int) -> None:
    attempts = 0
    waits: list[float] = []

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(status, json=fixture("openfda_fetch_429.json"))
        return httpx.Response(200, json=fixture("openfda_fetch_labels.json"))

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        result = FDAClient(http, sleep=waits.append).get("label", "x", limit=25)
    assert result["results"][-1]["set_id"] == "a"
    assert 1.0 in waits and 2.0 in waits


def test_rate_limit_uses_monotonic_time_and_never_bursts() -> None:
    now = 0.0
    sent: list[float] = []

    def sleep(seconds: float) -> None:
        nonlocal now
        now += seconds

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(now)
        return httpx.Response(200, json={"results": []})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = FDAClient(http, sleep=sleep, clock=lambda: now)
        for _ in range(5):
            client.get("label", "x", limit=25)
    assert all(b - a >= 0.34 - 1e-9 for a, b in itertools.pairwise(sent))


def test_dry_run_does_not_request_or_write(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        pytest.fail("Không được gọi mạng khi dry-run")

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources("openfda", [drug()], tmp_path, FDAClient(http), dry_run=True)
    assert rows[0]["trang_thai"] == "se_lay"
    assert list(tmp_path.iterdir()) == []


def test_ndc_deduplication_and_manifest(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/drug/ndc.json"
        return httpx.Response(200, json=fixture("openfda_fetch_ndc.json"))

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        fetch_sources("ndc", [drug()], tmp_path, FDAClient(http))
    rows = json.loads((tmp_path / "openfda_ndc/meropenem.json").read_text())["san_pham"]
    assert len(rows) == 2
    assert rows[0]["ten_biet_duoc"] == "Synthetic A"
    assert rows[0]["ham_luong"] == [{"hoat_chat": "MEROPENEM", "ham_luong": "1 g/vial"}]
    assert rows[0]["duong_dung"] == ["INTRAVENOUS"]
    manifest_entry = json.loads((tmp_path / "manifest.json").read_text())["tep"][0]
    assert manifest_entry["nguon"] == "openfda_ndc"
    assert manifest_entry["bac_truy_van"] == 1


def test_coverage_counts_presence_characters_tables_and_missing_routes(tmp_path: Path) -> None:
    rich = fixture("openfda_fetch_labels.json")["results"][-1]
    rich = copy.deepcopy(rich)
    rich["dosage_and_administration"] = ["2.2 Renal Impairment Dosage adjustment."]
    rich["dosage_and_administration_table"] = [
        "<table><tr><th>Group</th><th>Dose</th></tr><tr><td>A</td><td>B</td></tr></table>"
    ]
    rich["drug_interactions"] = ["Interactions"]
    row = label_coverage(rich)
    assert row["muc"]["chi_dinh"] == {"co": True, "so_ky_tu": 10}
    assert row["muc"]["canh_bao"] == {"co": False, "so_ky_tu": 0}
    assert row["so_bang_lieu"] == 1 and row["co_muc_chinh_lieu_than"] is True
    assert row["co_muc_tuong_tac"] is True
    assert label_coverage({})["co_muc_chinh_lieu_than"] is False
    source = tmp_path / "sources/openfda"
    source.mkdir(parents=True)
    (source / "meropenem.json").write_text(json.dumps({"results": [rich]}), encoding="utf-8")
    (source / "sparse.json").write_text(json.dumps({"results": [{}]}), encoding="utf-8")
    specs = [drug(), DrugSpec(hoat_chat="missing", ma="missing", duong_dung=["ORAL"])]
    report = write_coverage_report(tmp_path / "sources", tmp_path / "reports", specs)
    assert report["so_nhan"] == 2
    assert report["thieu_nhan"] == [{"ma": "missing", "duong_dung": "ORAL"}]
    assert len(report["nhan_thieu_tu_2_muc"]) == 2
    before = (tmp_path / "reports/openfda_do_phu.json").read_bytes()
    write_coverage_report(tmp_path / "sources", tmp_path / "reports", specs)
    assert (tmp_path / "reports/openfda_do_phu.json").read_bytes() == before


def test_config_contains_exactly_existing_fifty_labels() -> None:
    specs = load_config(Path("config/kb/hoat_chat_can_lay.yaml"))
    existing = json.loads(Path("data/kb/hoat_chat.json").read_text(encoding="utf-8"))["nhan"]
    assert len(specs) == 50 and {s.ma for s in specs} == set(existing)
    assert next(s for s in specs if s.ma == "metoprolol_tartrate").duong_dung == ["INTRAVENOUS"]


def test_client_sanitizes_transport_failures() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(str(request.url), request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(FetchError) as exc:
            FDAClient(http, api_key="synthetic-secret", sleep=lambda _: None).get("label", "x", 25)
    assert "synthetic-secret" not in str(exc.value)


@pytest.mark.parametrize("kind", ["openfda", "ndc"])
def test_malformed_results_are_reported_and_next_drug_continues(tmp_path: Path, kind: str) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if "meropenem" in request.url.params["search"].lower():
            return httpx.Response(200, json=fixture("openfda_fetch_invalid.json"))
        return httpx.Response(404, json=api_sample("err_404.json"))

    other = DrugSpec(hoat_chat="other", ma="other", duong_dung=["ORAL"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources(kind, [drug(), other], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert [row["trang_thai"] for row in rows] == ["phan_hoi_sai_cau_truc", "khong_tim_thay"]
    assert "results" in rows[0]["ly_do"]
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize("kind", ["openfda", "ndc"])
@pytest.mark.parametrize(
    ("body", "reason_field"),
    [
        pytest.param(b"not JSON", "JSON", id="invalid-json"),
        pytest.param(b"[]", "đối tượng", id="non-object"),
        pytest.param(b"{}", "results", id="missing-results"),
        pytest.param(b'{"results": null}', "results", id="null-results"),
        pytest.param(b'{"results": {}}', "results", id="non-list-results"),
        pytest.param(b'{"results": [null]}', "results[0]", id="null-entry"),
        pytest.param(b'{"results": ["invalid"]}', "results[0]", id="non-object-entry"),
    ],
)
def test_malformed_response_cli_preserves_old_source_and_reports_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    kind: str,
    body: bytes,
    reason_field: str,
) -> None:
    sources_dir = tmp_path / "data/kb_sources"
    sources_dir.mkdir(parents=True)
    good = fixture("openfda_fetch_labels.json" if kind == "openfda" else "openfda_fetch_ndc.json")
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=good))
    ) as http:
        seeded = fetch_sources(kind, [drug()], sources_dir, FDAClient(http, sleep=lambda _: None))
    assert seeded[0]["trang_thai"] == "da_lay"
    source_path = sources_dir / seeded[0]["duong_dan"]
    old_source = source_path.read_bytes()
    manifest_path = sources_dir / "manifest.json"
    old_manifest = manifest_path.read_bytes()
    other = DrugSpec(hoat_chat="other", ma="other", duong_dung=["ORAL"])
    config_dir = tmp_path / "config/kb"
    config_dir.mkdir(parents=True)
    (config_dir / "hoat_chat_can_lay.yaml").write_text(
        yaml.safe_dump([drug().model_dump(), other.model_dump()]), encoding="utf-8"
    )

    def respond(request: httpx.Request) -> httpx.Response:
        if "meropenem" in request.url.params["search"].lower():
            return httpx.Response(200, content=body)
        return httpx.Response(404, json=api_sample("err_404.json"))

    real_client = httpx.Client

    def make_client(**_: object) -> httpx.Client:
        return real_client(transport=httpx.MockTransport(respond))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_cli.httpx, "Client", make_client)
    monkeypatch.setattr(fetch_cli, "FDAClient", lambda http: FDAClient(http, sleep=lambda _: None))
    assert fetch_cli.main([kind, "--refresh"]) == 1
    rows = json.loads(
        (tmp_path / f"data/kb_reports/openfda_fetch_{kind}.json").read_text(encoding="utf-8")
    )
    assert [row["trang_thai"] for row in rows] == ["phan_hoi_sai_cau_truc", "khong_tim_thay"]
    assert reason_field in rows[0]["ly_do"]
    assert source_path.read_bytes() == old_source
    assert manifest_path.read_bytes() == old_manifest
    assert "[phan_hoi_sai_cau_truc]" in capsys.readouterr().out
    report_dir = tmp_path / "data/kb_reports"
    report = json.loads((report_dir / "openfda_do_phu.json").read_text(encoding="utf-8"))
    assert report["ket_qua_tai"][kind] == rows
    markdown = (report_dir / "openfda_do_phu.md").read_text(encoding="utf-8")
    route = "INTRAVENOUS" if kind == "openfda" else "NDC"
    assert f"  - `meropenem` ({route}): phan_hoi_sai_cau_truc {rows[0]['ly_do']}" in markdown


def test_optional_api_key_uses_existing_secret_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFDA_API_KEY", "synthetic-secret")
    keys: list[str | None] = []

    def respond(request: httpx.Request) -> httpx.Response:
        keys.append(request.url.params.get("api_key"))
        return httpx.Response(200, json={"results": []})

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        FDAClient(http).get("label", "x", 25)
        monkeypatch.delenv("OPENFDA_API_KEY")
        FDAClient(http).get("label", "x", 25)
    assert keys == ["synthetic-secret", None]


@pytest.mark.parametrize("kind", ["openfda", "ndc"])
def test_unexpected_http_response_is_not_a_connection_error(tmp_path: Path, kind: str) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(400, json={"error": {"code": "BAD_REQUEST"}})
        )
    ) as http:
        rows = fetch_sources(kind, [drug()], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert rows[0]["trang_thai"] == "phan_hoi_sai_cau_truc"
    assert "HTTP 400" in rows[0]["ly_do"]
    assert fetch_cli._exit_code(rows) == 1
    assert not (tmp_path / "manifest.json").exists()


@pytest.mark.parametrize(
    "meta", [None, {"results": {"total": None}}, {"results": {"total": "bad"}}]
)
def test_malformed_ndc_pagination_metadata_names_the_field(tmp_path: Path, meta: object) -> None:
    payload = fixture("openfda_fetch_ndc.json")
    payload["meta"] = meta
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload))
    ) as http:
        rows = fetch_sources("ndc", [drug()], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert rows[0]["trang_thai"] == "phan_hoi_sai_cau_truc"
    assert "meta.results.total" in rows[0]["ly_do"]
    assert fetch_cli._exit_code(rows) == 1
    assert not (tmp_path / "openfda_ndc/meropenem.json").exists()
    assert not (tmp_path / "manifest.json").exists()


def test_multiple_routes_retire_legacy_manifest_only_after_all_succeed(tmp_path: Path) -> None:
    response = fixture("openfda_fetch_labels.json")
    for entry in response["results"]:
        entry["openfda"]["route"].append("INTRAMUSCULAR")
    fail_second = False

    def respond(request: httpx.Request) -> httpx.Response:
        if fail_second and "INTRAMUSCULAR" in request.url.params["search"]:
            return httpx.Response(404, json=api_sample("err_404.json"))
        return httpx.Response(200, json=response)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = FDAClient(http, sleep=lambda _: None)
        fetch_sources("openfda", [drug()], tmp_path, client)
        spec = DrugSpec(
            hoat_chat="meropenem", ma="meropenem", duong_dung=["INTRAVENOUS", "INTRAMUSCULAR"]
        )
        fail_second = True
        fetch_sources("openfda", [spec], tmp_path, client)
        entries = json.loads((tmp_path / "manifest.json").read_text())["tep"]
        assert any(e["duong_dan"] == "openfda/meropenem.json" for e in entries)
        fail_second = False
        fetch_sources("openfda", [spec], tmp_path, client)
    entries = json.loads((tmp_path / "manifest.json").read_text())["tep"]
    assert {e["duong_dan"] for e in entries} == {
        "openfda/meropenem__intravenous.json",
        "openfda/meropenem__intramuscular.json",
    }
    assert (tmp_path / "openfda/meropenem.json").is_file()


@pytest.mark.parametrize("missing_second_page", [False, True])
def test_ndc_requires_all_pages_before_writing(tmp_path: Path, missing_second_page: bool) -> None:
    payload = fixture("openfda_fetch_ndc.json")

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.params["skip"] == "0":
            return httpx.Response(
                200,
                json={
                    "meta": {"results": {"total": 101}},
                    "results": [payload["results"][0]] * 100,
                },
            )
        assert request.url.params["skip"] == "100"
        if missing_second_page:
            return httpx.Response(404, json=api_sample("err_404.json"))
        return httpx.Response(
            200,
            json={
                "meta": {"results": {"total": 101}},
                "results": [payload["results"][-1]],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources("ndc", [drug()], tmp_path, FDAClient(http, sleep=lambda _: None))
    path = tmp_path / "openfda_ndc/meropenem.json"
    if missing_second_page:
        assert rows[0]["trang_thai"] == "phan_hoi_sai_cau_truc"
        assert "trang rỗng" in rows[0]["ly_do"]
        assert not path.exists()
    else:
        assert rows[0]["trang_thai"] == "da_lay" and rows[0]["so_ung_vien"] == 101
        assert len(json.loads(path.read_text())["san_pham"]) == 2


def test_openfda_tiered_fallback_with_real_sample_and_longer_generic(tmp_path: Path) -> None:
    real_mero = api_sample("mero_label_rx_iv.json")
    not_found = api_sample("err_404.json")
    levo = DrugSpec(hoat_chat="levofloxacin", ma="levofloxacin", duong_dung=["INTRAVENOUS"])
    enoxa = DrugSpec(hoat_chat="enoxaparin sodium", ma="enoxaparin", duong_dung=["SUBCUTANEOUS"])
    seen_searches: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        search = request.url.params["search"]
        seen_searches.append(search)
        if 'openfda.generic_name.exact:"MEROPENEM"' in search:
            return httpx.Response(200, json=real_mero)
        if 'openfda.generic_name:"levofloxacin"' in search:
            return httpx.Response(
                200,
                json={
                    "results": [
                        _minimal_label(
                            set_id="levo-iv-1",
                            generic_name=["LEVOFLOXACIN IN 5% DEXTROSE"],
                            substance_name=["LEVOFLOXACIN"],
                            route=["INTRAVENOUS"],
                        )
                    ]
                },
            )
        if 'openfda.substance_name.exact:"ENOXAPARIN SODIUM"' in search:
            return httpx.Response(
                200,
                json={
                    "results": [
                        _minimal_label(
                            set_id="enoxa-sc-1",
                            generic_name=["ENOXAPARIN SODIUM INJECTION,USP"],
                            substance_name=["ENOXAPARIN SODIUM"],
                            route=["SUBCUTANEOUS"],
                        )
                    ]
                },
            )
        return httpx.Response(404, json=not_found)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources(
            "openfda",
            [drug(), levo, enoxa],
            tmp_path,
            FDAClient(http, sleep=lambda _: None),
        )
    assert [(r["ma"], r["trang_thai"], r["bac_truy_van"]) for r in rows] == [
        ("meropenem", "da_lay", 1),
        ("levofloxacin", "da_lay", 3),
        ("enoxaparin", "da_lay", 2),
    ]
    manifest_rows = json.loads((tmp_path / "manifest.json").read_text())["tep"]
    manifest = {entry["ten_goi"]: entry for entry in manifest_rows}
    assert manifest["meropenem"]["set_id"] == "31dd2160-7dbd-51fa-e054-00144ff88e88"
    assert manifest["levofloxacin"]["bac_truy_van"] == 3
    assert 'openfda.generic_name:"levofloxacin"' in manifest["levofloxacin"]["truy_van"]
    assert manifest["enoxaparin"]["bac_truy_van"] == 2
    # Bảo đảm dừng ở bậc đầu tiên đạt chuẩn (meropenem chỉ gọi 1 lần).
    assert sum("MEROPENEM" in s.upper() for s in seen_searches) == 1


def test_selection_rejects_biosimilar_suffix_and_wrong_salt() -> None:
    insulin_spec = DrugSpec(
        hoat_chat="insulin glargine",
        ma="insulin_glargine",
        duong_dung=["SUBCUTANEOUS"],
    )
    biosimilar = _minimal_label(
        set_id="bio-1",
        generic_name=["INSULIN GLARGINE-ALDY"],
        substance_name=["INSULIN GLARGINE"],
        route=["SUBCUTANEOUS"],
    )
    originator = _minimal_label(
        set_id="orig-1",
        generic_name=["INSULIN GLARGINE"],
        substance_name=["INSULIN GLARGINE"],
        route=["SUBCUTANEOUS"],
    )
    assert select_label([biosimilar], insulin_spec, "SUBCUTANEOUS") is None
    assert select_label([biosimilar, originator], insulin_spec, "SUBCUTANEOUS") == originator

    tartrate_spec = DrugSpec(
        hoat_chat="metoprolol tartrate",
        ma="metoprolol_tartrate",
        duong_dung=["INTRAVENOUS"],
    )
    succinate = _minimal_label(
        set_id="succ-1",
        generic_name=["METOPROLOL SUCCINATE"],
        substance_name=["METOPROLOL SUCCINATE"],
        route=["INTRAVENOUS"],
    )
    tartrate_iv = _minimal_label(
        set_id="tart-1",
        generic_name=["METOPROLOL TARTRATE INJECTION"],
        substance_name=["METOPROLOL TARTRATE"],
        route=["INTRAVENOUS"],
    )
    assert select_label([succinate], tartrate_spec, "INTRAVENOUS") is None
    assert select_label([succinate, tartrate_iv], tartrate_spec, "INTRAVENOUS") == tartrate_iv


def test_ndc_tiered_fallback_with_real_mero_ndc_and_warfarin_saltless(tmp_path: Path) -> None:
    mero_ndc = api_sample("mero_ndc.json")
    mero_ndc["meta"]["results"]["total"] = len(mero_ndc["results"])
    not_found = api_sample("err_404.json")
    warfarin = DrugSpec(hoat_chat="warfarin sodium", ma="warfarin", duong_dung=["ORAL"])

    def respond(request: httpx.Request) -> httpx.Response:
        search = request.url.params["search"]
        if 'active_ingredients.name.exact:"MEROPENEM"' in search:
            return httpx.Response(200, json=mero_ndc)
        if 'generic_name:"warfarin"' in search:
            return httpx.Response(
                200,
                json={
                    "meta": {"results": {"total": 2}},
                    "results": [
                        {
                            "brand_name": "Warfarin Combo Synth",
                            "generic_name": "Warfarin Sodium and Aspirin",
                            "active_ingredients": [
                                {"name": "WARFARIN SODIUM", "strength": "5 mg/1"},
                                {"name": "ASPIRIN", "strength": "81 mg/1"},
                            ],
                            "dosage_form": "TABLET",
                            "route": ["ORAL"],
                            "product_type": "HUMAN PRESCRIPTION DRUG",
                        },
                        {
                            "brand_name": "Warfarin Sodium",
                            "generic_name": "Warfarin Sodium",
                            "active_ingredients": [
                                {"name": "WARFARIN SODIUM", "strength": "5 mg/1"}
                            ],
                            "dosage_form": "TABLET",
                            "route": ["ORAL"],
                            "product_type": "HUMAN PRESCRIPTION DRUG",
                        },
                    ],
                },
            )
        return httpx.Response(404, json=not_found)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources(
            "ndc",
            [drug(), warfarin],
            tmp_path,
            FDAClient(http, sleep=lambda _: None),
        )
    assert [(r["ma"], r["trang_thai"], r["bac_truy_van"]) for r in rows] == [
        ("meropenem", "da_lay", 2),
        ("warfarin", "da_lay", 4),
    ]
    warfarin_saved = json.loads((tmp_path / "openfda_ndc/warfarin.json").read_text())["san_pham"]
    assert len(warfarin_saved) == 1
    assert warfarin_saved[0]["ten_chung"] == "Warfarin Sodium"
    manifest_rows = json.loads((tmp_path / "manifest.json").read_text())["tep"]
    manifest = {entry["ten_goi"]: entry for entry in manifest_rows}
    assert manifest["meropenem"]["bac_truy_van"] == 2
    assert manifest["warfarin"]["bac_truy_van"] == 4


def test_combination_candidate_rejected_at_loose_tier_and_records_reasons(tmp_path: Path) -> None:
    not_found = api_sample("err_404.json")
    levo = DrugSpec(hoat_chat="levofloxacin", ma="levofloxacin", duong_dung=["INTRAVENOUS"])
    combo_cand = _minimal_label(
        set_id="cand-combo",
        generic_name=["LEVOFLOXACIN AND DEXAMETHASONE"],
        substance_name=["LEVOFLOXACIN", "DEXAMETHASONE"],
        route=["INTRAVENOUS"],
    )
    oral_cand = _minimal_label(
        set_id="cand-oral",
        generic_name=["LEVOFLOXACIN"],
        substance_name=["LEVOFLOXACIN"],
        route=["ORAL"],
    )
    otc_cand = _minimal_label(
        set_id="cand-otc",
        generic_name=["LEVOFLOXACIN"],
        substance_name=["LEVOFLOXACIN"],
        route=["INTRAVENOUS"],
        product_type=["HUMAN OTC DRUG"],
    )
    extra_combo = _minimal_label(
        set_id="cand-combo-2",
        generic_name=["LEVOFLOXACIN AND PREDNISOLONE"],
        substance_name=["LEVOFLOXACIN", "PREDNISOLONE"],
        route=["INTRAVENOUS"],
    )
    bad_results = [combo_cand, oral_cand, otc_cand, extra_combo]

    def respond_all_bad(request: httpx.Request) -> httpx.Response:
        if 'openfda.generic_name:"levofloxacin"' in request.url.params["search"]:
            return httpx.Response(200, json={"results": bad_results})
        return httpx.Response(404, json=not_found)

    with httpx.Client(transport=httpx.MockTransport(respond_all_bad)) as http:
        rows = fetch_sources("openfda", [levo], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert len(rows) == 1
    assert rows[0]["trang_thai"] == "khong_co_ung_vien_hop_le"
    assert rows[0]["so_ung_vien"] == 4
    assert len(rows[0]["ly_do_loai"]) == 3
    assert [item["ung_vien"] for item in rows[0]["ly_do_loai"]] == [
        "cand-combo",
        "cand-oral",
        "cand-otc",
    ]
    assert "dạng phối hợp" in rows[0]["ly_do_loai"][0]["ly_do"]

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "openfda_fetch_openfda.json").write_text(json.dumps(rows), encoding="utf-8")
    (tmp_path / "openfda").mkdir()
    write_coverage_report(tmp_path, reports_dir, [levo])
    md = (reports_dir / "openfda_do_phu.md").read_text(encoding="utf-8")
    assert "khong_co_ung_vien_hop_le" in md
    assert "cand-combo" in md

    valid_cand = _minimal_label(
        set_id="levo-iv-ok",
        generic_name=["LEVOFLOXACIN IN 5% DEXTROSE"],
        substance_name=["LEVOFLOXACIN"],
        route=["INTRAVENOUS"],
    )

    def respond_mixed(request: httpx.Request) -> httpx.Response:
        if 'openfda.generic_name:"levofloxacin"' in request.url.params["search"]:
            return httpx.Response(200, json={"results": [combo_cand, valid_cand]})
        return httpx.Response(404, json=not_found)

    with httpx.Client(transport=httpx.MockTransport(respond_mixed)) as http:
        ok_rows = fetch_sources("openfda", [levo], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert ok_rows[0]["trang_thai"] == "da_lay"
    saved = json.loads((tmp_path / "openfda/levofloxacin.json").read_text(encoding="utf-8"))
    assert saved["results"][0]["set_id"] == "levo-iv-ok"

    # Kiểm cả NDC: ứng viên phối hợp ở bậc lỏng bị loại hết -> khong_co_ung_vien_hop_le.
    ndc_combo = {
        "product_ndc": "99999-001",
        "generic_name": "Levofloxacin and Dexamethasone",
        "active_ingredients": [
            {"name": "LEVOFLOXACIN", "strength": "5 mg/mL"},
            {"name": "DEXAMETHASONE", "strength": "1 mg/mL"},
        ],
        "product_type": "HUMAN PRESCRIPTION DRUG",
    }

    def respond_ndc_combo(request: httpx.Request) -> httpx.Response:
        if 'generic_name:"levofloxacin"' in request.url.params["search"]:
            ndc_payload = {"meta": {"results": {"total": 1}}, "results": [ndc_combo]}
            return httpx.Response(200, json=ndc_payload)
        return httpx.Response(404, json=not_found)

    with httpx.Client(transport=httpx.MockTransport(respond_ndc_combo)) as http:
        ndc_rows = fetch_sources("ndc", [levo], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert ndc_rows[0]["trang_thai"] == "khong_co_ung_vien_hop_le"
    assert "dạng phối hợp" in ndc_rows[0]["ly_do_loai"][0]["ly_do"]


def test_exit_codes_distinguish_four_outcomes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert fetch_cli._exit_code([{"trang_thai": "da_lay"}, {"trang_thai": "bo_qua"}]) == 0
    assert fetch_cli._exit_code([{"trang_thai": "khong_tim_thay"}]) == 3
    code_2 = fetch_cli._exit_code(
        [{"trang_thai": "khong_tim_thay"}, {"trang_thai": "khong_co_ung_vien_hop_le"}]
    )
    assert code_2 == 2
    code_1 = fetch_cli._exit_code(
        [
            {"trang_thai": "khong_tim_thay"},
            {"trang_thai": "khong_co_ung_vien_hop_le"},
            {"trang_thai": "loi_ket_noi"},
        ]
    )
    assert code_1 == 1
    assert fetch_cli._exit_code([{"trang_thai": "phan_hoi_sai_cau_truc"}]) == 1
    assert (
        fetch_cli._exit_code(
            [
                {"trang_thai": "khong_tim_thay"},
                {"trang_thai": "khong_co_ung_vien_hop_le"},
                {"trang_thai": "phan_hoi_sai_cau_truc"},
            ]
        )
        == 1
    )

    (tmp_path / "config/kb").mkdir(parents=True)
    (tmp_path / "data/kb_sources").mkdir(parents=True)
    (tmp_path / "data/kb_reports").mkdir(parents=True)
    cfg_items = [{"hoat_chat": "meropenem", "ma": "meropenem", "duong_dung": ["INTRAVENOUS"]}]
    (tmp_path / "config/kb/hoat_chat_can_lay.yaml").write_text(
        yaml.safe_dump(cfg_items),
        encoding="utf-8",
    )
    not_found = api_sample("err_404.json")
    real_client = httpx.Client

    def make_client(**_: object) -> httpx.Client:
        transport = httpx.MockTransport(lambda _req: httpx.Response(404, json=not_found))
        return real_client(transport=transport)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(fetch_cli.httpx, "Client", make_client)
    assert fetch_cli.main(["openfda"]) == 3


def test_replacing_wrong_route_label_counts_changed_chunk_ids(tmp_path: Path) -> None:
    sources_dir = tmp_path / "sources"
    (sources_dir / "openfda").mkdir(parents=True)
    out_dir = tmp_path / "curated"
    reports_dir = tmp_path / "reports"
    levo = DrugSpec(hoat_chat="levofloxacin", ma="levofloxacin", duong_dung=["INTRAVENOUS"])

    old_payload = {
        "results": [
            _minimal_label(
                set_id="old-oral-levo",
                generic_name=["LEVOFLOXACIN"],
                substance_name=["LEVOFLOXACIN"],
                route=["ORAL"],
                indication="Old oral levofloxacin label for urinary tract infections.",
            )
        ]
    }
    label_file = sources_dir / "openfda/levofloxacin.json"
    label_file.write_text(json.dumps(old_payload), encoding="utf-8")
    manifest = {
        "tep": [
            {
                "duong_dan": "openfda/levofloxacin.json",
                "nguon": "openfda_drug_label",
                "ten_goi": "levofloxacin",
                "set_id": "old-oral-levo",
                "effective_time": "20261105",
                "sha256": hashlib.sha256(label_file.read_bytes()).hexdigest(),
            }
        ]
    }
    (sources_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    names_path = _ROOT / "data/kb/hoat_chat.json"
    _, code_before = kb_build.build_kb(sources_dir, out_dir, reports_dir, names_path=names_path)
    assert code_before == 0
    chunks_before = kb_build.load_chunks(out_dir / "chunks.jsonl")
    assert chunks_before

    new_payload = {
        "results": [
            _minimal_label(
                set_id="new-iv-levo",
                generic_name=["LEVOFLOXACIN IN 5% DEXTROSE"],
                substance_name=["LEVOFLOXACIN"],
                route=["INTRAVENOUS"],
                indication="New intravenous levofloxacin label for nosocomial pneumonia.",
            )
        ]
    }
    not_found = api_sample("err_404.json")

    def respond(request: httpx.Request) -> httpx.Response:
        if 'openfda.generic_name:"levofloxacin"' in request.url.params["search"]:
            return httpx.Response(200, json=new_payload)
        return httpx.Response(404, json=not_found)

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources("openfda", [levo], sources_dir, FDAClient(http, sleep=lambda _: None))
    assert rows[0]["trang_thai"] == "da_lay"

    report_after, code_after = kb_build.build_kb(
        sources_dir, out_dir, reports_dir, names_path=names_path
    )
    assert code_after == 0
    assert report_after.so_ma_doan_bi_doi == len(chunks_before)
    assert report_after.so_ma_doan_khong_doi_noi_dung_bi_doi == 0


def test_tmp_path_uses_default_pytest_temp_outside_repo(tmp_path: Path) -> None:
    repo_tmp = Path(__file__).parent / ".tmp"
    assert repo_tmp not in tmp_path.parents
