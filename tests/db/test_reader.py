"""Đối chiếu 66 ca qua ánh xạ thật, không mở PostgreSQL trong test."""

import copy
import re
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock, Mock

import psycopg
import pytest

from app.core.errors import ConfigError
from app.db import reader
from app.db.mapping import TABLES
from app.db.sources import Batch, prepare_cases
from app.pipeline import run_case
from app.rules import load_renal_rules

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "data/kb/quy_tac_lieu_than.json"
CASE_IDS = [f"DEMO-{i:02}" for i in range(1, 7)] + [f"HS-{i:03}" for i in range(1, 61)]


@pytest.fixture(scope="module")
def batch() -> Batch:
    result = prepare_cases(ROOT)
    assert not result.rejected
    return result


@pytest.fixture(scope="module")
def comparisons(batch: Batch) -> tuple[dict, dict]:
    cases, errors = reader.build_cases(batch.rows)
    assert not errors
    assert [case.ca_id for case in cases] == CASE_IDS
    return {
        case.ca_id: reader.comparison_dump(case) for case in cases
    }, reader.expected_source_dumps(ROOT)


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_round_trip_each_source_case(case_id: str, comparisons: tuple[dict, dict]) -> None:
    actual, expected = comparisons
    assert actual[case_id] == expected[case_id]


def test_fixed_catalog_normalizations(comparisons: tuple[dict, dict]) -> None:
    actual, expected = comparisons
    raw = {case.ca_id: reader.comparison_dump(case) for case in reader.load_source_cases(ROOT)}
    changes = Counter(
        key
        for case_id in CASE_IDS
        for key in raw[case_id]
        if raw[case_id][key] != expected[case_id][key]
    )
    assert changes == {"danh_muc_hoat_chat": 65, "danh_muc_thuoc": 12}
    assert (
        sum(
            len(raw[key]["danh_muc_thuoc"]) - len(expected[key]["danh_muc_thuoc"])
            for key in CASE_IDS
        )
        == 15
    )
    # Khóa rõ metadata KB đã thay thế metadata tệp khi nạp T40.
    ingredient = next(
        row
        for row in actual["DEMO-01"]["danh_muc_hoat_chat"]
        if row["hoat_chat_id"] == "amlodipine"
    )
    assert ingredient == {
        "hoat_chat_id": "amlodipine",
        "ten_hoat_chat": "amlodipin",
        "ten_quoc_te": "amlodipine",
        "ma_atc": None,
        "nhom_duoc_ly": "chen_kenh_canxi",
    }


def test_only_focus_encounter_and_other_active_lines(batch: Batch) -> None:
    cases, errors = reader.build_cases(batch.rows)
    assert not errors
    sources = {case.ca_id: case for case in reader.load_source_cases(ROOT)}
    for case in cases:
        source = sources[case.ca_id]
        assert case.dot_dieu_tri == source.dot_dieu_tri
        assert case.mo_ta_ngan == source.mo_ta_ngan
        assert {row.chi_tiet_y_lenh_id for row in case.thuoc_dang_dung} == {
            row.chi_tiet_y_lenh_id for row in source.thuoc_dang_dung
        }
        assert all(row.trang_thai_dong == "active" for row in case.thuoc_dang_dung)
        assert not {row.chi_tiet_y_lenh_id for row in case.thuoc_dang_dung} & {
            row.chi_tiet_y_lenh_id for row in case.y_lenh_cho_duyet.chi_tiet
        }


def test_build_is_pure_and_order_independent(batch: Batch) -> None:
    before = copy.deepcopy(batch.rows)
    cases, errors = reader.build_cases(batch.rows)
    assert batch.rows == before
    shuffled = {table: list(reversed(rows)) for table, rows in before.items()}
    reordered, other_errors = reader.build_cases(shuffled)
    assert errors == other_errors == []
    assert [reader.comparison_dump(case) for case in cases] == [
        reader.comparison_dump(case) for case in reordered
    ]


@pytest.mark.parametrize("missing", ["nguoi_benh", "thuoc", "hoat_chat", "dot_dieu_tri"])
def test_missing_reference_isolated_with_field_name(batch: Batch, missing: str) -> None:
    rows = copy.deepcopy(batch.rows)
    table = f"{'tri_thuc' if missing == 'hoat_chat' else 'nghiep_vu'}.{missing}"
    rows[table].pop(0)
    cases, errors = reader.build_cases(rows)
    assert cases and errors
    assert len(cases) + len(errors) == 66
    assert all(missing in error for _, error in errors)


def test_bad_clinical_value_isolated_without_echoing_input(batch: Batch) -> None:
    rows = copy.deepcopy(batch.rows)
    rows["nghiep_vu.sinh_hieu"][0]["gia_tri"] = "KHONG_DUOC_LO_DU_LIEU"
    cases, errors = reader.build_cases(rows)
    assert len(cases) == 65 and len(errors) == 1
    assert "gia_tri" in errors[0][1]
    assert "KHONG_DUOC_LO_DU_LIEU" not in str(errors)


def test_no_clinical_default_or_rounding(batch: Batch) -> None:
    rows = copy.deepcopy(batch.rows)
    row = rows["nghiep_vu.chi_tiet_y_lenh"][0]
    row["lieu_moi_lan"] = 1.123456789
    row["so_lan_moi_ngay"] = None
    cases, errors = reader.build_cases(rows)
    assert not errors
    line = next(
        line
        for case in cases
        for line in case.y_lenh_cho_duyet.chi_tiet
        if line.chi_tiet_y_lenh_id == row["chi_tiet_y_lenh_id"]
    )
    assert line.lieu_moi_lan == 1.123456789
    assert line.so_lan_moi_ngay is None


