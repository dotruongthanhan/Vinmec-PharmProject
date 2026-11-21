"""Các nút của đồ thị thẩm định AI; mỗi nút là một lớp nhỏ, nhận phụ thuộc qua hàm khởi tạo.

Quy ước nút:
- `__call__(state)` trả một dict chỉ gồm các trường nút thay đổi.
- Nút không ném ngoại lệ ra ngoài: lỗi không mong muốn được bọc thành `{"loi": ...}` (xem
  `an_toan`); các nút sau thấy `loi` thì bỏ qua, nút `hoan_tat` dựng kết quả chỉ-luật.
- Không nút nào được xoá hoặc hạ phát hiện của bộ luật, không ghi log dữ liệu ca hay prompt.
"""

import time
from collections import Counter
from collections.abc import Callable
from functools import wraps
from typing import Any

from app.core.progress import NguonTomTat, ghi_buoc, tien_trinh_hien_tai
from app.core.types import Chunk
from app.llm.schema import KetQuaLLM, NhanDinhCuoi
from app.llm.synthesizer import Synthesizer
from app.orchestration.evidence import EvidenceCollector
from app.orchestration.graph.result import AiRunResult
from app.orchestration.graph.state import ThamDinhState
from app.pipeline import KetQuaThamDinh

NodeFn = Callable[[ThamDinhState], dict]

_MAX_SOURCE_GROUPS = 8
_SOURCE_LABELS: dict[str, str] = {
    "openfda": "Nhãn FDA",
    "openfda_drug_label": "Nhãn FDA",
    "byt": "Hướng dẫn Bộ Y tế",
    "van_ban_byt": "Văn bản Bộ Y tế",
    "duoc_thu": "Dược thư Quốc gia",
}


def _source_label(nguon: str) -> str:
    """Đổi mã nguồn công khai sang nhãn hiển thị tiếng Việt (không chứa dấu gạch dưới)."""
    return _SOURCE_LABELS.get(nguon, nguon.replace("_", " "))


def canh_bao_loi(exc: Exception) -> str:
    """Câu cảnh báo chung cho lỗi không mong muốn, chỉ nêu tên loại lỗi (không lộ dữ liệu)."""
    return f"Bước AI gặp lỗi không mong muốn ({type(exc).__name__})"


def an_toan(fn: Callable[[Any, ThamDinhState], dict]) -> Callable[[Any, ThamDinhState], dict]:
    """Bọc phương thức nút: bỏ qua khi đã có lỗi, và đổi ngoại lệ thành `{"loi": ...}`."""

    @wraps(fn)
    def wrapper(self: Any, state: ThamDinhState) -> dict:
        if state.get("loi"):
            return {}
        try:
            return fn(self, state)
        except Exception as exc:
            tracker = tien_trinh_hien_tai.get()
            if tracker is not None:
                if isinstance(self, ThuThapNguon):
                    tracker.loi(
                        "thu_thap_nguon",
                        ly_do="Không lấy được nguồn",
                        goi_y="Thử lại; bảng luật vẫn dùng được",
                    )
                else:
                    step_id = tracker.dang_chay_ma() or "tong_hop_1"
                    tracker.loi(
                        step_id,
                        ly_do="Bước tổng hợp gặp lỗi",
                        goi_y="Bảng luật vẫn đúng; bấm Thử lại sau ít phút",
                    )
            return {"loi": canh_bao_loi(exc)}

    return wrapper


def dung_ket_qua_loi(
    synthesizer: object,
    ket_qua: KetQuaThamDinh,
    doan: list[Chunk],
    canh_bao: str,
    bat_dau: float,
) -> AiRunResult:
    """Kết quả chỉ-luật khi bước AI lỗi; y hệt nhánh `except` của đường tuần tự."""
    elapsed_ms = (time.perf_counter() - bat_dau) * 1000.0
    prompt_version = getattr(getattr(synthesizer, "prompt_path", None), "stem", "")
    model_name = getattr(synthesizer, "model_name", None)
    rule_only = [NhanDinhCuoi(nguon_goc="luat", phat_hien=ph) for ph in ket_qua.phat_hien]
    llm_error = KetQuaLLM(
        trang_thai="loi_llm",
        nhan_dinh=rule_only,
        so_lan_goi=0,
        canh_bao=[canh_bao],
        phien_ban_prompt=prompt_version,
        mo_hinh=model_name,
    )
    return AiRunResult(llm=llm_error, doan=doan, canh_bao=[canh_bao], thoi_gian_ms=elapsed_ms)


class ThuThapNguon:
    """Nút thu thập đoạn nguồn và cảnh báo truy xuất bằng `EvidenceCollector.collect`."""

    def __init__(self, collector: EvidenceCollector) -> None:
        self._collector = collector

    @an_toan
    def __call__(self, state: ThamDinhState) -> dict:
        ghi_buoc("bat_dau", "thu_thap_nguon")
        doan, canh_bao = self._collector.collect(state["ca"], state["ket_qua_luat"])
        if doan:
            counts = Counter(chunk.nguon for chunk in doan)
            top_groups = sorted(
                counts.items(),
                key=lambda item: (-item[1], _source_label(item[0])),
            )[:_MAX_SOURCE_GROUPS]
            nguon = [
                NguonTomTat(nhan=_source_label(code), so_doan=count) for code, count in top_groups
            ]
            ghi_buoc(
                "xong",
                "thu_thap_nguon",
                chi_tiet=f"{len(doan)} đoạn từ {len(counts)} nguồn",
                nguon=nguon,
            )
        else:
            ghi_buoc(
                "xong",
                "thu_thap_nguon",
                chi_tiet="Không tìm thấy đoạn nguồn phù hợp",
            )
        return {"doan": doan, "canh_bao": canh_bao}


class TongHop:
    """Nút tổng hợp: gọi `Synthesizer.run` (dựng ngữ cảnh, LLM, kiểm chứng, thử lại, ghép luật)."""

    def __init__(self, synthesizer: Synthesizer) -> None:
        self._synthesizer = synthesizer

    @an_toan
    def __call__(self, state: ThamDinhState) -> dict:
        ket_qua_llm = self._synthesizer.run(state["ca"], state["ket_qua_luat"], state["doan"])
        return {"ket_qua_llm": ket_qua_llm}


class HoanTat:
    """Nút cuối: gộp cảnh báo (bỏ trùng, giữ thứ tự), tính thời gian và dựng `AiRunResult`."""

    def __init__(self, synthesizer: Synthesizer) -> None:
        self._synthesizer = synthesizer

    def __call__(self, state: ThamDinhState) -> dict:
        doan = state.get("doan", [])
        bat_dau = state["thoi_gian_bat_dau"]
        loi = state.get("loi")
        if not loi:
            try:
                ket_qua_llm: KetQuaLLM = state["ket_qua_llm"]
                canh_bao = list(dict.fromkeys([*state.get("canh_bao", []), *ket_qua_llm.canh_bao]))
                elapsed_ms = (time.perf_counter() - bat_dau) * 1000.0
                ket_qua = AiRunResult(
                    llm=ket_qua_llm, doan=doan, canh_bao=canh_bao, thoi_gian_ms=elapsed_ms
                )
                return {"ket_qua": ket_qua}
            except Exception as exc:
                loi = canh_bao_loi(exc)
        ket_qua_loi = dung_ket_qua_loi(self._synthesizer, state["ket_qua_luat"], doan, loi, bat_dau)
        return {"ket_qua": ket_qua_loi}
