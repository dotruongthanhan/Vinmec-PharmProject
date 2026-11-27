"""Các nút của đồ thị LangGraph cho agent hỏi đáp theo ca."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from contextvars import copy_context
from dataclasses import replace
from functools import wraps
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agent.state import HoiDapState, KeHoachTacTu, LoiGoiCongCu
from app.agent.tools.gateway import ToolGateway, _is_iso_time
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.config.settings import CaseContextSettings
from app.core.interfaces import LLMClient
from app.core.progress import ghi_buoc, tien_trinh_hien_tai
from app.core.types import ChatMessage
from app.deid.scrubber import TOKEN_PATTERN, DeidError, restore_text
from app.deid.session import DeidSession
from app.llm.case_context import open_deid_session
from app.llm.prompt_loader import load_prompt
from app.orchestration.ask import (
    ERROR_MESSAGE,
    NO_SOURCE_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    AskResult,
    AskVerificationError,
    _ask_error_reason,
    _has_injection_directive,
    _output_attempts_override,
    _safe_step_error_message,
    _scrub_history_and_question,
    chuan_bi_ngu_canh_ca,
    kiem_chung_tra_loi,
)
from app.rules import RenalRuleBook
from app.tracing import (
    che_chu_so_ma_ly_do,
    dong_buoc_node_dang_chay,
    ghi_su_kien_bao_mat,
    goi_llm_co_vet,
    span,
    vet_hien_tai,
)
from app.verify.number import unverified_numbers

__all__ = [
    "ChanDauVao",
    "ChePii",
    "ChuanBiNguCanh",
    "DuPhong",
    "GoiCongCu",
    "HoanTat",
    "KeHoachTacTu",
    "KiemChung",
    "LoiGoiCongCu",
    "NodeFn",
    "TacTu",
    "an_toan",
]

NodeFn = Callable[[HoiDapState], dict[str, Any]]

_DATA_SPLIT_MARKER = "\n## DỮ LIỆU ĐẦU VÀO\n"
_FALLBACK_SYSTEM_PROMPT = "Bạn là tác tử AI hỗ trợ dược sĩ lâm sàng giải đáp về ca bệnh đang mở."
_ROLE_LABELS = {"nguoi_dung": "Dược sĩ", "he_thong": "Hệ thống"}
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_AGENT_BLOCK_MARKERS = (
    "<<<DANH_SACH_CONG_CU",
    "DANH_SACH_CONG_CU>>>",
    "<<<KET_QUA_CONG_CU",
    "KET_QUA_CONG_CU>>>",
)
_AGENT_PLACEHOLDER_RE = re.compile(
    r"\{\{(van_ban_ca|doan_nguon|lich_su|cau_hoi|loi_lan_truoc|"
    r"danh_sach_cong_cu|so_vong_con_lai)\}\}"
)


def _sanitize_agent_markers(text: str) -> str:
    """Loại bỏ ký hiệu phân khối riêng của prompt tác tử khỏi văn bản không tin cậy."""
    cleaned = text
    for marker in _AGENT_BLOCK_MARKERS:
        while marker in cleaned:
            cleaned = cleaned.replace(marker, "[đã bỏ ký hiệu]")
    return cleaned


def _build_agent_messages(
    template: str,
    *,
    van_ban_ca: str,
    doan_nguon: str,
    lich_su: str,
    cau_hoi: str,
    loi_lan_truoc: str,
    danh_sach_cong_cu: str,
    so_vong_con_lai: str,
) -> list[ChatMessage]:
    """Tách phần chỉ thị hệ thống và dữ liệu đầu vào cho nút tác tử."""
    values = {
        "van_ban_ca": van_ban_ca,
        "doan_nguon": doan_nguon,
        "lich_su": lich_su,
        "cau_hoi": cau_hoi,
        "loi_lan_truoc": loi_lan_truoc,
        "danh_sach_cong_cu": danh_sach_cong_cu,
        "so_vong_con_lai": so_vong_con_lai,
    }

    def _render(part: str) -> str:
        return _AGENT_PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], part)

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


def _run_with_deadline(fn: Callable[[], object], deadline: float) -> object:
    """Chạy tác vụ trong luồng phụ với thời gian còn lại tới hạn chót."""
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


def an_toan(
    fn: Callable[[Any, HoiDapState], dict[str, Any]],
) -> Callable[[Any, HoiDapState], dict[str, Any]]:
    """Bọc nút đồ thị: không để ngoại lệ thoát ra ngoài, chuyển sang luồng dự phòng."""

    @wraps(fn)
    def wrapper(self: Any, state: HoiDapState) -> dict[str, Any]:
        try:
            return fn(self, state)
        except Exception as exc:
            dong_buoc_node_dang_chay(loai_ngoai_le=type(exc).__name__)
            tracker = tien_trinh_hien_tai.get()
            if tracker is not None:
                step_id = tracker.dang_chay_ma()
                if step_id is not None:
                    tracker.loi(
                        step_id,
                        ly_do="Bước xử lý gặp lỗi",
                        goi_y="Chuyển sang luồng dự phòng",
                    )
            return {"can_du_phong": True, "ly_do_du_phong": "loi"}

    return wrapper


class ChePii:
    """Mở DeidSession theo ca và che định danh cho câu hỏi cùng lịch sử hội thoại."""

    @an_toan
    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        ghi_buoc("bat_dau", "agent_che_pii", ten="Che thông tin định danh")
        ctx = state["ctx"]
        cau_hoi_sach = state["cau_hoi_sach"]
        with span("che_pii", "che_dinh_danh") as pii_span:
            try:
                session = open_deid_session(ctx.ca, []) if ctx.ca is not None else DeidSession()
                vet = vet_hien_tai.get()
                if vet is not None:
                    vet.dat_phien_che(session)
                cau_hoi_che, lich_su_che = _scrub_history_and_question(
                    cau_hoi_sach,
                    ctx.lich_su_goc,
                    session,
                )
                cau_hoi_che = _sanitize_agent_markers(cau_hoi_che)
                lich_su_che = [
                    (role, _sanitize_agent_markers(content)) for role, content in lich_su_che
                ]
            except DeidError:
                pii_span.dat_trang_thai("loi")
                pii_span.dat_thuoc_tinh(thanh_cong=False, loai_ngoai_le="DeidError")
                ghi_buoc(
                    "loi",
                    "agent_che_pii",
                    ly_do="Không che được định danh",
                    goi_y="Bấm Thử lại sau ít phút",
                )
                return {
                    "ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE),
                }
            kinds = sorted({key.strip("[]").rsplit("_", 1)[0] for key in session.anh_xa})
            pii_span.dat_thuoc_tinh(
                so_ma_tam=len(session.anh_xa),
                loai_dinh_danh=kinds,
                thanh_cong=True,
            )
        ghi_buoc("xong", "agent_che_pii")
        return {
            "session": session,
            "ctx": replace(ctx, deid_session=session),
            "cau_hoi_che": cau_hoi_che,
            "lich_su_che": lich_su_che,
        }


class ChanDauVao:
    """Chặn câu hỏi chứa chỉ thị vượt quyền hoặc ép duyệt đơn trước khi gọi LLM."""

    @an_toan
    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        ghi_buoc("bat_dau", "agent_chan_dau_vao", ten="Kiểm tra câu hỏi")
        cau_hoi_sach = state["cau_hoi_sach"]
        no_zw = _ZERO_WIDTH_RE.sub("", cau_hoi_sach)
        with span("chan_dau_vao", "kiem_tra_chen_lenh", nguon_kiem_tra="cau_hoi") as guard_span:
            if _has_injection_directive(cau_hoi_sach) or _has_injection_directive(no_zw):
                guard_span.dat_trang_thai("tu_choi")
                guard_span.dat_thuoc_tinh(bi_chan=True)
                ghi_su_kien_bao_mat("chen_lenh_dau_vao", nguon="chan_dau_vao")
                vet = vet_hien_tai.get()
                if vet is not None:
                    vet.tang_so_bi_chan()
                ghi_buoc("xong", "agent_chan_dau_vao", chi_tiet="Ngoài phạm vi hỗ trợ")
                return {
                    "ket_qua": AskResult(
                        trang_thai="ngoai_pham_vi",
                        noi_dung=OUT_OF_SCOPE_MESSAGE,
                    ),
                }
            guard_span.dat_thuoc_tinh(bi_chan=False)
        ghi_buoc("xong", "agent_chan_dau_vao")
        return {}


class ChuanBiNguCanh:
    """Chạy bộ luật (nếu chưa có) và dựng gói ngữ cảnh ca đã che định danh."""

    def __init__(
        self,
        case_settings: CaseContextSettings,
        renal_rules_getter: Callable[[], RenalRuleBook],
    ) -> None:
        self._case_settings = case_settings
        self._renal_rules_getter = renal_rules_getter

    @an_toan
    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        ghi_buoc("bat_dau", "agent_ngu_canh", ten="Đọc hồ sơ ca và chạy bộ luật")
        ctx = state["ctx"]
        assert ctx.ca is not None
        ngu_canh = chuan_bi_ngu_canh_ca(
            ctx.ca,
            ctx.ket_qua_luat,
            ctx.ai_result,
            ctx.nhan_dinh_id,
            state["session"],
            self._case_settings,
            self._renal_rules_getter,
        )
        ghi_buoc(
            "xong",
            "agent_ngu_canh",
            chi_tiet=f"{len(ngu_canh.active_result.phat_hien)} phát hiện của bộ luật",
        )
        return {"ngu_canh": ngu_canh}


class TacTu:
    """Gọi LLM một lần để lập kế hoạch JSON theo lược đồ KeHoachTacTu."""

    def __init__(
        self,
        llm: LLMClient,
        danh_muc: DanhMucCongCu,
        chinh_sach: ChinhSachCongCu,
        prompt_path: Path,
        max_turns: int,
    ) -> None:
        self._llm = llm
        self._danh_muc = danh_muc
        self._chinh_sach = chinh_sach
        self._prompt_path = Path(prompt_path)
        self._max_turns = max_turns

    @an_toan
    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        luot = state.get("luot_tac_tu", 0) + 1
        step_ma = f"agent_tac_tu_{luot}"
        ghi_buoc("bat_dau", step_ma, ten=f"Agent lập kế hoạch, lượt {luot}")

        ctx = state["ctx"]
        if time.monotonic() >= ctx.han_chot:
            ghi_buoc("xong", step_ma, chi_tiet="Hết thời gian xử lý")
            return {
                "luot_tac_tu": luot,
                "can_du_phong": True,
                "ly_do_du_phong": "het_gio",
            }

        ngu_canh = state["ngu_canh"]
        allowed_names = self._chinh_sach.cac_cong_cu_duoc_phep(
            ctx.vai_tro,
            ctx.che_do,
            self._danh_muc,
        )
        forced_answer = state.get("buoc_tra_loi_chu", False)
        if forced_answer:
            allowed_names = []
        tool_specs = self._danh_muc.mo_ta_cho_llm(allowed_names)
        danh_sach_cong_cu = json.dumps(tool_specs, ensure_ascii=False, indent=2)
        ket_qua_cong_cu = state.get("ket_qua_cong_cu", [])
        doan_nguon = "\n\n".join(ket_qua_cong_cu) if ket_qua_cong_cu else "(chưa gọi công cụ nào)"
        lich_su_che = state.get("lich_su_che", [])
        lich_su_text = (
            "\n".join(
                f"- {_ROLE_LABELS.get(role, role)}: "
                + (
                    re.sub(r"mh-\d+", "hình (không còn hiển thị)", content)
                    if role == "he_thong"
                    else content
                )
                for role, content in lich_su_che
            )
            if lich_su_che
            else "(không có)"
        )
        so_vong = state.get("so_vong", 0)
        so_vong_con_lai = str(max(0, self._max_turns - so_vong))
        prompt_version, template = load_prompt(self._prompt_path)
        if "ve_bieu_do" in allowed_names:
            _, skill = load_prompt(self._prompt_path.parent / "ky_nang_minh_hoa.v1.md")
            template = template.replace(_DATA_SPLIT_MARKER, "\n\n" + skill + _DATA_SPLIT_MARKER, 1)
        messages = _build_agent_messages(
            template,
            van_ban_ca=ngu_canh.van_ban_ca,
            doan_nguon=doan_nguon,
            lich_su=lich_su_text,
            cau_hoi=state["cau_hoi_che"],
            loi_lan_truoc=state.get("loi_lan_truoc") or "Không có.",
            danh_sach_cong_cu=danh_sach_cong_cu,
            so_vong_con_lai=so_vong_con_lai,
        )
        schema = KeHoachTacTu.model_json_schema()
        if forced_answer:
            schema["properties"]["hanh_dong"]["enum"] = ["tra_loi", "hoi_lai"]
            with span("node", "buoc_tra_loi_chu", buoc_tra_loi_chu=True):
                pass

        def _call_llm() -> object:
            vet = vet_hien_tai.get()
            has_drawing_hint = any(
                "mã căn cứ hợp lệ:" in result or "bộ dữ liệu và cột hiện có:" in result
                for result in ket_qua_cong_cu
            )
            if vet is None or not has_drawing_hint:
                return goi_llm_co_vet(self._llm, messages, schema, phien_ban_prompt=prompt_version)
            # Không ghi lại danh sách gợi ý trong prompt hay phản hồi của LLM.
            previous_level = vet.muc_noi_dung
            vet.muc_noi_dung = "sieu_du_lieu"
            try:
                return goi_llm_co_vet(self._llm, messages, schema, phien_ban_prompt=prompt_version)
            finally:
                vet.muc_noi_dung = previous_level

        try:
            raw = _run_with_deadline(_call_llm, ctx.han_chot)
        except TimeoutError:
            ghi_buoc("loi", step_ma, ly_do="Hết thời gian xử lý")
            return {
                "luot_tac_tu": luot,
                "can_du_phong": True,
                "ly_do_du_phong": "het_gio",
            }
        except Exception as exc:
            reason = _ask_error_reason(exc)
            ghi_buoc(
                "loi",
                step_ma,
                ly_do=_safe_step_error_message(reason),
                goi_y="Chuyển sang luồng dự phòng",
            )
            return {
                "luot_tac_tu": luot,
                "can_du_phong": True,
                "ly_do_du_phong": "loi",
            }

        try:
            ke_hoach = KeHoachTacTu.model_validate(raw)
        except ValidationError as exc:
            errors = "; ".join(
                f"{'.'.join(map(str, err['loc']))}:{err['type']}"
                for err in exc.errors(include_input=False, include_context=False)
            )
            sai_count = state.get("so_lan_sai_luoc_do", 0) + 1
            next_round = so_vong + 1
            if forced_answer and sai_count < 2:
                return {
                    "luot_tac_tu": luot,
                    "so_lan_sai_luoc_do": sai_count,
                    "can_du_phong": True,
                    "ly_do_du_phong": "khong_du_can_cu",
                }
            if sai_count >= 2 or next_round >= self._max_turns:
                ghi_buoc("loi", step_ma, ly_do="Đầu ra sai định dạng")
                return {
                    "ke_hoach": None,
                    "so_vong": next_round,
                    "so_lan_sai_luoc_do": sai_count,
                    "luot_tac_tu": luot,
                    "can_du_phong": True,
                    "ly_do_du_phong": "loi",
                }
            ghi_buoc("xong", step_ma, chi_tiet="Đầu ra sai định dạng, thử lại")
            return {
                "ke_hoach": None,
                "so_vong": next_round,
                "so_lan_sai_luoc_do": sai_count,
                "luot_tac_tu": luot,
                "loi_lan_truoc": (
                    f"Lần trước sai lược đồ JSON ({errors}). "
                    "Chỉ trả về đúng đối tượng JSON hợp lệ khớp lược đồ KeHoachTacTu."
                ),
            }

        if forced_answer and ke_hoach.hanh_dong not in ("tra_loi", "hoi_lai"):
            return {
                "ke_hoach": None,
                "luot_tac_tu": luot,
                "can_du_phong": True,
                "ly_do_du_phong": "khong_du_can_cu",
            }

        if ke_hoach.hanh_dong == "goi_cong_cu":
            if time.monotonic() >= ctx.han_chot:
                ghi_buoc("xong", step_ma, chi_tiet="Hết thời gian xử lý")
                return {
                    "ke_hoach": ke_hoach,
                    "so_lan_sai_luoc_do": 0,
                    "luot_tac_tu": luot,
                    "can_du_phong": True,
                    "ly_do_du_phong": "het_gio",
                }
            chi_ve = bool(ke_hoach.goi) and all(
                call.cong_cu == "ve_bieu_do" for call in ke_hoach.goi
            )
            if chi_ve and state.get("so_vong_ve", 0) >= 3:
                if state.get("da_nhac_het_luot_ve", False):
                    if state.get("da_buoc_tra_loi_chu", False):
                        return {
                            "ke_hoach": None,
                            "luot_tac_tu": luot,
                            "can_du_phong": True,
                            "ly_do_du_phong": "khong_du_can_cu",
                        }
                    return {
                        "ke_hoach": None,
                        "luot_tac_tu": luot,
                        "buoc_tra_loi_chu": True,
                        "da_buoc_tra_loi_chu": True,
                        "loi_lan_truoc": (
                            "het_luot_ve: không còn công cụ; chỉ được trả lời bằng chữ "
                            "hoặc hỏi lại, không gọi công cụ."
                        ),
                    }
                return {
                    "ke_hoach": None,
                    "luot_tac_tu": luot,
                    "da_nhac_het_luot_ve": True,
                    "loi_lan_truoc": "het_luot_ve: không vẽ thêm, hãy trả lời bằng chữ",
                }
            if not chi_ve and so_vong >= self._max_turns:
                ghi_buoc("xong", step_ma, chi_tiet="Hết lượt gọi công cụ")
                return {
                    "ke_hoach": ke_hoach,
                    "so_lan_sai_luoc_do": 0,
                    "luot_tac_tu": luot,
                    "can_du_phong": True,
                    "ly_do_du_phong": "het_luot",
                }
            ghi_buoc("xong", step_ma, chi_tiet=f"Đề xuất {len(ke_hoach.goi)} công cụ")
            return {
                "ke_hoach": ke_hoach,
                "so_lan_sai_luoc_do": 0,
                "luot_tac_tu": luot,
            }

        if (
            ke_hoach.hanh_dong in ("tra_loi", "khong_du_can_cu")
            and nguoi_dung_yeu_cau_ve(state["cau_hoi_sach"])
            and _NHAC_VE not in ket_qua_cong_cu
            and not (state.get("gateway") and state["gateway"].minh_hoa)
            and so_vong < self._max_turns
            and not forced_answer
        ):
            return {
                "ke_hoach": None,
                "luot_tac_tu": luot,
                "ket_qua_cong_cu": [*ket_qua_cong_cu, _NHAC_VE],
                "loi_lan_truoc": _NHAC_VE,
            }

        if ke_hoach.hanh_dong == "tra_loi":
            ghi_buoc("xong", step_ma, chi_tiet="Đủ căn cứ, chuyển kiểm chứng")
            return {
                "ke_hoach": ke_hoach,
                "buoc_tra_loi_chu": False,
                "so_lan_sai_luoc_do": 0,
                "luot_tac_tu": luot,
            }

        if ke_hoach.hanh_dong == "hoi_lai":
            cau_hoi_lai = (ke_hoach.cau_hoi_lai or "").strip()
            bad_nums = unverified_numbers([cau_hoi_lai], ngu_canh.allowed_numbers)
            is_override = _output_attempts_override(cau_hoi_lai, ngu_canh.active_result)
            if not cau_hoi_lai or bad_nums or is_override:
                reasons = [che_chu_so_ma_ly_do(item) for item in bad_nums]
                if not cau_hoi_lai:
                    reasons.append("empty_followup")
                if is_override:
                    reasons.append("output_attempts_override")
                with span(
                    "kiem_chung",
                    "kiem_chung_hoi_lai",
                    so_bi_chan=1,
                    so_dat=0,
                    tong_so=1,
                    ma_ly_do=reasons,
                    trang_thai_ket_qua="tu_choi",
                ) as kc_span:
                    kc_span.dat_trang_thai("tu_choi")
                if is_override:
                    ghi_su_kien_bao_mat("chen_lenh_dau_ra", nguon="tac_tu")
                vet = vet_hien_tai.get()
                if vet is not None:
                    vet.tang_so_bi_chan()
                ghi_buoc("xong", step_ma, chi_tiet="Câu hỏi lại không đạt kiểm chứng")
                return {
                    "ke_hoach": ke_hoach,
                    "so_lan_sai_luoc_do": 0,
                    "luot_tac_tu": luot,
                    "can_du_phong": True,
                    "ly_do_du_phong": "khong_du_can_cu",
                }
            restored = ngu_canh.ids.doi_van_ban_sang_that(
                restore_text(cau_hoi_lai, ngu_canh.anh_xa)
            )
            ghi_buoc("xong", step_ma, chi_tiet="Hỏi lại dược sĩ")
            return {
                "ke_hoach": ke_hoach,
                "so_lan_sai_luoc_do": 0,
                "luot_tac_tu": luot,
                "ket_qua": AskResult(trang_thai="ok", noi_dung=restored, trich_dan=[]),
            }

        ghi_buoc("xong", step_ma, chi_tiet="Chuyển luồng dự phòng")
        return {
            "ke_hoach": ke_hoach,
            "so_lan_sai_luoc_do": 0,
            "luot_tac_tu": luot,
            "can_du_phong": True,
            "ly_do_du_phong": "khong_du_can_cu",
        }


class GoiCongCu:
    """Thực thi tuần tự tối đa 3 lời gọi công cụ mỗi vòng qua ToolGateway."""

    def __init__(
        self,
        danh_muc: DanhMucCongCu,
        chinh_sach: ChinhSachCongCu,
        max_turns: int,
    ) -> None:
        self._danh_muc = danh_muc
        self._chinh_sach = chinh_sach
        self._max_turns = max_turns

    @an_toan
    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        ke_hoach = state.get("ke_hoach")
        assert ke_hoach is not None
        ctx = state["ctx"]
        gateway = state.get("gateway")
        if gateway is None:
            gateway = ToolGateway(
                self._danh_muc,
                self._chinh_sach,
                so_lan_goi_toi_da=self._max_turns * 3,
            )

        can_cu = list(state.get("can_cu", []))
        ket_qua_cong_cu = list(state.get("ket_qua_cong_cu", []))
        cong_cu_da_goi = list(state.get("cong_cu_da_goi", []))
        chi_ve = bool(ke_hoach.goi) and all(call.cong_cu == "ve_bieu_do" for call in ke_hoach.goi)
        vong = state.get("so_vong", 0) + (not chi_ve)
        vong_ve = state.get("so_vong_ve", 0) + chi_ve

        with span("node", f"agent_goi_cong_cu_{vong}", so_vong=vong):
            for call in ke_hoach.goi[:3]:
                res = gateway.goi(call.cong_cu, call.tham_so, ctx)
                if res.trang_thai == "tu_choi":
                    ket_qua_cong_cu.append(
                        f"<<<KET_QUA_CONG_CU ten={call.cong_cu} tu_choi=true>>>\n"
                        f"Bị từ chối ({res.ma_loi}): {res.noi_dung}\n"
                        "KET_QUA_CONG_CU>>>"
                    )
                    continue

                if res.noi_dung:
                    ket_qua_cong_cu.append(res.noi_dung)
                if res.can_cu:
                    can_cu.extend(res.can_cu)
                if call.cong_cu not in cong_cu_da_goi:
                    cong_cu_da_goi.append(call.cong_cu)

        if chi_ve and vong_ve == 3:
            ket_qua_cong_cu.append(
                "<<<KET_QUA_CONG_CU ten=ve_bieu_do tu_choi=true>>>\n"
                "het_luot_ve: không vẽ thêm, hãy trả lời bằng chữ\n"
                "KET_QUA_CONG_CU>>>"
            )

        return {
            "gateway": gateway,
            "can_cu": can_cu,
            "ket_qua_cong_cu": ket_qua_cong_cu,
            "cong_cu_da_goi": cong_cu_da_goi,
            "so_vong": vong,
            "so_vong_ve": vong_ve,
        }


_NHAC_HINH = re.compile(
    r"(?:xem\s+(?:hình|biểu đồ|minh hoạ|minh họa)|"
    r"(?:hình|biểu đồ|minh hoạ|minh họa)\s+(?:ở\s+)?(?:bên\s+)?dưới)",
    re.IGNORECASE,
)
_YEU_CAU_VE = re.compile(
    r"\b(?:vẽ|biểu đồ|đồ thị|minh hoạ|minh họa|hình(?!\s+(?:thức|ảnh\s+học))|chart|plot)\b",
    re.IGNORECASE,
)
_NHAC_VE = (
    "Dược sĩ đã yêu cầu hình; hãy gọi ve_bieu_do với bộ dữ liệu đã có hoặc lấy dữ liệu cần thiết."
)


def nguoi_dung_yeu_cau_ve(cau_hoi: str) -> bool:
    """Nhận diện yêu cầu hình trong câu hỏi."""
    question = re.sub(r"\bđịnh\s+hình\b", "", cau_hoi, flags=re.IGNORECASE)
    return bool(_YEU_CAU_VE.search(question))


def _filter_missing_figure(text: str, question: str) -> str:
    """Bỏ câu dẫn tới hình không tồn tại sau kiểm chứng."""
    kept = text
    if _NHAC_HINH.search(text):
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        kept = " ".join(part for part in sentences if not _NHAC_HINH.search(part)).strip()
    if nguoi_dung_yeu_cau_ve(question):
        kept = f"{kept}\nChưa dựng được hình cho câu hỏi này.".strip()
    return kept


class KiemChung:
    """Kiểm chứng câu trả lời của agent bằng hàm dùng chung kiem_chung_tra_loi."""

    @an_toan
    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        attempt = state.get("so_lan_kiem_chung", 0) + 1
        step_ma = f"agent_kiem_chung_{attempt}"
        ghi_buoc("bat_dau", step_ma, ten="Kiểm chứng trích dẫn và số liệu")

        ke_hoach = state.get("ke_hoach")
        assert ke_hoach is not None and ke_hoach.tra_loi is not None
        ngu_canh = state["ngu_canh"]
        ctx = state["ctx"]
        assert ctx.ca is not None

        chunk_by_id = {
            cc.doan.doan_trich_id: cc.doan
            for cc in state.get("can_cu", [])
            if cc.loai == "doan" and cc.doan is not None
        }
        bang_by_ma = {
            cc.ma: (cc.nhan, cc.noi_dung)
            for cc in state.get("can_cu", [])
            if cc.loai in ("bang", "tinh") and cc.noi_dung
        }
        try:
            verified = kiem_chung_tra_loi(
                ca=ctx.ca,
                ket_qua=ngu_canh.active_result,
                cleaned_question=state["cau_hoi_sach"],
                output=ke_hoach.tra_loi,
                allowed_record_ids=ngu_canh.allowed_record_ids,
                allowed_calc_ids=ngu_canh.allowed_calc_ids,
                allowed_numbers=ngu_canh.allowed_numbers,
                chunk_by_id=chunk_by_id,
                anh_xa=ngu_canh.anh_xa,
                ids=ngu_canh.ids,
                tools_called=list(state.get("cong_cu_da_goi", [])),
                perf_start=state.get("thoi_gian_bat_dau", time.perf_counter()),
                bang_by_ma=bang_by_ma,
            )
        except AskVerificationError as exc:
            if attempt == 1:
                ghi_buoc("xong", step_ma, chi_tiet="Không đạt, thử lại")
                return {
                    "so_lan_kiem_chung": attempt,
                    "loi_lan_truoc": (
                        "Câu trả lời trước không qua kiểm chứng: "
                        f"{exc}. "
                        "Hãy viết lại toàn bộ câu trả lời cùng trích dẫn từ ngữ cảnh đã cấp. "
                        "Không chỉ xoá riêng câu hay trích dẫn hỏng; không bịa mã hoặc con số."
                    ),
                }
            ghi_buoc("xong", step_ma, chi_tiet="Chuyển luồng dự phòng")
            return {
                "so_lan_kiem_chung": attempt,
                "can_du_phong": True,
                "ly_do_du_phong": "truot_kiem_chung",
            }

        if verified.trang_thai == "khong_co_nguon":
            ghi_buoc("xong", step_ma, chi_tiet="Không đủ căn cứ, chuyển luồng dự phòng")
            return {
                "so_lan_kiem_chung": attempt,
                "can_du_phong": True,
                "ly_do_du_phong": "khong_du_can_cu",
            }

        if verified.trang_thai == "ok" and state.get("gateway") is not None:
            blocks = []
            for block in state["gateway"].minh_hoa:
                checked = block.model_dump(mode="json")
                for dataset in checked["bo_du_lieu"]:
                    time_columns = {
                        col["ten"] for col in dataset["cot"] if col["kieu"] == "thoi_gian"
                    }
                    for row in dataset["dong"]:
                        for key in time_columns:
                            value = row.get(key)
                            if isinstance(value, str) and _is_iso_time(value):
                                row[key] = None
                serialized = json.dumps(checked, ensure_ascii=False)
                session = state["session"]
                try:
                    masked_tokens = re.sub(TOKEN_PATTERN, "", serialized)
                    has_pii = (
                        session.mask_known(serialized) != serialized
                        or session.scrub(masked_tokens) != masked_tokens
                    )
                except DeidError:
                    has_pii = True
                if has_pii:
                    with span(
                        "tool", "kiem_pii_minh_hoa", ly_do_tu_choi="pii_trong_khoi"
                    ) as pii_span:
                        pii_span.dat_trang_thai("tu_choi")
                else:
                    blocks.append(block)
            verified = verified.model_copy(update={"minh_hoa": blocks})

        if verified.trang_thai == "ok" and not verified.minh_hoa:
            verified = verified.model_copy(
                update={
                    "noi_dung": _filter_missing_figure(verified.noi_dung, state["cau_hoi_sach"])
                }
            )

        chi_tiet = "Ngoài phạm vi hỗ trợ" if verified.trang_thai == "ngoai_pham_vi" else "Đạt"
        ghi_buoc("xong", step_ma, chi_tiet=chi_tiet)
        return {
            "so_lan_kiem_chung": attempt,
            "ket_qua": verified,
        }


class DuPhong:
    """Kết thúc an toàn khi agent lỗi, hết lượt, hết giờ hoặc không đủ căn cứ.

    Không còn gọi luồng cũ: đường lui về luồng cũ nằm ở cờ `ask.engine: co_dinh`
    (người dùng chốt 22/11/2026, plan 1.9 mục 6.6).
    """

    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        ghi_buoc("bat_dau", "agent_du_phong", ten="Kết thúc an toàn")
        if state.get("ly_do_du_phong") == "loi":
            ghi_buoc("xong", "agent_du_phong", chi_tiet="Gặp lỗi khi xử lý")
            return {"ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)}
        ghi_buoc("xong", "agent_du_phong", chi_tiet="Không đủ căn cứ")
        content = _filter_missing_figure(NO_SOURCE_MESSAGE, state.get("cau_hoi_sach", ""))
        return {"ket_qua": AskResult(trang_thai="khong_co_nguon", noi_dung=content)}


class HoanTat:
    """Nút cuối cùng: bảo đảm có AskResult, ghép cong_cu_da_goi và tính thời gian chạy."""

    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        try:
            bat_dau = state.get("thoi_gian_bat_dau")
            elapsed_ms = int((time.perf_counter() - bat_dau) * 1000.0) if bat_dau is not None else 0
            ket_qua = state.get("ket_qua")
            if ket_qua is None:
                ket_qua = AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)
            merged_tools = list(
                dict.fromkeys([*ket_qua.cong_cu_da_goi, *state.get("cong_cu_da_goi", [])])
            )
            vet = vet_hien_tai.get()
            ma_vet = vet.ma_vet if vet is not None else ket_qua.ma_vet
            if vet is not None:
                vet.dat_trang_thai_cuoi(ket_qua.trang_thai)
            return {
                "ket_qua": ket_qua.model_copy(
                    update={
                        "cong_cu_da_goi": merged_tools,
                        "thoi_gian_ms": elapsed_ms,
                        "ma_vet": ma_vet,
                    }
                )
            }
        except Exception:
            return {"ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)}
