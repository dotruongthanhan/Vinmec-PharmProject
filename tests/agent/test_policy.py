"""Kiểm thử ChinhSachCongCu: đọc YAML, phân quyền mặc định từ chối và cờ môi trường."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict

from app.agent.tools.base import KetQuaCongCu, Tool, ToolContext
from app.agent.tools.policy import ChinhSachCongCu, luong_cu_cung_dang_bat
from app.agent.tools.registry import DanhMucCongCu
from app.core.errors import ConfigError

ROOT = Path(__file__).resolve().parents[2]


class _EmptyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _StubTool(Tool):
    ten: ClassVar[str] = "tool_stub"
    ten_hien_thi: ClassVar[str] = "Stub"
    mo_ta: ClassVar[str] = "Stub."
    LuocDoThamSo: ClassVar[type[BaseModel]] = _EmptyParams

    def __init__(self, name: str) -> None:
        self.ten = name  # type: ignore[misc]

    def chay(self, tham_so: BaseModel, ctx: ToolContext) -> KetQuaCongCu:
        del tham_so, ctx
        return KetQuaCongCu(trang_thai="ok")


def test_real_tool_policy_loads_and_allows_duoc_si_ls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CDSS_LUONG_CU_CUNG", raising=False)
    policy = ChinhSachCongCu.tu_tep()
    assert policy.cong_cu_bat("luong_cu_cung") is True
    assert policy.cho_phep("duoc_si_ls", "ca", "luong_cu_cung") is True
    assert policy.cho_phep("duoc_si_ls", "chung", "luong_cu_cung") is True
    assert policy.cho_phep("admin", "ca", "luong_cu_cung") is True

    registry = DanhMucCongCu()
    registry.dang_ky(_StubTool("luong_cu_cung"))
    registry.dang_ky(_StubTool("tool_chua_khai_bao"))
    assert policy.cac_cong_cu_duoc_phep("duoc_si_ls", "ca", registry) == ["luong_cu_cung"]


def test_unknown_role_is_denied() -> None:
    policy = ChinhSachCongCu.tu_tep()
    assert policy.cho_phep("vai_tro_la", "ca", "luong_cu_cung") is False
    assert policy.cho_phep("vai_tro_la", "chung", "luong_cu_cung") is False


def test_tool_banned_in_chung_mode_is_still_allowed_in_ca_mode(tmp_path: Path) -> None:
    policy_file = tmp_path / "tool_policy.yaml"
    policy_file.write_text(
        "\n".join(
            [
                "mac_dinh: tu_choi",
                "cong_cu:",
                "  tinh_chi_so:",
                "    bat: true",
                "vai_tro:",
                "  duoc_si_ls:",
                "    cho_phep: [tinh_chi_so]",
                "che_do:",
                "  chung:",
                "    cam: [tinh_chi_so]",
            ]
        ),
        encoding="utf-8",
    )
    policy = ChinhSachCongCu.tu_tep(policy_file)
    assert policy.cho_phep("duoc_si_ls", "ca", "tinh_chi_so") is True
    assert policy.cho_phep("duoc_si_ls", "chung", "tinh_chi_so") is False


def test_unknown_yaml_key_raises_config_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad_policy.yaml"
    bad_file.write_text(
        "\n".join(
            [
                "mac_dinh: tu_choi",
                "khoa_la: 123",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigError):
        ChinhSachCongCu.tu_tep(bad_file)


@pytest.mark.parametrize("raw_val", ["0", "false", "OFF", "khong"])
def test_env_disables_luong_cu_cung(monkeypatch: pytest.MonkeyPatch, raw_val: str) -> None:
    monkeypatch.setenv("CDSS_LUONG_CU_CUNG", raw_val)
    assert luong_cu_cung_dang_bat(ROOT / "config/tool_policy.yaml") is False


def test_missing_policy_file_defaults_to_true(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CDSS_LUONG_CU_CUNG", raising=False)
    assert luong_cu_cung_dang_bat(tmp_path / "khong_ton_tai.yaml") is True
