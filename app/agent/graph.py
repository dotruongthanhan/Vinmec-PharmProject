"""Dựng đồ thị LangGraph cho agent hỏi đáp theo ca (không checkpointer).

Sơ đồ:
    START -> che_pii -> chan_dau_vao
    chan_dau_vao -- (đã có ket_qua) ------------------> hoan_tat -> END
    chan_dau_vao -- (qua) -----------------------------> chuan_bi_ngu_canh -> tac_tu
    tac_tu -- (goi_cong_cu & còn lượt & còn giờ) ------> goi_cong_cu -> tac_tu
    tac_tu -- (tra_loi) -------------------------------> kiem_chung
    tac_tu -- (hoi_lai hợp lệ / đã có ket_qua) --------> hoan_tat -> END
    tac_tu -- (khong_du_can_cu / hết lượt / hết giờ / sai lược đồ 2 lần) -> du_phong
    kiem_chung -- (trượt lần 1) -----------------------> tac_tu
    kiem_chung -- (trượt lần 2 / khong_co_nguon) ------> du_phong
    kiem_chung -- (qua) -------------------------------> hoan_tat -> END
    du_phong ---------------------------------> hoan_tat -> END

Ngoại lệ không mong muốn ở bất kỳ nút nào đều được `@an_toan` bắt và rẽ về `du_phong`.

Cách thêm công cụ mới sau này:
1. Tạo lớp kế thừa `Tool` trong `app/agent/tools/`.
2. Đăng ký vào `DanhMucCongCu`.
3. Khai báo quyền trong `config/tool_policy.yaml`.
Không cần sửa đồ thị này.

Cách thêm nút mới:
1. Viết lớp nút trong `app/agent/nodes.py` dùng `@an_toan` và trả dict các trường đổi.
2. Nếu nút ghi trường mới, bổ sung vào `HoiDapState` (`app/agent/state.py`).
3. Đăng ký nút và nối cạnh điều kiện trong `dung_do_thi_hoi_dap` bên dưới.

Đồ thị biên dịch không có checkpointer để không lưu trạng thái chứa dữ liệu ca bệnh.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    ChanDauVao,
    ChePii,
    ChuanBiNguCanh,
    DuPhong,
    GoiCongCu,
    HoanTat,
    KiemChung,
    TacTu,
)
from app.agent.state import HoiDapState
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.config.settings import CaseContextSettings
from app.core.interfaces import LLMClient
from app.rules import RenalRuleBook

CHE_PII = "che_pii"
CHAN_DAU_VAO = "chan_dau_vao"
CHUAN_BI_NGU_CANH = "chuan_bi_ngu_canh"
TAC_TU = "tac_tu"
GOI_CONG_CU = "goi_cong_cu"
KIEM_CHUNG = "kiem_chung"
DU_PHONG = "du_phong"
HOAN_TAT = "hoan_tat"


def _sau_che_pii(state: HoiDapState) -> str:
    if state.get("can_du_phong"):
        return DU_PHONG
    if state.get("ket_qua") is not None:
        return HOAN_TAT
    return CHAN_DAU_VAO


def _sau_chan_dau_vao(state: HoiDapState) -> str:
    if state.get("can_du_phong"):
        return DU_PHONG
    if state.get("ket_qua") is not None:
        return HOAN_TAT
    return CHUAN_BI_NGU_CANH


def _sau_chuan_bi(state: HoiDapState) -> str:
    if state.get("can_du_phong"):
        return DU_PHONG
    return TAC_TU


def _sau_tac_tu(state: HoiDapState) -> str:
    if state.get("can_du_phong"):
        return DU_PHONG
    if state.get("ket_qua") is not None:
        return HOAN_TAT
    ke_hoach = state.get("ke_hoach")
    if ke_hoach is None:
        return TAC_TU
    if ke_hoach.hanh_dong == "goi_cong_cu":
        return GOI_CONG_CU
    if ke_hoach.hanh_dong == "tra_loi":
        return KIEM_CHUNG
    if ke_hoach.hanh_dong == "hoi_lai":
        return HOAN_TAT
    return DU_PHONG


def _sau_goi_cong_cu(state: HoiDapState) -> str:
    if state.get("can_du_phong"):
        return DU_PHONG
    return TAC_TU


def _sau_kiem_chung(state: HoiDapState) -> str:
    if state.get("can_du_phong"):
        return DU_PHONG
    if state.get("ket_qua") is not None:
        return HOAN_TAT
    return TAC_TU


def dung_do_thi_hoi_dap(
    llm: LLMClient,
    danh_muc: DanhMucCongCu,
    chinh_sach: ChinhSachCongCu,
    prompt_path: Path,
    case_settings: CaseContextSettings,
    renal_rules_getter: Callable[[], RenalRuleBook],
    max_turns: int,
) -> Any:
    """Dựng và biên dịch đồ thị hỏi đáp agent; không dùng checkpointer."""
    builder = StateGraph(HoiDapState)
    builder.add_node(CHE_PII, ChePii())
    builder.add_node(CHAN_DAU_VAO, ChanDauVao())
    builder.add_node(CHUAN_BI_NGU_CANH, ChuanBiNguCanh(case_settings, renal_rules_getter))
    builder.add_node(TAC_TU, TacTu(llm, danh_muc, chinh_sach, prompt_path, max_turns))
    builder.add_node(GOI_CONG_CU, GoiCongCu(danh_muc, chinh_sach, max_turns))
    builder.add_node(KIEM_CHUNG, KiemChung())
    builder.add_node(DU_PHONG, DuPhong(llm, max_turns))
    builder.add_node(HOAN_TAT, HoanTat())

    builder.add_edge(START, CHE_PII)
    builder.add_conditional_edges(
        CHE_PII,
        _sau_che_pii,
        {
            CHAN_DAU_VAO: CHAN_DAU_VAO,
            DU_PHONG: DU_PHONG,
            HOAN_TAT: HOAN_TAT,
        },
    )
    builder.add_conditional_edges(
        CHAN_DAU_VAO,
        _sau_chan_dau_vao,
        {
            CHUAN_BI_NGU_CANH: CHUAN_BI_NGU_CANH,
            DU_PHONG: DU_PHONG,
            HOAN_TAT: HOAN_TAT,
        },
    )
    builder.add_conditional_edges(
        CHUAN_BI_NGU_CANH,
        _sau_chuan_bi,
        {
            TAC_TU: TAC_TU,
            DU_PHONG: DU_PHONG,
        },
    )
    builder.add_conditional_edges(
        TAC_TU,
        _sau_tac_tu,
        {
            TAC_TU: TAC_TU,
            GOI_CONG_CU: GOI_CONG_CU,
            KIEM_CHUNG: KIEM_CHUNG,
            DU_PHONG: DU_PHONG,
            HOAN_TAT: HOAN_TAT,
        },
    )
    builder.add_conditional_edges(
        GOI_CONG_CU,
        _sau_goi_cong_cu,
        {
            TAC_TU: TAC_TU,
            DU_PHONG: DU_PHONG,
        },
    )
    builder.add_conditional_edges(
        KIEM_CHUNG,
        _sau_kiem_chung,
        {
            TAC_TU: TAC_TU,
            DU_PHONG: DU_PHONG,
            HOAN_TAT: HOAN_TAT,
        },
    )
    builder.add_edge(DU_PHONG, HOAN_TAT)
    builder.add_edge(HOAN_TAT, END)

    return builder.compile()
