"""Dịch vụ ca bệnh giữ bộ đệm thẩm định, điều phối AI nền và ghi phản hồi JSONL."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from fastapi import HTTPException

from app import container as container_mod
from app.api import schemas as s
from app.api.presenter import (
    ai_finding_id,
    current_mode,
    finding_id,
    present_ai_result,
    present_case,
    present_feedback,
    present_queue,
    present_record,
    present_source,
    present_warnings,
)
from app.auth.principal import Principal
from app.auth.roles import ADMIN
from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.core.types import Chunk
from app.domain.models import CaBenh
from app.feedback import PhanHoi, load_feedback, save_feedback
from app.kb.names import DrugNameIndex
from app.llm import setup as llm_setup
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.ask import AskResult, CaseAsker
from app.orchestration.evidence import EvidenceCollector, LazyRetrieverFactory
from app.orchestration.jobs import AiJobManager, AiJobState
from app.pipeline import KetQuaThamDinh, run_case
from app.retrieval.query_builder import QueryBuilder
from app.rules import RenalRuleBook, load_renal_rules
from app.ui.labels import NHOM_LY_DO
from app.ui.services import NotReadyAskService, PipelineReviewService

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


def _is_ai_disabled() -> bool:
    """Đọc cờ tắt AI qua lớp cấu hình tập trung, không đọc .env trực tiếp."""
    try:
        return get_secret("CDSS_AI").strip().lower() == "off"
    except ConfigError:
        return False


class CaseService:
    """Nạp danh sách cố định và chỉ tính kết quả mỗi ca một lần."""

    def __init__(
        self,
        case_dir: Path,
        renal_rules_path: Path,
        feedback_path: Path,
        *,
        ai_runner: Any = _AUTO,
        corpus_path: Path | None = None,
        asker: Any = _AUTO,
    ) -> None:
        self._loader = PipelineReviewService(case_dir, renal_rules_path)
        self._renal_rules_path = Path(renal_rules_path)
        self._feedback_path = Path(feedback_path)
        self._corpus_path = (
            Path(corpus_path) if corpus_path is not None else _ROOT / "data/kb_curated/chunks.jsonl"
        )
        self._cases: dict[str, CaBenh] | None = None
        self._load_errors: list[s.LoadError] = []
        self._results: dict[str, KetQuaThamDinh] = {}
        self._renal_rules: RenalRuleBook | None = None
        self._ask = NotReadyAskService()
        self._lock = RLock()
        self._jobs = AiJobManager()
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
        if self._corpus_path.is_file():
            self._retriever_factory = LazyRetrieverFactory(container, self._corpus_path)
            retriever: LazyRetrieverFactory | None = self._retriever_factory
        else:
            retriever = None
        names = DrugNameIndex.load(_ROOT / "data/kb/hoat_chat.json")
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
        names = DrugNameIndex.load(_ROOT / "data/kb/hoat_chat.json")
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
        return current_mode(
            co_llm=self._ai_enabled,
            has_corpus=self._corpus_path.is_file(),
            hoi_them=self._ai_enabled and self._asker_impl is not None,
        )

    def shutdown(self) -> None:
        """Đóng bộ chạy nền AI và máy khách HTTP dùng chung nếu có."""
        self._jobs.shutdown()
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

    def _get_case(self, case_id: str) -> CaBenh:
        """Tra mã trong danh sách đã nạp, không tạo đường dẫn từ mã."""
        if self._cases is None:
            cases, errors = self._loader.list_cases()
            self._cases = {case.ca_id: case for case in cases}
            self._load_errors = [s.LoadError(tep=path, loi=error) for path, error in errors]
        case = self._cases.get(case_id)
        if case is None:
            raise HTTPException(404, "Không tìm thấy ca bệnh.")
        return case

    def _review(self, case: CaBenh) -> KetQuaThamDinh:
        """Tính và giữ kết quả riêng cho mỗi ca."""
        if case.ca_id not in self._results:
            if self._renal_rules is None:
                self._renal_rules = load_renal_rules(self._renal_rules_path)
            self._results[case.ca_id] = run_case(case, self._renal_rules)
        return self._results[case.ca_id]

    def list_cases(self) -> s.DanhSachCa:
        """Trả hàng đợi đã sắp xếp, kèm lỗi nạp và phản hồi mới nhất."""
        with self._lock:
            if self._cases is None:
                cases, errors = self._loader.list_cases()
                self._cases = {case.ca_id: case for case in cases}
                self._load_errors = [s.LoadError(tep=path, loi=error) for path, error in errors]
            cases = list(self._cases.values())
            results = {case.ca_id: self._review(case) for case in cases}
            return s.DanhSachCa(
                cases=present_queue(cases, results, load_feedback(self._feedback_path)),
                loi_nap=self._load_errors,
                che_do=self.mode(),
            )

    def get_case(self, case_id: str) -> s.ChiTietCa:
        """Đọc chi tiết cùng bộ đệm thẩm định hiện có, không bị bước AI chặn."""
        with self._lock:
            case = self._get_case(case_id)
            rule_result = self._review(case)
            feedbacks = load_feedback(self._feedback_path)
            mode = self.mode()
        return present_case(case, rule_result, feedbacks, che_do=mode)

    def get_record(self, case_id: str, record_id: str) -> s.BanGhi:
        """Tra bản ghi trong đúng ca mà không truy cập đường dẫn từ người gọi."""
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
        """Chuyển trạng thái tác vụ nền sang KetQuaAI."""
        if state.trang_thai == "dang_chay":
            return s.KetQuaAI(
                trang_thai="dang_chay",
                nhan_dinh=None,
                canh_bao=present_warnings(state.canh_bao),
                thoi_gian_ms=None,
                mo_hinh=self._ai_model_name(),
            )
        if state.trang_thai == "loi":
            return s.KetQuaAI(
                trang_thai="loi",
                nhan_dinh=None,
                canh_bao=present_warnings(state.canh_bao),
                thoi_gian_ms=None,
                mo_hinh=self._ai_model_name(),
            )
        assert state.ket_qua is not None
        return present_ai_result(case, rule_result, state.ket_qua, feedbacks)

    def start_ai(self, case_id: str, *, restart: bool = False) -> s.KetQuaAI:
        """Khởi động phân tích AI nền cho một ca hoặc trả trạng thái hiện có."""
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
            rule_result = self._review(case)
            runner = self._ai_runner
            state = self._jobs.start(
                case_id,
                lambda: runner.run(case, rule_result),
                restart=restart,
            )
            feedbacks = load_feedback(self._feedback_path) if state.trang_thai == "xong" else []
        return self._present_job_state(case, rule_result, state, feedbacks)

    def get_ai(self, case_id: str) -> s.KetQuaAI:
        """Chỉ đọc trạng thái phân tích AI hiện tại của ca."""
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
            state = self._jobs.get(case_id)
            if state is None:
                raise HTTPException(
                    404,
                    detail={
                        "ma": "chua_chay",
                        "thong_bao": "Chưa chạy phân tích AI cho ca bệnh này.",
                    },
                )
            rule_result = self._review(case)
            feedbacks = load_feedback(self._feedback_path) if state.trang_thai == "xong" else []
        return self._present_job_state(case, rule_result, state, feedbacks)

    def get_source(self, case_id: str, chunk_id: str) -> s.DoanNguon:
        """Tra đoạn nguồn đã cấp cho ca bệnh trong phân tích AI hoặc hỏi đáp."""
        with self._lock:
            if case_id != "__global__":
                self._get_case(case_id)
            chunk: Chunk | None = None
            state = self._jobs.get(case_id) if case_id != "__global__" else None
            if state is not None and state.trang_thai == "xong" and state.ket_qua is None:
                chunk = None
            elif state is not None and state.trang_thai == "xong" and state.ket_qua is not None:
                chunk = next(
                    (item for item in state.ket_qua.doan if item.doan_trich_id == chunk_id),
                    None,
                )
            if chunk is None:
                chunk = self._ask_sources.get(case_id, {}).get(chunk_id)
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
        state = self._jobs.get(case.ca_id)
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
        with self._lock:
            case = self._get_case(case_id)
            rule_result = self._review(case)
            finding = next(
                (
                    item
                    for item in rule_result.phat_hien
                    if finding_id(item) == request.nhan_dinh_id
                ),
                None,
            )
            ai_line: tuple[str, int, list[str]] | None = None
            if finding is None:
                ai_line = self._find_ai_feedback_target(case, rule_result, request.nhan_dinh_id)
            if finding is None and ai_line is None:
                raise HTTPException(404, "Không tìm thấy nhận định trong ca bệnh.")
            reasons = {label: code for code, label in NHOM_LY_DO.items()}
            if request.phan_hoi in ("bac_bo", "can_sua") and not request.nhom_ly_do:
                raise HTTPException(422, "Cần chọn nhóm lý do.")
            if request.nhom_ly_do is not None and request.nhom_ly_do not in reasons:
                raise HTTPException(422, "Nhóm lý do không hợp lệ.")
            if finding is not None:
                ma_luat = finding.ma_luat
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
            save_feedback(item, self._feedback_path)
            return present_feedback(item)

    def _save_chat_log(
        self, case_id: str, cau_hoi: str, response: s.TraLoi, principal: Principal
    ) -> None:
        """Ghi nhận lượt hỏi đáp vào tệp JSONL cục bộ để lưu vết hội thoại."""
        try:
            chat_path = self._feedback_path.parent / "hoi_thoai.jsonl"
            chat_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "thoi_diem": datetime.now(UTC).isoformat(),
                "ca_id": case_id,
                "cau_hoi": cau_hoi,
                "tra_loi": response.model_dump(mode="json"),
                "nguoi_dung_id": principal.nguoi_dung_id,
                "phien_id": principal.phien_id,
            }
            with chat_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    @staticmethod
    def _owns_conversation(item: dict[str, Any], principal: Principal) -> bool:
        """Admin chỉ được thêm quyền với dòng cũ không có chủ."""
        owner = item.get("nguoi_dung_id")
        return owner == principal.nguoi_dung_id or (owner is None and principal.vai_tro == ADMIN)

    def list_conversations(self, principal: Principal) -> dict[str, list[dict[str, object]]]:
        """Đọc lịch sử hội thoại đã lưu theo từng phạm vi, phạm vi hoạt động gần nhất đứng đầu."""
        with self._lock:
            chat_path = self._feedback_path.parent / "hoi_thoai.jsonl"
            if not chat_path.is_file():
                return {}
            grouped: dict[str, list[dict[str, object]]] = {}
            last_seen: dict[str, str] = {}
            try:
                for raw_line in chat_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict) or not self._owns_conversation(item, principal):
                        continue
                    ca_id = str(item.get("ca_id") or "")
                    cau_hoi = str(item.get("cau_hoi") or "")
                    tra_loi = item.get("tra_loi")
                    thoi_diem = str(item.get("thoi_diem") or "")
                    if ca_id and cau_hoi and isinstance(tra_loi, dict):
                        grouped.setdefault(ca_id, []).append(
                            {"cau_hoi": cau_hoi, "tra_loi": tra_loi, "thoi_diem": thoi_diem}
                        )
                        last_seen[ca_id] = max(last_seen.get(ca_id, ""), thoi_diem)
            except (OSError, ValueError):
                return {}
            ordered = sorted(grouped, key=lambda key: last_seen.get(key, ""), reverse=True)
            return {key: grouped[key] for key in ordered}

    def clear_conversation(self, case_id: str, principal: Principal) -> None:
        """Xoá các lượt hội thoại của một phạm vi khỏi tệp JSONL."""
        with self._lock:
            chat_path = self._feedback_path.parent / "hoi_thoai.jsonl"
            if not chat_path.is_file():
                return
            try:
                kept: list[str] = []
                for raw_line in chat_path.read_text(encoding="utf-8").splitlines():
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except ValueError:
                        kept.append(line)
                        continue
                    if (
                        not isinstance(item, dict)
                        or str(item.get("ca_id") or "") != case_id
                        or not self._owns_conversation(item, principal)
                    ):
                        kept.append(line)
                content = ("\n".join(kept) + "\n") if kept else ""
                chat_path.write_text(content, encoding="utf-8")
            except OSError:
                pass

    def ask(self, case_id: str, request: s.GuiCauHoi, principal: Principal) -> s.TraLoi:
        """Gọi CaseAsker khi có LLM; hỗ trợ cả hỏi đáp chung (__global__) và theo từng ca."""
        history_pairs = [(item.vai, item.noi_dung) for item in request.lich_su]
        if case_id == "__global__":
            with self._lock:
                if self._cases is None:
                    cases_list, errors = self._loader.list_cases()
                    self._cases = {c.ca_id: c for c in cases_list}
                    self._load_errors = [s.LoadError(tep=p, loi=e) for p, e in errors]
                all_cases = list(self._cases.values())
                all_results = {c.ca_id: self._review(c) for c in all_cases}
                asker = self._asker_impl
                enabled = self._ai_enabled and asker is not None
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
            result = asker.ask_global(all_cases, all_results, request.cau_hoi, history_pairs)
        else:
            with self._lock:
                case = self._get_case(case_id)
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
                state = self._jobs.get(case_id)
                ai_result = (
                    state.ket_qua if state is not None and state.trang_thai == "xong" else None
                )
                asker = self._asker_impl

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
                case_sources = self._ask_sources.setdefault(case_id, {})
                for chunk in result.doan:
                    case_sources[chunk.doan_trich_id] = chunk

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
