"""Kiểm độ phủ bằng nguồn giả lập nhỏ, không dùng mạng."""

import copy
import csv
import importlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

FIXTURE = Path(__file__).parent / "fixtures/coverage/sources.json"
Row = dict[str, Any]


@pytest.fixture
def sources() -> Row:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def calculate(sources: Row, required: tuple[str, ...] | None = None) -> tuple[list[Row], Row]:
    from app.kb.coverage.models import CoverageData
    from app.kb.coverage.report import calculate_coverage

    kwargs = {} if required is None else {"required_sources": required}
    rows, summary = calculate_coverage(CoverageData.model_validate(sources), **kwargs)
    return [row.model_dump() for row in rows], summary.model_dump()


def test_combination_label_is_linked_by_ingredient_ids(sources: Row) -> None:
    rows, _ = calculate(sources)
    by_id = {row["hoat_chat_id"]: row for row in rows}
    assert by_id["amoxicillin"]["so_doan_nhan_fda"] == 1
    assert by_id["clavulanic_acid"]["so_doan_nhan_fda"] == 2
    assert by_id["clavulanic_acid"]["set_id_nhan_fda"] == ["combo-set"]
    assert by_id["fixture_missing"]["so_doan_nhan_fda"] == 0


def test_optional_source_absent_is_unknown(sources: Row) -> None:
    rows, summary = calculate(sources)
    assert all(row["co_livertox"] is None for row in rows)
    assert summary["trang_thai_nguon"]["livertox"] == "chưa có nguồn"
    assert [row["co_lactmed"] for row in rows] == [False, True, False]


@pytest.mark.parametrize(
    ("totals", "counts", "expected"),
    [
        ({"D1": 1}, {"D1": 1}, True),
        ({"D1": 2}, {"D1": 1}, False),
        ({"D1": 0}, {}, True),
        ({"D1": 1}, {"D1": 2}, False),
        ({}, {}, None),
    ],
)
def test_ddinter_requires_exact_page_row_count(
    sources: Row, totals: dict[str, int | None], counts: dict[str, int], expected: bool | None
) -> None:
    sources["tong_ddinter"] = totals
    sources["so_dong_ddinter"] = counts
    rows, _ = calculate(sources)
    assert rows[0]["ddinter_da_cao_du"] is expected
    assert rows[2]["ddinter_da_cao_du"] is None


def test_ndc_strips_salt_and_optional_names_match_exactly(sources: Row) -> None:
    sources["ten_livertox"] = [" AMOXÍCILLIN ", "Fixture missing extra"]
    rows, _ = calculate(sources)
    assert [row["co_ndc"] for row in rows] == [True, False, False]
    assert [row["co_livertox"] for row in rows] == [True, False, False]


def test_summary_lists_case_gaps_and_counts_columns(sources: Row) -> None:
    rows, summary = calculate(sources)
    assert rows[0]["thieu"] == []
    assert rows[1]["thieu"] == ["atc", "ddinter"]
    assert rows[2]["thieu"] == ["dav", "rxcui", "atc", "ddinter", "nhan_fda"]
    assert summary["so_hoat_chat"] == 3
    assert summary["so_du_nguon_bat_buoc"] == 1
    assert summary["theo_cot"]["so_doan_nhan_fda"] == 2
    assert summary["theo_cot"]["ddinter_da_cao_du"] == 1
    assert summary["trong_ca_gia_lap"]["so_hoat_chat"] == 2
    assert summary["trong_ca_gia_lap"]["hoat_chat_thieu"] == [
        {
            "hoat_chat_id": "clavulanic_acid",
            "ten_inn": "Clavulanic acid",
            "thieu": ["atc", "ddinter"],
        }
    ]


def test_required_sources_are_configurable_and_do_not_mutate_input(sources: Row) -> None:
    from app.kb.coverage.models import CoverageData
    from app.kb.coverage.report import calculate_coverage

    data = CoverageData.model_validate(sources)
    before = copy.deepcopy(data)
    rows, summary = calculate_coverage(data, required_sources=("nhan_fda", "livertox"))
    assert rows[0].thieu == ["livertox"]
    assert rows[2].thieu == ["nhan_fda", "livertox"]
    assert summary.so_du_nguon_bat_buoc == 0
    assert data == before
    with pytest.raises(ValueError, match="nguon"):
        calculate(sources, ("unknown",))


