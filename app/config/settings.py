"""Cấu hình bất biến, trộn sâu theo hồ sơ và đọc bí mật tập trung."""

import io
import logging
import os
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Literal, Self, cast
from urllib.parse import parse_qs, unquote, urlsplit

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.errors import ConfigError

_ROOT = Path(__file__).resolve().parents[2]
_LOGGER = logging.getLogger(__name__)
_warned_missing_loader_url = False
_loader_warn_lock = Lock()
_LOCAL_DB_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_OWNER_DB_USERS = frozenset({"bvienx_admin", "postgres"})
_GENERIC_DB_URL_WARNING = "DATABASE_URL không hợp lệ; không phân tích được chuỗi kết nối DB."
DEFAULT_LLM_ASK_PER_5MIN = 20
DEFAULT_LLM_AI_PER_HOUR = 15
DEFAULT_LLM_DAILY_CALLS = 600


_LUONG_CU_CUNG_ENV = "CDSS_LUONG_CU_CUNG"
_ENV_FALSE_VALUES = frozenset({"0", "false", "off", "khong"})


def luong_cu_cung_tat_qua_env() -> bool:
    """Biến CDSS_LUONG_CU_CUNG đặt 0/false/off/khong thì tắt luồng cũ cứng (plan 1.9 mục 6.6)."""
    raw = os.getenv(_LUONG_CU_CUNG_ENV)
    return raw is not None and raw.strip().casefold() in _ENV_FALSE_VALUES


def _read_positive_int_env(name: str, default: int) -> int:
    """Đọc số nguyên dương từ biến môi trường; rỗng trả mặc định, sai ghi cảnh báo."""
    raw = os.getenv(name)
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    try:
        value = int(stripped)
    except ValueError:
        _LOGGER.warning("Giá trị %s không hợp lệ; dùng mặc định %d.", name, default)
        return default
    if value < 1:
        _LOGGER.warning("Giá trị %s phải >= 1; dùng mặc định %d.", name, default)
        return default
    return value


def load_llm_rate_limits() -> tuple[int, int, int]:
    """Đọc giới hạn tốc độ và ngân sách ngày gọi LLM từ biến môi trường."""
    return (
        _read_positive_int_env("LLM_ASK_PER_5MIN", DEFAULT_LLM_ASK_PER_5MIN),
        _read_positive_int_env("LLM_AI_PER_HOUR", DEFAULT_LLM_AI_PER_HOUR),
        _read_positive_int_env("LLM_DAILY_CALLS", DEFAULT_LLM_DAILY_CALLS),
    )


def load_case_source() -> Literal["db", "file"]:
    """Chọn nguồn ca; mặc định giữ bộ nạp tệp hiện có."""
    value = os.getenv("CASE_SOURCE", "file").strip().lower()
    if value not in ("db", "file"):
        raise ConfigError("CASE_SOURCE phải là db hoặc file")
    return value


def load_kb_source() -> Literal["auto", "file", "db"]:
    """Chọn nguồn kho tri thức; mặc định auto (tệp có dùng tệp, thiếu thì DB)."""
    value = os.getenv("KB_SOURCE", "auto").strip().lower()
    if value not in ("auto", "file", "db"):
        raise ConfigError("KB_SOURCE phải là auto, file hoặc db")
    return cast(Literal["auto", "file", "db"], value)


def load_case_cache_ttl() -> int:
    """Đọc TTL của bộ đệm ca DB, giới hạn từ 10 đến 600 giây."""
    try:
        value = int(os.getenv("CASE_CACHE_TTL_SECONDS", "60"))
    except ValueError:
        value = 60
    return max(10, min(600, value))


def load_access_log_enabled() -> bool:
    """Nhật ký mặc định bật, chỉ tắt khi ACCESS_LOG=off."""
    return os.getenv("ACCESS_LOG", "on") != "off"


