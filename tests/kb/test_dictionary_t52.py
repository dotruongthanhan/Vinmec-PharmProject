"""Kiểm các quy tắc T52 và luồng CLI bằng một bản sao dữ liệu giả lập."""

import csv
import hashlib
import json
from collections.abc import Sequence
from itertools import combinations
from pathlib import Path

import pytest

from app.config.settings import load_settings
from app.kb.dictionary.__main__ import main
from app.kb.dictionary.accept import RankedCandidate, can_accept, candidate_path
from app.kb.dictionary.build import build_dictionary
from app.kb.dictionary.candidates import rank_names
from app.kb.dictionary.catalog import CATALOG_PATH, baseline
from app.kb.dictionary.review import queue
from app.kb.dictionary.rules_extra import load_rules, with_final_e
from app.kb.dictionary.storage import Row, read_jsonl, write_json, write_jsonl
from app.kb.sources.rxnav import BASE_URL
from app.providers.fakes import HashEmbedder

FIXTURES = Path(__file__).parent / "fixtures/tu_dien"
NEIGHBORS = json.loads((FIXTURES / "rxnorm_ten_gan.json").read_text(encoding="utf-8-sig"))


def inputs(root: Path, names: list[str], extra: Sequence[tuple[str, str, str]] = ()) -> None:
    write_json(root / "kb/hoat_chat.json", {"hoat_chat": [], "nhan": {}})
    write_json(root / "kb_sources/dav/manifest.json", {"trang_thai": "xong"})
    write_jsonl(
        root / "kb_staging/tu_dien/dav_thuoc.jsonl",
        (
            {
                "dav_id": str(i),
                "so_dang_ky": f"FIX-{i}",
                "ten_thuoc": f"Fixture {i}",
                "hoat_chat_goc": name,
                "ham_luong_goc": None,
                "dang_bao_che": None,
                "duong_dung_goc": None,
                "con_hieu_luc": True,
                "url_hdsd": None,
            }
            for i, name in enumerate(names)
        ),
    )
    write_json(
        root / "kb_sources/rxnav" / CATALOG_PATH,
        {
            "minConceptGroup": {
                "minConcept": [
                    {"rxcui": code, "name": name, "tty": tty}
                    for code, name, tty in [*((a, b, "IN") for a, b in NEIGHBORS), *extra]
                ]
            },
        },
    )


def test_near_names_do_not_cross_match(tmp_path: Path) -> None:
    inputs(tmp_path, [])
    _, _, _, catalog = baseline(tmp_path)
    rules = load_rules()
    assert rules.tu_nhan_ngu_nghia is False
    truncated = {name[:-1]: code for code, name in NEIGHBORS if name.endswith("e")}
    variants = truncated | {name: code for code, name in NEIGHBORS}
    variants.update({name[:-2] + name[-1]: code for code, name in NEIGHBORS})
    for keys, code in truncated.items():
        assert with_final_e(keys, catalog).rxcui == code
    for _, name in NEIGHBORS:
        assert with_final_e(name, catalog) is None
    for record in rank_names(catalog, sorted(variants), HashEmbedder(), "fake"):
        assert len(record.ung_vien) == 5
        assert len({pick.rxcui for pick in record.ung_vien}) == 5
        if can_accept(
            record.ung_vien,
            rules.nguong_nhung,
            rules.nguong_ky_tu,
            rules.chenh_toi_thieu,
        ):
            assert record.ung_vien[0].rxcui == variants[record.khoa_chuan_hoa]

    for (_, first), (_, second) in combinations(NEIGHBORS, 2):
        for wrong, actual in [(first, second), (second, first)]:
            picks = [_pick(wrong, "1", 1, 0.98), _pick(actual, "2", 2, 0.97)]
            assert not can_accept(
                picks,
                rules.nguong_nhung,
                rules.nguong_ky_tu,
                rules.chenh_toi_thieu,
            )