@pytest.fixture
def root(tmp_path: Path, sources: Row) -> Path:
    database = tmp_path / "data/kb_curated/tra_cuu/tra_cuu.sqlite"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as db:
        db.executescript("""
            CREATE TABLE hoat_chat(hoat_chat_id TEXT PRIMARY KEY, ten_inn TEXT,
                ten_viet TEXT, rxcui TEXT, ma_atc_json TEXT, loai TEXT,
                ddinter_id TEXT, ddinter_cach_khop TEXT);
            CREATE TABLE thuoc_thanh_phan(thuoc_id TEXT, hoat_chat_id TEXT);
            CREATE TABLE chuyen_ma_ca(ma_ca TEXT, hoat_chat_id TEXT);
        """)
        for row in sources["hoat_chat"]:
            db.execute(
                "INSERT INTO hoat_chat VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["hoat_chat_id"],
                    row["ten_inn"],
                    row.get("ten_viet"),
                    row["rxcui"],
                    json.dumps(row["ma_atc"]),
                    row["loai"],
                    row["ddinter_id"],
                    row.get("ddinter_cach_khop"),
                ),
            )
            for i in range(row["so_che_pham_dav"]):
                db.execute(
                    "INSERT INTO thuoc_thanh_phan VALUES (?, ?)", (f"dav:{i}", row["hoat_chat_id"])
                )
            if row["trong_ca_gia_lap"]:
                db.executemany(
                    "INSERT INTO chuyen_ma_ca VALUES (?, ?)",
                    [("HC-1", row["hoat_chat_id"]), ("HC-2", row["hoat_chat_id"])],
                )
    files = {
        "kb_curated/chunks.jsonl": sources["doan_nhan"],
        "kb_staging/ddinter/thuoc.jsonl": [
            {"ddinter_id": key, "tong_tuong_tac_tren_trang": {"tuong_tac_thuoc": value}}
            for key, value in sources["tong_ddinter"].items()
        ],
        "kb_staging/ddinter/tuong_tac_thuoc.jsonl": [
            {"tu_trang_cua": "D1", "ddinter_id_a": "D1", "ddinter_id_b": "D2"},
            {"tu_trang_cua": "D2", "ddinter_id_a": "D1", "ddinter_id_b": "D2"},
        ],
    }
    for name, rows in files.items():
        path = tmp_path / "data" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    ndc = tmp_path / "data/kb_sources/openfda_ndc/unrelated_filename.json"
    ndc.parent.mkdir(parents=True)
    ndc.write_text(
        json.dumps({"results": [{"active_ingredients": [{"name": "Amoxicillin trihydrate"}]}]}),
        encoding="utf-8",
    )
    return tmp_path


def test_report_reads_sources_without_modifying_them_and_writes_bom(root: Path) -> None:
    from app.kb.coverage.storage import report

    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    summary = report(root)
    assert summary.so_hoat_chat == 3
    output = root / "data/kb_reports/do_phu_da_nguon.csv"
    assert output.read_bytes().startswith(b"\xef\xbb\xbf")
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["co_livertox"] == ""
    assert rows[0]["co_ndc"] == "True"
    assert rows[0]["ddinter_da_cao_du"] == "True"
    assert rows[1]["ddinter_da_cao_du"] == "False"
    assert json.loads((output.with_suffix(".json")).read_text(encoding="utf-8")) == (
        summary.model_dump(mode="json")
    )
    assert all(path.read_bytes() == content for path, content in before.items())


def test_local_ndc_cache_and_present_optional_catalog(root: Path) -> None:
    from app.kb.coverage.report import calculate_coverage
    from app.kb.coverage.storage import load_sources

    ndc = root / "data/kb_sources/openfda_ndc/unrelated_filename.json"
    ndc.write_text(
        json.dumps({"san_pham": [{"ham_luong": [{"hoat_chat": "AMOXICILLIN TRIHYDRATE"}]}]}),
        encoding="utf-8",
    )
    catalog = root / "data/kb_sources/livertox/muc_luc.csv"
    catalog.parent.mkdir(parents=True)
    catalog.write_text("ten_inn,url\nAmoxicillin,local\n", encoding="utf-8-sig")
    rows, summary = calculate_coverage(load_sources(root))
    assert rows[0].co_ndc is True
    assert [row.co_livertox for row in rows] == [True, False, False]
    assert summary.trang_thai_nguon["livertox"] == "đã có nguồn"


def test_cli_accepts_required_sources(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from app.kb.coverage.__main__ import main

    assert main(["report", "--required-sources", "nhan_fda"], root=root) == 0
    assert json.loads(capsys.readouterr().out)["so_du_nguon_bat_buoc"] == 2


def test_publish_missing_secret_preserves_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.errors import ConfigError

    module = importlib.import_module("app.kb.dictionary.publish")
    monkeypatch.setattr(module, "_snapshot", lambda root: ("T52-test", {}))

    def missing(name: str) -> str:
        raise ConfigError(name)

    monkeypatch.setattr(module, "get_secret", missing, raising=False)
    monkeypatch.setenv("DATABASE_URL", "do-not-connect")

    def unexpected_connection(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Không được kết nối DB khi thiếu bí mật")

    monkeypatch.setattr(module.psycopg, "connect", unexpected_connection)
    with pytest.raises(ValueError, match="Thieu bien moi truong DATABASE_URL"):
        module.publish(Path("unused"), yes=True)
