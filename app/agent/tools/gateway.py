"""Chốt an toàn duy nhất giữa LLM và công cụ: quyền, ngân sách, PII, chèn lệnh và kiểm toán."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from threading import Lock
from typing import Any

from pydantic import ValidationError

from app.agent.tools.base import KetQuaCongCu, Tool, ToolContext
from app.agent.tools.policy import ChinhSachCongCu
from app.agent.tools.registry import DanhMucCongCu
from app.core.progress import ghi_buoc
from app.deid.scrubber import TOKEN_PATTERN, DeidError
from app.deid.session import DeidSession
from app.orchestration.ask import _has_injection_directive

_AUDIT_LOGGER = logging.getLogger("app.agent.audit")
_DEID_TOKEN_RE = re.compile(TOKEN_PATTERN)
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_MAX_TOOL_OUTPUT_CHARS = 8000
_SCRUB_FALLBACK = "[không đưa được kết quả vào vì lỗi che định danh]"
_INJECTION_BLOCKED_MESSAGE = "Kết quả công cụ có câu giống chỉ thị nên bị loại."
_BLOCK_MARKERS = (
    "<<<DU_LIEU_BENH_AN",
    "DU_LIEU_BENH_AN>>>",
    "<<<DOAN_NGUON",
    "DOAN_NGUON>>>",
    "<<<LICH_SU",
    "LICH_SU>>>",
    "<<<CAU_HOI",
    "CAU_HOI>>>",
    "<<<KET_QUA_CONG_CU",
    "KET_QUA_CONG_CU>>>",
)
_SAFE_STEP_REASONS: dict[str, str] = {
    "khong_co_cong_cu": "Công cụ không tồn tại",
    "khong_co_quyen": "Không có quyền gọi công cụ",
    "het_ngan_sach": "Đã hết lượt gọi công cụ",
    "het_gio": "Hết thời gian xử lý công cụ",
    "sai_tham_so": "Tham số công cụ không hợp lệ",
    "tham_so_co_dinh_danh": "Tham số chứa định danh người bệnh",
    "nghi_chen_lenh": "Kết quả công cụ bị nghi chèn lệnh",
    "loi_cong_cu": "Công cụ gặp lỗi khi thực thi",
}


def _sanitize_markers(text: str) -> str:
    """Loại bỏ các chuỗi phân tách khối dữ liệu khỏi văn bản kết quả công cụ."""
    cleaned = text
    for marker in _BLOCK_MARKERS:
        while marker in cleaned:
            cleaned = cleaned.replace(marker, "[đã bỏ ký hiệu]")
    return cleaned


def _iter_strings(value: Any) -> Iterator[str]:
    """Duyệt mọi chuỗi nằm trong giá trị tham số kể cả lồng trong list/dict."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str):
                yield key
            yield from _iter_strings(item)
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _iter_strings(item)


def _string_has_pii(text: str, session: DeidSession) -> bool:
    """Kiểm tra chuỗi tham số có chứa định danh thật ngoài mã tạm hợp lệ hay không."""
    try:
        if session.mask_known(text) != text:
            return True
        if _DEID_TOKEN_RE.search(text) is None and session.scrub(text) != text:
            return True
    except DeidError:
        return True
    return False


def _params_contain_pii(data: Any, session: DeidSession) -> bool:
    """Quét PII trên toàn bộ chuỗi trong tham số đã xác thực."""
    return any(_string_has_pii(text, session) for text in _iter_strings(data))


def _hash_case_id(ctx: ToolContext) -> str:
    """Băm mã ca sang 12 ký tự hex để ghi nhật ký kiểm toán."""
    if ctx.ca is not None and ctx.ca.ca_id:
        return hashlib.sha256(ctx.ca.ca_id.encode("utf-8")).hexdigest()[:12]
    return "-"


def _run_tool_with_timeout(
    tool: Tool,
    tham_so: Any,
    ctx: ToolContext,
    timeout: float,
) -> KetQuaCongCu:
    """Chạy công cụ trong luồng phụ với giới hạn thời gian như CaseAsker._run_with_deadline."""
    if timeout <= 0:
        raise TimeoutError("Hết thời gian xử lý công cụ")
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(tool.chay, tham_so, ctx)
    try:
        result = future.result(timeout=timeout)
    except FuturesTimeoutError as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError("Công cụ chạy quá thời gian cho phép") from exc
    else:
        executor.shutdown(wait=False)
        return result


