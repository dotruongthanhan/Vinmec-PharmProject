"""Dịch vụ thẩm định phi trạng thái trong RAM cho Chrome Extension (Zero-Retention)."""

from __future__ import annotations

import logging
import math
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from fastapi import HTTPException

from app import container as container_mod
from app.agent.asker import AgenticAsker
from app.api import schemas as core_s
from app.api.presenter import (
    current_mode,
    present_ai_result,
    present_case,
    present_source,
    present_warnings,
)
from app.api.rate_limit import LlmRateLimits, SlidingWindowLimiter
from app.auth.principal import Principal
from app.config.extension import ExtensionSettings, load_extension_settings
from app.config.settings import AuthSettings, get_secret, load_auth_settings, load_kb_source
from app.core.errors import ConfigError
from app.core.progress import AskProgressRegistry, BuocTienTrinh, TienTrinh, tien_trinh_hien_tai
from app.core.types import Chunk
from app.domain.models import CaBenh
from app.extension_api import schemas as ext_s
from app.extension_api.extractor import (
    CaseRecalcPatch,
    ClassifiedField,
    EmrSectionPayload,
    GeminiClientProtocol,
    apply_case_patch,
    classify_schema_fields,
    extract_to_case,
)
from app.kb.names import DrugNameIndex
from app.llm import setup as llm_setup
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.ask import AskResult, CaseAsker
from app.orchestration.evidence import EvidenceCollector, LazyRetrieverFactory
from app.orchestration.jobs import AiJobManager, AiJobState, AiQueueFullError
from app.pipeline import KetQuaThamDinh, run_case
from app.providers.gemini_llm import GeminiLLM
from app.providers.http import create_client
from app.retrieval.query_builder import QueryBuilder
from app.rules.renal_dose import DEFAULT_RENAL_RULES_PATH, RenalRuleBook, load_renal_rules
from app.ui.services import NotReadyAskService

_AUTO = object()
_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_MAX_ASK_SOURCES_PER_KEY = 200
_MIN_IMAGE_BYTES = 16


class AiRunnerProtocol(Protocol):
    """Giao diện chạy AI nền để có thể tiêm bản giả khi kiểm thử."""

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult: ...


class AskRunnerProtocol(Protocol):
    """Giao diện hỏi đáp để có thể tiêm bản giả khi kiểm thử."""

    def ask(
        self,
        ca: CaBenh,
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
        *,
        ket_qua: KetQuaThamDinh | None = None,
        ai_result: AiRunResult | None = None,
        nhan_dinh_id: str | None = None,
    ) -> AskResult: ...


@dataclass
class EphemeralSessionRecord:
    """Bản ghi ca bệnh chỉ tồn tại trong RAM, gắn chặt với một chủ sở hữu JWT."""

    session_id: str
    owner_user_id: str
    created_at_mono: float
    last_access_mono: float
    case: CaBenh
    rule_result: KetQuaThamDinh
    canh_bao_trinh_duyet: list[str] = field(default_factory=list)
    canh_bao_pii_anh: list[str] = field(default_factory=list)
    mo_hinh_da_dung: dict[str, str] = field(default_factory=dict)
    chat_history: list[tuple[str, str]] = field(default_factory=list)
    ai_started: bool = False


