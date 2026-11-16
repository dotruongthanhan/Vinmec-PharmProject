"""Dịch vụ ca bệnh giữ bộ đệm thẩm định, điều phối AI nền và ghi phản hồi JSONL."""

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
from app.config.settings import get_secret
from app.core.errors import ConfigError
from app.domain.models import CaBenh
from app.feedback import PhanHoi, load_feedback, save_feedback
from app.kb.names import DrugNameIndex
from app.llm import setup as llm_setup
from app.llm.synthesizer import Synthesizer
from app.orchestration.ai_review import AiReviewer, AiRunResult
from app.orchestration.evidence import EvidenceCollector, LazyRetrieverFactory
from app.orchestration.jobs import AiJobManager, AiJobState
from app.pipeline import KetQuaThamDinh, run_case
from app.retrieval.query_builder import QueryBuilder
from app.rules import RenalRuleBook, load_renal_rules
from app.ui.labels import NHOM_LY_DO
from app.ui.services import NotReadyAskService, PipelineReviewService

_AUTO = object()
_ROOT = Path(__file__).resolve().parents[2]


class AiRunner(Protocol):
    """Giao diện tối thiểu của bộ chạy AI để tiêm bản giả khi kiểm thử."""

    def run(self, ca: CaBenh, ket_qua: KetQuaThamDinh) -> AiRunResult: ...


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
        self._synthesizer: Synthesizer | None = None
        self._retriever_factory: LazyRetrieverFactory | None = None
        if ai_runner is _AUTO:
            self._ai_runner: AiRunner | None = self._build_default_ai_runner()
        else:
            self._ai_runner = ai_runner
        self._ai_enabled = self._ai_runner is not None

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

    def mode(self) -> s.CheDo:
        """Trả chế độ vận hành hiện tại của dịch vụ."""
        return current_mode(
            co_llm=self._ai_enabled,
            has_corpus=self._corpus_path.is_file(),
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
        """Tra đoạn nguồn đã cấp cho ca bệnh trong lần phân tích gần nhất."""
        with self._lock:
            self._get_case(case_id)
            state = self._jobs.get(case_id)
            if state is None or state.trang_thai != "xong" or state.ket_qua is None:
                raise HTTPException(404, "Không tìm thấy đoạn nguồn trong ca bệnh.")
            chunk = next(
                (item for item in state.ket_qua.doan if item.doan_trich_id == chunk_id),
                None,
            )
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
            row.nhan_dinh_id
            for row in (*presented.nhan_dinh.can_chu_y, *presented.nhan_dinh.dat)
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

    def feedback(self, case_id: str, request: s.GuiPhanHoi) -> s.PhanHoiDaGhi:
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
            )
            save_feedback(item, self._feedback_path)
            return present_feedback(item)

    def ask(self, case_id: str, request: s.GuiCauHoi) -> s.TraLoi:
        """Dùng dịch vụ hỏi thêm chưa sẵn sàng, không gọi mạng hay LLM."""
        with self._lock:
            reply = self._ask.ask(
                self._get_case(case_id),
                request.cau_hoi,
                [(item.vai, item.noi_dung) for item in request.lich_su],
            )
            return s.TraLoi(
                trang_thai=reply.trang_thai,
                noi_dung=reply.noi_dung,
                trich_dan=[
                    s.Citation(
                        so=item.so,
                        loai_ma=item.loai,
                        nhan=item.nhan,
                        ban_ghi_id=item.ban_ghi_id,
                    )
                    for item in reply.trich_dan
                ],
                cong_cu_da_goi=reply.cong_cu_da_goi,
            )
