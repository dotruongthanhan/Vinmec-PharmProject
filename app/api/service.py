"""Dịch vụ ca bệnh giữ bộ đệm thẩm định, điều phối AI nền và lưu phản hồi/hội thoại."""

import logging
import math
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import combinations, product
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Protocol

from fastapi import HTTPException

from app import container as container_mod
from app.api import schemas as s
from app.api.presenter import (
    ai_finding_id,
    current_mode,
    finding_id,
    finding_ids,
    present_ai_result,
    present_case,
    present_feedback,
    present_queue,
    present_record,
    present_source,
    present_warnings,
)
from app.api.rate_limit import LlmRateLimits, SlidingWindowLimiter
from app.auth.principal import Principal
from app.config.settings import (
    get_secret,
    load_case_cache_ttl,
    load_case_source,
    load_kb_source,
)
from app.core.errors import ConfigError
from app.core.progress import TienTrinh
from app.core.types import Chunk
from app.db import administrative, medical_record
from app.db.reader import DatabaseReadError, DbReviewService
from app.db.timezone import VN_TZ
from app.domain.models import CaBenh
from app.feedback import PhanHoi
from app.kb.names import DrugNameIndex
from app.kb.resolver import DrugResolver
from app.llm import setup as llm_setup
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.ask import AskResult, CaseAsker
from app.orchestration.evidence import EvidenceCollector, LazyRetrieverFactory
from app.orchestration.jobs import AiJobManager, AiJobState, AiQueueFullError
from app.pipeline import KetQuaThamDinh, run_case
from app.retrieval.query_builder import QueryBuilder
from app.rules import renal_dose as renal_dose_mod
from app.rules.renal_dose import RenalRuleBook, load_renal_rules
from app.rules.types import effective_lines
from app.storage.feedback_chat import (
    DbFeedbackChatStore,
    FeedbackAndChatStore,
    FileFeedbackChatStore,
    owns_conversation,
)
from app.storage.review_results import (
    DbReviewResultStore,
    NoopReviewResultStore,
    ReviewResultStore,
    compute_rule_version,
)
from app.ui.labels import NHOM_LY_DO
from app.ui.services import NotReadyAskService, PipelineReviewService, ReviewService

_AUTO = object()
_ROOT = Path(__file__).resolve().parents[2]
_LOGGER = logging.getLogger(__name__)


class AiRunner(Protocol):
    """Giao diện tối thiểu của bộ chạy AI để tiêm bản giả khi kiểm thử."""

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult: ...


class AskRunner(Protocol):
    """Giao diện tối thiểu của bộ hỏi đáp để tiêm bản giả khi kiểm thử."""

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


_DB_READ_TTL_SECONDS = 60.0
_CASE_REFRESH_RETRY_SECONDS = 15.0
_MAX_ASK_SOURCES_PER_KEY = 200
_INTERACTION_EXCLUDED = {"dich_truyen_dien_giai", "duoc_lieu"}


def _ask_source_key(case_id: str, principal: Principal | None) -> str:
    """Tách kho đoạn nguồn hỏi đáp chung theo người dùng, giữ khoá theo ca như cũ."""
    if case_id == "__global__":
        user_id = principal.nguoi_dung_id if principal is not None else "__anonymous__"
        return f"__global__:{user_id}"
    return case_id


def _collect_interaction_pairs(
    cases: Sequence[CaBenh],
    resolver: DrugResolver,
) -> list[tuple[str, str]]:
    """Thu toàn bộ cặp ddinter_id cần tra cho danh sách ca trước khi chạy luật."""
    pairs: list[tuple[str, str]] = []
    for ca in cases:
        try:
            lines = effective_lines(ca)
            resolved = [resolver.resolve_line(ca, line) for line in lines]
            for i, j in combinations(range(len(resolved)), 2):
                ra, rb = resolved[i], resolved[j]
                if "khong_ap_dung" in {ra.trang_thai, rb.trang_thai}:
                    continue
                ca_comp = [row for row in ra.thanh_phan if row.loai not in _INTERACTION_EXCLUDED]
                cb_comp = [row for row in rb.thanh_phan if row.loai not in _INTERACTION_EXCLUDED]
                ca_ids = {row.hoat_chat_id for row in ca_comp}
                cb_ids = {row.hoat_chat_id for row in cb_comp}
                if (
                    ra.trang_thai == rb.trang_thai == "da_phan_giai"
                    and ca_comp
                    and cb_comp
                    and ca_ids == cb_ids
                ):
                    continue
                for ia, ib in product(ca_comp, cb_comp):
                    if ia.hoat_chat_id != ib.hoat_chat_id and ia.ddinter_id and ib.ddinter_id:
                        pairs.append((ia.ddinter_id, ib.ddinter_id))
        except Exception as exc:
            _LOGGER.debug("Bỏ qua ca khi gom cặp tương tác (%s)", type(exc).__name__)
            continue
    return pairs


def _is_ai_disabled() -> bool:
    """Đọc cờ tắt AI qua lớp cấu hình tập trung, không đọc .env trực tiếp."""
    try:
        return get_secret("CDSS_AI").strip().lower() == "off"
    except ConfigError:
        return False