def _pick(
    name: str,
    code: str,
    rank: int,
    combined: float,
    *atc: str,
) -> RankedCandidate:
    return RankedCandidate(
        rxcui=code,
        ten=name,
        ten_chinh=name,
        tty="IN",
        hang=rank,
        ma_atc=atc,
        diem_nhung=0.99,
        diem_ky_tu=0.99,
        diem_ket_hop=combined,
    )


def test_prefix_and_atc_block_at_required_margin() -> None:
    winner = _pick("cefotaxime", "2186", 1, 0.875, "J01DD01")
    assert can_accept([winner, _pick("amiloride", "644", 2, 0.75)], 0.94, 0.9, 0.125)
    assert not can_accept([winner, _pick("cefoxitin", "2189", 2, 0.75)], 0.94, 0.9, 0.125)
    assert not can_accept(
        [winner, _pick("ceftazidime", "2191", 2, 0.75, "J01DD02")],
        0.94,
        0.9,
        0.125,
    )
    assert not can_accept([winner, _pick("amiloride", "644", 2, 0.70)], 0.99, 0.9, 0.125)


def test_vitamin_context_and_herbs_do_not_leak(tmp_path: Path) -> None:
    inputs(
        tmp_path,
        [
            "C",
            "Vitamin C",
            "C; B6",
            "E; Cefotaxim",
            "Cam thảo; Đương quy; Bạch truật",
            "Cam thảo",
            "Vitamin B6; B12",
            "cao khô Cam thảo; Bạch truật",
            "Cam thảo; Đương quy; Bạch truật; Cefotaxim",
        ],
        [
            ("1151", "ascorbic acid", "IN"),
            ("684879", "pyridoxine", "IN"),
            ("1236136", "tocopherol", "IN"),
        ],
    )
    result = build_dictionary(tmp_path)
    assert result["do_phu"]["sau"]["bang_vitamin"] == 2
    assert result["do_phu"]["sau"]["them_e_cuoi"] == 0
    folder = tmp_path / "kb_curated/tu_dien"
    products = read_jsonl(folder / "thuoc.jsonl")
    assert products[0]["trang_thai_tra"] == "chua_khop"
    assert products[1]["trang_thai_tra"] == products[2]["trang_thai_tra"] == "du_thanh_phan"
    assert products[3]["trang_thai_tra"] == "chua_khop"
    assert products[4]["trang_thai_tra"] == "khong_co_du_lieu_tra"
    assert products[5]["trang_thai_tra"] == "chua_khop"
    assert products[7]["trang_thai_tra"] == "khong_co_du_lieu_tra"
    assert products[8]["trang_thai_tra"] == "chua_khop"
    aliases = {row["khoa_chuan_hoa"] for row in read_jsonl(folder / "dong_nghia.jsonl")}
    assert "vitamin c" in aliases
    assert not {"c", "e", "b6"} & aliases
    assert queue(tmp_path)["cam thao"]["so_che_pham"] == 2
    rows = read_jsonl(folder / "hoat_chat.jsonl")
    assert all(
        any(ref.startswith("rxnav:danh_muc/") for ref in r["nguon_ban_ghi_ids"]) for r in rows
    )


def test_pin_requires_cached_relationship_and_preserves_full_key(tmp_path: Path) -> None:
    inputs(
        tmp_path,
        ["Cefotaxim", "Cefotaxime disodium"],
        [("203151", "cefotaxime disodium", "PIN")],
    )
    build_dictionary(tmp_path)
    assert queue(tmp_path)["cefotaxime disodium"]["ly_do"] == "pin_thieu_quan_he_in"
    cache_key = hashlib.sha256((BASE_URL + "rxcui/203151/related.json?tty=IN").encode()).hexdigest()
    write_json(
        tmp_path / f"kb_sources/rxnav/cache/{cache_key}.json",
        {
            "relatedGroup": {
                "conceptGroup": [
                    {
                        "tty": "IN",
                        "conceptProperties": [
                            {"rxcui": "2186", "name": "cefotaxime"},
                        ],
                    }
                ]
            },
        },
    )
    build_dictionary(tmp_path)
    edges = read_jsonl(tmp_path / "kb_curated/tu_dien/thuoc_thanh_phan.jsonl")
    assert {row["hoat_chat_id"] for row in edges} == {"cefotaxime"}
    assert len(edges) == 2 and f"rxnav:{cache_key}" in edges[1]["nguon_ban_ghi_ids"]
    assert "pin_ve_in" not in edges[1]