class AuthSettings(BaseModel):
    """Đọc cấu hình xác thực từ môi trường, không tự nạp .env."""

    model_config = ConfigDict(frozen=True)

    auth_mode: Literal["required", "off"] = "required"
    auth_online_ttl: int = 60
    supabase_url: str = ""
    supabase_anon_key: str = Field(default="", repr=False)
    supabase_jwt_secret: str = Field(default="", repr=False)
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @field_validator("auth_online_ttl", mode="before")
    @classmethod
    def clamp_online_ttl(cls, value: object) -> int:
        """Giữ bộ đệm trong 10–300 giây, cấu hình lỗi dùng 60 giây."""
        try:
            parsed = int(str(value))
        except (TypeError, ValueError):
            parsed = 60
        return max(10, min(300, parsed))


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
        auth_online_ttl=os.getenv("AUTH_ONLINE_TTL", "60"),
        supabase_url=os.getenv("SUPABASE_URL", "").strip().rstrip("/"),
        supabase_anon_key=os.getenv("SUPABASE_ANON_KEY", ""),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
        **values,
    )


def assert_auth_mode_allowed() -> None:
    """Cấm chạy AUTH_MODE=off khi ứng dụng nằm trong container."""
    runtime = os.getenv("CDSS_RUNTIME", "").strip().lower()
    if os.getenv("AUTH_MODE") == "off" and runtime == "container":
        raise ConfigError("AUTH_MODE=off bị cấm khi chạy trong container")


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


class ReadDatabaseSettings(BaseModel):
    """Giới hạn kết nối đọc và thời gian ngắt khi DB không sẵn sàng."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    thoi_han_ket_noi_giay: int = Field(default=3, gt=0)
    cau_dao_giay: int = Field(default=60, gt=0)


class VectorStoreSettings(BaseModel):
    """Tên nhà cung cấp kho véc-tơ."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    provider: str


class PromptSettings(BaseModel):
    """Đường dẫn các prompt có phiên bản."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tong_hop: str
    hoi_them: str
    tac_tu: str = "config/prompts/tac_tu.v1.md"


class OrchestrationSettings(BaseModel):
    """Chọn đường chạy bước AI: đồ thị LangGraph hoặc hàm tuần tự cũ."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    engine: Literal["langgraph", "tuan_tu"]


class AskSettings(BaseModel):
    """Chọn đường chạy hỏi đáp: luồng cứng cũ hoặc agent theo đồ thị (plan 1.9 mục 6.6)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    engine: Literal["co_dinh", "agentic"] = "co_dinh"
    tool_policy: str = "config/tool_policy.yaml"


class ModelPriceSettings(BaseModel):
    """Đơn giá ước tính (USD mỗi 1 triệu token) theo mô hình LLM."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    vao_moi_trieu: float = Field(default=0.0, ge=0.0)
    ra_moi_trieu: float = Field(default=0.0, ge=0.0)


class TracerSettings(BaseModel):
    """Cấu hình ghi vết lượt chạy AI ra tệp JSONL theo ngày."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    bat: bool = True
    muc_noi_dung: Literal["sieu_du_lieu", "noi_dung_da_che", "day_du"] = "sieu_du_lieu"
    so_ngay_luu: int = Field(default=30, gt=0)
    thu_muc: str = "data/runtime/vet"
    hang_doi_toi_da: int = Field(default=1000, gt=0)
    kich_thuoc_tep_mb: int = Field(default=200, gt=0)
    bang_gia: dict[str, ModelPriceSettings] = Field(default_factory=dict)


def assert_tracer_settings_allowed(tracer: TracerSettings) -> None:
    """Cấm mức nội dung 'day_du' khi APP_ENV=production để tránh lộ dữ liệu."""
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if tracer.muc_noi_dung == "day_du" and app_env == "production":
        raise ConfigError(
            "Không được khởi động với tracer.muc_noi_dung='day_du' khi APP_ENV=production"
        )


class AppSettings(BaseModel):
    """Thư mục ca và tên hồ sơ chạy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    case_dir: str
    profile: str
    tra_cuu: str = "data/kb_curated/tra_cuu/tra_cuu.sqlite"
    tuong_tac: str = "data/kb_curated/tuong_tac/ddinter.sqlite"
    kb_source: Literal["auto", "file", "db"] = "auto"


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
    db: ReadDatabaseSettings = Field(default_factory=ReadDatabaseSettings)
    vector_store: VectorStoreSettings
    prompts: PromptSettings
    orchestration: OrchestrationSettings = OrchestrationSettings(engine="tuan_tu")
    ask: AskSettings = AskSettings()
    tracer: TracerSettings = Field(default_factory=TracerSettings)


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
    if "KB_SOURCE" in os.environ:
        app_raw = raw.get("app")
        if isinstance(app_raw, dict):
            app_raw["kb_source"] = load_kb_source()
    try:
        settings = Settings.model_validate(raw)
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_context=False)
        ]
        raise ConfigError("; ".join(errors)) from exc
    assert_tracer_settings_allowed(settings.tracer)
    return settings


