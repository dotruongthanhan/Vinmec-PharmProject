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

from app.kb.fetch.client import FDAClient, FetchError
from app.kb.fetch.labels import DrugSpec, build_query, select_label
from app.kb.fetch.report import label_coverage, write_coverage_report
from app.kb.fetch.runner import fetch_sources, load_config

_FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def drug(**kwargs: object) -> DrugSpec:
    return DrugSpec(hoat_chat="meropenem", ma="meropenem", duong_dung=["INTRAVENOUS"], **kwargs)


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
        assert manifest["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        path.write_text("{}", encoding="utf-8")
        fetch_sources("openfda", [drug()], tmp_path, client)
        assert len(requests) == 3


def test_retry_and_failure_continue_with_next_drug(tmp_path: Path) -> None:
    attempts = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        if "meropenem" in request.url.params["search"]:
            attempts += 1
            return httpx.Response(429, json=fixture("openfda_fetch_429.json"))
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

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
    assert json.loads((tmp_path / "manifest.json").read_text())["tep"][0]["nguon"] == "openfda_ndc"


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
        if "meropenem" in request.url.params["search"]:
            return httpx.Response(200, json=fixture("openfda_fetch_invalid.json"))
        return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})

    other = DrugSpec(hoat_chat="other", ma="other", duong_dung=["ORAL"])
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        rows = fetch_sources(kind, [drug(), other], tmp_path, FDAClient(http, sleep=lambda _: None))
    assert [row["trang_thai"] for row in rows] == ["phan_hoi_sai_cau_truc", "khong_tim_thay"]
    assert "results" in rows[0]["ly_do"]
    assert not (tmp_path / "manifest.json").exists()


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


def test_multiple_routes_retire_legacy_manifest_only_after_all_succeed(tmp_path: Path) -> None:
    response = fixture("openfda_fetch_labels.json")
    for entry in response["results"]:
        entry["openfda"]["route"].append("INTRAMUSCULAR")
    fail_second = False

    def respond(request: httpx.Request) -> httpx.Response:
        if fail_second and "INTRAMUSCULAR" in request.url.params["search"]:
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
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
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
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
