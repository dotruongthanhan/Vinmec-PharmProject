"""Kiểm phụ thuộc chỉ mục dùng chung cả khi nhiều luồng thẩm định."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app import container as container_mod
from app.config.settings import load_settings
from app.container import Container
from app.kb.interactions import InteractionStore
from app.kb.interactions.build import INDEX_PATH
from app.kb.resolver import DrugResolver
from app.pipeline import run_case
from tests.rules.test_interaction import create_dependencies, make_case


def test_shared_context_loads_indices_once_across_threads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_dependencies(tmp_path)
    settings = load_settings("test")
    settings = settings.model_copy(
        update={
            "app": settings.app.model_copy(
                update={
                    "tra_cuu": str(tmp_path / "resolver.sqlite"),
                    "tuong_tac": str(tmp_path / INDEX_PATH),
                }
            )
        }
    )
    container = Container(settings)
    monkeypatch.setattr(container_mod, "_SHARED_RULE_CONTEXT", None)
    monkeypatch.setattr(container_mod, "build_container", lambda: container)
    loads: list[str] = []
    resolver_load = DrugResolver.from_index
    store_load = InteractionStore.from_path

    def load_resolver(path: Path) -> DrugResolver:
        loads.append("resolver")
        return resolver_load(path)

    def load_store(path: Path) -> InteractionStore:
        loads.append("store")
        return store_load(path)

    monkeypatch.setattr(DrugResolver, "from_index", load_resolver)
    monkeypatch.setattr(InteractionStore, "from_path", load_store)
    with ThreadPoolExecutor(max_workers=4) as pool:
        contexts = list(pool.map(lambda _: container_mod.get_rule_context(), range(8)))
    assert loads == ["resolver", "store"]
    assert all(context is contexts[0] for context in contexts)
    for context in contexts:
        result = run_case(
            make_case(["alpha", "beta"]),
            context.renal_rules,
            resolver=context.resolver,
            interactions=context.interactions,
        )
        assert result.ma_tran_tuong_tac is not None
        assert result.ma_tran_tuong_tac.cap[0].muc == "nghiem_trong"
    assert loads == ["resolver", "store"]