def test_focus_active_line_never_becomes_background(batch: Batch) -> None:
    rows = copy.deepcopy(batch.rows)
    focus = next(row for row in rows["nghiep_vu.y_lenh"] if row.get("ca_id"))
    line = next(
        row for row in rows["nghiep_vu.chi_tiet_y_lenh"] if row["y_lenh_id"] == focus["y_lenh_id"]
    )
    line["trang_thai_dong"] = "active"
    rows["nghiep_vu.chi_tiet_y_lenh"].append(
        {
            **line,
            "chi_tiet_y_lenh_id": "CT-GIA-LAP-NEN",
            "y_lenh_id": "YL-GIA-LAP-NEN",
        }
    )
    cases, errors = reader.build_cases(rows)
    assert not errors
    case = next(case for case in cases if case.ca_id == focus["ca_id"])
    assert [line.chi_tiet_y_lenh_id for line in case.thuoc_dang_dung] == ["CT-GIA-LAP-NEN"]


def test_read_queries_are_batched_and_read_only(
    batch: Batch, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    statements = []
    focuses = {row["dot_dieu_tri_id"] for row in batch.rows["nghiep_vu.y_lenh"] if row.get("ca_id")}

    def execute(query: object, params: tuple | None = None) -> Mock:
        statement = query if isinstance(query, str) else query.as_string()
        statements.append(statement)
        assert statement.startswith("SELECT ")
        table_match = re.search(r'FROM ([a-z_]+\.[a-z_]+|"[a-z_]+"\."[a-z_]+")', statement)
        assert table_match is not None
        table = table_match[1].replace('"', "")
        rows = batch.rows[table]
        if params is None:
            rows = [row for row in rows if row["dot_dieu_tri_id"] in focuses]
        else:
            column = re.search(r'WHERE "([a-z_]+)"', statement)[1]
            rows = [row for row in rows if row[column] in params[0]]
        return Mock(fetchall=Mock(return_value=rows))

    connection.execute.side_effect = execute
    connect = Mock(return_value=connection)
    secret = Mock(return_value="chaine-factice")
    monkeypatch.setattr(reader.psycopg, "connect", connect)
    monkeypatch.setattr(reader, "get_secret", secret)
    rows = reader.read_case_rows()
    secret.assert_called_once_with("DATABASE_URL")
    assert connect.call_args.kwargs["options"] == "-c default_transaction_read_only=on"
    assert connection.read_only is True
    assert connection.isolation_level == psycopg.IsolationLevel.REPEATABLE_READ
    assert len(statements) == len(rows) == 15
    assert len(reader.build_cases(rows)[0]) == 66
    for table in rows:
        assert table in TABLES
    connection.__exit__.assert_called_once()


@pytest.mark.parametrize("failure", [ConfigError("DATABASE_URL"), "", "   "])
def test_missing_url_does_not_connect(failure: object, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = (
        Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    )
    connect = Mock()
    monkeypatch.setattr(reader, "get_secret", secret)
    monkeypatch.setattr(reader.psycopg, "connect", connect)
    with pytest.raises(reader.DatabaseReadError, match="Chưa cấu hình DATABASE_URL"):
        reader.read_case_rows()
    connect.assert_not_called()


def test_connection_error_never_echoes_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    marker = "SECRET_CONNEXION_FACTICE"
    monkeypatch.setattr(reader, "get_secret", Mock(return_value=marker))
    monkeypatch.setattr(
        reader.psycopg, "connect", Mock(side_effect=psycopg.OperationalError(marker))
    )
    with pytest.raises(reader.DatabaseReadError) as error:
        reader.read_case_rows()
    assert marker not in str(error.value)
    assert error.value.__suppress_context__


def test_query_error_closes_connection_and_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = MagicMock()
    connection.__enter__.return_value = connection
    marker = "SECRET_DONNEES_FACTICES"
    connection.execute.side_effect = psycopg.OperationalError(marker)
    monkeypatch.setattr(reader, "get_secret", Mock(return_value="connexion-factice"))
    monkeypatch.setattr(reader.psycopg, "connect", Mock(return_value=connection))
    with pytest.raises(reader.DatabaseReadError) as error:
        reader.read_case_rows()
    assert marker not in str(error.value)
    connection.__exit__.assert_called_once()


def test_cache_refresh_and_review(batch: Batch, monkeypatch: pytest.MonkeyPatch) -> None:
    query = Mock(return_value=batch.rows)
    monkeypatch.setattr(reader, "read_case_rows", query)
    service = reader.DbReviewService(RULES)
    cases, _ = service.list_cases()
    service.list_cases()
    query.assert_called_once()
    actual = service.review(cases[0]).model_dump(exclude={"thoi_gian_ms"})
    expected = run_case(cases[0], load_renal_rules(RULES)).model_dump(exclude={"thoi_gian_ms"})
    assert actual == expected
    service.refresh()
    assert service.list_cases()[0] == cases
    assert query.call_count == 2


@pytest.mark.parametrize("drift", [False, True])
def test_verify_reports_real_mismatches(
    batch: Batch, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, drift: bool
) -> None:
    rows = copy.deepcopy(batch.rows)
    if drift:
        rows["nghiep_vu.chi_tiet_y_lenh"][0]["lieu_moi_lan"] = 123.987654321
    monkeypatch.setattr(reader, "read_case_rows", Mock(return_value=rows))
    assert reader.verify_read(ROOT) == int(drift)
    output = capsys.readouterr().out
    assert ("Khớp 65/66" if drift else "Khớp 66/66") in output
    assert "123.987654321" not in output
