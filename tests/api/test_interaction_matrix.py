"""Kiểm hợp đồng ma trận và nối mã nhận định từ kết quả thực tế."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.api.presenter import finding_id, present_case
from app.config.settings import load_settings
from app.container import Container
from app.kb.interactions import InteractionStore
from app.kb.interactions.models import MaTranTuongTac
from app.kb.resolver import DrugResolver
from app.pipeline import run_case
from app.rules import load_renal_rules
from app.rules.engine import run_rules
from app.rules.interaction import build_interaction_matrix
from app.rules.registry import RuleContext, default_rules, run_registered
from tests.rules.test_interaction import create_dependencies, make_case


@pytest.fixture
def dependencies(tmp_path: Path) -> tuple[DrugResolver, InteractionStore]:
    return create_dependencies(tmp_path)


def test_matrix_links_to_presented_findings_without_mutating_inputs(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["alpha", "beta"])
    renal = load_renal_rules(Path("data/kb/quy_tac_lieu_than.json"))
    result = run_case(ca, renal)
    result.phat_hien = run_registered(ca, RuleContext(renal, resolver, store), default_rules())
    matrix = build_interaction_matrix(ca, resolver, store)
    before = (ca.model_dump_json(), result.model_dump_json(), matrix.model_dump_json())
    detail = present_case(ca, result, [], ma_tran_tuong_tac=matrix)
    assert detail.ma_tran_tuong_tac is not None
    pair = detail.ma_tran_tuong_tac.cap[0]
    finding = next(row for row in detail.nhan_dinh.can_chu_y if row.yeu_to.startswith("4."))
    assert pair.nhan_dinh_id == finding.nhan_dinh_id == "tuong_tac_thuoc|P0,P1"
    assert pair.nhan_dinh_id == finding_id(next(row for row in result.phat_hien if row.yeu_to == 4))
    assert (
        detail.ma_tran_tuong_tac.thuoc[0].ten == detail.chi_tiet.y_lenh.cho_duyet.dong[0]["Thuốc"]
    )
    assert detail.ma_tran_tuong_tac.nguon == "DDInter 2.0 (sàng lọc, CC BY-NC-SA 4.0)"
    assert detail.nhan_dinh.so_luat_da_chay == 6
    assert before == (ca.model_dump_json(), result.model_dump_json(), matrix.model_dump_json())
    assert (
        MaTranTuongTac.model_validate(detail.model_dump()["ma_tran_tuong_tac"])
        == detail.ma_tran_tuong_tac
    )


def test_matrix_is_null_without_running_factor_four(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["alpha", "beta"])
    result = run_case(ca, load_renal_rules(Path("data/kb/quy_tac_lieu_than.json")))
    detail = present_case(ca, result, [])
    assert detail.ma_tran_tuong_tac is None
    assert detail.nhan_dinh.so_luat_da_chay == 5
    assert "4. Tương tác thuốc" in detail.nhan_dinh.yeu_to_chua_kiem


def test_absent_dependency_keeps_other_registered_rules(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["alpha", "beta"])
    renal = load_renal_rules(Path("data/kb/quy_tac_lieu_than.json"))
    findings = run_registered(ca, RuleContext(renal), default_rules())
    assert findings == run_rules(ca, renal)


def test_damaged_index_does_not_stop_other_rules(tmp_path: Path) -> None:
    index = tmp_path / "damaged.sqlite"
    with closing(sqlite3.connect(index)) as db:
        db.executescript(
            "CREATE TABLE cap(ddinter_id_a, ddinter_id_b); INSERT INTO cap VALUES ('A','B');"
        )
    settings = load_settings("test")
    settings = settings.model_copy(
        update={
            "app": settings.app.model_copy(
                update={
                    "tra_cuu": str(tmp_path / "absent.sqlite"),
                    "tuong_tac": str(index),
                }
            )
        }
    )
    container = Container(settings)
    assert container.rule_context.interactions is None
    assert container.rule_context.resolver is None
    assert run_registered(make_case(["alpha", "beta"]), container.rule_context, container.rules)