class EphemeralSessionStore:
    """Kho phiên RAM tạm thời với TTL và trần số lượng chống phình bộ nhớ."""

    def __init__(self, *, ttl_seconds: int = 14400, max_sessions: int = 200) -> None:
        self._ttl = max(60, ttl_seconds)
        self._max = max(1, max_sessions)
        self._lock = RLock()
        self._items: dict[str, EphemeralSessionRecord] = {}

    def _prune_locked(self, now: float) -> list[str]:
        expired = [
            sid for sid, rec in self._items.items() if now - rec.last_access_mono > self._ttl
        ]
        for sid in expired:
            del self._items[sid]
        removed = list(expired)
        while len(self._items) >= self._max:
            oldest = min(self._items, key=lambda key: self._items[key].last_access_mono)
            del self._items[oldest]
            removed.append(oldest)
        return removed

    def create(self, record: EphemeralSessionRecord) -> list[str]:
        """Thêm phiên mới sau khi dọn các phiên hết hạn hoặc quá ngưỡng."""
        with self._lock:
            now = time.monotonic()
            removed = self._prune_locked(now)
            self._items[record.session_id] = record
            return removed

    def get_owned(self, session_id: str, principal: Principal) -> EphemeralSessionRecord:
        """Lấy phiên đúng chủ sở hữu; mọi lỗi không tồn tại hoặc chéo người dùng đều trả 404."""
        with self._lock:
            now = time.monotonic()
            self._prune_locked(now)
            rec = self._items.get(session_id)
            if rec is None or rec.owner_user_id != principal.nguoi_dung_id:
                raise HTTPException(404, "Không tìm thấy phiên làm việc.")
            rec.last_access_mono = now
            return rec

    def delete_owned(self, session_id: str, principal: Principal) -> None:
        """Xoá phiên đúng chủ sở hữu khỏi RAM; sai người dùng trả 404."""
        with self._lock:
            now = time.monotonic()
            self._prune_locked(now)
            rec = self._items.get(session_id)
            if rec is None or rec.owner_user_id != principal.nguoi_dung_id:
                raise HTTPException(404, "Không tìm thấy phiên làm việc.")
            del self._items[session_id]

    def count(self) -> int:
        """Đếm số phiên còn hiệu lực trong RAM (phục vụ kiểm thử dọn dẹp)."""
        with self._lock:
            self._prune_locked(time.monotonic())
            return len(self._items)


def validate_image_bytes(raw: bytes, *, max_bytes: int) -> str:
    """Kiểm tra dung lượng và chữ ký magic bytes PNG/JPEG/WebP, không dùng tên tệp làm căn cứ."""
    if len(raw) > max_bytes:
        raise HTTPException(413, "Ảnh chụp OH vượt quá giới hạn dung lượng cho phép.")
    if len(raw) < _MIN_IMAGE_BYTES:
        raise HTTPException(422, "Tệp ảnh chụp OH bị rỗng hoặc quá nhỏ.")
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    raise HTTPException(422, "Chỉ chấp nhận ảnh PNG, JPEG hoặc WebP hợp lệ.")


def _present_progress_steps(steps: Sequence[BuocTienTrinh]) -> list[core_s.BuocAI]:
    """Chuyển các bước tiến trình sang lược đồ công khai BuocAI."""
    return [
        core_s.BuocAI(
            ma=step.ma,
            ten=step.ten,
            trang_thai=step.trang_thai,
            chi_tiet=step.chi_tiet,
            nguon=[core_s.NguonTomTat(nhan=item.nhan, so_doan=item.so_doan) for item in step.nguon],
            thoi_gian_ms=step.thoi_gian_ms,
            ly_do=step.ly_do,
            goi_y=step.goi_y,
        )
        for step in steps
    ]


