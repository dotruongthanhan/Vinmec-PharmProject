"""Các nút của đồ thị LangGraph cho agent hỏi đáp theo ca."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import replace
from functools import wraps
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agent.state import HoiDapState, KeHoachTacTu, LoiGoiCongCu
from app.agent.tools.base import KetQuaCongCu
from app.agent.tools.gateway import ToolGateway
from app.agent.tools.luong_cu_cung import LuongCuCung
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.config.settings import CaseContextSettings
from app.core.interfaces import LLMClient
from app.core.progress import ghi_buoc, tien_trinh_hien_tai
from app.core.types import ChatMessage
from app.deid.scrubber import DeidError, restore_text
from app.deid.session import DeidSession
from app.llm.case_context import open_deid_session
from app.llm.prompt_loader import load_prompt
from app.orchestration.ask import (
    ERROR_MESSAGE,
    NO_SOURCE_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    AskResult,
    AskVerificationError,
    NguCanhCa,
    _ask_error_reason,
    _has_injection_directive,
    _output_attempts_override,
    _safe_step_error_message,
    _scrub_history_and_question,
    chuan_bi_ngu_canh_ca,
    kiem_chung_tra_loi,
)
from app.rules import RenalRuleBook
from app.verify.number import unverified_numbers

__all__ = [
    "ChanDauVao",
    "ChePii",
    "ChuanBiNguCanh",
    "DuPhongLuongCu",
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
    future = executor.submit(fn)
    try:
        result = future.result(timeout=remaining)
    except FuturesTimeoutError as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError("Quá thời gian xử lý hỏi đáp") from exc
    else:
        executor.shutdown(wait=False)
        return result


def _unwrap_luong_cu_result(
    res: KetQuaCongCu,
    session: DeidSession | None,
    ngu_canh: NguCanhCa | None,
) -> AskResult:
    """Dựng lại AskResult từ kết quả Gateway của luong_cu_cung để không gọi lại LLM."""
    body = res.noi_dung
    prefix = "<<<KET_QUA_CONG_CU ten=luong_cu_cung>>>\n"
    suffix = "\nKET_QUA_CONG_CU>>>"
    if body.startswith(prefix):
        body = body[len(prefix) :]
    if body.endswith(suffix):
        body = body[: -len(suffix)]
    if session is not None:
        body = restore_text(body, session.anh_xa)
    if ngu_canh is not None:
        body = ngu_canh.ids.doi_van_ban_sang_that(body)
    doan = [cc.doan for cc in res.can_cu if cc.doan is not None]
    return AskResult(trang_thai="ok", noi_dung=body, doan=doan)


def an_toan(
    fn: Callable[[Any, HoiDapState], dict[str, Any]],
) -> Callable[[Any, HoiDapState], dict[str, Any]]:
    """Bọc nút đồ thị: không để ngoại lệ thoát ra ngoài, chuyển sang luồng dự phòng."""

    @wraps(fn)
    def wrapper(self: Any, state: HoiDapState) -> dict[str, Any]:
        try:
            return fn(self, state)
        except Exception:
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
        try:
            session = open_deid_session(ctx.ca, []) if ctx.ca is not None else DeidSession()
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
            ghi_buoc(
                "loi",
                "agent_che_pii",
                ly_do="Không che được định danh",
                goi_y="Bấm Thử lại sau ít phút",
            )
            return {
                "ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE),
            }
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
        if _has_injection_directive(cau_hoi_sach) or _has_injection_directive(no_zw):
            ghi_buoc("xong", "agent_chan_dau_vao", chi_tiet="Ngoài phạm vi hỗ trợ")
            return {
                "ket_qua": AskResult(
                    trang_thai="ngoai_pham_vi",
                    noi_dung=OUT_OF_SCOPE_MESSAGE,
                ),
            }
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
        tool_specs = self._danh_muc.mo_ta_cho_llm(allowed_names)
        danh_sach_cong_cu = json.dumps(tool_specs, ensure_ascii=False, indent=2)
        ket_qua_cong_cu = state.get("ket_qua_cong_cu", [])
        doan_nguon = "\n\n".join(ket_qua_cong_cu) if ket_qua_cong_cu else "(chưa gọi công cụ nào)"
        lich_su_che = state.get("lich_su_che", [])
        lich_su_text = (
            "\n".join(
                f"- {_ROLE_LABELS.get(role, role)}: {content}" for role, content in lich_su_che
            )
            if lich_su_che
            else "(không có)"
        )
        so_vong = state.get("so_vong", 0)
        so_vong_con_lai = str(max(0, self._max_turns - so_vong))
        _, template = load_prompt(self._prompt_path)
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

        try:
            raw = _run_with_deadline(
                lambda msgs=messages: self._llm.complete_json(msgs, schema),
                ctx.han_chot,
            )
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
            if so_vong >= self._max_turns:
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

        if ke_hoach.hanh_dong == "tra_loi":
            ghi_buoc("xong", step_ma, chi_tiet="Đủ căn cứ, chuyển kiểm chứng")
            return {
                "ke_hoach": ke_hoach,
                "so_lan_sai_luoc_do": 0,
                "luot_tac_tu": luot,
            }

        if ke_hoach.hanh_dong == "hoi_lai":
            cau_hoi_lai = (ke_hoach.cau_hoi_lai or "").strip()
            has_bad_nums = bool(unverified_numbers([cau_hoi_lai], ngu_canh.allowed_numbers))
            is_override = _output_attempts_override(cau_hoi_lai, ngu_canh.active_result)
            if not cau_hoi_lai or has_bad_nums or is_override:
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
        ket_qua_luong_cu = state.get("ket_qua_luong_cu")

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
            if call.cong_cu == "luong_cu_cung" and res.trang_thai == "ok":
                ket_qua_luong_cu = _unwrap_luong_cu_result(
                    res,
                    state.get("session"),
                    state.get("ngu_canh"),
                )

        updates: dict[str, Any] = {
            "gateway": gateway,
            "can_cu": can_cu,
            "ket_qua_cong_cu": ket_qua_cong_cu,
            "cong_cu_da_goi": cong_cu_da_goi,
            "so_vong": state.get("so_vong", 0) + 1,
        }
        if ket_qua_luong_cu is not None:
            updates["ket_qua_luong_cu"] = ket_qua_luong_cu
        return updates


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

        chi_tiet = "Ngoài phạm vi hỗ trợ" if verified.trang_thai == "ngoai_pham_vi" else "Đạt"
        ghi_buoc("xong", step_ma, chi_tiet=chi_tiet)
        return {
            "so_lan_kiem_chung": attempt,
            "ket_qua": verified,
        }


class DuPhongLuongCu:
    """Đường lui về luồng cũ cứng hoặc thông báo an toàn khi luong_cu_cung bị tắt."""

    def __init__(
        self,
        danh_muc: DanhMucCongCu,
        chinh_sach: ChinhSachCongCu,
        luong_cu: LuongCuCung | None,
    ) -> None:
        self._danh_muc = danh_muc
        self._chinh_sach = chinh_sach
        self._luong_cu = luong_cu

    def __call__(self, state: HoiDapState) -> dict[str, Any]:
        ghi_buoc("bat_dau", "agent_du_phong", ten="Chuyển sang luồng cũ cứng")
        try:
            cached = state.get("ket_qua_luong_cu")
            if cached is not None:
                ghi_buoc("xong", "agent_du_phong", chi_tiet="Dùng kết quả luồng cũ")
                return {"ket_qua": cached}

            fallback_tool = self._luong_cu
            if fallback_tool is None:
                registered = self._danh_muc.lay("luong_cu_cung")
                if isinstance(registered, LuongCuCung):
                    fallback_tool = registered

            if self._chinh_sach.cong_cu_bat("luong_cu_cung") and fallback_tool is not None:
                result = fallback_tool.chay_truc_tiep(state["ctx"])
                cong_cu_da_goi = list(state.get("cong_cu_da_goi", []))
                if "luong_cu_cung" not in cong_cu_da_goi:
                    cong_cu_da_goi.append("luong_cu_cung")
                ghi_buoc("xong", "agent_du_phong", chi_tiet="Dùng kết quả luồng cũ")
                return {"ket_qua": result, "cong_cu_da_goi": cong_cu_da_goi}
        except Exception:
            ghi_buoc("loi", "agent_du_phong", ly_do="Không chạy được luồng dự phòng")
            return {"ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)}

        if state.get("ly_do_du_phong") == "loi":
            ghi_buoc("xong", "agent_du_phong", chi_tiet="Luồng dự phòng đang tắt")
            return {"ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)}

        ghi_buoc("xong", "agent_du_phong", chi_tiet="Không đủ căn cứ")
        return {"ket_qua": AskResult(trang_thai="khong_co_nguon", noi_dung=NO_SOURCE_MESSAGE)}


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
            return {
                "ket_qua": ket_qua.model_copy(
                    update={"cong_cu_da_goi": merged_tools, "thoi_gian_ms": elapsed_ms}
                )
            }
        except Exception:
            return {"ket_qua": AskResult(trang_thai="loi", noi_dung=ERROR_MESSAGE)}
