"""Kiểm thử nối CaseService theo cờ ask.engine (co_dinh / agentic) và truyền vai_tro."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from app import container as container_mod
from app.agent.asker import AgenticAsker
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.api import schemas as s
from app.api.service import CaseService
from app.auth.principal import Principal
from app.config.settings import AskSettings, load_settings
from app.core.errors import ConfigError
from app.domain.models import CaBenh
from app.llm import setup as llm_setup
from app.orchestration.ai_review import AiRunResult
from app.orchestration.ask import AskResult, CaseAsker
from app.pipeline import KetQuaThamDinh
from app.providers.fakes import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "config/prompts/tac_tu.v1.md"


class _SpyAgenticAsker(AgenticAsker):
    def __init__(self) -> None:
        settings = load_settings("test")
        super().__init__(
            llm=FakeLLM([]),
            danh_muc=DanhMucCongCu(),
            chinh_sach=ChinhSachCongCu.tu_tep(ROOT / "config/tool_policy.yaml"),
            global_asker=None,
            prompt_path=PROMPT_PATH,
            case_settings=settings.case_context,
            max_turns=2,
        )
        self.seen_roles: list[tuple[str, str]] = []

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
        vai_tro: str = "duoc_si_ls",
    ) -> AskResult:
        del ca, cau_hoi, lich_su, ket_qua, ai_result, nhan_dinh_id
        self.seen_roles.append(("ca", vai_tro))
        return AskResult(trang_thai="ok", noi_dung="Trả lời ca.")

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        vai_tro: str = "duoc_si_ls",
    ) -> AskResult:
        del cases, results, cau_hoi, lich_su
        self.seen_roles.append(("chung", vai_tro))
        return AskResult(trang_thai="ok", noi_dung="Trả lời chung.")


@pytest.fixture
def ai_bat_voi_llm_gia(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bật AI với LLM giả để test không phụ thuộc khoá DeepSeek hay CDSS_AI của môi trường."""
    monkeypatch.setenv("CDSS_AI", "on")
    monkeypatch.setattr(llm_setup, "build_llm", lambda container: FakeLLM([]))


class _LegacyFakeAsker:
    """Bộ hỏi giả theo chữ ký cũ không nhận vai_tro."""

    def __init__(self) -> None:
        self.calls = 0

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult:
        del ca, cau_hoi, lich_su, ket_qua, ai_result, nhan_dinh_id
        self.calls += 1
        return AskResult(trang_thai="ok", noi_dung="Bộ hỏi cũ.")


@pytest.mark.luong_cu_cung
def test_default_co_dinh_uses_case_asker(
    ai_bat_voi_llm_gia: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CDSS_PROFILE", "test")
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
    )
    try:
        assert isinstance(service._asker_impl, CaseAsker)
    finally:
        service.shutdown()


def test_injected_legacy_asker_keeps_old_signature(tmp_path: Path) -> None:
    legacy = _LegacyFakeAsker()
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
        ai_runner=object(),  # type: ignore[arg-type]
        asker=legacy,
    )
    try:
        principal = Principal(nguoi_dung_id="u-1", email="u1@example.test", vai_tro="duoc_si_ls")
        reply = service.ask("DEMO-02", s.GuiCauHoi(cau_hoi="Vì sao?"), principal)
        assert reply.trang_thai == "ok"
        assert reply.minh_hoa == []
        assert legacy.calls == 1
    finally:
        service.shutdown()


def test_agentic_engine_uses_agentic_asker_and_passes_principal_role(
    ai_bat_voi_llm_gia: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_settings = load_settings("test")
    agentic_settings = base_settings.model_copy(
        update={"ask": AskSettings(engine="agentic", tool_policy="config/tool_policy.yaml")}
    )

    def fake_build_container(profile: str | None = None) -> container_mod.Container:
        del profile
        return container_mod.Container(agentic_settings)

    monkeypatch.setattr(container_mod, "build_container", fake_build_container)
    monkeypatch.setenv("CDSS_LUONG_CU_CUNG", "0")

    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
    )
    try:
        assert isinstance(service._asker_impl, AgenticAsker)
    finally:
        service.shutdown()

    spy_asker = _SpyAgenticAsker()
    spy_service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi_spy.jsonl",
        ai_runner=object(),  # type: ignore[arg-type]
        asker=spy_asker,
    )
    try:
        admin = Principal(nguoi_dung_id="u-admin", email="admin@example.test", vai_tro="admin")
        pharm = Principal(nguoi_dung_id="u-ds", email="ds@example.test", vai_tro="duoc_si_ls")
        res_ca = spy_service.ask("DEMO-02", s.GuiCauHoi(cau_hoi="Creatinin?"), admin)
        res_global = spy_service.ask("__global__", s.GuiCauHoi(cau_hoi="Tổng quan?"), pharm)
        assert res_ca.trang_thai == "ok"
        assert res_global.trang_thai == "ok"
        assert spy_asker.seen_roles == [("ca", "admin"), ("chung", "duoc_si_ls")]
    finally:
        spy_service.shutdown()


def test_co_dinh_with_disabled_luong_cu_cung_raises_config_error(
    ai_bat_voi_llm_gia: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CDSS_PROFILE", "test")
    monkeypatch.setenv("CDSS_LUONG_CU_CUNG", "0")
    with pytest.raises(ConfigError, match="ask.engine=co_dinh"):
        CaseService(
            ROOT / "data/mock/demo",
            ROOT / "data/kb/quy_tac_lieu_than.json",
            tmp_path / "phan_hoi.jsonl",
        )


def test_production_config_defaults_to_co_dinh_engine() -> None:
    """Demo chạy luồng cũ ổn định (CaseAsker); agent chỉ bật bằng cờ ask.engine=agentic."""
    assert load_settings("dev").ask.engine == "co_dinh"
    assert load_settings("test").ask.engine == "co_dinh"


def test_agentic_flag_still_builds_agentic_asker(
    ai_bat_voi_llm_gia: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agentic_settings = load_settings("dev").model_copy(
        update={"ask": AskSettings(engine="agentic", tool_policy="config/tool_policy.yaml")}
    )
    monkeypatch.setattr(
        container_mod,
        "build_container",
        lambda profile=None: container_mod.Container(agentic_settings),
    )
    monkeypatch.setenv("CDSS_LUONG_CU_CUNG", "0")
    service = CaseService(
        ROOT / "data/mock/demo",
        ROOT / "data/kb/quy_tac_lieu_than.json",
        tmp_path / "phan_hoi.jsonl",
    )
    try:
        assert isinstance(service._asker_impl, AgenticAsker)
    finally:
        service.shutdown()
