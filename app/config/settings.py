"""Cấu hình bất biến, trộn sâu theo hồ sơ và đọc bí mật tập trung."""

import os
from copy import deepcopy
from pathlib import Path
from typing import Literal, Self

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.errors import ConfigError

_ROOT = Path(__file__).resolve().parents[2]


class AuthSettings(BaseModel):
    """Đọc cấu hình xác thực từ môi trường, không tự nạp .env."""

    model_config = ConfigDict(frozen=True)

    auth_mode: Literal["required", "off"] = "required"
    supabase_url: str = ""
    supabase_anon_key: str = Field(default="", repr=False)
    supabase_jwt_secret: str = Field(default="", repr=False)
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")


def load_auth_settings() -> AuthSettings:
    """Giá trị chế độ lạ luôn yêu cầu xác thực."""
    origins = os.getenv("CORS_ORIGINS")
    values = (
        {}
        if origins is None
        else {
            "cors_origins": tuple(origin.strip() for origin in origins.split(",") if origin.strip())
        }
    )
    return AuthSettings(
        auth_mode="off" if os.getenv("AUTH_MODE") == "off" else "required",
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
        **values,
    )


class ChunkingSettings(BaseModel):
    """Kích thước cắt đoạn."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    target_chars: int = Field(gt=0)
    max_chars: int = Field(gt=0)
    min_chars: int = Field(gt=0)
    overlap_sentences: int = Field(gt=0)
    parent_max_chars: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_sizes(self) -> Self:
        """Kiểm tra thứ tự kích thước."""
        if not self.min_chars < self.target_chars <= self.max_chars:
            raise ValueError("min_chars < target_chars <= max_chars")
        return self


class CollectionRetrieval(BaseModel):
    """Số kết quả truy xuất và xếp hạng lại của một nhóm nguồn."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    k_query: int = Field(gt=0)
    k_rerank: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Không xếp hạng lại nhiều hơn số đã truy xuất."""
        if self.k_rerank > self.k_query:
            raise ValueError("k_rerank <= k_query")
        return self


class RetrievalSettings(BaseModel):
    """Tham số truy xuất các nhóm nguồn."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    nhan_thuoc: CollectionRetrieval
    van_ban_byt: CollectionRetrieval
    rrf_k: int = Field(gt=0)
    rerank_min_score: float
    expand_parent: bool
    query_languages: list[str]


class EvidenceSettings(BaseModel):
    """Giới hạn gói căn cứ."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_chars: int = Field(gt=0)


class CaseContextSettings(BaseModel):
    """Giới hạn ngữ cảnh ca bệnh."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_chars: int = Field(gt=0)
    notes_latest_n: int = Field(gt=0)


class GenerationSettings(BaseModel):
    """Tham số sinh nhận định."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    temperature: float = Field(ge=0, le=2)
    max_tokens: int = Field(gt=0)
    top_p: float
    stream: bool


class AgentSettings(BaseModel):
    """Giới hạn số lượt và số lần thử."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    max_turns: int = Field(gt=0)
    max_attempts: int = Field(gt=0)
    max_synthesis_attempts: int = Field(gt=0)


class LLMSettings(BaseModel):
    """Tên nhà cung cấp và mô hình ngôn ngữ."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: str
    model: str
    max_tokens: int = Field(gt=0)
    max_tokens_retry: int = Field(gt=0)
    reasoning: dict[str, str] | None = None


class EmbeddingSettings(BaseModel):
    """Tham số nhúng và bộ đệm."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: str
    active: str
    dimensions: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    cache_path: str


class RerankSettings(BaseModel):
    """Tên nhà cung cấp và mô hình xếp hạng lại."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: str
    active: str


class DatabaseSettings(BaseModel):
    """Tên biến môi trường chứa chuỗi kết nối."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    url_env: str


class VectorStoreSettings(BaseModel):
    """Tên nhà cung cấp kho véc-tơ."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: str


class PromptSettings(BaseModel):
    """Đường dẫn các prompt có phiên bản."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tong_hop: str
    hoi_them: str


class AppSettings(BaseModel):
    """Thư mục ca và tên hồ sơ chạy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_dir: str
    profile: str


class Settings(BaseModel):
    """Toàn bộ cấu hình công khai, không chứa bí mật."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    app: AppSettings
    chunking: ChunkingSettings
    retrieval: RetrievalSettings
    evidence: EvidenceSettings
    case_context: CaseContextSettings
    generation: GenerationSettings
    agent: AgentSettings
    llm: LLMSettings
    embedding: EmbeddingSettings
    rerank: RerankSettings
    database: DatabaseSettings
    vector_store: VectorStoreSettings
    prompts: PromptSettings


def _read_yaml(path: Path) -> dict:
    """Đọc một ánh xạ YAML, chuyển lỗi về lỗi cấu hình."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"Không đọc được cấu hình {path.name}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path.name}: gốc YAML phải là ánh xạ")
    return raw


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Trộn ánh xạ lồng nhau, thay thế các giá trị còn lại."""
    result = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_settings(profile: str | None = None, config_dir: Path | None = None) -> Settings:
    """Nạp cấu hình gốc rồi ghi đè theo hồ sơ được chọn."""
    selected = profile if profile is not None else os.getenv("CDSS_PROFILE", "dev")
    folder = Path(config_dir) if config_dir is not None else _ROOT / "config"
    raw = _read_yaml(folder / "settings.yaml")
    overlay = folder / f"settings.{selected}.yaml"
    if overlay.is_file():
        raw = _deep_merge(raw, _read_yaml(overlay))
    try:
        return Settings.model_validate(raw)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_context=False)
        ]
        raise ConfigError("; ".join(errors)) from exc


def get_secret(name: str) -> str:
    """Đọc bí mật, không ghi đè môi trường và không đưa giá trị vào lỗi."""
    load_dotenv(dotenv_path=_ROOT / ".env", override=False)
    value = os.getenv(name)
    if not value:
        raise ConfigError(name)
    return value