class ExtensionService:
    """Điều phối Extension độc lập: chỉ dùng tri_thuc chỉ đọc và RAM tạm thời."""

    def __init__(
        self,
        *,
        settings: ExtensionSettings | None = None,
        auth_settings: AuthSettings | None = None,
        renal_rules_path: Path | None = None,
        schema_client: GeminiClientProtocol | None | object = _AUTO,
        vision_client: GeminiClientProtocol | None | object = _AUTO,
        emr_client: GeminiClientProtocol | None | object = _AUTO,
        ai_runner: AiRunnerProtocol | None | object = _AUTO,
        asker: AskRunnerProtocol | None | object = _AUTO,
        limits: LlmRateLimits | None = None,
    ) -> None:
        self.settings = settings or load_extension_settings()
        self.auth_settings = auth_settings or load_auth_settings()
        self._renal_rules_path = renal_rules_path or DEFAULT_RENAL_RULES_PATH
        self._renal_rules: RenalRuleBook | None = None
        self._sessions = EphemeralSessionStore(
            ttl_seconds=self.settings.server.session_ttl_seconds,
            max_sessions=self.settings.server.max_sessions,
        )
        self._lock = RLock()
        self._http_client = None
        self._jobs = AiJobManager()
        self._ask_progress = AskProgressRegistry()
        self._limits = limits if limits is not None else LlmRateLimits.from_env()
        self._ask_sources: dict[str, dict[str, Chunk]] = {}
        self._ask_fallback = NotReadyAskService()

        self._container: container_mod.Container | None = None
        self._synthesizer: Synthesizer | None = None
        self._retriever_factory: LazyRetrieverFactory | None = None

        self._schema_client = self._resolve_gemini_client(
            schema_client, self.settings.models.schema_classifier
        )
        self._vision_client = self._resolve_gemini_client(
            vision_client, self.settings.models.oh_vision
        )
        self._emr_client = self._resolve_gemini_client(emr_client, self.settings.models.emr_extract)

        if ai_runner is _AUTO:
            self._ai_runner: AiRunnerProtocol | None = self._build_default_ai_runner()
        else:
            self._ai_runner = ai_runner  # type: ignore[assignment]
        self._ai_enabled = self._ai_runner is not None

        if asker is _AUTO:
            self._asker_impl: AskRunnerProtocol | None = (
                self._build_default_asker(self._container)
                if self._ai_enabled and self._container is not None
                else None
            )
        else:
            self._asker_impl = asker  # type: ignore[assignment]

    def _ensure_http_client(self) -> Any:
        if self._http_client is None:
            self._http_client = create_client()
        return self._http_client

    def _resolve_gemini_client(
        self,
        injected: Any,
        stage_cfg: Any,
    ) -> GeminiClientProtocol | None:
        if injected is not _AUTO:
            return injected
        try:
            api_key = get_secret("GEMINI_API_KEY")
        except ConfigError:
            return None
        return GeminiLLM(
            model=stage_cfg.model,
            api_key=api_key,
            client=self._ensure_http_client(),
            temperature=stage_cfg.temperature,
            max_tokens=stage_cfg.max_tokens,
            timeout_seconds=stage_cfg.timeout_seconds,
            max_attempts=stage_cfg.max_attempts,
        )

    def _corpus_mode(self, container: container_mod.Container | None = None) -> str:
        default_corpus = _ROOT / "data/kb_curated/chunks.jsonl"
        kb_source = container.settings.app.kb_source if container is not None else load_kb_source()
        has_db = container._database_url() is not None if container is not None else False
        if kb_source == "db":
            return "db" if has_db else "none"
        if kb_source == "file":
            return "file" if default_corpus.is_file() else "none"
        if default_corpus.is_file():
            return "file"
        return "db" if has_db else "none"

    def _build_default_ai_runner(self) -> AiRunnerProtocol | None:
        try:
            container = container_mod.build_container()
            synthesizer = llm_setup.build_synthesizer(container)
        except ConfigError:
            return None
        if synthesizer.llm is None:
            return None

        self._container = container
        self._synthesizer = synthesizer
        corpus_mode = self._corpus_mode(container)
        default_corpus = _ROOT / "data/kb_curated/chunks.jsonl"
        if corpus_mode == "db":
            self._retriever_factory = LazyRetrieverFactory(container, use_db=True)
            retriever: LazyRetrieverFactory | None = self._retriever_factory
        elif corpus_mode == "file":
            self._retriever_factory = LazyRetrieverFactory(container, default_corpus, use_db=False)
            retriever = self._retriever_factory
        else:
            retriever = None
        names = DrugNameIndex.load()
        collector = EvidenceCollector(
            retriever=retriever,
            query_builder=QueryBuilder(container.settings.retrieval),
            resolve_name=names.resolve,
        )
        return AiReviewer(collector, synthesizer)

    def _build_default_asker(self, container: container_mod.Container) -> AskRunnerProtocol | None:
        if container.settings.ask.engine == "agentic":
            return container.agentic_asker
        if self._synthesizer is None or self._synthesizer.llm is None:
            return None
        names = DrugNameIndex.load()
        raw_prompt = Path(container.settings.prompts.hoi_them)
        prompt_path = raw_prompt if raw_prompt.is_absolute() else _ROOT / raw_prompt
        return CaseAsker(
            llm=self._synthesizer.llm,
            retriever=self._retriever_factory,
            query_builder=QueryBuilder(container.settings.retrieval),
            resolve_name=names.resolve,
            prompt_path=prompt_path,
            case_settings=container.settings.case_context,
            evidence_max_chars=container.settings.evidence.max_chars,
            model_name=self._synthesizer.model_name,
            renal_rules=container.renal_rules,
        )

    def mode(self) -> core_s.CheDo:
        """Trả chế độ tri thức và AI hiện có cho giao diện Side Panel."""
        has_corpus = (
            self._retriever_factory is not None or self._corpus_mode(self._container) != "none"
        )
        return current_mode(
            co_llm=self._ai_enabled,
            has_corpus=has_corpus,
            hoi_them=self._ai_enabled and self._asker_impl is not None,
        )

    def health(self) -> ext_s.ExtensionHealthResponse:
        """Tình trạng dịch vụ Extension độc lập."""
        models_cfg = self.settings.models
        return ext_s.ExtensionHealthResponse(
            che_do=self.mode(),
            xac_thuc=self.auth_settings.auth_mode,
            mo_hinh_trich_xuat={
                "schema_classifier": models_cfg.schema_classifier.model,
                "oh_vision": models_cfg.oh_vision.model,
                "emr_extract": models_cfg.emr_extract.model,
                "deep_review": self._ai_model_name() or models_cfg.deep_review.model,
            },
        )

    def shutdown(self) -> None:
        """Giải phóng luồng nền và kết nối HTTP khi tắt ứng dụng."""
        self._jobs.shutdown()
        if self._retriever_factory is not None:
            self._retriever_factory.close()
        if self._http_client is not None:
            self._http_client.close()
        if self._synthesizer is not None and self._synthesizer.llm is not None:
            client = getattr(self._synthesizer.llm, "client", None)
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                close_fn()

    def _run_rules(self, case: CaBenh) -> KetQuaThamDinh:
        """Chạy 14 công thức + 14 luật tất định trên CaBenh tạm trong RAM."""
        with self._lock:
            if self._renal_rules is None:
                self._renal_rules = load_renal_rules(self._renal_rules_path)
            renal_rules = self._renal_rules
        ctx = container_mod.get_rule_context()
        return run_case(
            case,
            renal_rules,
            resolver=ctx.resolver,
            interactions=ctx.interactions,
        )

    def _present_review(
        self,
        record: EphemeralSessionRecord,
        *,
        elapsed_ms: float,
    ) -> ext_s.ExtensionReviewResponse:
        detail = present_case(
            record.case,
            record.rule_result,
            feedbacks=(),
            che_do=self.mode(),
            ma_tran_tuong_tac=record.rule_result.ma_tran_tuong_tac,
        )
        return ext_s.ExtensionReviewResponse(
            session_id=record.session_id,
            expires_in_seconds=self.settings.server.session_ttl_seconds,
            chi_tiet=detail,
            canh_bao_trinh_duyet=list(record.canh_bao_trinh_duyet),
            canh_bao_pii_anh=list(record.canh_bao_pii_anh),
            mo_hinh_da_dung=dict(record.mo_hinh_da_dung),
            thoi_gian_ms=round(elapsed_ms, 2),
            che_do=self.mode(),
        )

    def classify_schema(
        self,
        request: ext_s.ClassifySchemaRequest,
        principal: Principal,
    ) -> ext_s.ClassifySchemaResponse:
        """Phân loại chỉ tên nhãn DOM bằng sàn PII tất định + Gemini 3.5 Flash Lite."""
        del principal  # Chỉ dùng để buộc đăng nhập hợp lệ qua dependency.
        fields: list[ClassifiedField] = classify_schema_fields(
            request.fields,
            self._schema_client,
            self.settings.prompts.ext_schema,
        )
        return ext_s.ClassifySchemaResponse(
            schema_hash=request.schema_hash,
            mo_hinh=self._schema_client.model if self._schema_client is not None else None,
            fields=fields,
        )

    def extract_and_review(
        self,
        *,
        emr_payload: ext_s.ExtractEmrPayload,
        oh_image_bytes: bytes | None,
        oh_image_mime: str | None,
        principal: Principal,
    ) -> ext_s.ExtensionReviewResponse:
        """Trích xuất song song 4 luồng + chạy ngay engine tất định, lưu phiên RAM tạm."""
        started = time.perf_counter()
        session_id = f"EXT-{secrets.token_urlsafe(18)}"
        sections: list[EmrSectionPayload] = list(emr_payload.sections)
        try:
            extracted = extract_to_case(
                ca_id=session_id,
                sections=sections,
                oh_image_bytes=oh_image_bytes,
                oh_image_mime=oh_image_mime,
                vision_client=self._vision_client,
                emr_client=self._emr_client,
                vision_prompt_path=self.settings.prompts.ext_oh_vision,
                emr_prompt_path=self.settings.prompts.ext_emr_extract,
                max_workers=self.settings.limits.max_extract_workers,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

        rule_result = self._run_rules(extracted.ca_benh)
        now_mono = time.monotonic()
        record = EphemeralSessionRecord(
            session_id=session_id,
            owner_user_id=principal.nguoi_dung_id,
            created_at_mono=now_mono,
            last_access_mono=now_mono,
            case=extracted.ca_benh,
            rule_result=rule_result,
            canh_bao_trinh_duyet=list(extracted.canh_bao),
            canh_bao_pii_anh=list(extracted.canh_bao_pii_anh),
            mo_hinh_da_dung=dict(extracted.mo_hinh_da_dung),
        )
        removed_sids = self._sessions.create(record)
        for old_sid in removed_sids:
            self._ask_sources.pop(old_sid, None)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return self._present_review(record, elapsed_ms=elapsed_ms)

    def recalc(
        self,
        session_id: str,
        patch: CaseRecalcPatch,
        principal: Principal,
    ) -> ext_s.ExtensionReviewResponse:
        """Chạy lại 14 công thức + 14 luật sau khi dược sĩ chỉnh tay trong Side Panel."""
        started = time.perf_counter()
        record = self._sessions.get_owned(session_id, principal)
        try:
            updated_case = apply_case_patch(record.case, patch)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        rule_result = self._run_rules(updated_case)
        with self._lock:
            record.case = updated_case
            record.rule_result = rule_result
            record.ai_started = False
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return self._present_review(record, elapsed_ms=elapsed_ms)

    def delete_session(self, session_id: str, principal: Principal) -> None:
        """Xoá sạch phiên tạm thời và lịch sử nguồn hỏi đáp khỏi RAM."""
        self._sessions.delete_owned(session_id, principal)
        with self._lock:
            self._ask_sources.pop(session_id, None)

    def session_count(self) -> int:
        """Số phiên còn hoạt động trong RAM."""
        return self._sessions.count()

    def _ai_model_name(self) -> str | None:
        if self._synthesizer is not None:
            return self._synthesizer.model_name
        return getattr(self._ai_runner, "model_name", None)

    def _enforce_llm_limits(
        self,
        limiter: SlidingWindowLimiter,
        principal: Principal,
        route_path: str,
        rate_message: str,
    ) -> None:
        user_key = principal.nguoi_dung_id or "__anonymous__"
        wait = limiter.hit(user_key)
        if wait is not None:
            wait_sec = max(1, math.ceil(wait))
            raise HTTPException(
                429,
                detail={
                    "ma": "vuot_gioi_han",
                    "thong_bao": f"{rate_message} Vui lòng thử lại sau {wait_sec} giây.",
                },
                headers={"Retry-After": str(wait_sec)},
            )
        if not self._limits.daily_budget.take():
            reset_fn = getattr(self._limits.daily_budget, "seconds_until_reset", None)
            wait_sec = int(reset_fn()) if callable(reset_fn) else 3600
            raise HTTPException(
                429,
                detail={
                    "ma": "het_ngan_sach_ngay",
                    "thong_bao": (
                        "Hệ thống đã đạt giới hạn lượt LLM trong ngày. "
                        f"Vui lòng thử lại sau {wait_sec} giây."
                    ),
                },
                headers={"Retry-After": str(wait_sec)},
            )

    def _present_job_state(
        self,
        record: EphemeralSessionRecord,
        state: AiJobState,
    ) -> core_s.KetQuaAI:
        if state.trang_thai == "dang_chay":
            base = core_s.KetQuaAI(
                trang_thai="dang_chay",
                nhan_dinh=None,
                canh_bao=present_warnings(state.canh_bao),
                thoi_gian_ms=None,
                mo_hinh=self._ai_model_name(),
            )
        elif state.trang_thai == "loi":
            base = core_s.KetQuaAI(
                trang_thai="loi",
                nhan_dinh=None,
                canh_bao=present_warnings(state.canh_bao),
                thoi_gian_ms=None,
                mo_hinh=self._ai_model_name(),
            )
        else:
            assert state.ket_qua is not None
            base = present_ai_result(record.case, record.rule_result, state.ket_qua, ())

        tracker = state.tien_trinh if isinstance(state.tien_trinh, TienTrinh) else None
        if tracker is None:
            return base.model_copy(update={"thuong_le_ms": self._jobs.thuong_le_ms()})
        snapshot_at = state.ket_thuc if state.trang_thai != "dang_chay" else None
        steps = _present_progress_steps(tracker.chup(now=snapshot_at))
        return base.model_copy(
            update={
                "cac_buoc": steps,
                "da_chay_ms": tracker.tong_ms(now=snapshot_at),
                "thuong_le_ms": self._jobs.thuong_le_ms(),
            }
        )

    def start_ai(
        self,
        session_id: str,
        *,
        restart: bool,
        principal: Principal,
    ) -> core_s.KetQuaAI:
        """Khởi động phân tích AI nền bằng deepseek-flash cho phiên tạm thời."""
        record = self._sessions.get_owned(session_id, principal)
        if not self._ai_enabled or self._ai_runner is None:
            return core_s.KetQuaAI(
                trang_thai="tat",
                nhan_dinh=None,
                canh_bao=[],
                thoi_gian_ms=None,
                mo_hinh=None,
            )

        with self._lock:
            raw_job = self._jobs.get(session_id)
            effective_restart = restart or not record.ai_started
            already_running = raw_job is not None and raw_job.trang_thai == "dang_chay"
            will_submit = raw_job is None or (not already_running and effective_restart)
            if will_submit:
                if self._jobs.pending_count() >= self._jobs.max_pending:
                    raise HTTPException(
                        429,
                        detail={
                            "ma": "hang_doi_day",
                            "thong_bao": (
                                "Hàng đợi phân tích AI đang bận. Vui lòng thử lại sau 30 giây."
                            ),
                        },
                        headers={"Retry-After": "30"},
                    )
                self._enforce_llm_limits(
                    self._limits.ai_limiter,
                    principal,
                    "/api/extension/sessions/{session_id}/ai",
                    "Bạn đã yêu cầu phân tích AI quá nhiều lần.",
                )
            runner = self._ai_runner
            case_snap = record.case
            rule_snap = record.rule_result
            try:
                state = self._jobs.start(
                    session_id,
                    lambda: runner.run(case_snap, rule_snap),
                    restart=effective_restart,
                )
            except AiQueueFullError:
                raise HTTPException(
                    429,
                    detail={
                        "ma": "hang_doi_day",
                        "thong_bao": (
                            "Hàng đợi phân tích AI đang bận. Vui lòng thử lại sau 30 giây."
                        ),
                    },
                    headers={"Retry-After": "30"},
                ) from None
            record.ai_started = True
        return self._present_job_state(record, state)

    def get_ai(self, session_id: str, principal: Principal) -> core_s.KetQuaAI:
        """Lấy tiến trình và kết quả phân tích AI của phiên đúng chủ sở hữu."""
        record = self._sessions.get_owned(session_id, principal)
        if not self._ai_enabled or self._ai_runner is None:
            return core_s.KetQuaAI(
                trang_thai="tat",
                nhan_dinh=None,
                canh_bao=[],
                thoi_gian_ms=None,
                mo_hinh=None,
            )
        state = self._jobs.get(session_id) if record.ai_started else None
        if state is None:
            raise HTTPException(
                404,
                detail={
                    "ma": "chua_chay",
                    "thong_bao": "Chưa chạy phân tích AI cho phiên này.",
                },
            )
        return self._present_job_state(record, state)

    def get_ask_progress(self, session_id: str, principal: Principal) -> core_s.TienTrinhHoiDap:
        """Đọc tiến trình hỏi đáp đang chạy của phiên đúng chủ sở hữu."""
        self._sessions.get_owned(session_id, principal)
        snapshot = self._ask_progress.doc((session_id, principal.nguoi_dung_id))
        if snapshot is None:
            return core_s.TienTrinhHoiDap(dang_chay=False, cac_buoc=[], da_chay_ms=None)
        dang_chay, steps, tong_ms = snapshot
        return core_s.TienTrinhHoiDap(
            dang_chay=dang_chay,
            cac_buoc=_present_progress_steps(steps),
            da_chay_ms=tong_ms,
        )

    def ask(
        self,
        session_id: str,
        request: core_s.GuiCauHoi,
        principal: Principal,
    ) -> core_s.TraLoi:
        """Hỏi đáp agentic trên ca tạm trong RAM, giữ lịch sử hội thoại theo phiên."""
        record = self._sessions.get_owned(session_id, principal)
        progress_key = (session_id, principal.nguoi_dung_id)
        progress_token, progress_tracker = self._ask_progress.bat_dau(progress_key, ())
        ctx_token = tien_trinh_hien_tai.set(progress_tracker)
        succeeded = False
        try:
            with self._lock:
                max_pairs = self.settings.limits.max_ask_history_turns * 2
                history_pairs = list(record.chat_history[-max_pairs:])
                asker = self._asker_impl
                if not self._ai_enabled or asker is None:
                    reply = self._ask_fallback.ask(record.case, request.cau_hoi, history_pairs)
                    return core_s.TraLoi(
                        trang_thai=reply.trang_thai,
                        noi_dung=reply.noi_dung,
                        trich_dan=[],
                        cong_cu_da_goi=[],
                        thoi_gian_ms=0,
                    )
                state = self._jobs.get(session_id) if record.ai_started else None
                ai_result = (
                    state.ket_qua if state is not None and state.trang_thai == "xong" else None
                )
                case_snap = record.case
                rule_snap = record.rule_result

            self._enforce_llm_limits(
                self._limits.ask_limiter,
                principal,
                "/api/extension/sessions/{session_id}/ask",
                "Bạn đã gửi quá nhiều câu hỏi.",
            )
            if isinstance(asker, AgenticAsker):
                result = asker.ask(
                    case_snap,
                    request.cau_hoi,
                    history_pairs,
                    ket_qua=rule_snap,
                    ai_result=ai_result,
                    nhan_dinh_id=request.nhan_dinh_id,
                    vai_tro=principal.vai_tro,
                )
            else:
                result = asker.ask(
                    case_snap,
                    request.cau_hoi,
                    history_pairs,
                    ket_qua=rule_snap,
                    ai_result=ai_result,
                    nhan_dinh_id=request.nhan_dinh_id,
                )

            succeeded = result.trang_thai == "ok"
            with self._lock:
                max_msgs = self.settings.limits.max_ask_history_turns * 2
                record.chat_history.append(("nguoi_dung", request.cau_hoi[:2000]))
                record.chat_history.append(("he_thong", result.noi_dung[:4000]))
                if len(record.chat_history) > max_msgs:
                    record.chat_history = record.chat_history[-max_msgs:]

                if result.trang_thai == "ok" and result.doan:
                    bucket = self._ask_sources.setdefault(session_id, {})
                    for chunk in result.doan:
                        if chunk.doan_trich_id in bucket:
                            del bucket[chunk.doan_trich_id]
                        bucket[chunk.doan_trich_id] = chunk
                        while len(bucket) > _MAX_ASK_SOURCES_PER_KEY:
                            del bucket[next(iter(bucket))]

            return core_s.TraLoi(
                trang_thai=result.trang_thai,
                noi_dung=result.noi_dung,
                trich_dan=[
                    core_s.Citation(
                        so=item.so,
                        loai_ma=item.loai_ma,
                        nhan=item.nhan,
                        ban_ghi_id=item.ban_ghi_id,
                        doan_trich_id=item.doan_trich_id,
                        trich_nguyen_van=item.trich_nguyen_van,
                    )
                    for item in result.trich_dan
                ],
                cong_cu_da_goi=list(result.cong_cu_da_goi),
                thoi_gian_ms=result.thoi_gian_ms,
            )
        finally:
            tien_trinh_hien_tai.reset(ctx_token)
            self._ask_progress.ket_thuc(progress_key, progress_token, succeeded)

    def get_source(
        self,
        session_id: str,
        chunk_id: str,
        principal: Principal,
    ) -> core_s.DoanNguon:
        """Tra đoạn nguồn mở đã dùng trong phân tích AI hoặc hỏi đáp của phiên."""
        record = self._sessions.get_owned(session_id, principal)
        chunk: Chunk | None = None
        state = self._jobs.get(session_id) if record.ai_started else None
        if state is not None and state.trang_thai == "xong" and state.ket_qua is not None:
            chunk = next(
                (item for item in state.ket_qua.doan if item.doan_trich_id == chunk_id),
                None,
            )
        if chunk is None:
            with self._lock:
                chunk = self._ask_sources.get(session_id, {}).get(chunk_id)
        if chunk is None:
            raise HTTPException(404, "Không tìm thấy đoạn nguồn trong phiên này.")
        return present_source(chunk)