def test_pin_can_strip_salt_only_for_one_exact_in(tmp_path: Path) -> None:
    inputs(
        tmp_path,
        ["Cefotaxime sodium", "Metformin hydrochloride", "Sodium valproate"],
        [
            ("203151", "cefotaxime sodium", "PIN"),
            ("100001", "metformin hydrochloride", "PIN"),
            ("100002", "Metformin", "IN"),
            ("100003", "sodium valproate", "PIN"),
            ("100004", "valproate", "IN"),
        ],
    )
    build_dictionary(tmp_path)
    folder = tmp_path / "kb_curated/tu_dien"
    edges = read_jsonl(folder / "thuoc_thanh_phan.jsonl")
    assert len(edges) == 1
    assert edges[0]["hoat_chat_id"] == "cefotaxime"
    for row in (edges[0], read_jsonl(folder / "anh_xa.jsonl")[0]):
        assert row["cach_khop"] == "rxnav_chinh_xac"
        assert row["pin_ve_in"] == "bo_muoi"
        assert {f"rxnav:{CATALOG_PATH}#rxcui={code}" for code in ("2186", "203151")} <= set(
            row["nguon_ban_ghi_ids"]
        )
    pending = queue(tmp_path)
    assert pending["metformin hydrochloride"]["ly_do"] == "pin_thieu_quan_he_in"
    assert pending["sodium valproate"]["ly_do"] == "pin_thieu_quan_he_in"


def test_build_rejects_missing_and_changed_t50_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs(tmp_path, ["Cefotaxim", "Fixture"])
    reports = tmp_path / "kb_reports"
    write_jsonl(
        reports / "T52_moc_T50.jsonl",
        [
            {"thuoc_id": "dav:FIX-0", "hoat_chat_ids": ["ceftriaxone"]},
            {"thuoc_id": "dav:FIX-1", "hoat_chat_ids": ["amlodipine"]},
            {"thuoc_id": "dav:FIX-2", "hoat_chat_ids": ["metformin"]},
        ],
    )
    assert main(["build"], root=tmp_path) == 1
    regressions = {row["thuoc_id"]: row for row in read_jsonl(reports / "T52_lui.jsonl")}
    assert regressions["dav:FIX-0"]["ly_do"] == ["doi_tap_hoat_chat"]
    assert regressions["dav:FIX-0"]["hoat_chat_ids_sau"] == ["cefotaxime"]
    assert regressions["dav:FIX-1"]["hoat_chat_ids_sau"] == []
    assert regressions["dav:FIX-2"]["ly_do"] == ["thieu_che_pham"]
    assert not (tmp_path / "kb_curated/tu_dien/thuoc.jsonl").exists()
    config = load_rules().model_copy(
        update={
            "ly_do_lui_cho_phep": {
                reason for row in regressions.values() for reason in row["ly_do"]
            }
        }
    )
    monkeypatch.setattr("app.kb.dictionary.build.load_rules", lambda: config)
    assert main(["build"], root=tmp_path) == 0
    assert len(read_jsonl(reports / "T52_lui.jsonl")) == 3


def test_unresolved_pin_keeps_t50_component_and_review(tmp_path: Path) -> None:
    inputs(
        tmp_path,
        ["Cefotaxime sodium", "Cefotaxime sodium; Ceftriaxon"],
        [("203151", "cefotaxime sodium", "PIN"), ("100002", "Cefotaxime", "IN")],
    )
    write_json(
        tmp_path / "kb/hoat_chat.json",
        {
            "hoat_chat": [
                {"hoat_chat_id": "cefotaxime", "ten_inn": "Cefotaxime", "ten_viet": "Cefotaxim"},
            ],
            "nhan": {},
        },
    )
    result = build_dictionary(tmp_path)
    folder = tmp_path / "kb_curated/tu_dien"
    assert result["do_phu"]["sau"]["du_thanh_phan"] == 1
    edges = read_jsonl(folder / "thuoc_thanh_phan.jsonl")
    assert [(row["thuoc_id"], row["hoat_chat_id"]) for row in edges] == [
        ("dav:FIX-0", "cefotaxime"),
    ]
    assert queue(tmp_path)["cefotaxime sodium"]["so_che_pham"] == 2