class ToolGateway:
    """Chốt kiểm soát duy nhất cho mọi lần gọi công cụ trong một lượt hỏi đáp."""

    def __init__(
        self,
        danh_muc: DanhMucCongCu,
        chinh_sach: ChinhSachCongCu,
        so_lan_goi_toi_da: int,
    ) -> None:
        self._danh_muc = danh_muc
        self._chinh_sach = chinh_sach
        self._so_lan_goi_toi_da = max(0, so_lan_goi_toi_da)
        self._so_lan_da_goi = 0
        self._so_thu_tu_buoc = 0
        self._lock = Lock()

    def _audit(
        self,
        ten: str,
        ctx: ToolContext,
        ket_qua_nhan: str,
        so_can_cu: int,
        elapsed_ms: int,
    ) -> None:
        """Ghi đúng một dòng nhật ký kiểm toán mức INFO, không chứa nội dung hay tham số."""
        _AUDIT_LOGGER.info(
            "tool=%s vai_tro=%s che_do=%s ca=%s ket_qua=%s can_cu=%d thoi_gian_ms=%d",
            ten,
            ctx.vai_tro,
            ctx.che_do,
            _hash_case_id(ctx),
            ket_qua_nhan,
            so_can_cu,
            elapsed_ms,
        )

    def goi(
        self,
        ten: str,
        tham_so_tho: dict[str, Any],
        ctx: ToolContext,
    ) -> KetQuaCongCu:
        """Kiểm tra quyền, ngân sách, lược đồ, PII; chạy tool; hậu xử lý và ghi kiểm toán."""
        perf_start = time.perf_counter()
        with self._lock:
            self._so_thu_tu_buoc += 1
            step_no = self._so_thu_tu_buoc
        ma_buoc = f"cong_cu_{step_no}"

        def _elapsed_ms() -> int:
            return int((time.perf_counter() - perf_start) * 1000.0)

        def _reject(ma_loi: str, message: str) -> KetQuaCongCu:
            ghi_buoc("bat_dau", ma_buoc, ten="Gọi công cụ bị từ chối")
            ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS.get(ma_loi, "Bị từ chối"))
            res = KetQuaCongCu(trang_thai="tu_choi", ma_loi=ma_loi, noi_dung=message)
            self._audit(ten, ctx, f"tu_choi:{ma_loi}", 0, _elapsed_ms())
            return res

        # 1. Kiểm tra công cụ có trong danh mục.
        tool = self._danh_muc.lay(ten)
        if tool is None:
            return _reject("khong_co_cong_cu", "Công cụ không tồn tại trong danh mục.")

        # 2. Kiểm tra quyền theo vai trò và chế độ.
        if (
            not self._chinh_sach.cho_phep(ctx.vai_tro, ctx.che_do, ten)
            or ctx.che_do not in tool.che_do_cho_phep
        ):
            return _reject(
                "khong_co_quyen",
                "Vai trò hoặc chế độ hiện tại không được phép gọi công cụ này.",
            )

        # 3. Kiểm tra ngân sách lượt gọi và hạn chót thời gian.
        with self._lock:
            if self._so_lan_da_goi >= self._so_lan_goi_toi_da:
                return _reject(
                    "het_ngan_sach",
                    "Đã hết số lần gọi công cụ cho phép trong lượt này.",
                )
        if time.monotonic() >= ctx.han_chot:
            return _reject("het_gio", "Đã hết thời gian xử lý của lượt hỏi.")

        # 4. Xác thực tham số theo LuocDoThamSo; không lặp lại giá trị đầu vào.
        if not isinstance(tham_so_tho, Mapping):
            return _reject("sai_tham_so", "Tham số công cụ không hợp lệ ở trường: tham_so.")
        try:
            tham_so = tool.LuocDoThamSo.model_validate(tham_so_tho)
        except ValidationError as exc:
            fields = sorted(
                {
                    ".".join(str(part) for part in err["loc"]) or "tham_so"
                    for err in exc.errors(include_input=False, include_context=False)
                }
            )
            return _reject(
                "sai_tham_so",
                f"Tham số công cụ không hợp lệ ở trường: {', '.join(fields)}.",
            )

        # 5. Quét PII trong toàn bộ chuỗi tham số.
        session = ctx.deid_session if ctx.deid_session is not None else DeidSession()
        if _params_contain_pii(tham_so.model_dump(), session):
            return _reject(
                "tham_so_co_dinh_danh",
                "Tham số công cụ có chứa định danh người bệnh nên bị từ chối.",
            )

        # Chiếm một lượt ngân sách và bắt đầu bước tiến trình chạy công cụ.
        with self._lock:
            if self._so_lan_da_goi >= self._so_lan_goi_toi_da:
                return _reject(
                    "het_ngan_sach",
                    "Đã hết số lần gọi công cụ cho phép trong lượt này.",
                )
            self._so_lan_da_goi += 1

        ghi_buoc("bat_dau", ma_buoc, ten=tool.ten_hien_thi)

        # 6. Chạy công cụ trong luồng phụ có giới hạn thời gian.
        timeout = min(tool.thoi_gian_toi_da, ctx.han_chot - time.monotonic())
        try:
            raw_result = _run_tool_with_timeout(tool, tham_so, ctx, timeout)
        except TimeoutError:
            ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS["het_gio"])
            self._audit(ten, ctx, "loi:het_gio", 0, _elapsed_ms())
            return KetQuaCongCu(
                trang_thai="loi",
                ma_loi="het_gio",
                noi_dung="Công cụ xử lý quá thời gian cho phép.",
            )
        except Exception:
            ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS["loi_cong_cu"])
            self._audit(ten, ctx, "loi:loi_cong_cu", 0, _elapsed_ms())
            return KetQuaCongCu(
                trang_thai="loi",
                ma_loi="loi_cong_cu",
                noi_dung="Công cụ gặp lỗi khi thực thi.",
            )

        # 7. Hậu xử lý kết quả.
        trang_thai = raw_result.trang_thai
        ma_loi = raw_result.ma_loi
        can_cu = list(raw_result.can_cu[: tool.so_can_cu_toi_da])

        # 7.1 Che PII trong noi_dung.
        try:
            if _DEID_TOKEN_RE.search(raw_result.noi_dung):
                cleaned = session.mask_known(raw_result.noi_dung)
            else:
                cleaned = session.scrub(raw_result.noi_dung)
        except DeidError:
            cleaned = _SCRUB_FALLBACK
            trang_thai = "loi"
            ma_loi = ma_loi or "loi_cong_cu"
            can_cu = []

        # 7.2 Loại bỏ chuỗi phân tách khối.
        cleaned = _sanitize_markers(cleaned)

        # 7.3 Quét chèn lệnh.
        cleaned_no_zw = _ZERO_WIDTH_RE.sub("", cleaned)
        if _has_injection_directive(cleaned) or _has_injection_directive(cleaned_no_zw):
            cleaned = _INJECTION_BLOCKED_MESSAGE
            trang_thai = "loi"
            ma_loi = "nghi_chen_lenh"
            can_cu = []

        # 7.4 Cắt độ dài tối đa 8000 ký tự (can_cu đã cắt ở trên).
        cleaned = cleaned[:_MAX_TOOL_OUTPUT_CHARS]

        # 7.5 Bọc kết quả trong khối dữ liệu riêng của công cụ.
        wrapped = f"<<<KET_QUA_CONG_CU ten={tool.ten}>>>\n{cleaned}\nKET_QUA_CONG_CU>>>"

        # 8. Cập nhật tiến trình.
        if trang_thai in ("ok", "khong_co"):
            ghi_buoc("xong", ma_buoc, chi_tiet=raw_result.chi_tiet_tien_trinh or "Xong")
            audit_status = "cho_phep"
        elif trang_thai == "tu_choi":
            code = ma_loi or "khong_co_quyen"
            ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS.get(code, "Bị từ chối"))
            audit_status = f"tu_choi:{code}"
        else:
            code = ma_loi or "loi_cong_cu"
            ghi_buoc("loi", ma_buoc, ly_do=_SAFE_STEP_REASONS.get(code, "Công cụ gặp lỗi"))
            audit_status = f"loi:{code}"

        # 9. Ghi nhật ký kiểm toán.
        self._audit(ten, ctx, audit_status, len(can_cu), _elapsed_ms())

        return KetQuaCongCu(
            trang_thai=trang_thai,
            noi_dung=wrapped,
            can_cu=can_cu,
            chi_tiet_tien_trinh=raw_result.chi_tiet_tien_trinh,
            ma_loi=ma_loi,
        )
