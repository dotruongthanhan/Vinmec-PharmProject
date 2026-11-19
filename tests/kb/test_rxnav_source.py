"""Kiểm thử nhận diện IN/PIN và truy vết cache RxNav."""

from pathlib import Path

import httpx
import pytest

from app.kb.dictionary.http import SourceHTTP
from app.kb.dictionary.storage import read_json
from app.kb.sources.rxnav import BASE_URL, RxNav


@pytest.fixture
def rx_transport() -> httpx.MockTransport:
    fixtures = read_json(Path(__file__).parent / "fixtures/rxnav/responses.json")

    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        assert url.startswith(BASE_URL) and request.method == "GET"
        endpoint = request.url.path.removeprefix("/REST/")
        if endpoint == "rxcui.json":
            assert request.url.params["search"] == "0"
            payload = fixtures.get(request.url.params["name"], {"idGroup": {}})
        elif endpoint == "rxclass/class/byRxcui.json":
            assert request.url.params["relaSource"] == "ATC"
            payload = fixtures["rxclass/" + request.url.params["rxcui"]]
        else:
            if endpoint.endswith("/related.json"):
                assert request.url.params["tty"] == "IN"
            payload = fixtures[endpoint]
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handle)


def test_rxnav_pin_and_cache(tmp_path: Path, rx_transport: httpx.MockTransport) -> None:
    with httpx.Client(transport=rx_transport) as client:
        nav = RxNav(tmp_path, SourceHTTP(client, 0))
        cef, error = nav.exact("ceftriaxone sodium")
        assert cef is not None and not error
        assert (cef.rxcui, cef.ten_inn, cef.ma_atc) == ("2", "ceftriaxone", ["J01DD04"])
        assert len(cef.nguon_ban_ghi_ids) == 4
        assert nav.exact("insufficient pin") == (None, "pin_khong_co_mot_in")
        assert nav.exact("brand fixture") == (None, "rxnav_khong_co_in_pin")
        sodium, _ = nav.exact("sodium chloride")
        assert sodium is not None
        assert sodium.ma_atc == ["A12CA01", "B05XA03"]
        assert sodium.ten_lop_atc == ["Sodium chloride", "Sodium chloride"]
        suggestions, _ = nav.suggestions("natri clorit")
        assert len(suggestions) == 1 and suggestions[0]["diem"] == "88"
        nav.manifest("xong", {"so_ten_tra": 4})
    assert len(read_json(tmp_path / "manifest.json")["tep"]) == nav.downloaded
    offline = RxNav(tmp_path)
    assert offline.exact("ceftriaxone sodium")[0] == cef
    assert offline.reused == 4


def test_rxnav_real_response_shapes(tmp_path: Path) -> None:
    """Phản hồi thật của RxNav: IN có ATC, IN không có lớp ATC (RxClass trả {})."""
    warfarin_class = {
        "rxclassDrugInfoList": {
            "rxclassDrugInfo": [
                {
                    "minConcept": {"rxcui": "11289", "name": "warfarin", "tty": "IN"},
                    "rxclassMinConceptItem": {
                        "classId": "B01AA",
                        "className": "Vitamin K antagonists",
                        "classType": "ATC1-4",
                    },
                    "rela": "",
                    "relaSource": "ATC",
                }
            ]
        }
    }
    clav_related = {
        "relatedGroup": {
            "rxcui": None,
            "conceptGroup": [
                {
                    "tty": "IN",
                    "conceptProperties": [
                        {"rxcui": "48203", "name": "clavulanate", "tty": "IN", "synonym": ""}
                    ],
                }
            ],
        }
    }

    def handle(request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.removeprefix("/REST/")
        name, rxcui = request.url.params.get("name"), request.url.params.get("rxcui")
        if endpoint == "rxcui.json":
            ids = {"warfarin": ["11289"], "clavulanate": ["48203"]}.get(name or "", [])
            return httpx.Response(200, json={"idGroup": {"rxnormId": ids}})
        if endpoint == "rxclass/class/byRxcui.json":
            return httpx.Response(200, json=warfarin_class if rxcui == "11289" else {})
        assert endpoint == "rxcui/48203/related.json"
        return httpx.Response(200, json=clav_related)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        nav = RxNav(tmp_path, SourceHTTP(client, 0))
        warfarin, _ = nav.exact("warfarin")
        clav, _ = nav.exact("clavulanate")
    assert warfarin is not None and warfarin.ma_atc == ["B01AA"]
    assert clav is not None and (clav.rxcui, clav.ten_inn, clav.ma_atc) == (
        "48203",
        "clavulanate",
        [],
    )