def load_env_file() -> None:
    """Nạp `.env` gốc vào môi trường khi chạy local; biến đã có sẵn luôn được ưu tiên."""
    if os.getenv("PYTHON_DOTENV_DISABLED") == "1":
        return
    load_dotenv(dotenv_path=_ROOT / ".env", override=False)


def get_secret(name: str) -> str:
    """Đọc bí mật, không ghi đè môi trường và không đưa giá trị vào lỗi."""
    if os.getenv("PYTHON_DOTENV_DISABLED") == "1":
        load_dotenv(stream=io.StringIO(""), override=False)
    else:
        load_dotenv(dotenv_path=_ROOT / ".env", override=False)
    value = os.getenv(name)
    if not value:
        raise ConfigError(name)
    return value


def get_process_secret(name: str) -> str | None:
    """Đọc biến môi trường đã nạp mà không mở tệp môi trường."""
    return os.getenv(name)


def loader_database_url(
    url_env: str = "DATABASE_URL",
    *,
    secret_reader: Callable[[str], str] | None = None,
) -> str:
    """Trả DATABASE_URL_LOADER cho script nạp; thiếu thì dùng url_env kèm cảnh báo một lần."""
    global _warned_missing_loader_url
    reader = get_secret if secret_reader is None else secret_reader
    try:
        loader_url = reader("DATABASE_URL_LOADER").strip()
    except ConfigError:
        loader_url = ""
    if loader_url:
        return loader_url
    fallback_url = reader(url_env).strip()
    if not fallback_url:
        raise ConfigError(url_env)
    with _loader_warn_lock:
        if not _warned_missing_loader_url:
            _warned_missing_loader_url = True
            _LOGGER.warning(
                "Thiếu DATABASE_URL_LOADER; tạm dùng %s cho script nạp dữ liệu.",
                url_env,
            )
    return fallback_url


def database_url_warnings(url: str) -> list[str]:
    """Kiểm tra tài khoản chủ và sslmode trên chuỗi kết nối DB, không lộ mật khẩu/URL."""
    stripped = url.strip()
    if not stripped:
        return [_GENERIC_DB_URL_WARNING]
    try:
        parsed = urlsplit(stripped)
        _ = parsed.port
        host = (parsed.hostname or "").strip().lower()
    except ValueError:
        return [_GENERIC_DB_URL_WARNING]
    if parsed.scheme.lower() not in ("postgres", "postgresql") or not host:
        return [_GENERIC_DB_URL_WARNING]

    warnings: list[str] = []
    username = unquote(parsed.username or "").strip().lower()
    if username in _OWNER_DB_USERS:
        warnings.append("API đang dùng tài khoản chủ DB")

    if host not in _LOCAL_DB_HOSTS:
        query = parse_qs(parsed.query, keep_blank_values=True)
        sslmode = (query.get("sslmode", [""])[-1] or "").strip().lower()
        if sslmode != "verify-full":
            warnings.append(
                "Kết nối DB từ xa chưa bật sslmode=verify-full để kiểm chứng chỉ máy chủ."
            )
    return warnings
