"""Điều phối hỏi đáp theo ca bệnh đang mở kèm che định danh, truy xuất và kiểm chứng."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextlib import nullcontext
from contextvars import copy_context
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NoReturn

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.minh_hoa.models import KhoiMinhHoa
from app.config.settings import CaseContextSettings
from app.core.errors import ProviderError
from app.core.interfaces import LLMClient, Retriever
from app.core.progress import NguonTomTat, ghi_buoc, tien_trinh_hien_tai
from app.core.types import ChatMessage, Chunk, RetrievalQuery, ScoredChunk, SearchFilter
from app.deid.known import GiaTriDinhDanh
from app.deid.scrubber import TOKEN_PATTERN, DeidError, restore_text, scrub_text
from app.deid.session import DeidSession
from app.domain.loader import ingredients_of
from app.domain.models import CaBenh, ChiTietYLenh
from app.llm.case_context import (
    RecordIdMap,
    build_case_bundle,
    open_deid_session,
)
from app.llm.prompt_loader import load_prompt
from app.orchestration.ai_review import AiRunResult
from app.orchestration.evidence import LazyRetrieverFactory
from app.pipeline import KetQuaThamDinh, run_case
from app.retrieval.query_builder import QueryBuilder
from app.rules import RenalRuleBook, load_renal_rules
from app.tracing import (
    bat_dau_vet,
    che_chu_so_ma_ly_do,
    dong_buoc_node_dang_chay,
    ghi_su_kien_bao_mat,
    goi_llm_co_vet,
    span,
    vet_hien_tai,
)
from app.ui import labels
from app.ui import view_model as vm
from app.verify.citation import quote_matches_source
from app.verify.number import mask_citation_markers, numbers_in_text, unverified_numbers

MAX_HISTORY_MESSAGES = 6
MAX_ASK_CHUNKS = 6
DEFAULT_ASK_TIMEOUT_SECONDS = 45.0
_LOGGER = logging.getLogger(__name__)

NO_SOURCE_MESSAGE = (
    "Không đủ căn cứ trong dữ liệu ca bệnh và kho nguồn hiện có để trả lời chắc chắn "
    "câu hỏi này. Dược sĩ vui lòng đối chiếu trực tiếp hồ sơ và tài liệu chuyên môn."
)
OUT_OF_SCOPE_MESSAGE = (
    "Câu hỏi nằm ngoài phạm vi hỗ trợ của hệ thống cho ca bệnh đang mở hoặc yêu cầu xử lý "
    "ngoài vai trò tham khảo. Hệ thống chỉ giải đáp dựa trên hồ sơ ca và tài liệu chuyên môn."
)
ERROR_MESSAGE = (
    "Đã xảy ra lỗi hoặc quá thời gian khi xử lý câu hỏi. Dược sĩ vui lòng thử lại hoặc "
    "xem trực tiếp bảng nhận định bên trái."
)
NOT_READY_MESSAGE = (
    "Chức năng hỏi thêm chưa được nối với hệ thống. Bảng nhận định bên trái vẫn dùng được."
)

_ROOT = Path(__file__).resolve().parents[2]
_MAX_SOURCE_GROUPS = 8
_ASK_RETRY_HINT = "Bấm Thử lại sau ít phút"
_DATA_SPLIT_MARKER = "\n## DỮ LIỆU ĐẦU VÀO\n"
_FALLBACK_SYSTEM_PROMPT = "Bạn là trợ lý hỗ trợ dược sĩ lâm sàng giải đáp về ca bệnh đang mở."
_ROLE_LABELS = {"nguoi_dung": "Dược sĩ", "he_thong": "Hệ thống"}
_SOURCE_LABELS: dict[str, str] = {
    "openfda": "Nhãn FDA",
    "openfda_drug_label": "Nhãn FDA",
    "byt": "Hướng dẫn Bộ Y tế",
    "van_ban_byt": "Văn bản Bộ Y tế",
    "duoc_thu": "Dược thư Quốc gia",
}
_BLOCK_MARKERS = (
    "<<<DU_LIEU_BENH_AN",
    "DU_LIEU_BENH_AN>>>",
    "<<<DOAN_NGUON",
    "DOAN_NGUON>>>",
    "<<<LICH_SU",
    "LICH_SU>>>",
    "<<<CAU_HOI",
    "CAU_HOI>>>",
)
_DEID_TOKEN_RE = re.compile(TOKEN_PATTERN)
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_SCRUB_FALLBACK = "[không đưa được vào vì lỗi che định danh]"
_CITATION_REF_RE = re.compile(r"\[(\d+)\]")
_CLINICAL_QUESTION_RE = re.compile(
    r"\b(?:thuốc|liều|tương\s+tác|xét\s+nghiệm|creatinin|crcl|egfr|"
    r"hoạt\s+chất|kháng\s+sinh|dị\s+ứng|dose|dosage|drug|interaction)\b",
    re.IGNORECASE,
)
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<<<\s*(?:DU_LIEU_BENH_AN|DOAN_NGUON|LICH_SU|CAU_HOI)\b", re.IGNORECASE),
    re.compile(r"\b(?:DU_LIEU_BENH_AN|DOAN_NGUON|LICH_SU|CAU_HOI)\s*>>>", re.IGNORECASE),
    re.compile(
        r"\bbỏ\s+qua\s+(?:mọi|tất\s+cả|các)?\s*(?:hướng\s+dẫn|quy\s+tắc|chỉ\s+thị|lệnh)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ignore|disregard|forget)\s+"
        r"(?:(?:all|any|the|previous|prior|above|earlier|your|these|those)\s+){0,4}"
        r"(?:instructions|rules|directions)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:ghi|báo|kết\s+luận|xác\s+nhận)\s+(?:là\s+|đơn\s+(?:này\s+)?)?đạt\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:tự\s+động\s+)?(?:duyệt|phê\s+duyệt|kê\s+đơn)\s+(?:thay|giúp)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:hãy|vui\s+lòng|giúp\s+tôi|(?:muốn|cần)\s+(?:bạn|hệ\s+thống)|"
        r"(?:bạn|hệ\s+thống)\s+có\s+thể)\s+(?:tự\s+động\s+)?"
        r"(?:duyệt|phê\s+duyệt|kê)\s+(?:đơn|y\s+lệnh)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:duyệt|phê\s+duyệt|kê)\s+(?:đơn|y\s+lệnh)\b[^?.!\n]{0,80}"
        r"\b(?:giúp|thay|cho)\s+(?:tôi|dược\s+sĩ)\b",
        re.IGNORECASE,
    ),
)
_OVERRIDE_OUTPUT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:ghi|kết\s+luận)\s+là\s+đạt\b", re.IGNORECASE),
    re.compile(r"\b(?:tự\s+động\s+duyệt|đã\s+duyệt\s+đơn)\b", re.IGNORECASE),
)

IngredientResolver = Callable[[str], Sequence[str] | str | None]


class AskVerificationError(ValueError):
    """Giữ lỗi cụ thể để yêu cầu LLM sửa toàn bộ câu trả lời đúng một lần."""


_AskVerificationError = AskVerificationError


@dataclass(frozen=True)
class NguCanhCa:
    """Ngữ cảnh ca bệnh đã chạy bộ luật, che định danh và tổng hợp chuỗi cho LLM."""

    active_result: KetQuaThamDinh
    van_ban_ca: str
    ids: RecordIdMap
    anh_xa: dict[str, str]
    allowed_record_ids: set[str]
    allowed_calc_ids: set[str]
    allowed_numbers: list[float]
    priority_chunk_ids: set[str]


def _log_rejection(step: str, reason: str, chunks: int = 0) -> str:
    """Ghi bước loại và trả lý do đã che định danh để dùng lại khi thử lại LLM."""
    try:
        safe_reason = scrub_text(_DEID_TOKEN_RE.sub("[đã che định danh]", reason)).van_ban
    except DeidError:
        safe_reason = "diagnostic_redacted"
    log_reason = che_chu_so_ma_ly_do(reason)
    try:
        log_reason = scrub_text(_DEID_TOKEN_RE.sub("[đã che định danh]", log_reason)).van_ban
    except DeidError:
        log_reason = "diagnostic_redacted"
    _LOGGER.info("ask rejected step=%s reason=%s chunks=%s", step, log_reason, chunks)
    return safe_reason


def _summarize_sources(chunks: Sequence[Chunk]) -> tuple[str, list[NguonTomTat]]:
    """Tóm tắt số đoạn và nhóm nguồn công khai cho bước truy xuất."""
    if not chunks:
        return "0 đoạn từ 0 nguồn", []
    counts = Counter(chunk.nguon for chunk in chunks)
    top_groups = sorted(
        counts.items(),
        key=lambda item: (-item[1], _source_label(item[0])),
    )[:_MAX_SOURCE_GROUPS]
    nguon = [NguonTomTat(nhan=_source_label(code), so_doan=count) for code, count in top_groups]
    return f"{len(chunks)} đoạn từ {len(counts)} nguồn", nguon


def _ask_error_reason(exc: Exception) -> str:
    """Rút gọn ngoại lệ thành mã lý do ngắn gọn, không lộ dữ liệu nhạy cảm."""
    reason = type(exc).__name__
    if isinstance(exc, ProviderError):
        message = str(exc)
        if message == "Lỗi kết nối nhà cung cấp":
            return "provider_connection_error"
        if message in {"dau_ra_khong_hop_le", "het_han_muc_token"}:
            return message
        if match := re.match(r"HTTP (\d{3}):", message):
            return f"provider_http_status={match.group(1)}"
    return reason


def _safe_step_error_message(reason: str) -> str:
    """Đổi mã lỗi đã lọc sang lý do tiếng Việt an toàn cho dược sĩ."""
    if reason == "het_han_muc_token":
        return "Vượt hạn mức độ dài"
    if reason == "provider_connection_error":
        return "Không kết nối được nhà cung cấp mô hình"
    return "Không soạn được câu trả lời"


def _mark_running_step_error(fallback_step: str, reason: str) -> None:
    """Đánh dấu bước đang chạy là lỗi với lý do và gợi ý an toàn."""
    dong_buoc_node_dang_chay(loai_ngoai_le=reason)
    tracker = tien_trinh_hien_tai.get()
    if tracker is None:
        return
    step_id = tracker.dang_chay_ma() or fallback_step
    tracker.loi(
        step_id,
        ly_do=_safe_step_error_message(reason),
        goi_y=_ASK_RETRY_HINT,
    )


class AskCitationRaw(BaseModel):
    """Mục trích dẫn thô do LLM trả về trước khi đối chiếu."""

    model_config = ConfigDict(extra="forbid")

    so: int
    loai: Literal["du_lieu_ca", "tinh_toan", "tai_lieu", "bang"]
    ma: str
    trich_nguyen_van: str | None = None


class AskLLMOutput(BaseModel):
    """Đầu ra JSON mong đợi từ LLM ở luồng hỏi đáp."""

    model_config = ConfigDict(extra="forbid")

    pham_vi: Literal["trong", "ngoai"]
    tra_loi: str
    trich_dan: list[AskCitationRaw] = Field(default_factory=list)


class AskCitation(BaseModel):
    """Trích dẫn đã kiểm chứng sẵn sàng chuyển sang hợp đồng API v1.2."""

    model_config = ConfigDict(extra="forbid")

    so: int
    loai_ma: Literal["du_lieu", "tinh_toan", "tai_lieu"]
    nhan: str
    ban_ghi_id: str | None = None
    doan_trich_id: str | None = None
    trich_nguyen_van: str | None = None


class AskResult(BaseModel):
    """Kết quả đầy đủ của một lượt hỏi đáp theo ca."""

    model_config = ConfigDict(extra="forbid")

    trang_thai: Literal["chua_san_sang", "ok", "khong_co_nguon", "ngoai_pham_vi", "loi"]
    noi_dung: str
    trich_dan: list[AskCitation] = Field(default_factory=list)
    cong_cu_da_goi: list[str] = Field(default_factory=list)
    thoi_gian_ms: int = 0
    doan: list[Chunk] = Field(default_factory=list)
    ma_vet: str | None = None
    minh_hoa: list[KhoiMinhHoa] = Field(default_factory=list, max_length=3)


def _source_label(nguon: str) -> str:
    """Đổi mã nguồn đoạn trích sang nhãn tiếng Việt."""
    return _SOURCE_LABELS.get(nguon, nguon.replace("_", " "))


def _ai_finding_id(yeu_to: int, nhan_xet: str, chi_tiet_y_lenh_id: Sequence[str]) -> str:
    """Tạo mã nhận định ổn định cho dòng do AI đề xuất."""
    line_ids = ",".join(sorted(chi_tiet_y_lenh_id))
    raw = f"{yeu_to}|{nhan_xet}|{line_ids}".encode()
    return "ai|" + hashlib.sha256(raw).hexdigest()[:12]


def _sanitize_markers(text: str) -> str:
    """Loại bỏ các chuỗi phân tách khối dữ liệu khỏi văn bản không tin cậy."""
    cleaned = text
    for marker in _BLOCK_MARKERS:
        while marker in cleaned:
            cleaned = cleaned.replace(marker, "[đã bỏ ký hiệu]")
    return cleaned


def _normalize_resolved(raw: Sequence[str] | str | None) -> list[str]:
    """Chuẩn hoá danh sách mã hoạt chất trả về từ bộ tra cứu tên thuốc."""
    if raw is None:
        return []
    if isinstance(raw, str):
        cleaned = raw.strip()
        return [cleaned] if cleaned else []
    seen: list[str] = []
    for item in raw:
        cleaned = str(item).strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _has_injection_directive(text: str) -> bool:
    """Phát hiện câu hỏi chứa chỉ thị vượt quyền hoặc ép duyệt đơn."""
    if any(pattern.search(text) for pattern in _INJECTION_PATTERNS):
        return True
    stripped = _ZERO_WIDTH_RE.sub("", text)
    return stripped != text and any(pattern.search(stripped) for pattern in _INJECTION_PATTERNS)


def _output_attempts_override(reply_text: str, ket_qua: KetQuaThamDinh) -> bool:
    """Chặn câu trả lời tự duyệt đơn hoặc khẳng định đạt trái phát hiện cần xem."""
    if any(pattern.search(reply_text) for pattern in _OVERRIDE_OUTPUT_PATTERNS):
        return True
    has_attention = any(ph.ket_luan != "dat" for ph in ket_qua.phat_hien)
    if has_attention and re.search(r"\bđơn\s+(?:này\s+)?đạt\b", reply_text, re.IGNORECASE):
        return True
    return False


def _scrub_history_and_question(
    cau_hoi: str,
    lich_su: Sequence[tuple[str, str]],
    session: DeidSession,
) -> tuple[str, list[tuple[str, str]]]:
    """Che câu hỏi và tối đa 6 tin gần nhất bằng phiên chung (lớp 1 rồi lớp 2).

    Một giá trị một mã trong cả phiên; bảng khôi phục nằm ở session.anh_xa.
    """
    recent = list(lich_su)[-MAX_HISTORY_MESSAGES:]
    scrubbed_question = _sanitize_markers(session.scrub(cau_hoi))
    scrubbed_history = [
        (role, _sanitize_markers(session.scrub(content))) for role, content in recent
    ]
    return scrubbed_question, scrubbed_history


def _scrub_free_text(session: DeidSession, text: str) -> str:
    """Che văn bản tự do (lớp 1 và lớp 2); lỗi thì thay bằng dòng báo, không để lọt bản gốc."""
    try:
        return session.scrub(text)
    except DeidError:
        return _SCRUB_FALLBACK


def _collect_case_numbers(
    ca: CaBenh,
    ket_qua: KetQuaThamDinh,
    base_numbers: Sequence[float],
    kept_record_ids: set[str],
    ai_result: AiRunResult | None,
    session: DeidSession,
) -> list[float]:
    """Gom toàn bộ con số hợp lệ từ hồ sơ, chỉ số, phát hiện luật và nhận định AI."""
    numbers = list(base_numbers)
    numbers.extend(float(i) for i in range(0, 13))
    numbers.extend((24.0, 48.0, 72.0))
    numbers.extend(
        float(n)
        for n in (
            len(ca.y_lenh_cho_duyet.chi_tiet),
            len(ca.xet_nghiem),
            len(ca.chan_doan),
            len(ca.di_ung),
            len(ca.vi_sinh),
            len(ca.dien_bien),
            len(ca.thuoc_dang_dung),
            len(ket_qua.phat_hien),
        )
    )
    days = vm.length_of_stay_days(ca, now=ca.y_lenh_cho_duyet.thoi_diem_ke)
    if days is not None:
        numbers.append(float(days))

    for cd in ca.chan_doan:
        numbers.extend(numbers_in_text(cd.noi_dung))
    for cdia in ca.co_dia:
        if cdia.gia_tri:
            numbers.extend(numbers_in_text(cdia.gia_tri))
    for du in ca.di_ung:
        numbers.extend(numbers_in_text(du.tac_nhan))
        if du.phan_ung:
            numbers.extend(numbers_in_text(du.phan_ung))
    for db in ca.dien_bien:
        if db.dien_bien_id in kept_record_ids:
            try:
                safe_note = session.scrub(db.noi_dung)
            except DeidError:
                continue
            numbers.extend(numbers_in_text(safe_note))
    for xn in ca.xet_nghiem:
        if xn.gia_tri_text:
            try:
                numbers.extend(numbers_in_text(session.scrub(xn.gia_tri_text)))
            except DeidError:
                continue
    for line in (*ca.y_lenh_cho_duyet.chi_tiet, *ca.thuoc_dang_dung):
        if line.cach_dung:
            try:
                numbers.extend(numbers_in_text(session.scrub(line.cach_dung)))
            except DeidError:
                continue

    for ph in ket_qua.phat_hien:
        numbers.extend(numbers_in_text(ph.mo_ta))
        for cc in ph.can_cu:
            numbers.extend(numbers_in_text(cc.mo_ta))

    if ai_result is not None and ai_result.llm.trang_thai == "ok":
        for item in ai_result.llm.nhan_dinh:
            if item.nguon_goc == "luat" and item.dien_giai is not None:
                numbers.extend(numbers_in_text(item.dien_giai.nhan_xet))
                if item.dien_giai.de_xuat:
                    numbers.extend(numbers_in_text(item.dien_giai.de_xuat))
            elif item.nguon_goc == "ai_da_kiem_chung" and item.de_xuat is not None:
                numbers.extend(numbers_in_text(item.de_xuat.nhan_xet))
                if item.de_xuat.de_xuat:
                    numbers.extend(numbers_in_text(item.de_xuat.de_xuat))

    return numbers


def _format_ai_section(
    ai_result: AiRunResult | None,
    ids: RecordIdMap,
    session: DeidSession,
) -> str:
    """Định dạng phần nhận định AI đã kiểm chứng; mã bản ghi thành mã tạm, định danh được che."""
    if ai_result is None or ai_result.llm.trang_thai != "ok":
        return ""
    ai_rule_findings = [
        item.phat_hien
        for item in ai_result.llm.nhan_dinh
        if item.nguon_goc == "luat" and item.phat_hien is not None
    ]
    ai_rule_nids = iter(vm.finding_ids(ai_rule_findings))
    lines: list[str] = []
    for item in ai_result.llm.nhan_dinh:
        if item.nguon_goc == "luat" and item.phat_hien is not None:
            fid = next(ai_rule_nids)
            if item.dien_giai is not None:
                cites = ", ".join(td.doan_trich_id for td in item.dien_giai.trich_dan) or "không có"
                explanation = _scrub_free_text(session, item.dien_giai.nhan_xet)
                lines.append(
                    f"- Diễn giải AI cho {fid}: {explanation}"
                    + (
                        f" | Đề xuất: {_scrub_free_text(session, item.dien_giai.de_xuat)}"
                        if item.dien_giai.de_xuat
                        else ""
                    )
                    + f" | Nguồn: {cites}"
                )
        elif item.nguon_goc == "ai_da_kiem_chung" and item.de_xuat is not None:
            dx = item.de_xuat
            aid = _ai_finding_id(dx.yeu_to, dx.nhan_xet, dx.chi_tiet_y_lenh_id)
            cites = ", ".join(td.doan_trich_id for td in dx.trich_dan) or "không có"
            records = ", ".join(ids.tam(record_id) for record_id in dx.ban_ghi_ids) or "không có"
            lines.append(
                f"- [{aid}] Yếu tố {dx.yeu_to} | {dx.ket_luan} | "
                f"{_scrub_free_text(session, dx.nhan_xet)}"
                + (f" | Đề xuất: {_scrub_free_text(session, dx.de_xuat)}" if dx.de_xuat else "")
                + f" | Bản ghi: {records} | Nguồn: {cites}"
            )
    if not lines:
        return ""
    return session.mask_known(
        ids.doi_van_ban_sang_tam("\n".join(["NHẬN ĐỊNH AI ĐÃ KIỂM CHỨNG", *lines]))
    )


def _format_priority_finding(
    nhan_dinh_id: str | None,
    ket_qua: KetQuaThamDinh,
    ai_result: AiRunResult | None,
    ids: RecordIdMap,
    session: DeidSession,
) -> tuple[str, set[str]]:
    """Đưa nhận định được chọn cùng căn cứ lên đầu ngữ cảnh, đã đổi mã tạm và che định danh."""
    block, chunk_ids = _priority_finding_raw(nhan_dinh_id, ket_qua, ai_result, ids, session)
    if not block:
        return block, chunk_ids
    return session.mask_known(ids.doi_van_ban_sang_tam(block)), chunk_ids


def _priority_finding_raw(
    nhan_dinh_id: str | None,
    ket_qua: KetQuaThamDinh,
    ai_result: AiRunResult | None,
    ids: RecordIdMap,
    session: DeidSession,
) -> tuple[str, set[str]]:
    """Dựng khối nhận định ưu tiên; mã bản ghi được cấp mã tạm trước khi đổi văn bản."""
    if not nhan_dinh_id:
        return "", set()

    rule_nids = vm.finding_ids(ket_qua.phat_hien)
    for ph, fid in zip(ket_qua.phat_hien, rule_nids, strict=True):
        if fid == nhan_dinh_id:
            for line_id in ph.chi_tiet_y_lenh_id:
                ids.tam(line_id)
            lines = [
                "NHẬN ĐỊNH ĐANG ĐƯỢC HỎI (ƯU TIÊN)",
                f"- nhan_dinh_id: {nhan_dinh_id}",
                f"- ma_luat={ph.ma_luat} | yeu_to={ph.yeu_to} | ket_luan={ph.ket_luan}"
                f" | muc_do={ph.muc_do}",
                f"- dong={', '.join(ph.chi_tiet_y_lenh_id) or 'cả đơn'} | mo_ta: {ph.mo_ta}",
            ]
            if ph.thong_tin_con_thieu:
                lines.append(f"- thieu: {', '.join(ph.thong_tin_con_thieu)}")
            for cc in ph.can_cu:
                ref = cc.ban_ghi_id or "-"
                lines.append(f"  + Căn cứ [{cc.loai}] ma={ref}: {cc.mo_ta}")
            cited_chunk_ids: set[str] = set()
            if ai_result is not None and ai_result.llm.trang_thai == "ok":
                ai_rule_findings = [
                    item.phat_hien
                    for item in ai_result.llm.nhan_dinh
                    if item.nguon_goc == "luat" and item.phat_hien is not None
                ]
                ai_rule_nids = iter(vm.finding_ids(ai_rule_findings))
                for item in ai_result.llm.nhan_dinh:
                    if item.nguon_goc == "luat" and item.phat_hien is not None:
                        ai_fid = next(ai_rule_nids)
                        if ai_fid == nhan_dinh_id and item.dien_giai is not None:
                            lines.append(
                                "- Diễn giải AI: "
                                f"{_scrub_free_text(session, item.dien_giai.nhan_xet)}"
                            )
                            if item.dien_giai.de_xuat:
                                lines.append(
                                    "- Đề xuất AI: "
                                    f"{_scrub_free_text(session, item.dien_giai.de_xuat)}"
                                )
                            for td in item.dien_giai.trich_dan:
                                cited_chunk_ids.add(td.doan_trich_id)
                                lines.append(
                                    f"  + Trích dẫn tài liệu [{td.doan_trich_id}]: "
                                    f"{td.trich_nguyen_van}"
                                )
            return "\n".join(lines), cited_chunk_ids

    if ai_result is not None and ai_result.llm.trang_thai == "ok":
        for item in ai_result.llm.nhan_dinh:
            if item.nguon_goc == "ai_da_kiem_chung" and item.de_xuat is not None:
                dx = item.de_xuat
                aid = _ai_finding_id(dx.yeu_to, dx.nhan_xet, dx.chi_tiet_y_lenh_id)
                if aid == nhan_dinh_id:
                    for record_id in (*dx.chi_tiet_y_lenh_id, *dx.ban_ghi_ids):
                        ids.tam(record_id)
                    lines = [
                        "NHẬN ĐỊNH ĐANG ĐƯỢC HỎI (ƯU TIÊN)",
                        f"- nhan_dinh_id: {aid}",
                        f"- yeu_to={dx.yeu_to} | ket_luan={dx.ket_luan} | muc_do={dx.muc_do}",
                        f"- dong={', '.join(dx.chi_tiet_y_lenh_id) or 'cả đơn'}"
                        f" | nhan_xet: {_scrub_free_text(session, dx.nhan_xet)}",
                    ]
                    if dx.de_xuat:
                        lines.append(f"- Đề xuất AI: {_scrub_free_text(session, dx.de_xuat)}")
                    for record_id in dx.ban_ghi_ids:
                        lines.append(f"  + Căn cứ [du_lieu] ma={record_id}")
                    cited_chunk_ids = set()
                    for td in dx.trich_dan:
                        cited_chunk_ids.add(td.doan_trich_id)
                        lines.append(
                            f"  + Trích dẫn tài liệu [{td.doan_trich_id}]: {td.trich_nguyen_van}"
                        )
                    return "\n".join(lines), cited_chunk_ids

    return "", set()


def _select_evidence_chunks(
    doan: Sequence[Chunk],
    evidence_max_chars: int,
) -> tuple[list[Chunk], str]:
    """Chọn tuần tự các đoạn nguồn vừa trần ký tự và định dạng khối đoạn nguồn."""
    selected: list[Chunk] = []
    blocks: list[str] = []
    total_chars = 0
    for chunk in doan:
        chunk_len = len(chunk.noi_dung_goc)
        if selected and total_chars + chunk_len > evidence_max_chars:
            break
        if not selected and chunk_len > evidence_max_chars:
            break
        selected.append(chunk)
        total_chars += chunk_len
        blocks.append(
            f"[{chunk.doan_trich_id}] (tầng {chunk.tang_tin_cay}, {chunk.duong_dan_muc})\n"
            f"{_sanitize_markers(chunk.noi_dung_goc)}"
        )
    text = "\n\n".join(blocks) if blocks else "(không có đoạn nguồn)"
    return selected, text


def _build_messages(
    template: str,
    *,
    van_ban_ca: str,
    doan_nguon: str,
    lich_su: str,
    cau_hoi: str,
    loi_lan_truoc: str,
) -> list[ChatMessage]:
    """Tách phần chỉ thị hệ thống và dữ liệu ca bệnh để gửi cho mô hình."""
    values = {
        "van_ban_ca": van_ban_ca,
        "doan_nguon": doan_nguon,
        "lich_su": lich_su,
        "cau_hoi": cau_hoi,
        "loi_lan_truoc": loi_lan_truoc,
    }

    def _render(part: str) -> str:
        return re.sub(
            r"\{\{(van_ban_ca|doan_nguon|lich_su|cau_hoi|loi_lan_truoc)\}\}",
            lambda match: values[match.group(1)],
            part,
        )

    if _DATA_SPLIT_MARKER in template:
        sys_part, user_template = template.split(_DATA_SPLIT_MARKER, maxsplit=1)
        return [
            ChatMessage(role="system", content=sys_part.strip()),
            ChatMessage(role="user", content=_render(user_template).strip()),
        ]
    return [
        ChatMessage(role="system", content=_FALLBACK_SYSTEM_PROMPT),
        ChatMessage(role="user", content=_render(template).strip()),
    ]


def _format_global_order_line(line: ChiTietYLenh) -> str:
    """Định dạng một dòng y lệnh cho bảng tóm tắt chung, chịu được trường None."""
    name = line.ten_tu_do or line.thuoc_id or line.chi_tiet_y_lenh_id
    unit = (line.don_vi_lieu or "").strip()
    if line.lieu_moi_lan is not None:
        dose_num = f"{line.lieu_moi_lan:g}"
        dose_part = f"{dose_num} {unit}" if unit else f"{dose_num} (đơn vị chưa ghi)"
    elif unit:
        dose_part = f"liều chưa ghi ({unit})"
    else:
        dose_part = "liều chưa ghi"
    freq_part = (line.tan_suat or "").strip() or "tần suất chưa ghi"
    route_part = (line.duong_dung or "").strip() or "đường dùng chưa ghi"
    return f"{name} {dose_part} ({freq_part}, {route_part})"


def chuan_bi_ngu_canh_ca(
    ca: CaBenh,
    ket_qua: KetQuaThamDinh | None,
    ai_result: AiRunResult | None,
    nhan_dinh_id: str | None,
    session: DeidSession,
    case_settings: CaseContextSettings,
    renal_rules_getter: Callable[[], RenalRuleBook],
) -> NguCanhCa:
    """Chạy bộ luật (nếu chưa có), dựng gói ca đã che định danh và danh sách số/mã hợp lệ."""
    active_result = ket_qua or run_case(ca, renal_rules_getter())
    bundle = build_case_bundle(ca, active_result, case_settings, session=session)
    goi = bundle.goi
    ids = bundle.ma_ban_ghi
    anh_xa = session.anh_xa
    allowed_record_ids = set(goi.ban_ghi_ids)
    allowed_calc_ids = {cs.cong_thuc for cs in active_result.chi_so if cs.ket_qua is not None}
    allowed_numbers = _collect_case_numbers(
        ca,
        active_result,
        goi.so_cho_phep,
        set(ids.that_nhieu(goi.ban_ghi_ids)),
        ai_result,
        session,
    )

    priority_block, priority_chunk_ids = _format_priority_finding(
        nhan_dinh_id,
        active_result,
        ai_result,
        ids,
        session,
    )
    ai_block = _format_ai_section(ai_result, ids, session)
    context_parts = [part for part in (priority_block, goi.van_ban_ca, ai_block) if part.strip()]
    van_ban_ca = _sanitize_markers("\n\n".join(context_parts))
    return NguCanhCa(
        active_result=active_result,
        van_ban_ca=van_ban_ca,
        ids=ids,
        anh_xa=anh_xa,
        allowed_record_ids=allowed_record_ids,
        allowed_calc_ids=allowed_calc_ids,
        allowed_numbers=allowed_numbers,
        priority_chunk_ids=priority_chunk_ids,
    )


def kiem_chung_tra_loi(
    *,
    ca: CaBenh,
    ket_qua: KetQuaThamDinh,
    cleaned_question: str,
    output: AskLLMOutput,
    allowed_record_ids: set[str],
    allowed_calc_ids: set[str],
    allowed_numbers: list[float],
    chunk_by_id: dict[str, Chunk],
    anh_xa: dict[str, str],
    ids: RecordIdMap,
    tools_called: list[str],
    perf_start: float,
    bang_by_ma: Mapping[str, tuple[str, str]] | None = None,
) -> AskResult:
    """Kiểm chứng phạm vi, trích dẫn, chuỗi con nguyên văn và mọi con số trong câu trả lời.

    allowed_record_ids là mã tạm; mã thật chỉ xuất hiện ở kết quả trả về giao diện.
    bang_by_ma: mã dòng bảng do công cụ trả về -> (nhãn nguồn, nội dung dòng); None là không có.
    """
    with span("kiem_chung", "kiem_chung_tra_loi") as kc_span:
        return _kiem_chung_tra_loi_noi_bo(
            ca=ca,
            ket_qua=ket_qua,
            cleaned_question=cleaned_question,
            output=output,
            allowed_record_ids=allowed_record_ids,
            allowed_calc_ids=allowed_calc_ids,
            allowed_numbers=allowed_numbers,
            chunk_by_id=chunk_by_id,
            anh_xa=anh_xa,
            ids=ids,
            tools_called=tools_called,
            perf_start=perf_start,
            bang_by_ma=bang_by_ma,
            kc_span=kc_span,
        )


def _kiem_chung_tra_loi_noi_bo(
    *,
    ca: CaBenh,
    ket_qua: KetQuaThamDinh,
    cleaned_question: str,
    output: AskLLMOutput,
    allowed_record_ids: set[str],
    allowed_calc_ids: set[str],
    allowed_numbers: list[float],
    chunk_by_id: dict[str, Chunk],
    anh_xa: dict[str, str],
    ids: RecordIdMap,
    tools_called: list[str],
    perf_start: float,
    bang_by_ma: Mapping[str, tuple[str, str]] | None,
    kc_span: object,
) -> AskResult:
    """Thực thi kiểm chứng bên trong span kiem_chung và ghi lý do đã che chữ số dài."""
    vet = vet_hien_tai.get()

    def _set_kc_attrs(
        *,
        so_bi_chan: int,
        so_dat: int,
        ma_ly_do: Sequence[str],
        trang_thai_ket_qua: str,
    ) -> None:
        masked = [che_chu_so_ma_ly_do(item) for item in ma_ly_do]
        kc_span.dat_thuoc_tinh(  # type: ignore[attr-defined]
            tong_so=1,
            so_dat=so_dat,
            so_bi_chan=so_bi_chan,
            ma_ly_do=masked,
            trang_thai_ket_qua=trang_thai_ket_qua,
        )
        if so_bi_chan > 0 and vet is not None:
            vet.tang_so_bi_chan(so_bi_chan)

    def _restore(text: str) -> str:
        return ids.doi_van_ban_sang_that(restore_text(text, anh_xa))

    def _elapsed() -> int:
        return int((time.perf_counter() - perf_start) * 1000.0)

    if _has_injection_directive(cleaned_question):
        _log_rejection("scope", "input_directive", len(chunk_by_id))
        ghi_su_kien_bao_mat("chen_lenh_dau_vao", nguon="kiem_chung")
        kc_span.dat_trang_thai("tu_choi")  # type: ignore[attr-defined]
        _set_kc_attrs(
            so_bi_chan=1,
            so_dat=0,
            ma_ly_do=["input_directive"],
            trang_thai_ket_qua="ngoai_pham_vi",
        )
        return AskResult(
            trang_thai="ngoai_pham_vi",
            noi_dung=OUT_OF_SCOPE_MESSAGE,
            trich_dan=[],
            cong_cu_da_goi=tools_called,
            thoi_gian_ms=_elapsed(),
            doan=[],
        )

    reply_text = output.tra_loi.strip()

    if output.pham_vi == "ngoai":
        clinical = bool(_CLINICAL_QUESTION_RE.search(cleaned_question))
        _log_rejection(
            "scope", f"llm_pham_vi=ngoai; clinical_question={clinical}", len(chunk_by_id)
        )
        if (
            reply_text
            and not _output_attempts_override(reply_text, ket_qua)
            and not unverified_numbers([reply_text], list(allowed_numbers))
        ):
            natural_msg = _restore(reply_text)
        else:
            natural_msg = NO_SOURCE_MESSAGE if clinical else OUT_OF_SCOPE_MESSAGE
        status_ngoai: Literal["khong_co_nguon", "ngoai_pham_vi"] = (
            "khong_co_nguon" if clinical else "ngoai_pham_vi"
        )
        _set_kc_attrs(
            so_bi_chan=0,
            so_dat=1,
            ma_ly_do=["llm_pham_vi=ngoai"],
            trang_thai_ket_qua=status_ngoai,
        )
        return AskResult(
            trang_thai=status_ngoai,
            noi_dung=natural_msg,
            cong_cu_da_goi=tools_called,
            thoi_gian_ms=_elapsed(),
        )

    if _output_attempts_override(reply_text, ket_qua):
        _log_rejection("scope", "output_attempts_override", len(chunk_by_id))
        ghi_su_kien_bao_mat("chen_lenh_dau_ra", nguon="kiem_chung")
        kc_span.dat_trang_thai("tu_choi")  # type: ignore[attr-defined]
        _set_kc_attrs(
            so_bi_chan=1,
            so_dat=0,
            ma_ly_do=["output_attempts_override"],
            trang_thai_ket_qua="ngoai_pham_vi",
        )
        return AskResult(
            trang_thai="ngoai_pham_vi",
            noi_dung=OUT_OF_SCOPE_MESSAGE,
            trich_dan=[],
            cong_cu_da_goi=tools_called,
            thoi_gian_ms=_elapsed(),
            doan=[],
        )

    if not reply_text:
        _log_rejection("verification", "empty_answer_or_citations", len(chunk_by_id))
        kc_span.dat_trang_thai("tu_choi")  # type: ignore[attr-defined]
        _set_kc_attrs(
            so_bi_chan=1,
            so_dat=0,
            ma_ly_do=["empty_answer_or_citations"],
            trang_thai_ket_qua="khong_co_nguon",
        )
        return AskResult(
            trang_thai="khong_co_nguon",
            noi_dung=NO_SOURCE_MESSAGE,
            trich_dan=[],
            cong_cu_da_goi=tools_called,
            thoi_gian_ms=_elapsed(),
            doan=[],
        )

    if not output.trich_dan:
        _log_rejection("verification", "empty_answer_or_citations", len(chunk_by_id))
        number_errors = unverified_numbers([reply_text], list(allowed_numbers))
        if number_errors:
            _set_kc_attrs(
                so_bi_chan=1,
                so_dat=0,
                ma_ly_do=number_errors,
                trang_thai_ket_qua="tu_choi",
            )
            safe_reason = _log_rejection("verification", "; ".join(number_errors), len(chunk_by_id))
            raise AskVerificationError(safe_reason)
        clinical = bool(_CLINICAL_QUESTION_RE.search(cleaned_question))
        status_no_cite: Literal["khong_co_nguon", "ok"] = "khong_co_nguon" if clinical else "ok"
        _set_kc_attrs(
            so_bi_chan=1 if clinical else 0,
            so_dat=0 if clinical else 1,
            ma_ly_do=["empty_answer_or_citations"] if clinical else [],
            trang_thai_ket_qua=status_no_cite,
        )
        return AskResult(
            trang_thai=status_no_cite,
            noi_dung=_restore(reply_text),
            trich_dan=[],
            cong_cu_da_goi=tools_called,
            thoi_gian_ms=_elapsed(),
            doan=[],
        )

    citations: list[AskCitation] = []
    seen_so: set[int] = set()
    cited_chunks: list[Chunk] = []
    seen_chunk_ids: set[str] = set()
    effective_numbers = list(allowed_numbers)

    def _reject(reason: str) -> NoReturn:
        reasons = [part.strip() for part in reason.split(";") if part.strip()]
        _set_kc_attrs(
            so_bi_chan=1,
            so_dat=0,
            ma_ly_do=reasons,
            trang_thai_ket_qua="tu_choi",
        )
        safe_reason = _log_rejection("verification", reason, len(chunk_by_id))
        raise AskVerificationError(safe_reason)

    for item in output.trich_dan:
        if item.so <= 0 or item.so in seen_so:
            _reject(f"invalid_citation_number:{item.so}")
        seen_so.add(item.so)

        if item.loai == "du_lieu_ca":
            if item.ma not in allowed_record_ids:
                _reject(f"unknown_record_id:{item.ma}")
            real_id = ids.that(item.ma)
            detail = vm.record_detail(ca, real_id)
            label = (
                f"{detail['loai']}: {detail['tieu_de']}"
                if detail is not None
                else f"Bản ghi {real_id}"
            )
            citations.append(
                AskCitation(
                    so=item.so,
                    loai_ma="du_lieu",
                    nhan=label,
                    ban_ghi_id=real_id,
                )
            )
        elif item.loai == "tinh_toan":
            ma_tinh = item.ma.strip().strip("[]").strip()
            if ma_tinh.startswith("tinh:"):
                row = (bang_by_ma or {}).get(ma_tinh)
                if row is None:
                    _reject(f"unknown_calc_row:{item.ma}")
                row_label, row_text = row
                effective_numbers.extend(numbers_in_text(row_text, include_en_thousands=True))
                citations.append(
                    AskCitation(
                        so=item.so,
                        loai_ma="tai_lieu",
                        nhan=row_label,
                        ban_ghi_id=None,
                        doan_trich_id=None,
                        trich_nguyen_van=None,
                    )
                )
            else:
                if item.ma not in allowed_calc_ids:
                    _reject(f"unknown_calc_id:{item.ma}")
                calc_label = labels.NHAN_CONG_THUC.get(item.ma, item.ma.replace("_", " "))
                citations.append(
                    AskCitation(
                        so=item.so,
                        loai_ma="tinh_toan",
                        nhan=calc_label,
                        ban_ghi_id=item.ma,
                    )
                )
        elif item.loai == "bang":
            table = bang_by_ma or {}
            ma_bang = item.ma.strip().strip("[]").strip()
            row = table.get(ma_bang)
            if row is None and not ma_bang.startswith("bang:"):
                row = table.get(f"bang:{ma_bang}")
            if row is None:
                _reject(f"unknown_table_row:{item.ma}")
            row_label, row_text = row
            effective_numbers.extend(numbers_in_text(row_text, include_en_thousands=True))
            citations.append(
                AskCitation(
                    so=item.so,
                    loai_ma="tai_lieu",
                    nhan=row_label,
                    ban_ghi_id=None,
                    doan_trich_id=None,
                    trich_nguyen_van=None,
                )
            )
        else:
            chunk = chunk_by_id.get(item.ma)
            if chunk is None:
                _reject(f"unknown_chunk_id:{item.ma}")
            if not item.trich_nguyen_van:
                _reject(f"empty_quote:so={item.so}; ma={item.ma}")
            if not quote_matches_source(item.trich_nguyen_van, chunk.noi_dung_goc):
                _reject(f"quote_mismatch:so={item.so}; ma={item.ma}")
            if chunk.doan_trich_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.doan_trich_id)
                cited_chunks.append(chunk)
                effective_numbers.extend(
                    numbers_in_text(
                        chunk.noi_dung_goc,
                        include_en_thousands=chunk.ngon_ngu == "en",
                    )
                )
            citations.append(
                AskCitation(
                    so=item.so,
                    loai_ma="tai_lieu",
                    nhan=f"{_source_label(chunk.nguon)} · {chunk.duong_dan_muc}",
                    ban_ghi_id=None,
                    doan_trich_id=chunk.doan_trich_id,
                    trich_nguyen_van=item.trich_nguyen_van.strip(),
                )
            )

    referenced_nums = {int(match.group(1)) for match in _CITATION_REF_RE.finditer(reply_text)}
    if not referenced_nums.issubset(seen_so):
        _reject(f"unknown_markers:{sorted(referenced_nums - seen_so)}")

    masked_reply = mask_citation_markers(reply_text, seen_so)
    number_errors = unverified_numbers([masked_reply], effective_numbers)
    if number_errors:
        _reject("; ".join(number_errors))

    _set_kc_attrs(so_bi_chan=0, so_dat=1, ma_ly_do=[], trang_thai_ket_qua="ok")
    restored_reply = _restore(reply_text)
    return AskResult(
        trang_thai="ok",
        noi_dung=restored_reply,
        trich_dan=citations,
        cong_cu_da_goi=tools_called,
        thoi_gian_ms=_elapsed(),
        doan=cited_chunks,
    )


class CaseAsker:
    """Xử lý câu hỏi của dược sĩ về ca bệnh đang mở qua che định danh, RAG và kiểm chứng."""

    def __init__(
        self,
        llm: LLMClient | None,
        retriever: Retriever | LazyRetrieverFactory | None,
        query_builder: QueryBuilder,
        resolve_name: IngredientResolver,
        prompt_path: Path,
        case_settings: CaseContextSettings,
        evidence_max_chars: int,
        model_name: str | None = None,
        *,
        renal_rules: RenalRuleBook | None = None,
        timeout_seconds: float = DEFAULT_ASK_TIMEOUT_SECONDS,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._query_builder = query_builder
        self._resolve_name = resolve_name
        self._prompt_path = Path(prompt_path)
        self._case_settings = case_settings
        self._evidence_max_chars = evidence_max_chars
        self._model_name = model_name
        self._renal_rules = renal_rules
        self._timeout_seconds = timeout_seconds

    def close(self) -> None:
        """Đóng máy khách HTTP dùng chung nếu có."""
        if isinstance(self._retriever, LazyRetrieverFactory):
            self._retriever.close()
        if self._llm is not None:
            client = getattr(self._llm, "client", None)
            close_fn = getattr(client, "close", None)
            if callable(close_fn):
                close_fn()

    def _get_renal_rules(self) -> RenalRuleBook:
        """Nạp bảng quy tắc chỉnh liều thận khi người gọi không truyền sẵn kết quả luật."""
        if self._renal_rules is None:
            self._renal_rules = load_renal_rules()
        return self._renal_rules

    def _run_with_deadline(self, fn: Callable[[], object], deadline: float) -> object:
        """Chạy tác vụ có giới hạn thời gian còn lại để không treo quá 45 giây."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Hết thời gian xử lý hỏi đáp")
        executor = ThreadPoolExecutor(max_workers=1)
        ctx_copy = copy_context()

        def run_with_context() -> object:
            from app.providers.http import han_chot_llm

            token = han_chot_llm.set(deadline)
            try:
                return fn()
            finally:
                han_chot_llm.reset(token)

        future = executor.submit(ctx_copy.run, run_with_context)
        try:
            result = future.result(timeout=remaining)
        except FuturesTimeoutError as exc:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise TimeoutError("Quá thời gian xử lý hỏi đáp") from exc
        else:
            executor.shutdown(wait=False)
            return result

    def _collect_drug_scope(self, ca: CaBenh) -> tuple[list[str], list[str], list[str]]:
        """Lấy tập mã hoạt chất chuẩn và tên thuốc trong y lệnh để giới hạn truy xuất."""
        active_lines = list(ca.y_lenh_cho_duyet.chi_tiet)
        active_lines.extend(
            line for line in ca.thuoc_dang_dung if line.trang_thai_dong in ("active", "pending")
        )
        kb_ids: list[str] = []
        vi_names: list[str] = []
        inn_names: list[str] = []
        seen_kb: set[str] = set()
        seen_vi: set[str] = set()
        seen_inn: set[str] = set()

        for line in active_lines:
            for hc in ingredients_of(ca, line):
                if hc.ten_hoat_chat and hc.ten_hoat_chat not in seen_vi:
                    seen_vi.add(hc.ten_hoat_chat)
                    vi_names.append(hc.ten_hoat_chat)
                inn = (
                    hc.ten_quoc_te.strip()
                    if hc.ten_quoc_te and hc.ten_quoc_te.strip()
                    else hc.ten_hoat_chat
                )
                if inn and inn not in seen_inn:
                    seen_inn.add(inn)
                    inn_names.append(inn)

                resolved = _normalize_resolved(self._resolve_name(inn))
                if not resolved and hc.ten_hoat_chat != inn:
                    resolved = _normalize_resolved(self._resolve_name(hc.ten_hoat_chat))
                for kb_id in resolved:
                    if kb_id not in seen_kb:
                        seen_kb.add(kb_id)
                        kb_ids.append(kb_id)
        return kb_ids, vi_names, inn_names

    def _retrieve_chunks(
        self,
        ca: CaBenh,
        scrubbed_question: str,
        deadline: float,
    ) -> tuple[list[Chunk], bool]:
        """Truy xuất tối đa 6 đoạn liên quan trong phạm vi hoạt chất của ca bệnh."""
        if self._retriever is None:
            return [], False
        kb_ids, vi_names, inn_names = self._collect_drug_scope(ca)
        if not kb_ids:
            return [], False

        base_question = _DEID_TOKEN_RE.sub(" ", scrubbed_question).strip()
        queries: list[str] = []
        for drug_list in (vi_names, inn_names):
            drug_part = " ".join(drug_list).strip()
            combined = f"{base_question} {drug_part}".strip()
            if combined and combined not in queries:
                queries.append(combined)
        if not queries:
            queries = [" ".join(inn_names or vi_names)]

        retrieval_query = RetrievalQuery(
            van_ban=queries,
            bo_loc=SearchFilter(hoat_chat_ids=kb_ids),
            k_query=max(self._query_builder.settings.nhan_thuoc.k_query, MAX_ASK_CHUNKS),
            k_rerank=MAX_ASK_CHUNKS,
        )

        def _execute() -> list[ScoredChunk]:
            assert self._retriever is not None
            if isinstance(self._retriever, LazyRetrieverFactory):
                active_retriever = self._retriever.for_ingredients(set(kb_ids))
            else:
                active_retriever = self._retriever
            return active_retriever.retrieve(retrieval_query)

        try:
            scored = self._run_with_deadline(_execute, deadline)
        except TimeoutError:
            raise
        except Exception:
            return [], False

        assert isinstance(scored, list)
        ranked = sorted(scored, key=lambda item: item.diem, reverse=True)
        selected: list[Chunk] = []
        seen_ids: set[str] = set()
        for item in ranked:
            cid = item.chunk.doan_trich_id
            if cid in seen_ids:
                continue
            seen_ids.add(cid)
            selected.append(item.chunk)
            if len(selected) >= MAX_ASK_CHUNKS:
                break
        return selected, True

    def _verify_and_build_reply(
        self,
        *,
        ca: CaBenh,
        ket_qua: KetQuaThamDinh,
        cleaned_question: str,
        output: AskLLMOutput,
        allowed_record_ids: set[str],
        allowed_calc_ids: set[str],
        allowed_numbers: list[float],
        chunk_by_id: dict[str, Chunk],
        anh_xa: dict[str, str],
        ids: RecordIdMap,
        tools_called: list[str],
        perf_start: float,
    ) -> AskResult:
        """Kiểm chứng phạm vi, trích dẫn, chuỗi con nguyên văn và mọi con số trong câu trả lời.

        allowed_record_ids là mã tạm; mã thật chỉ xuất hiện ở kết quả trả về giao diện.
        """
        return kiem_chung_tra_loi(
            ca=ca,
            ket_qua=ket_qua,
            cleaned_question=cleaned_question,
            output=output,
            allowed_record_ids=allowed_record_ids,
            allowed_calc_ids=allowed_calc_ids,
            allowed_numbers=allowed_numbers,
            chunk_by_id=chunk_by_id,
            anh_xa=anh_xa,
            ids=ids,
            tools_called=tools_called,
            perf_start=perf_start,
        )

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
        """Trả lời câu hỏi theo ca: che định danh, truy xuất, gọi LLM và kiểm chứng."""
        perf_start = time.perf_counter()
        deadline = time.monotonic() + self._timeout_seconds

        def _elapsed() -> int:
            return int((time.perf_counter() - perf_start) * 1000.0)

        cleaned_question = cau_hoi.strip()
        if not 1 <= len(cleaned_question) <= 1000:
            raise ValueError("cau_hoi phải dài từ 1 đến 1000 ký tự sau khi cắt khoảng trắng")

        if self._llm is None:
            _log_rejection("configuration", "missing_llm")
            return AskResult(
                trang_thai="chua_san_sang",
                noi_dung=NOT_READY_MESSAGE,
                trich_dan=[],
                cong_cu_da_goi=[],
                thoi_gian_ms=_elapsed(),
                doan=[],
            )

        existing_vet = vet_hien_tai.get()
        phien_ban = {
            key: value
            for key, value in (
                ("prompt", self._prompt_path.stem),
                ("mo_hinh", self._model_name or ""),
            )
            if value
        }
        trace_cm = (
            nullcontext(existing_vet)
            if existing_vet is not None
            else bat_dau_vet(
                loai="hoi_dap",
                engine="co_dinh",
                ca_id=ca.ca_id,
                phien_ban=phien_ban,
            )
        )
        with trace_cm as vet:
            res = self._ask_traced(
                ca,
                cleaned_question,
                lich_su,
                ket_qua=ket_qua,
                ai_result=ai_result,
                nhan_dinh_id=nhan_dinh_id,
                perf_start=perf_start,
                deadline=deadline,
            )
            if vet is not None:
                vet.dat_trang_thai_cuoi(res.trang_thai)
                return res.model_copy(update={"ma_vet": vet.ma_vet})
            return res

    def _ask_traced(
        self,
        ca: CaBenh,
        cleaned_question: str,
        lich_su: list[tuple[str, str]] | None,
        *,
        ket_qua: KetQuaThamDinh | None,
        ai_result: AiRunResult | None,
        nhan_dinh_id: str | None,
        perf_start: float,
        deadline: float,
    ) -> AskResult:
        """Thân thực thi ask nằm trong phạm vi vết hiện hành."""

        def _elapsed() -> int:
            return int((time.perf_counter() - perf_start) * 1000.0)

        ghi_buoc("bat_dau", "chuan_bi", ten="Đọc hồ sơ ca và chạy bộ luật")
        with span("che_pii", "che_dinh_danh") as pii_span:
            try:
                session = open_deid_session(ca, [])
                vet = vet_hien_tai.get()
                if vet is not None:
                    vet.dat_phien_che(session)
                scrubbed_question, scrubbed_history = _scrub_history_and_question(
                    cleaned_question,
                    lich_su or [],
                    session,
                )
            except Exception as exc:
                pii_span.dat_trang_thai("loi")
                pii_span.dat_thuoc_tinh(thanh_cong=False, loai_ngoai_le=type(exc).__name__)
                _log_rejection("deid", "scrub_failed")
                ghi_buoc(
                    "loi",
                    "chuan_bi",
                    ly_do="Không soạn được câu trả lời",
                    goi_y=_ASK_RETRY_HINT,
                )
                return AskResult(
                    trang_thai="loi",
                    noi_dung=ERROR_MESSAGE,
                    trich_dan=[],
                    cong_cu_da_goi=[],
                    thoi_gian_ms=_elapsed(),
                    doan=[],
                )
            kinds = sorted({key.strip("[]").rsplit("_", 1)[0] for key in session.anh_xa})
            pii_span.dat_thuoc_tinh(
                so_ma_tam=len(session.anh_xa),
                loai_dinh_danh=kinds,
                thanh_cong=True,
            )

        tools_called = ["du_lieu_ca", "bo_luat"]
        step = "context"
        selected_chunks: list[Chunk] = []
        try:
            ngu_canh = chuan_bi_ngu_canh_ca(
                ca,
                ket_qua,
                ai_result,
                nhan_dinh_id,
                session,
                self._case_settings,
                self._get_renal_rules,
            )
            active_result = ngu_canh.active_result
            ids = ngu_canh.ids
            anh_xa = ngu_canh.anh_xa
            allowed_record_ids = ngu_canh.allowed_record_ids
            allowed_calc_ids = ngu_canh.allowed_calc_ids
            allowed_numbers = ngu_canh.allowed_numbers
            priority_chunk_ids = ngu_canh.priority_chunk_ids
            van_ban_ca = ngu_canh.van_ban_ca
            ghi_buoc(
                "xong",
                "chuan_bi",
                chi_tiet=f"{len(active_result.phat_hien)} phát hiện của bộ luật",
            )

            step = "retrieval"
            ghi_buoc("bat_dau", "truy_xuat", ten="Tra cứu nhãn thuốc và hướng dẫn")
            retrieved_chunks, used_retrieval = self._retrieve_chunks(
                ca,
                scrubbed_question,
                deadline,
            )
            if used_retrieval:
                tools_called.append("truy_xuat")
                source_detail, source_groups = _summarize_sources(retrieved_chunks)
                ghi_buoc(
                    "xong",
                    "truy_xuat",
                    chi_tiet=source_detail,
                    nguon=source_groups,
                )
            else:
                ghi_buoc("xong", "truy_xuat", chi_tiet="Không dùng tra cứu nguồn")
            _LOGGER.info("ask retrieval chunks=%s used=%s", len(retrieved_chunks), used_retrieval)

            candidate_chunks = list(retrieved_chunks)
            if priority_chunk_ids and ai_result is not None and ai_result.llm.trang_thai == "ok":
                existing_ids = {chunk.doan_trich_id for chunk in candidate_chunks}
                extra_chunks = [
                    chunk
                    for chunk in ai_result.doan
                    if chunk.doan_trich_id in priority_chunk_ids
                    and chunk.doan_trich_id not in existing_ids
                ]
                if extra_chunks:
                    candidate_chunks = [*extra_chunks, *candidate_chunks][:MAX_ASK_CHUNKS]

            selected_chunks, doan_nguon_text = _select_evidence_chunks(
                candidate_chunks,
                self._evidence_max_chars,
            )
            chunk_by_id = {chunk.doan_trich_id: chunk for chunk in selected_chunks}

            step = "prompt"
            prompt_version, template = load_prompt(self._prompt_path)
            lich_su_text = (
                "\n".join(
                    f"- {_ROLE_LABELS.get(role, role)}: {content}"
                    for role, content in scrubbed_history
                )
                if scrubbed_history
                else "(không có)"
            )
            schema = AskLLMOutput.model_json_schema()
            previous_error = "Không có."
            llm = self._llm
            assert llm is not None
            for attempt in range(2):
                llm_step = "goi_mo_hinh" if attempt == 0 else f"goi_mo_hinh_{attempt + 1}"
                verify_step = "kiem_chung" if attempt == 0 else f"kiem_chung_{attempt + 1}"
                if attempt >= 1:
                    ghi_buoc("them", llm_step, ten=f"Soạn lại, lần {attempt + 1}")
                ghi_buoc(
                    "bat_dau",
                    llm_step,
                    chi_tiet="Đang gọi mô hình",
                    ten="Soạn câu trả lời" if attempt == 0 else None,
                )
                messages = _build_messages(
                    template,
                    van_ban_ca=van_ban_ca,
                    doan_nguon=doan_nguon_text,
                    lich_su=lich_su_text,
                    cau_hoi=scrubbed_question,
                    loi_lan_truoc=previous_error,
                )
                step = "llm"
                raw = self._run_with_deadline(
                    lambda msgs=messages, pv=prompt_version: goi_llm_co_vet(
                        llm,
                        msgs,
                        schema,
                        phien_ban_prompt=pv,
                        mo_hinh=self._model_name,
                    ),
                    deadline,
                )
                try:
                    parsed_output = AskLLMOutput.model_validate(raw)
                except ValidationError as exc:
                    errors = "; ".join(
                        f"{'.'.join(map(str, error['loc']))}:{error['type']}"
                        for error in exc.errors(include_input=False, include_context=False)
                    )
                    _log_rejection("llm_schema", f"invalid_json:{errors}", len(selected_chunks))
                    if attempt == 0:
                        ghi_buoc("xong", llm_step, chi_tiet="Đầu ra sai định dạng, thử lại")
                    else:
                        ghi_buoc(
                            "loi",
                            llm_step,
                            ly_do="Không soạn được câu trả lời",
                            goi_y=_ASK_RETRY_HINT,
                        )
                    previous_error = (
                        f"Lần trước sai lược đồ JSON ({errors}). "
                        "Chỉ trả về đúng đối tượng JSON hợp lệ."
                    )
                    continue

                ghi_buoc("xong", llm_step)
                step = "verification"
                if attempt >= 1:
                    ghi_buoc("them", verify_step, ten=f"Kiểm chứng lại, lần {attempt + 1}")
                ghi_buoc(
                    "bat_dau",
                    verify_step,
                    ten="Kiểm chứng trích dẫn và số liệu" if attempt == 0 else None,
                )
                try:
                    verified = self._verify_and_build_reply(
                        ca=ca,
                        ket_qua=active_result,
                        cleaned_question=cleaned_question,
                        output=parsed_output,
                        allowed_record_ids=allowed_record_ids,
                        allowed_calc_ids=allowed_calc_ids,
                        allowed_numbers=allowed_numbers,
                        chunk_by_id=chunk_by_id,
                        anh_xa=anh_xa,
                        ids=ids,
                        tools_called=tools_called,
                        perf_start=perf_start,
                    )
                except _AskVerificationError as exc:
                    if attempt == 1:
                        ghi_buoc("xong", verify_step, chi_tiet="Không đủ căn cứ")
                        return AskResult(
                            trang_thai="khong_co_nguon",
                            noi_dung=NO_SOURCE_MESSAGE,
                            cong_cu_da_goi=tools_called,
                            thoi_gian_ms=_elapsed(),
                        )
                    ghi_buoc("xong", verify_step, chi_tiet="Không đạt, thử lại")
                    previous_error = (
                        "Câu trả lời trước không qua kiểm chứng: "
                        f"{exc}. "
                        "Hãy viết lại toàn bộ câu trả lời cùng trích dẫn từ ngữ cảnh đã cấp. "
                        "Không chỉ xoá riêng câu hay trích dẫn hỏng; không bịa mã hoặc con số."
                    )
                else:
                    if verified.trang_thai == "ok":
                        ghi_buoc("xong", verify_step, chi_tiet="Đạt")
                    elif verified.trang_thai == "ngoai_pham_vi":
                        ghi_buoc("xong", verify_step, chi_tiet="Ngoài phạm vi hỗ trợ")
                    else:
                        ghi_buoc("xong", verify_step, chi_tiet="Không đủ căn cứ")
                    return verified

            _log_rejection("llm_schema", "invalid_json_after_retry", len(selected_chunks))
            return AskResult(
                trang_thai="loi",
                noi_dung=ERROR_MESSAGE,
                cong_cu_da_goi=tools_called,
                thoi_gian_ms=_elapsed(),
            )
        except Exception as exc:
            reason = _ask_error_reason(exc)
            _log_rejection(step, reason, len(selected_chunks))
            fallback_step = {
                "context": "chuan_bi",
                "retrieval": "truy_xuat",
                "prompt": "goi_mo_hinh",
                "llm": "goi_mo_hinh",
                "verification": "kiem_chung",
            }.get(step, "chuan_bi")
            _mark_running_step_error(fallback_step, reason)
            return AskResult(
                trang_thai="loi",
                noi_dung=ERROR_MESSAGE,
                trich_dan=[],
                cong_cu_da_goi=tools_called,
                thoi_gian_ms=_elapsed(),
                doan=[],
            )

    def _extract_question_drugs(
        self,
        question: str,
    ) -> list[str]:
        """Tìm hoạt chất được nhắc trực tiếp trong câu hỏi chung."""
        words = re.findall(r"[a-zA-ZÀ-ỹ0-9_-]+", question.lower())
        matched_kb: list[str] = []
        for size in (3, 2, 1):
            for idx in range(len(words) - size + 1):
                phrase = " ".join(words[idx : idx + size])
                for kb_id in _normalize_resolved(self._resolve_name(phrase)):
                    if kb_id not in matched_kb:
                        matched_kb.append(kb_id)
        return matched_kb

    def _build_global_summary(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
    ) -> str:
        """Dựng bảng tóm tắt các ca bệnh cho chế độ hỏi đáp chung."""
        summary_lines = [f"TỔNG QUAN HÀNG ĐỢI Y LỆNH ({len(cases)} ca bệnh đang có trên hệ thống):"]
        for ca in cases:
            kq = results.get(ca.ca_id) or run_case(ca, self._get_renal_rules())
            if ca.nguoi_benh.gioi_tinh == "nam":
                gioi = "Nam"
            elif ca.nguoi_benh.gioi_tinh == "nu":
                gioi = "Nữ"
            else:
                gioi = "Chưa rõ giới"
            tuoi_text = (
                f"{ca.nguoi_benh.tuoi} tuổi" if ca.nguoi_benh.tuoi is not None else "chưa rõ tuổi"
            )
            cd_chinh = next(
                (cd.noi_dung for cd in ca.chan_doan if cd.loai == "chinh"),
                "Chưa rõ",
            )
            drugs_str = ", ".join(
                _format_global_order_line(line) for line in ca.y_lenh_cho_duyet.chi_tiet
            )
            metrics_str = ", ".join(
                f"{cs.cong_thuc}={cs.ket_qua:.1f} {cs.don_vi}"
                for cs in kq.chi_so
                if cs.ket_qua is not None
            )
            attention = [ph for ph in kq.phat_hien if ph.ket_luan != "dat"]
            if attention:
                findings_str = "; ".join(
                    f"[{ph.muc_do}/{ph.ket_luan}] {ph.mo_ta}" for ph in attention
                )
            else:
                findings_str = "Đạt (không có cảnh báo cần xem)"
            summary_lines.append(
                f"- Ca {ca.ca_id} (Mã y lệnh {ca.y_lenh_cho_duyet.y_lenh_id}): "
                f"{gioi} {tuoi_text}, Khoa {ca.y_lenh_cho_duyet.khoa_ke_don}, "
                f"Chẩn đoán: {cd_chinh} | Thuốc kê: {drugs_str} | "
                f"Chỉ số: {metrics_str or 'chưa đủ'} | Kết quả bộ luật: {findings_str}"
            )
        return "\n".join(summary_lines)

    def ask_global(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cau_hoi: str,
        lich_su: list[tuple[str, str]] | None = None,
    ) -> AskResult:
        """Hỏi đáp chung trên danh sách y lệnh và tra cứu kho tri thức khi chưa mở riêng một ca."""
        perf_start = time.perf_counter()
        deadline = time.monotonic() + self._timeout_seconds

        def _elapsed() -> int:
            return int((time.perf_counter() - perf_start) * 1000.0)

        cleaned_question = cau_hoi.strip()
        if not 1 <= len(cleaned_question) <= 1000:
            raise ValueError("cau_hoi phải dài từ 1 đến 1000 ký tự sau khi cắt khoảng trắng")

        if self._llm is None:
            return AskResult(
                trang_thai="chua_san_sang",
                noi_dung=NOT_READY_MESSAGE,
                thoi_gian_ms=_elapsed(),
            )

        existing_vet = vet_hien_tai.get()
        phien_ban = {
            key: value
            for key, value in (
                ("prompt", self._prompt_path.stem),
                ("mo_hinh", self._model_name or ""),
            )
            if value
        }
        trace_cm = (
            nullcontext(existing_vet)
            if existing_vet is not None
            else bat_dau_vet(
                loai="hoi_dap",
                engine="co_dinh",
                ca_id=None,
                phien_ban=phien_ban,
            )
        )
        with trace_cm as vet:
            res = self._ask_global_traced(
                cases,
                results,
                cleaned_question,
                lich_su,
                perf_start=perf_start,
                deadline=deadline,
            )
            if vet is not None:
                vet.dat_trang_thai_cuoi(res.trang_thai)
                return res.model_copy(update={"ma_vet": vet.ma_vet})
            return res

    def _ask_global_traced(
        self,
        cases: Sequence[CaBenh],
        results: dict[str, KetQuaThamDinh],
        cleaned_question: str,
        lich_su: list[tuple[str, str]] | None,
        *,
        perf_start: float,
        deadline: float,
    ) -> AskResult:
        """Thân thực thi ask_global nằm trong phạm vi vết hiện hành."""

        def _elapsed() -> int:
            return int((time.perf_counter() - perf_start) * 1000.0)

        with span("chan_dau_vao", "kiem_tra_chen_lenh", nguon_kiem_tra="cau_hoi") as guard_span:
            if _has_injection_directive(cleaned_question):
                guard_span.dat_trang_thai("tu_choi")
                guard_span.dat_thuoc_tinh(bi_chan=True)
                ghi_su_kien_bao_mat("chen_lenh_dau_vao", nguon="chan_dau_vao")
                vet = vet_hien_tai.get()
                if vet is not None:
                    vet.tang_so_bi_chan()
                ghi_buoc("bat_dau", "chuan_bi", ten="Tổng hợp danh sách y lệnh")
                ghi_buoc("xong", "chuan_bi", chi_tiet="Ngoài phạm vi hỗ trợ")
                return AskResult(
                    trang_thai="ngoai_pham_vi",
                    noi_dung=OUT_OF_SCOPE_MESSAGE,
                    thoi_gian_ms=_elapsed(),
                )
            guard_span.dat_thuoc_tinh(bi_chan=False)

        ghi_buoc("bat_dau", "chuan_bi", ten="Tổng hợp danh sách y lệnh")
        # Câu hỏi chung: không có người bệnh đang mở nên chỉ che theo mẫu (lớp 2);
        # mã ca và mã y lệnh trong bảng tổng quan đổi thành mã tạm, khôi phục ở câu trả lời.
        try:
            session = DeidSession(
                GiaTriDinhDanh(loai="MA", gia_tri=code)
                for ca in cases
                for code in (ca.ca_id, ca.y_lenh_cho_duyet.y_lenh_id)
                if code
            )
            vet = vet_hien_tai.get()
            if vet is not None:
                vet.dat_phien_che(session)
            # Cấp mã ca trước mã khác để mã ca liên tiếp trong cùng phiên.
            for ca in cases:
                session.mask_known(ca.ca_id)
            scrubbed_question, scrubbed_history = _scrub_history_and_question(
                cleaned_question,
                lich_su or [],
                session,
            )
        except Exception:
            ghi_buoc(
                "loi",
                "chuan_bi",
                ly_do="Không soạn được câu trả lời",
                goi_y=_ASK_RETRY_HINT,
            )
            return AskResult(
                trang_thai="loi",
                noi_dung=ERROR_MESSAGE,
                thoi_gian_ms=_elapsed(),
            )
        anh_xa = session.anh_xa

        tools_called = ["danh_sach_y_lenh", "bo_luat"]
        summary_text = self._build_global_summary(cases, results)
        try:
            van_ban_ca = _sanitize_markers(session.mask_known(summary_text))
        except DeidError:
            ghi_buoc(
                "loi",
                "chuan_bi",
                ly_do="Không soạn được câu trả lời",
                goi_y=_ASK_RETRY_HINT,
            )
            return AskResult(
                trang_thai="loi",
                noi_dung=ERROR_MESSAGE,
                thoi_gian_ms=_elapsed(),
            )

        selected_chunks: list[Chunk] = []
        kb_ids = self._extract_question_drugs(scrubbed_question)
        if self._retriever is not None and kb_ids:
            base_q = _DEID_TOKEN_RE.sub(" ", scrubbed_question).strip()
            retrieval_query = RetrievalQuery(
                van_ban=[base_q or " ".join(kb_ids)],
                bo_loc=SearchFilter(hoat_chat_ids=kb_ids),
                k_query=max(self._query_builder.settings.nhan_thuoc.k_query, MAX_ASK_CHUNKS),
                k_rerank=MAX_ASK_CHUNKS,
            )

            def _exec_global() -> list[ScoredChunk]:
                assert self._retriever is not None
                if isinstance(self._retriever, LazyRetrieverFactory):
                    active_ret = self._retriever.for_ingredients(set(kb_ids))
                else:
                    active_ret = self._retriever
                return active_ret.retrieve(retrieval_query)

            try:
                scored = self._run_with_deadline(_exec_global, deadline)
                assert isinstance(scored, list)
                ranked = sorted(scored, key=lambda item: item.diem, reverse=True)
                seen_cids: set[str] = set()
                cand: list[Chunk] = []
                for item in ranked:
                    cid = item.chunk.doan_trich_id
                    if cid not in seen_cids:
                        seen_cids.add(cid)
                        cand.append(item.chunk)
                        if len(cand) >= MAX_ASK_CHUNKS:
                            break
                selected_chunks, doan_nguon_text = _select_evidence_chunks(
                    cand,
                    self._evidence_max_chars,
                )
                if selected_chunks:
                    tools_called.append("truy_xuat")
            except Exception:
                doan_nguon_text = "(không có đoạn nguồn)"
        else:
            doan_nguon_text = "(không có đoạn nguồn)"

        prep_detail = (
            f"{len(cases)} ca, {len(selected_chunks)} đoạn nguồn"
            if selected_chunks
            else f"{len(cases)} ca"
        )
        ghi_buoc("xong", "chuan_bi", chi_tiet=prep_detail)

        chunk_by_id = {c.doan_trich_id: c for c in selected_chunks}
        try:
            prompt_version, template = load_prompt(self._prompt_path)
            lich_su_text = (
                "\n".join(
                    f"- {_ROLE_LABELS.get(role, role)}: {content}"
                    for role, content in scrubbed_history
                )
                if scrubbed_history
                else "(không có)"
            )
            schema = AskLLMOutput.model_json_schema()
            messages = _build_messages(
                template,
                van_ban_ca=van_ban_ca,
                doan_nguon=doan_nguon_text,
                lich_su=lich_su_text,
                cau_hoi=scrubbed_question,
                loi_lan_truoc="Không có.",
            )
            ghi_buoc("bat_dau", "goi_mo_hinh", chi_tiet="Đang gọi mô hình", ten="Soạn câu trả lời")
            llm = self._llm
            assert llm is not None
            raw = self._run_with_deadline(
                lambda msgs=messages, pv=prompt_version: goi_llm_co_vet(
                    llm,
                    msgs,
                    schema,
                    phien_ban_prompt=pv,
                    mo_hinh=self._model_name,
                ),
                deadline,
            )
            parsed = AskLLMOutput.model_validate(raw)
            ghi_buoc("xong", "goi_mo_hinh")
            ghi_buoc("bat_dau", "kiem_chung", ten="Kiểm chứng trích dẫn và số liệu")
            with span("kiem_chung", "kiem_chung_tra_loi_chung") as kc_span:
                reply_text = parsed.tra_loi.strip()
                if not reply_text:
                    kc_span.dat_trang_thai("tu_choi")
                    kc_span.dat_thuoc_tinh(
                        tong_so=1,
                        so_dat=0,
                        so_bi_chan=1,
                        ma_ly_do=["empty_answer"],
                        trang_thai_ket_qua="khong_co_nguon",
                    )
                    vet = vet_hien_tai.get()
                    if vet is not None:
                        vet.tang_so_bi_chan()
                    ghi_buoc("xong", "kiem_chung", chi_tiet="Không đủ căn cứ")
                    return AskResult(
                        trang_thai="khong_co_nguon",
                        noi_dung=NO_SOURCE_MESSAGE,
                        cong_cu_da_goi=tools_called,
                        thoi_gian_ms=_elapsed(),
                    )
                citations: list[AskCitation] = []
                cited_chunks: list[Chunk] = []
                seen_so: set[int] = set()
                dropped_citations = 0
                for item in parsed.trich_dan:
                    if item.so <= 0 or item.so in seen_so:
                        dropped_citations += 1
                        continue
                    if item.loai == "tai_lieu" and item.ma in chunk_by_id:
                        ch = chunk_by_id[item.ma]
                        seen_so.add(item.so)
                        if ch not in cited_chunks:
                            cited_chunks.append(ch)
                        citations.append(
                            AskCitation(
                                so=item.so,
                                loai_ma="tai_lieu",
                                nhan=f"{_source_label(ch.nguon)} · {ch.duong_dan_muc}",
                                ban_ghi_id=None,
                                doan_trich_id=ch.doan_trich_id,
                                trich_nguyen_van=(item.trich_nguyen_van or "").strip() or None,
                            )
                        )
                    elif item.loai == "du_lieu_ca":
                        seen_so.add(item.so)
                        citations.append(
                            AskCitation(
                                so=item.so,
                                loai_ma="du_lieu",
                                nhan=f"Bản ghi ca ({item.ma})",
                                ban_ghi_id=item.ma,
                                doan_trich_id=None,
                                trich_nguyen_van=(item.trich_nguyen_van or "").strip() or None,
                            )
                        )
                    elif item.loai == "tinh_toan":
                        seen_so.add(item.so)
                        citations.append(
                            AskCitation(
                                so=item.so,
                                loai_ma="tinh_toan",
                                nhan=f"Chỉ số {item.ma}",
                                ban_ghi_id=item.ma,
                                doan_trich_id=None,
                                trich_nguyen_van=None,
                            )
                        )
                    else:
                        dropped_citations += 1
                allowed_case_ids = {
                    ca.ca_id
                    for ca in cases
                    if re.fullmatch(r"(?:HS|DEMO)-[A-Za-z0-9]+", ca.ca_id, re.IGNORECASE)
                }
                restored = restore_text(
                    reply_text,
                    {token: value for token, value in anh_xa.items() if value in allowed_case_ids},
                )
                restored = re.sub(r"\[MA_\d+\]", "[đã che]", restored)
                status: Literal["ok", "ngoai_pham_vi"] = (
                    "ngoai_pham_vi" if parsed.pham_vi == "ngoai" else "ok"
                )
                kc_span.dat_thuoc_tinh(
                    tong_so=1,
                    so_dat=1,
                    so_bi_chan=0,
                    ma_ly_do=[],
                    so_trich_dan_bi_loai=dropped_citations,
                    trang_thai_ket_qua=status,
                )
            ghi_buoc(
                "xong",
                "kiem_chung",
                chi_tiet="Ngoài phạm vi hỗ trợ" if status == "ngoai_pham_vi" else "Đạt",
            )
            return AskResult(
                trang_thai=status,
                noi_dung=restored,
                trich_dan=citations,
                cong_cu_da_goi=tools_called,
                thoi_gian_ms=_elapsed(),
                doan=cited_chunks,
            )
        except Exception as exc:
            _mark_running_step_error("goi_mo_hinh", _ask_error_reason(exc))
            return AskResult(
                trang_thai="loi",
                noi_dung=ERROR_MESSAGE,
                cong_cu_da_goi=tools_called,
                thoi_gian_ms=_elapsed(),
            )