def test_candidate_pool_excludes_brands_and_strength(tmp_path: Path) -> None:
    inputs(tmp_path, ["Metformin"])
    write_json(
        tmp_path / "kb/hoat_chat.json",
        {
            "hoat_chat": [
                {
                    "hoat_chat_id": "metformin",
                    "ten_inn": "Metformin",
                    "ten_viet": "Metformine",
                    "dong_nghia": ["Metformin 100 mg", "Metformin 1%", "Metformin HCl"],
                },
            ],
            "nhan": {},
        },
    )
    stage = tmp_path / "kb_staging/tu_dien/dav_thuoc.jsonl"
    rows = read_jsonl(stage)
    write_jsonl(
        stage,
        [
            {**rows[0], "ten_thuoc": "Fixture brand 50"},
            {**rows[0], "ten_thuoc": "Fixture brand", "dav_id": "1", "so_dang_ky": "FIX-1"},
        ],
    )
    _, _, _, catalog = baseline(tmp_path)
    assert {"metformin", "metformine", "metformin hcl"} <= catalog.by_key.keys()
    assert not {"fixture brand 50", "fixture brand", "metformin 100 mg", "metformin 1"} & (
        catalog.by_key.keys()
    )
    for record in rank_names(
        catalog, ["fixture brand 50", "fixture brand"], HashEmbedder(), "fake"
    ):
        assert all(not pick.ten.lower().startswith("fixture brand") for pick in record.ung_vien)


def test_final_e_respects_exact_collision(tmp_path: Path) -> None:
    inputs(tmp_path, ["Cefotaxim natri"], [("31", "t53m", "IN"), ("32", "t53me", "IN")])
    _, _, _, catalog = baseline(tmp_path)
    assert with_final_e("t53m", catalog) is None
    build_dictionary(tmp_path)
    edges = read_jsonl(tmp_path / "kb_curated/tu_dien/thuoc_thanh_phan.jsonl")
    assert [(row["hoat_chat_id"], row["cach_khop"]) for row in edges] == [
        ("cefotaxime", "them_e_cuoi"),
    ]


def test_pin_can_use_cached_reverse_when_forward_is_missing(tmp_path: Path) -> None:
    inputs(tmp_path, ["Cefotaxime sodium"], [("203151", "cefotaxime sodium", "PIN")])
    url = BASE_URL + "rxcui/2186/related.json?tty=PIN"
    cache_key = hashlib.sha256(url.encode()).hexdigest()
    source = tmp_path / "kb_sources/rxnav"
    write_json(source / "manifest.json", {"tep": [{"url": url}]})
    write_json(
        source / f"cache/{cache_key}.json",
        {
            "relatedGroup": {
                "conceptGroup": [
                    {
                        "tty": "PIN",
                        "conceptProperties": [{"rxcui": "203151", "name": "cefotaxime sodium"}],
                    },
                ]
            }
        },
    )
    build_dictionary(tmp_path)
    edges = read_jsonl(tmp_path / "kb_curated/tu_dien/thuoc_thanh_phan.jsonl")
    assert edges[0]["hoat_chat_id"] == "cefotaxime"
    assert f"rxnav:{cache_key}" in edges[0]["nguon_ban_ghi_ids"]


