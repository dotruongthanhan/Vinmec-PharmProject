"""Đọc và đánh giá chính sách phân quyền công cụ từ tệp YAML (mặc định từ chối)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.tools.base import CheDo
from app.agent.tools.registry import DanhMucCongCu
from app.config.settings import luong_cu_cung_tat_qua_env
from app.core.errors import ConfigError

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_POLICY_PATH = _ROOT / "config/tool_policy.yaml"


class _CongCuPolicy(BaseModel):
    """Trạng thái bật/tắt khai báo riêng cho một công cụ."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bat: bool = True


class _VaiTroPolicy(BaseModel):
    """Danh sách công cụ được phép gọi theo vai trò."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cho_phep: list[str] = Field(default_factory=list)


class _CheDoPolicy(BaseModel):
    """Danh sách công cụ bị cấm trong một chế độ chạy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cam: list[str] = Field(default_factory=list)


class ChinhSachCongCu(BaseModel):
    """Chính sách phân quyền công cụ đọc từ YAML theo nguyên tắc mặc định từ chối."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mac_dinh: Literal["tu_choi"] = "tu_choi"
    cong_cu: dict[str, _CongCuPolicy] = Field(default_factory=dict)
    vai_tro: dict[str, _VaiTroPolicy] = Field(default_factory=dict)
    che_do: dict[CheDo, _CheDoPolicy] = Field(default_factory=dict)

    @classmethod
    def tu_tep(cls, path: Path | None = None) -> ChinhSachCongCu:
        """Nạp chính sách từ tệp YAML; sai cấu trúc hoặc khoá lạ báo ConfigError."""
        target = Path(path) if path is not None else _DEFAULT_POLICY_PATH
        try:
            raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ConfigError(f"Không đọc được chính sách công cụ {target.name}") from exc
        if not isinstance(raw, dict):
            raise ConfigError(f"{target.name}: gốc YAML phải là ánh xạ")
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            errors = [
                f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}"
                for err in exc.errors(include_input=False, include_context=False)
            ]
            raise ConfigError("; ".join(errors)) from exc

    def cong_cu_bat(self, ten: str) -> bool:
        """Kiểm tra công cụ có đang bật không (ưu tiên CDSS_LUONG_CU_CUNG cho luong_cu_cung)."""
        if ten == "luong_cu_cung" and luong_cu_cung_tat_qua_env():
            return False
        entry = self.cong_cu.get(ten)
        return entry.bat if entry is not None else True

    def cho_phep(self, vai_tro: str, che_do: str, ten: str) -> bool:
        """Cho phép khi công cụ bật, vai trò có trong cho_phep và không bị cấm ở chế độ."""
        if not self.cong_cu_bat(ten):
            return False
        role_policy = self.vai_tro.get(vai_tro)
        if role_policy is None or ten not in role_policy.cho_phep:
            return False
        mode_policy = self.che_do.get(che_do)  # type: ignore[arg-type]
        if mode_policy is not None and ten in mode_policy.cam:
            return False
        return True

    def cac_cong_cu_duoc_phep(
        self,
        vai_tro: str,
        che_do: str,
        danh_muc: DanhMucCongCu,
    ) -> list[str]:
        """Trả tên các công cụ vừa đã đăng ký vừa được phép, giữ thứ tự đăng ký."""
        allowed: list[str] = []
        for ten in danh_muc.ten_da_dang_ky():
            tool = danh_muc.lay(ten)
            if (
                tool is not None
                and che_do in tool.che_do_cho_phep
                and self.cho_phep(vai_tro, che_do, ten)
            ):
                allowed.append(ten)
        return allowed


def luong_cu_cung_dang_bat(path: Path | None = None) -> bool:
    """Kiểm tra công cụ luong_cu_cung có đang bật không; thiếu hoặc lỗi tệp trả True."""
    try:
        policy = ChinhSachCongCu.tu_tep(path)
    except ConfigError:
        return True
    return policy.cong_cu_bat("luong_cu_cung")