def _has_database_url(url_env: str = "DATABASE_URL") -> bool:
    """Kiểm tra biến môi trường DATABASE_URL có giá trị không rỗng."""
    try:
        return bool(get_secret(url_env).strip())
    except ConfigError:
        return False


class CaseService:
    """Giữ danh sách ca và kết quả thẩm định theo dữ liệu hiện có."""

    def __init__(
        self,
        case_dir: Path,
        renal_rules_path: Path | None,
        feedback_path: Path,
        *,
        ai_runner: Any = _AUTO,
        corpus_path: Path | None = None,
        asker: Any = _AUTO,
        runtime_store: FeedbackAndChatStore | None = None,
        review_store: ReviewResultStore | None = None,
        limits: LlmRateLimits | None = None,
    ) -> None:
        resolved_renal_path = (
            Path(renal_rules_path)
            if renal_rules_path is not None
            else renal_dose_mod.DEFAULT_RENAL_RULES_PATH
        )
        self._loader: ReviewService = (
            DbReviewService(resolved_renal_path)
            if load_case_source() == "db"
            else PipelineReviewService(case_dir, resolved_renal_path)
        )
        self._renal_rules_path = resolved_renal_path
        self._feedback_path = Path(feedback_path)
        self._store: FeedbackAndChatStore = (
            runtime_store
            if runtime_store is not None
            else (
                DbFeedbackChatStore()
                if isinstance(self._loader, DbReviewService) and _has_database_url()
                else FileFeedbackChatStore(self._feedback_path)
            )
        )
        self._review_store: ReviewResultStore = (
            review_store
            if review_store is not None
            else (
                DbReviewResultStore()
                if isinstance(self._loader, DbReviewService) and _has_database_url()
                else NoopReviewResultStore()
            )
        )
        self._persisted_results: dict[str, KetQuaThamDinh] = {}
        self._persist_lock = Lock()
        self._detail_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="case-detail")
        self._persist_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="review-persist",
        )
        self._pending_persists: list[Future[None]] = []
        self._shut_down = False
        self._corpus_path = (
            Path(corpus_path) if corpus_path is not None else _ROOT / "data/kb_curated/chunks.jsonl"
        )
        self._cases: dict[str, CaBenh] | None = None
        self._case_cache_ttl = (
            load_case_cache_ttl() if isinstance(self._loader, DbReviewService) else None
        )
        self._next_case_refresh_at = 0.0
        self._cases_refreshed_at: datetime | None = None
        self._refresh_lock = Lock()
        self._load_errors: list[s.LoadError] = []
        self._results: dict[str, KetQuaThamDinh] = {}
        self._renal_rules: RenalRuleBook | None = None
        self._ask = NotReadyAskService()
        self._lock = RLock()
        self._db_cache: dict[str, tuple[float, CaBenh, s.MedicalRecord]] = {}
        self._jobs = AiJobManager()
        self._limits = limits if limits is not None else LlmRateLimits.from_env()
        self._ai_cases: set[str] = set()
        self._ask_sources: dict[str, dict[str, Chunk]] = {}
        self._container: container_mod.Container | None = None
        self._synthesizer: Synthesizer | None = None
        self._retriever_factory: LazyRetrieverFactory | None = None
        self._asker_impl: AskRunner | None = None
        if ai_runner is _AUTO:
            self._ai_runner: AiRunner | None = self._build_default_ai_runner()
        else:
            self._ai_runner = ai_runner
        self._ai_enabled = self._ai_runner is not None
        if asker is not _AUTO:
            self._asker_impl = asker
        elif self._ai_enabled and self._container is not None:
            self._asker_impl = self._build_default_asker(self._container)

    def _corpus_mode(self, container: container_mod.Container | None = None) -> str:
        """Trả 'db', 'file' hoặc 'none' cho kho đoạn theo cấu hình và đường dẫn."""
        default_corpus = _ROOT / "data/kb_curated/chunks.jsonl"
        if self._corpus_path != default_corpus:
            return "file" if self._corpus_path.is_file() else "none"
        kb_source = container.settings.app.kb_source if container is not None else load_kb_source()
        has_db = (
            container._database_url() is not None if container is not None else _has_database_url()
        )
        if kb_source == "db":
            return "db" if has_db else "none"
        if kb_source == "file":
            return "file" if self._corpus_path.is_file() else "none"
        if self._corpus_path.is_file():
            return "file"
        return "db" if has_db else "none"

    def _build_default_ai_runner(self) -> AiRunner | None:
        """Xác định bật/tắt AI một lần lúc khởi tạo dịch vụ."""
        if _is_ai_disabled():
            return None
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
        if corpus_mode == "db":
            self._retriever_factory = LazyRetrieverFactory(container, use_db=True)
            retriever: LazyRetrieverFactory | None = self._retriever_factory
        elif corpus_mode == "file":
            self._retriever_factory = LazyRetrieverFactory(
                container, self._corpus_path, use_db=False
            )
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

    def _build_default_asker(self, container: container_mod.Container) -> AskRunner | None:
        """Dựng CaseAsker qua container hoặc theo corpus_path tuỳ chỉnh khi kiểm thử."""
        default_corpus = _ROOT / "data/kb_curated/chunks.jsonl"
        if self._corpus_path == default_corpus:
            return container.case_asker
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

    def mode(self) -> s.CheDo:
        """Trả chế độ vận hành hiện tại của dịch vụ."""
        has_corpus = (
            self._retriever_factory is not None or self._corpus_mode(self._container) != "none"
        )
        return current_mode(
            co_llm=self._ai_enabled,
            has_corpus=has_corpus,
            hoi_them=self._ai_enabled and self._asker_impl is not None,
        )

    def shutdown(self) -> None:
        """Đóng bộ chạy nền AI, luồng đọc chi tiết/ghi nền và máy khách HTTP dùng chung nếu có."""
        with self._persist_lock:
            self._shut_down = True
        self._jobs.shutdown()
        self._detail_executor.shutdown(wait=True)
        self._persist_executor.shutdown(wait=True)
        if self._retriever_factory is not None:
            self._retriever_factory.close()
        if self._synthesizer is not None and self._synthesizer.llm is not None:
            client = getattr(self._synthesizer.llm, "client", None)
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                close_fn()
        if self._asker_impl is not None:
            close_asker = getattr(self._asker_impl, "close", None)
            if callable(close_asker):
                close_asker()

    def flush_persist(self, timeout: float | None = None) -> None:
        """Chờ toàn bộ tác vụ ghi nền kết quả thẩm định đang xếp hàng hoàn tất."""
        with self._persist_lock:
            pending = list(self._pending_persists)
        for future in pending:
            future.result(timeout=timeout)

    def _ensure_cases(self) -> None:
        """Nạp tệp một lần hoặc làm mới từ DB mà vẫn phục vụ dữ liệu cũ."""
        loader = self._loader
        ttl = self._case_cache_ttl
        if not isinstance(loader, DbReviewService) or ttl is None:
            with self._lock:
                if self._cases is None:
                    cases, errors = loader.list_cases()
                    self._cases = {case.ca_id: case for case in cases}
                    self._load_errors = [s.LoadError(tep=path, loi=error) for path, error in errors]
            return

        with self._lock:
            has_cases = self._cases is not None
            if has_cases and time.monotonic() < self._next_case_refresh_at:
                return
        if not self._refresh_lock.acquire(blocking=not has_cases):
            return

        try:
            with self._lock:
                has_cases = self._cases is not None
                if has_cases and time.monotonic() < self._next_case_refresh_at:
                    return
            try:
                loader.refresh()
                cases, errors = loader.list_cases()
            except DatabaseReadError:
                if not has_cases:
                    raise
                with self._lock:
                    self._next_case_refresh_at = time.monotonic() + _CASE_REFRESH_RETRY_SECONDS
                _LOGGER.warning("Tiếp tục dùng danh sách ca đã nạp do làm mới thất bại.")
                return
            updated = {case.ca_id: case for case in cases}
            with self._lock:
                for case_id, old in (self._cases or {}).items():
                    new = updated.get(case_id)
                    if new is not None and old.model_dump() == new.model_dump():
                        updated[case_id] = old
                        continue
                    self._results.pop(case_id, None)
                    self._persisted_results.pop(case_id, None)
                    self._db_cache.pop(case_id, None)
                    self._ai_cases.discard(case_id)
                    self._ask_sources.pop(case_id, None)
                self._cases = updated
                self._load_errors = [s.LoadError(tep=path, loi=error) for path, error in errors]
                self._next_case_refresh_at = time.monotonic() + ttl
                self._cases_refreshed_at = datetime.now(VN_TZ)
        finally:
            self._refresh_lock.release()

    def _get_case(self, case_id: str) -> CaBenh:
        """Tra mã trong danh sách đã nạp, dưới khóa chung."""
        assert self._cases is not None
        case = self._cases.get(case_id)
        if case is None:
            raise HTTPException(404, "Không tìm thấy ca bệnh.")
        return case

    def _review(self, case: CaBenh) -> KetQuaThamDinh:
        """Tính và giữ kết quả riêng cho mỗi ca."""
        if case.ca_id not in self._results:
            if self._renal_rules is None:
                self._renal_rules = load_renal_rules(self._renal_rules_path)
            ctx = container_mod.get_rule_context()
            self._results[case.ca_id] = run_case(
                case, self._renal_rules, resolver=ctx.resolver, interactions=ctx.interactions
            )
        return self._results[case.ca_id]

    def _prefetch_interactions(self, cases: Sequence[CaBenh]) -> None:
        """Nạp trước toàn bộ cặp DDInter của danh sách ca trong một lượt trước khi chạy luật."""
        if not cases:
            return
        ctx = container_mod.get_rule_context()
        if (
            ctx.resolver is None
            or ctx.interactions is None
            or not hasattr(ctx.interactions, "pairs")
        ):
            return
        needed_pairs = _collect_interaction_pairs(cases, ctx.resolver)
        if not needed_pairs:
            return
        try:
            ctx.interactions.pairs(needed_pairs)
        except Exception as exc:
            _LOGGER.warning("Lỗi nạp lô tương tác DDInter (%s)", type(exc).__name__)

    def list_cases(self) -> s.DanhSachCa:
        """Trả hàng đợi đã sắp xếp, kèm lỗi nạp và phản hồi mới nhất."""
        self._ensure_cases()
        with self._lock:
            assert self._cases is not None
            cases = list(self._cases.values())
            uncached = [case for case in cases if case.ca_id not in self._results]
            if uncached:
                self._prefetch_interactions(uncached)
            results = {case.ca_id: self._review(case) for case in cases}
            queue = present_queue(cases, results, self._store.load_feedback())
            load_errors = self._load_errors
            refreshed_at = self._cases_refreshed_at
        records = self._administrative(cases)
        by_id = {case.ca_id: case for case in cases}
        for row in queue:
            case = by_id[row.ca_id]
            row.chan_doan_chinh = (
                "; ".join(
                    diagnosis.noi_dung for diagnosis in case.chan_doan if diagnosis.loai == "chinh"
                )
                or None
            )
            row.vao_vien = case.dot_dieu_tri.thoi_diem_bat_dau
            record = records.get(case.nguoi_benh.nguoi_benh_id)
            if record is None:
                continue
            row.ho_ten = record.dinh_danh_day_du.ho_ten
            row.ngay_sinh = record.dinh_danh_day_du.ngay_sinh
            encounter = next(
                (
                    item
                    for item in record.lich_su_vao_vien
                    if item.dot_dieu_tri_id == case.dot_dieu_tri.dot_dieu_tri_id
                ),
                None,
            )
            if encounter:
                row.chan_doan_chinh = encounter.chan_doan_chinh
                row.vao_vien = encounter.thoi_diem_bat_dau
                row.so_y_lenh = len(encounter.y_lenh)
        return s.DanhSachCa(
            cases=queue,
            loi_nap=load_errors,
            che_do=self.mode(),
            lam_moi_luc=refreshed_at,
        )

    def get_case(self, case_id: str) -> s.ChiTietCa:
        """Đọc chi tiết cùng bộ đệm thẩm định hiện có, không bị bước AI chặn."""
        self._ensure_cases()
        with self._lock:
            case = self._get_case(case_id)
            rule_result = self._review(case)
            feedbacks = self._store.load_feedback()
            mode = self.mode()
        detail = present_case(
            case,
            rule_result,
            feedbacks,
            che_do=mode,
            ma_tran_tuong_tac=rule_result.ma_tran_tuong_tac,
        )
        medical_future = None
        if isinstance(self._loader, DbReviewService):
            # Hai lần đọc DB độc lập: chạy song song trong nhóm luồng dùng lại.
            admin_future = self._detail_executor.submit(self._administrative, [case])
            medical_future = self._detail_executor.submit(self._read_medical_record, case)
            record = admin_future.result().get(case.nguoi_benh.nguoi_benh_id)
        else:
            record = self._administrative([case]).get(case.nguoi_benh.nguoi_benh_id)
        if record:
            detail.dinh_danh_day_du = record.dinh_danh_day_du
            detail.lich_su_vao_vien = record.lich_su_vao_vien
            encounter = next(
                (
                    item
                    for item in record.lich_su_vao_vien
                    if item.dot_dieu_tri_id == case.dot_dieu_tri.dot_dieu_tri_id
                ),
                None,
            )
            if encounter:
                detail.quan_ly_nguoi_benh = s.PatientManagement.model_validate(
                    encounter.model_dump(include=set(s.PatientManagement.model_fields))
                )
        if medical_future is not None:
            try:
                medical = medical_future.result()
            except DatabaseReadError:
                raise DatabaseReadError("Không thể đọc y lệnh và phiếu điều trị.") from None
            detail.danh_sach_y_lenh = medical.danh_sach_y_lenh
            detail.phieu_dieu_tri = medical.phieu_dieu_tri
        else:
            order = case.y_lenh_cho_duyet
            detail.danh_sach_y_lenh = [
                s.MedicalOrder(
                    y_lenh_id=order.y_lenh_id,
                    dot_dieu_tri_id=case.dot_dieu_tri.dot_dieu_tri_id,
                    thu_tu_dot=1,
                    thoi_diem_ke=order.thoi_diem_ke,
                    trang_thai="cho_duyet",
                    khoa_ke_don=order.khoa_ke_don,
                    luong_duyet=order.luong_duyet,
                    la_trong_tam=True,
                    **detail.chi_tiet.y_lenh.cho_duyet.model_dump(),
                )
            ]
            if case.thuoc_dang_dung and detail.chi_tiet.y_lenh.dang_dung:
                detail.danh_sach_y_lenh.append(
                    s.MedicalOrder(
                        y_lenh_id=f"YL-{case.ca_id}-NEN",
                        dot_dieu_tri_id=case.dot_dieu_tri.dot_dieu_tri_id,
                        thu_tu_dot=1,
                        thoi_diem_ke=min(line.bat_dau for line in case.thuoc_dang_dung),
                        trang_thai="dang_thuc_hien",
                        khoa_ke_don=case.dot_dieu_tri.khoa_dieu_tri,
                        luong_duyet=order.luong_duyet,
                        la_trong_tam=False,
                        **detail.chi_tiet.y_lenh.dang_dung.model_dump(),
                    )
                )
            detail.danh_sach_y_lenh.sort(key=lambda item: (str(item.thoi_diem_ke), item.y_lenh_id))
        self._persist_review_if_needed(case.ca_id, rule_result, detail)
        return detail

    def _persist_review_if_needed(
        self,
        case_id: str,
        rule_result: KetQuaThamDinh,
        detail: s.ChiTietCa,
    ) -> None:
        """Ghi một lần cho mỗi lần chạy luật thật của ca bệnh ở chế độ DB (chạy nền)."""
        if isinstance(self._review_store, NoopReviewResultStore):
            return
        with self._persist_lock:
            if self._shut_down or self._persisted_results.get(case_id) is rule_result:
                return
            self._persisted_results[case_id] = rule_result
            with self._lock:
                renal_rules = self._renal_rules
            self._pending_persists = [item for item in self._pending_persists if not item.done()]
            future = self._persist_executor.submit(
                self._run_persist_review,
                case_id,
                detail,
                renal_rules,
            )
            self._pending_persists.append(future)

    def _run_persist_review(
        self,
        case_id: str,
        detail: s.ChiTietCa,
        renal_rules: RenalRuleBook | None,
    ) -> None:
        """Tính phiên bản luật và ghi kết quả thẩm định trong luồng nền."""
        try:
            che_do, phien_ban_luat = compute_rule_version(
                self._renal_rules_path,
                renal_rules,
                read_conn_factory=getattr(self._review_store, "_read_conn", None),
            )
            self._review_store.save_review(
                ca_id=case_id,
                detail=detail,
                phien_ban_luat=phien_ban_luat,
                che_do=che_do,
            )
        except Exception as exc:
            _LOGGER.warning(
                "Không lưu được kết quả thẩm định ở luồng nền (%s)",
                type(exc).__name__,
            )

    def list_review_history(self, case_id: str) -> s.LichSuThamDinh:
        """Trả danh sách các lần hệ thống đã thẩm định cho ca bệnh."""
        self._ensure_cases()
        with self._lock:
            self._get_case(case_id)
        items = self._review_store.list_history(case_id)
        return s.LichSuThamDinh(ca_id=case_id, lich_su=items)

    def _administrative(self, cases: list[CaBenh]) -> dict[str, s.AdministrativeRecord]:
        """Đọc riêng từng yêu cầu, không gắn vào bộ đệm ca hay kết quả AI."""
        if not isinstance(self._loader, DbReviewService):
            return {}
        patient_ids = sorted({case.nguoi_benh.nguoi_benh_id for case in cases})
        return administrative.read_administrative(patient_ids)

    def _read_medical_record(self, case: CaBenh) -> s.MedicalRecord:
        """Giữ y lệnh và phiếu tối đa 60 giây cho đúng phiên bản ca."""
        now = time.monotonic()
        with self._lock:
            hit = self._db_cache.get(case.ca_id)
            if hit is not None and hit[1] is case and now - hit[0] < _DB_READ_TTL_SECONDS:
                return hit[2]
        value = medical_record.read_medical_record(case.nguoi_benh.nguoi_benh_id, case.ca_id)
        with self._lock:
            if self._cases is not None and self._cases.get(case.ca_id) is case:
                if len(self._db_cache) > 256:
                    self._db_cache.clear()
                self._db_cache[case.ca_id] = (time.monotonic(), case, value)
        return value

    def get_record(self, case_id: str, record_id: str) -> s.BanGhi:
        """Tra bản ghi trong đúng ca mà không truy cập đường dẫn từ người gọi."""
        self._ensure_cases()
        with self._lock:
            record = present_record(self._get_case(case_id), record_id)
            if record is None:
                raise HTTPException(404, "Không tìm thấy bản ghi trong ca bệnh.")
            return record

    def _ai_model_name(self) -> str | None:
        """Lấy tên mô hình AI hiện cấu hình nếu có."""
        if self._synthesizer is not None:
            return self._synthesizer.model_name
        return getattr(self._ai_runner, "model_name", None)

    def _present_job_state(
        self,
        case: CaBenh,
        rule_result: KetQuaThamDinh,
        state: AiJobState,
        feedbacks: list[PhanHoi],
    ) -> s.KetQuaAI:
        """Chuyển trạng thái tác vụ nền sang KetQuaAI kèm danh sách bước tiến trình."""
        if state.trang_thai == "dang_chay":
            base = s.KetQuaAI(
                trang_thai="dang_chay",
                nhan_dinh=None,
                canh_bao=present_warnings(state.canh_bao),
                thoi_gian_ms=None,
                mo_hinh=self._ai_model_name(),
            )
        elif state.trang_thai == "loi":
            base = s.KetQuaAI(
                trang_thai="loi",
                nhan_dinh=None,
                canh_bao=present_warnings(state.canh_bao),
                thoi_gian_ms=None,
                mo_hinh=self._ai_model_name(),
            )
        else:
            assert state.ket_qua is not None
            base = present_ai_result(case, rule_result, state.ket_qua, feedbacks)

        tracker = state.tien_trinh if isinstance(state.tien_trinh, TienTrinh) else None
        if tracker is None:
            return base.model_copy(update={"thuong_le_ms": self._jobs.thuong_le_ms()})

        snapshot_at = state.ket_thuc if state.trang_thai != "dang_chay" else None
        steps = [
            s.BuocAI(
                ma=step.ma,
                ten=step.ten,
                trang_thai=step.trang_thai,
                chi_tiet=step.chi_tiet,
                nguon=[s.NguonTomTat(nhan=item.nhan, so_doan=item.so_doan) for item in step.nguon],
                thoi_gian_ms=step.thoi_gian_ms,
                ly_do=step.ly_do,
                goi_y=step.goi_y,
            )
            for step in tracker.chup(now=snapshot_at)
        ]
        return base.model_copy(
            update={
                "cac_buoc": steps,
                "da_chay_ms": tracker.tong_ms(now=snapshot_at),
                "thuong_le_ms": self._jobs.thuong_le_ms(),
            }
        )

    def _get_ai_state(self, case_id: str) -> AiJobState | None:
        """Chỉ lấy tác vụ AI thuộc phiên bản hiện tại của ca."""
        return self._jobs.get(case_id) if case_id in self._ai_cases else None

    def _log_limit_block(self, code: str, route_path: str, principal: Principal | None) -> None:
        """Ghi log lượt LLM bị chặn với mã lỗi, đường dẫn mẫu và 8 ký tự đầu mã người dùng."""
        user_prefix = principal.nguoi_dung_id[:8] if principal is not None else "anon"
        _LOGGER.warning("llm_rate_limited ma=%s path=%s user=%s", code, route_path, user_prefix)

    def _queue_full_error(self, principal: Principal | None) -> HTTPException:
        """Tạo lỗi 429 khi hàng đợi AI nền đã đạt trần số việc chưa xong."""
        self._log_limit_block("hang_doi_day", "/api/cases/{ca_id}/ai", principal)
        return HTTPException(
            429,
            detail={
                "ma": "hang_doi_day",
                "thong_bao": "Hàng đợi phân tích AI đang bận. Vui lòng thử lại sau 30 giây.",
            },
            headers={"Retry-After": "30"},
        )

    def _enforce_llm_limits(
        self,
        limiter: SlidingWindowLimiter,
        principal: Principal | None,
        route_path: str,
        rate_message: str,
    ) -> None:
        """Kiểm giới hạn tốc độ theo người dùng rồi trừ ngân sách lượt trong ngày."""
        user_key = principal.nguoi_dung_id if principal is not None else "__anonymous__"
        wait = limiter.hit(user_key)
        if wait is not None:
            wait_sec = max(1, math.ceil(wait))
            self._log_limit_block("vuot_gioi_han", route_path, principal)
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
            self._log_limit_block("het_ngan_sach_ngay", route_path, principal)
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

    def start_ai(
        self,
        case_id: str,
        *,
        restart: bool = False,
        principal: Principal | None = None,
    ) -> s.KetQuaAI:
        """Khởi động phân tích AI nền cho một ca hoặc trả trạng thái hiện có."""
        self._ensure_cases()
        with self._lock:
            case = self._get_case(case_id)
            if not self._ai_enabled or self._ai_runner is None:
                return s.KetQuaAI(
                    trang_thai="tat",
                    nhan_dinh=None,
                    canh_bao=[],
                    thoi_gian_ms=None,
                    mo_hinh=None,
                )
            raw_job = self._jobs.get(case_id)
            effective_restart = restart or case_id not in self._ai_cases
            already_running = raw_job is not None and raw_job.trang_thai == "dang_chay"
            will_submit = raw_job is None or (not already_running and effective_restart)
            if will_submit:
                if self._jobs.pending_count() >= self._jobs.max_pending:
                    raise self._queue_full_error(principal)
                self._enforce_llm_limits(
                    self._limits.ai_limiter,
                    principal,
                    "/api/cases/{ca_id}/ai",
                    "Bạn đã yêu cầu phân tích AI quá nhiều lần.",
                )
            rule_result = self._review(case)
            runner = self._ai_runner
            try:
                state = self._jobs.start(
                    case_id,
                    lambda: runner.run(case, rule_result),
                    restart=effective_restart,
                )
            except AiQueueFullError:
                raise self._queue_full_error(principal) from None
            self._ai_cases.add(case_id)
            feedbacks = self._store.load_feedback() if state.trang_thai == "xong" else []
        return self._present_job_state(case, rule_result, state, feedbacks)

    def get_ai(self, case_id: str) -> s.KetQuaAI:
        """Chỉ đọc trạng thái phân tích AI hiện tại của ca."""
        self._ensure_cases()
        with self._lock:
            case = self._get_case(case_id)
            if not self._ai_enabled or self._ai_runner is None:
                return s.KetQuaAI(
                    trang_thai="tat",
                    nhan_dinh=None,
                    canh_bao=[],
                    thoi_gian_ms=None,
                    mo_hinh=None,
                )
            state = self._get_ai_state(case_id)
            if state is None:
                raise HTTPException(
                    404,
                    detail={
                        "ma": "chua_chay",
                        "thong_bao": "Chưa chạy phân tích AI cho ca bệnh này.",
                    },
                )
            rule_result = self._review(case)
            feedbacks = self._store.load_feedback() if state.trang_thai == "xong" else []
        return self._present_job_state(case, rule_result, state, feedbacks)

    def get_source(
        self,
        case_id: str,
        chunk_id: str,
        principal: Principal | None = None,
    ) -> s.DoanNguon:
        """Tra đoạn nguồn đã cấp cho ca bệnh trong phân tích AI hoặc hỏi đáp."""
        if case_id != "__global__":
            self._ensure_cases()
        with self._lock:
            if case_id != "__global__":
                self._get_case(case_id)
            chunk: Chunk | None = None
            state = self._get_ai_state(case_id)
            if state is not None and state.trang_thai == "xong" and state.ket_qua is None:
                chunk = None
            elif state is not None and state.trang_thai == "xong" and state.ket_qua is not None:
                chunk = next(
                    (item for item in state.ket_qua.doan if item.doan_trich_id == chunk_id),
                    None,
                )
            if chunk is None:
                source_key = _ask_source_key(case_id, principal)
                chunk = self._ask_sources.get(source_key, {}).get(chunk_id)
            if chunk is None:
                raise HTTPException(404, "Không tìm thấy đoạn nguồn trong ca bệnh.")
            return present_source(chunk)

    def _find_ai_feedback_target(
        self,
        case: CaBenh,
        rule_result: KetQuaThamDinh,
        target_id: str,
    ) -> tuple[str, int, list[str]] | None:
        """Tìm dòng AI hợp lệ trong kết quả xong gần nhất của ca để ghi nhận phản hồi."""
        state = self._get_ai_state(case.ca_id)
        if state is None or state.trang_thai != "xong" or state.ket_qua is None:
            return None
        presented = present_ai_result(case, rule_result, state.ket_qua, ())
        if presented.trang_thai != "xong" or presented.nhan_dinh is None:
            return None
        valid_ids = {
            row.nhan_dinh_id for row in (*presented.nhan_dinh.can_chu_y, *presented.nhan_dinh.dat)
        }
        if target_id not in valid_ids:
            return None
        for item in state.ket_qua.llm.nhan_dinh:
            if item.nguon_goc == "ai_da_kiem_chung" and item.de_xuat is not None:
                if ai_finding_id(item.de_xuat) == target_id:
                    return (
                        target_id,
                        item.de_xuat.yeu_to,
                        list(item.de_xuat.chi_tiet_y_lenh_id),
                    )
        return None

    def feedback(self, case_id: str, request: s.GuiPhanHoi, principal: Principal) -> s.PhanHoiDaGhi:
        """Kiểm tra nhận định và lý do trước khi ghi phản hồi."""
        self._ensure_cases()
        with self._lock:
            case = self._get_case(case_id)
            rule_result = self._review(case)
            rule_nids = finding_ids(rule_result.phat_hien)
            matched = next(
                (
                    (item, nid)
                    for item, nid in zip(rule_result.phat_hien, rule_nids, strict=True)
                    if nid == request.nhan_dinh_id
                ),
                None,
            )
            ai_line: tuple[str, int, list[str]] | None = None
            if matched is None:
                ai_line = self._find_ai_feedback_target(case, rule_result, request.nhan_dinh_id)
            if matched is None and ai_line is None:
                raise HTTPException(404, "Không tìm thấy nhận định trong ca bệnh.")
            reasons = {label: code for code, label in NHOM_LY_DO.items()}
            if request.phan_hoi in ("bac_bo", "can_sua") and not request.nhom_ly_do:
                raise HTTPException(422, "Cần chọn nhóm lý do.")
            if request.nhom_ly_do is not None and request.nhom_ly_do not in reasons:
                raise HTTPException(422, "Nhóm lý do không hợp lệ.")
            if matched is not None:
                finding, nid = matched
                base_id = finding_id(finding)
                ma_luat = finding.ma_luat if nid == base_id else nid
                yeu_to = finding.yeu_to
                line_ids = list(finding.chi_tiet_y_lenh_id)
            else:
                assert ai_line is not None
                ma_luat, yeu_to, line_ids = ai_line
            item = PhanHoi(
                thoi_diem=datetime.now(UTC),
                ca_id=case_id,
                ma_luat=ma_luat,
                yeu_to=yeu_to,
                chi_tiet_y_lenh_id=line_ids,
                phan_hoi=request.phan_hoi,
                nhom_ly_do=reasons.get(request.nhom_ly_do),
                ly_do=request.ly_do,
                nguoi_dung_id=principal.nguoi_dung_id,
                phien_id=principal.phien_id,
            )
            self._store.save_feedback(item)
            return present_feedback(item)

    def _save_chat_log(
        self, case_id: str, cau_hoi: str, response: s.TraLoi, principal: Principal
    ) -> None:
        """Ghi nhận lượt hỏi đáp vào bộ lưu trữ tệp hoặc DB."""
        self._store.save_chat(
            case_id,
            cau_hoi,
            response.model_dump(mode="json"),
            datetime.now(UTC),
            principal,
        )

    @staticmethod
    def _owns_conversation(item: dict[str, Any], principal: Principal) -> bool:
        """Admin chỉ được thêm quyền với dòng cũ không có chủ."""
        owner = item.get("nguoi_dung_id")
        if owner is not None and not isinstance(owner, str):
            return False
        return owns_conversation(owner, principal)

    def list_conversations(self, principal: Principal) -> dict[str, list[dict[str, object]]]:
        """Đọc lịch sử hội thoại đã lưu theo từng phạm vi, phạm vi hoạt động gần nhất đứng đầu."""
        with self._lock:
            return self._store.list_conversations(principal)

    def clear_conversation(self, case_id: str, principal: Principal) -> None:
        """Xoá các lượt hội thoại của một phạm vi thuộc người gọi."""
        with self._lock:
            self._store.clear_conversation(case_id, principal)

    def _server_history_pairs(
        self,
        case_id: str,
        principal: Principal,
        *,
        max_turns: int = 3,
        max_messages: int = 6,
        max_chars: int = 4000,
    ) -> list[tuple[str, str]]:
        """Dựng tối đa 6 tin lịch sử từ các lượt gần nhất của chính người gọi trên máy chủ."""
        turns = self._store.recent_turns(case_id, principal, limit=max_turns)
        pairs: list[tuple[str, str]] = []
        for cau_hoi, tra_loi in turns:
            pairs.append(("nguoi_dung", cau_hoi[:max_chars]))
            pairs.append(("he_thong", tra_loi[:max_chars]))
        return pairs[-max_messages:]

    def ask(self, case_id: str, request: s.GuiCauHoi, principal: Principal) -> s.TraLoi:
        """Gọi CaseAsker khi có LLM; hỗ trợ cả hỏi đáp chung (__global__) và theo từng ca."""
        self._ensure_cases()
        if case_id == "__global__":
            with self._lock:
                assert self._cases is not None
                all_cases = list(self._cases.values())
                all_results = {c.ca_id: self._review(c) for c in all_cases}
                asker = self._asker_impl
                enabled = self._ai_enabled and asker is not None
                history_pairs = self._server_history_pairs(case_id, principal)
            if not enabled or asker is None or not hasattr(asker, "ask_global"):
                fallback_case = all_cases[0] if all_cases else None
                msg = (
                    self._ask.ask(fallback_case, request.cau_hoi, history_pairs).noi_dung
                    if fallback_case is not None
                    else "Chức năng hỏi thêm chưa được nối với hệ thống."
                )
                response = s.TraLoi(
                    trang_thai="chua_san_sang",
                    noi_dung=msg,
                    trich_dan=[],
                    cong_cu_da_goi=[],
                    thoi_gian_ms=0,
                )
                with self._lock:
                    self._save_chat_log(case_id, request.cau_hoi, response, principal)
                return response
            self._enforce_llm_limits(
                self._limits.ask_limiter,
                principal,
                "/api/ask",
                "Bạn đã gửi quá nhiều câu hỏi.",
            )
            result = asker.ask_global(all_cases, all_results, request.cau_hoi, history_pairs)
        else:
            with self._lock:
                case = self._get_case(case_id)
                history_pairs = self._server_history_pairs(case_id, principal)
                if not self._ai_enabled or self._asker_impl is None:
                    _LOGGER.info(
                        "ask rejected step=configuration reason=missing_llm_or_asker chunks=0"
                    )
                    reply = self._ask.ask(
                        case,
                        request.cau_hoi,
                        history_pairs,
                    )
                    response = s.TraLoi(
                        trang_thai=reply.trang_thai,
                        noi_dung=reply.noi_dung,
                        trich_dan=[],
                        cong_cu_da_goi=[],
                        thoi_gian_ms=0,
                    )
                    self._save_chat_log(case_id, request.cau_hoi, response, principal)
                    return response
                rule_result = self._review(case)
                state = self._get_ai_state(case_id)
                ai_result = (
                    state.ket_qua if state is not None and state.trang_thai == "xong" else None
                )
                asker = self._asker_impl

            self._enforce_llm_limits(
                self._limits.ask_limiter,
                principal,
                "/api/cases/{ca_id}/ask",
                "Bạn đã gửi quá nhiều câu hỏi.",
            )
            result = asker.ask(
                case,
                request.cau_hoi,
                history_pairs,
                ket_qua=rule_result,
                ai_result=ai_result,
                nhan_dinh_id=request.nhan_dinh_id,
            )

        if result.trang_thai == "ok" and result.doan:
            with self._lock:
                assert self._cases is not None
                if case_id == "__global__" or self._cases.get(case_id) is case:
                    source_key = _ask_source_key(case_id, principal)
                    case_sources = self._ask_sources.setdefault(source_key, {})
                    for chunk in result.doan:
                        if chunk.doan_trich_id in case_sources:
                            del case_sources[chunk.doan_trich_id]
                        case_sources[chunk.doan_trich_id] = chunk
                        while len(case_sources) > _MAX_ASK_SOURCES_PER_KEY:
                            del case_sources[next(iter(case_sources))]

        response = s.TraLoi(
            trang_thai=result.trang_thai,
            noi_dung=result.noi_dung,
            trich_dan=[
                s.Citation(
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
        with self._lock:
            self._save_chat_log(case_id, request.cau_hoi, response, principal)
        return response
