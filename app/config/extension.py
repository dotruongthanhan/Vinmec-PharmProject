"""Đọc cấu hình công khai và biến môi trường cho dịch vụ Chrome Extension độc lập."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.errors import ConfigError

_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_EXTENSION_CONFIG = _ROOT / "config" / "extension.yaml"
_DEFAULT_CHROME_EXT_REGEX = r"^chrome-extension://[a-p]{32}$"


class ExtensionServerSettings(BaseModel):
    """Tham số HTTP và quản lý phiên RAM tạm thời."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    port: int = Field(ge=1024, le=65535)
    max_json_body_bytes: int = Field(ge=1024, le=4_194_304)
    max_multipart_body_bytes: int = Field(ge=65536, le=16_777_216)
    session_ttl_seconds: int = Field(ge=60, le=86400)
    max_sessions: int = Field(ge=10, le=2000)


class GeminiStageModelSettings(BaseModel):
    """Cấu hình một mô hình Gemini theo từng bước trích xuất."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: Literal["gemini"]
    model: str = Field(min_length=1, max_length=120)
    temperature: float = Field(ge=0.0, le=2.0)
    max_tokens: int = Field(ge=256, le=16384)
    timeout_seconds: float = Field(gt=1.0, le=120.0)
    max_attempts: int = Field(ge=1, le=5)


class DeepReviewModelSettings(BaseModel):
    """Cấu hình mô hình thẩm định sâu giai đoạn 3."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: Literal["deepseek"]
    model: str = Field(min_length=1, max_length=120)


class ExtensionModelsSettings(BaseModel):
    """Định tuyến mô hình cho từng bước phân tích của Extension."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_classifier: GeminiStageModelSettings
    oh_vision: GeminiStageModelSettings
    emr_extract: GeminiStageModelSettings
    deep_review: DeepReviewModelSettings


class ExtensionPromptSettings(BaseModel):
    """Đường dẫn các tệp prompt có phiên bản của Extension."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    ext_schema: str = Field(min_length=1, max_length=240)
    ext_oh_vision: str = Field(min_length=1, max_length=240)
    ext_emr_extract: str = Field(min_length=1, max_length=240)


class ExtensionLimitsSettings(BaseModel):
    """Giới hạn kích thước đầu vào để chống lạm dụng tài nguyên."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_extract_workers: int = Field(ge=1, le=8)
    max_emr_sections: int = Field(ge=1, le=200)
    max_emr_chars: int = Field(ge=1000, le=500_000)
    max_schema_fields: int = Field(ge=1, le=300)
    max_oh_image_bytes: int = Field(ge=65536, le=16_777_216)
    max_ask_history_turns: int = Field(ge=1, le=20)


class ExtensionSettings(BaseModel):
    """Toàn bộ cấu hình công khai cho Extension API độc lập."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    server: ExtensionServerSettings
    models: ExtensionModelsSettings
    prompts: ExtensionPromptSettings
    limits: ExtensionLimitsSettings


def load_extension_settings(config_path: Path | None = None) -> ExtensionSettings:
    """Nạp và kiểm chứng `config/extension.yaml`."""
    path = Path(config_path) if config_path is not None else _DEFAULT_EXTENSION_CONFIG
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Không đọc được cấu hình {path.name}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path.name}: gốc YAML phải là ánh xạ")
    try:
        return ExtensionSettings.model_validate(raw)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_context=False)
        ]
        raise ConfigError("; ".join(errors)) from exc


def load_extension_cors_origins() -> list[str]:
    """Đọc danh sách nguồn CORS tường minh từ `EXTENSION_CORS_ORIGINS` (không dùng `*`)."""
    raw = os.getenv("EXTENSION_CORS_ORIGINS", "")
    origins: list[str] = []
    for item in raw.split(","):
        cleaned = item.strip().rstrip("/")
        if not cleaned or cleaned == "*":
            continue
        origins.append(cleaned)
    return origins


def load_extension_cors_regex() -> str | None:
    """Biểu thức khớp nguồn `chrome-extension://<id>` mặc định cho bản Side Panel."""
    raw = os.getenv("EXTENSION_CORS_ORIGIN_REGEX", _DEFAULT_CHROME_EXT_REGEX).strip()
    return raw or None
