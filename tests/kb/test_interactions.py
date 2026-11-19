"""Kiểm gộp DDInter, dữ liệu thiếu và kho chỉ đọc bằng nguồn giả lập."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.kb.interactions import InteractionStore
from app.kb.interactions.build import INDEX_PATH, build_index


def write_sources(root: Path) -> None:
    """Dữ liệu giả chỉ kiểm thuật toán, không dùng làm tri thức y khoa."""
    source = root / "data/kb_staging/ddinter"
    source.mkdir(parents=True)
    rows = {
        "thuoc": [
            {"ddinter_id": "A", "ten": "A", "tong_tuong_tac_tren_trang": {"tuong_tac_thuoc": 2}},
            {"ddinter_id": "B", "ten": "B", "tong_tuong_tac_tren_trang": {"tuong_tac_thuoc": 1}},
            {"ddinter_id": "C", "ten": "C", "tong_tuong_tac_tren_trang": {"tuong_tac_thuoc": 1}},
            {"ddinter_id": "D", "ten": "D", "tong_tuong_tac_tren_trang": {"tuong_tac_thuoc": 0}},
            {"ddinter_id": "E", "ten": "E"},
        ],
        "tuong_tac_thuoc": [
            dict(
                ddinter_id_a="B",
                ddinter_id_b="A",
                muc_do="Minor",
                muc_do_so=1,
                co_che=["Fixture minor"],
                ma_trang_cap=1,
                tu_trang_cua="A",
            ),
            dict(
                ddinter_id_a="A",
                ddinter_id_b="B",
                muc_do="Major",
                muc_do_so=3,
                co_che=["Fixture major"],
                ma_trang_cap=2,
                tu_trang_cua="A",
            ),
            dict(
                ddinter_id_a="A",
                ddinter_id_b="B",
                muc_do="Major",
                muc_do_so=3,
                co_che=["Fixture major"],
                ma_trang_cap=2,
                tu_trang_cua="B",
            ),
            dict(
                ddinter_id_a="E",
                ddinter_id_b="E",
                muc_do="Moderate",
                muc_do_so=2,
                co_che=[],
                ma_trang_cap=3,
                tu_trang_cua="E",
            ),
        ],
        "tuong_tac_chi_tiet": [
            dict(
                ma_trang_cap=1,
                ddinter_id_a="A",
                ddinter_id_b="B",
                muc_do="Minor",
                hau_qua="Fixture lower",
                xu_tri="Fixture lower",
                tai_lieu=[],
            ),
            dict(
                ma_trang_cap=2,
                ddinter_id_a="A",
                ddinter_id_b="B",
                muc_do="Major",
                hau_qua="Fixture highest",
                xu_tri="-",
                tai_lieu=["Fixture reference"],
                url_goc="https://example.invalid/2",
            ),
        ],
        "tuong_tac_thuc_an": [
            dict(
                ddinter_id="A",
                thuc_an="Fixture food",
                muc_do="Unknown",
                mo_ta="Fixture text",
                xu_tri="-",
                co_che=[],
            ),
        ],
    }
    for name, values in rows.items():
        (source / f"{name}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in values), encoding="utf-8"
        )


def test_build_merges_both_directions_and_is_reproducible(tmp_path: Path) -> None:
    write_sources(tmp_path)
    report = build_index(tmp_path)
    path = tmp_path / INDEX_PATH
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    store = InteractionStore.from_path(path)
    pair = store.pair("A", "B")
    assert pair is not None and pair == store.pair("B", "A")
    assert pair.muc_do == "Major" and pair.muc_do_so == 3
    assert pair.co_lech_muc and set(pair.cac_muc_nguon) == {"Major", "Minor"}
    assert pair.hau_qua == "Fixture highest"
    assert pair.xu_tri is None
    assert pair.tai_lieu == ["Fixture reference"]
    assert pair.url_goc == "https://example.invalid/2"
    assert set(pair.co_che) == {"Fixture minor", "Fixture major"}
    assert store.drug_complete("A") and store.drug_complete("B")
    assert store.drug_complete("D")
    assert not store.drug_complete("C")
    assert not store.drug_complete("E") and not store.drug_complete("missing")
    assert store.pair("A", "D") is None
    assert store.pair("E", "E") is None
    assert store.foods("A")[0].xu_tri is None
    assert store.foods("D") == []
    assert report["so_cap_theo_muc"] == {"Major": 1, "Moderate": 0, "Minor": 0, "Unknown": 0}
    assert report["so_cap_lech_muc"] == 1 and report["so_cap_co_chi_tiet"] == 1
    assert report["so_thuoc_da_cao_du"] == 3
    assert report["so_dong_tu_than_bo_qua"] == 1
    build_index(tmp_path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    # Kho đã nạp và đóng kết nối, vẫn đọc được sau khi thay tệp nguồn.
    path.unlink()
    assert store.pair("A", "B") == pair


def test_failed_build_preserves_previous_database(tmp_path: Path) -> None:
    write_sources(tmp_path)
    build_index(tmp_path)
    path = tmp_path / INDEX_PATH
    before = path.read_bytes()
    (tmp_path / "data/kb_staging/ddinter/tuong_tac_thuoc.jsonl").write_text(
        "invalid json\n", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        build_index(tmp_path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("placeholder", [None, "", " \t ", "-", "None", " none ", "\tN/A\n"])
def test_build_stores_missing_pair_and_food_descriptions_as_null(
    tmp_path: Path, placeholder: str | None
) -> None:
    write_sources(tmp_path)
    source = tmp_path / "data/kb_staging/ddinter"
    for name, description in (("tuong_tac_chi_tiet", "hau_qua"), ("tuong_tac_thuc_an", "mo_ta")):
        path = source / f"{name}.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        for row in rows:
            row[description] = row["xu_tri"] = placeholder
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    build_index(tmp_path)
    with closing(sqlite3.connect(tmp_path / INDEX_PATH)) as db:
        assert db.execute("SELECT hau_qua, xu_tri FROM cap").fetchall() == [(None, None)]
        assert db.execute("SELECT mo_ta, xu_tri FROM thuc_an").fetchall() == [(None, None)]
    store = InteractionStore.from_path(tmp_path / INDEX_PATH)
    pair = store.pair("A", "B")
    assert pair is not None and pair.hau_qua is None and pair.xu_tri is None
    food = store.foods("A")[0]
    assert food.mo_ta is None and food.xu_tri is None


def test_fallback_detail_links_to_its_actual_source_page(tmp_path: Path) -> None:
    write_sources(tmp_path)
    details = tmp_path / "data/kb_staging/ddinter/tuong_tac_chi_tiet.jsonl"
    lower = json.loads(details.read_text(encoding="utf-8").splitlines()[0])
    details.write_text(json.dumps(lower) + "\n", encoding="utf-8")
    build_index(tmp_path)
    pair = InteractionStore.from_path(tmp_path / INDEX_PATH).pair("A", "B")
    assert pair is not None and pair.muc_do == "Major"
    assert pair.hau_qua == "Fixture lower"
    assert pair.url_goc == "https://ddinter2.scbdd.com/server/interact/1/"