def test_review_import_cli_five_decisions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    names = ["Fixture mot", "Fixture hai", "Fixture ba", "Fixture bon", "Fixture nam"]
    inputs(tmp_path, names + [names[0]])
    assert main(["build"], root=tmp_path) == 0
    for task in ("candidates", "calibrate", "publish"):
        assert main([task, "--dry-run"], root=tmp_path) == 0
    assert main(["candidates", "--embedder", "fake"], root=tmp_path) == 0
    assert main(["review"], root=tmp_path) == 0
    assert not (tmp_path / "cache").exists()
    report = tmp_path / "kb_reports/T52_hang_duyet.csv"
    assert report.read_bytes().startswith(b"\xef\xbb\xbf")
    with report.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["khoa_chuan_hoa"] == "fixture mot" and rows[0]["so_che_pham"] == "2"
    assert all(row["quyet_dinh"] == "" for row in rows)
    assert not read_jsonl(tmp_path / "kb_curated/tu_dien/anh_xa.jsonl")
    score_fixture: list[Row] = [
        {
            "khoa_chuan_hoa": key,
            "mo_hinh": "HashEmbedder",
            "ung_vien": [
                _pick("cefotaxime", "2186", 1, 0.9).model_dump(),
                _pick("ceftriaxone", "2193", 2, 0.8).model_dump(),
            ],
        }
        for key in ("fixture mot", "fixture hai")
    ]
    write_jsonl(candidate_path(tmp_path, "fake"), score_fixture)
    fixture = FIXTURES / "duyet_5_dong.csv"
    invalid = tmp_path / "sai.csv"
    invalid.write_bytes(fixture.read_bytes().replace(b"rxcui:6809", b"rxcui:9999999999"))
    assert main(["nhap-duyet", str(invalid)], root=tmp_path) == 1
    saved = tmp_path / "kb_curated/tu_dien/duyet_tay.jsonl"
    assert not saved.exists()
    assert "RxCUI khong co trong kho ung vien" in capsys.readouterr().out
    assert main(["nhap-duyet", str(fixture)], root=tmp_path) == 0
    assert json.loads(capsys.readouterr().out) == {"so_dong_da_nhap": 5}
    assert all(row["cach_khop"] == "nguoi_duyet" for row in read_jsonl(saved))
    assert main(["build"], root=tmp_path) == 0
    folder = tmp_path / "kb_curated/tu_dien"
    mappings = read_jsonl(folder / "anh_xa.jsonl")
    assert len(mappings) == 4
    assert {row["hoat_chat_id"] for row in mappings} == {"cefotaxime", "ceftriaxone", "metformin"}
    assert all(row["cach_khop"] == "nguoi_duyet" and row["nguoi_duyet"] for row in mappings)
    assert not queue(tmp_path)
    assert read_jsonl(folder / "thuoc.jsonl")[3]["trang_thai_tra"] == "khong_co_du_lieu_tra"


def test_auto_accept_uses_only_real_rankings_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs(tmp_path, ["Tenthu fixture"])
    key = "tenthu fixture"
    scores = [
        _pick("cefotaxime", "2186", 1, 0.99).model_dump(),
        _pick("amlodipine", "17767", 2, 0.5).model_dump(),
    ]
    write_jsonl(
        candidate_path(tmp_path, "fake"),
        [
            {"khoa_chuan_hoa": key, "mo_hinh": "HashEmbedder", "ung_vien": scores},
        ],
    )
    folder = tmp_path / "kb_curated/tu_dien"
    build_dictionary(tmp_path)
    assert not read_jsonl(folder / "anh_xa.jsonl")

    config = load_rules().model_copy(update={"tu_nhan_ngu_nghia": True})
    monkeypatch.setattr("app.kb.dictionary.build.load_rules", lambda: config)
    build_dictionary(tmp_path)
    assert not read_jsonl(folder / "anh_xa.jsonl")

    write_jsonl(
        candidate_path(tmp_path, "that"),
        [
            {
                "khoa_chuan_hoa": key,
                "mo_hinh": load_settings().embedding.active,
                "ung_vien": scores,
            },
        ],
    )
    build_dictionary(tmp_path)
    result = read_jsonl(folder / "anh_xa.jsonl")[0]
    assert result["cach_khop"] == "ngu_nghia_tu_nhan"
    assert result["hoat_chat_id"] == "cefotaxime"
