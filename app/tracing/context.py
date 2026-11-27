"""Quản lý vết theo ContextVar, cây span lồng nhau và vòng đời tracer."""

from __future__ import annotations

import atexit
import copy
import logging
import time
import uuid
from collections.abc import Callable, Mapping
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock, RLock
from types import TracebackType
from typing import Any, Literal

from app.config.settings import TracerSettings, assert_tracer_settings_allowed
from app.deid.session import DeidSession
from app.tracing.models import (
    MAX_SPAN_NAME_CHARS,
    MAX_SPANS_PER_TRACE,
    MAX_TRACE_BYTES,
    LoaiSpan,
    LoaiVet,
    MucNoiDung,
    SpanBanGhi,
    VetChay,
)
from app.tracing.sanitize import (
    bam_ma_ca,
    che_bi_mat,
    chuan_hoa_noi_dung,
    loc_thuoc_tinh,
    tinh_chi_phi_uoc_tinh,
)
from app.tracing.sink import JsonlTraceSink, don_vet_qua_han, vn_now

_LOGGER = logging.getLogger(__name__)
_ROOT = Path(__file__).resolve().parents[2]
_HEADER_RESERVE_BYTES = 2048

vet_hien_tai: ContextVar[VetDangChay | None] = ContextVar("vet_hien_tai", default=None)
span_hien_tai: ContextVar[str | None] = ContextVar("span_hien_tai", default=None)

_DEFAULT_LOCK = Lock()
_DEFAULT_TRACER: Tracer | None = None
_CLEANED_DIRS: set[Path] = set()
_UNSET = object()


def _resolve_dir(raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else _ROOT / path


def _safe_span_name(ten: str) -> str:
    return che_bi_mat(ten)[:MAX_SPAN_NAME_CHARS]


@dataclass
class _OpenNodeSpan:
    """Trạng thái một span node mở qua ghi_buoc (chưa đóng bằng xong/loi)."""

    seq: int
    ma_buoc: str
    ma_buoc_cha: str | None
    ten: str
    bat_dau: datetime
    perf_start: float
    thuoc_tinh: dict[str, Any]
    span_token: Token[str | None] | None


class VetDangChay:
    """Trạng thái sống của một vết đang mở, an toàn khi chia sẻ qua luồng phụ."""

    def __init__(
        self,
        *,
        tracer: Tracer,
        loai: LoaiVet,
        engine: str,
        ca_id: str | None = None,
        nguoi_dung_id: str | None = None,
        vai_tro: str | None = None,
        phien_id: str | None = None,
        phien_ban: Mapping[str, str] | None = None,
        dong_ho: Callable[[], datetime] = vn_now,
    ) -> None:
        self._tracer = tracer
        self._lock = RLock()
        self._dong_ho = dong_ho
        self.ma_vet = str(uuid.uuid4())
        self.loai: LoaiVet = loai
        self.engine = engine
        self.nguoi_dung_id = nguoi_dung_id
        self.vai_tro = vai_tro
        self.phien_id = phien_id
        self.ca_bam = bam_ma_ca(ca_id)
        self.phien_ban: dict[str, str] = {
            str(k): che_bi_mat(str(v)) for k, v in (phien_ban or {}).items()
        }
        self.muc_noi_dung: MucNoiDung = tracer.settings.muc_noi_dung
        self.bat_dau = dong_ho()
        self._perf_start = time.perf_counter()
        self.trang_thai_cuoi = "ok"
        self.ma_loi: str | None = None
        self.tong_token_vao = 0
        self.tong_token_ra = 0
        self.chi_phi_uoc_tinh = 0.0
        self.so_tool = 0
        self.so_bi_chan = 0
        self.vet_bi_cat = False
        self.so_khoa_la_bi_bo = 0
        self._spans: list[tuple[int, SpanBanGhi]] = []
        self._seq = 0
        self._approx_bytes = _HEADER_RESERVE_BYTES
        self._open_nodes: dict[str, _OpenNodeSpan] = {}
        self._deid_session: DeidSession | None = None

    def dat_phien_che(self, session: DeidSession) -> None:
        """Sao chép phiên che để không thay đổi bảng ánh xạ của lượt xử lý."""
        try:
            self._deid_session = copy.deepcopy(session)
        except Exception:
            self._deid_session = None

    def che_noi_dung(self, value: Any) -> Any:
        """Che giá trị đã biết; không ghi nội dung khi thiếu phiên che."""
        if self._deid_session is None:
            return None
        if isinstance(value, str):
            return self._deid_session.mask_known(value)
        if isinstance(value, Mapping):
            return {key: self.che_noi_dung(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.che_noi_dung(item) for item in value]
        return value

    def cap_so_thu_tu(self) -> int:
        """Cấp số thứ tự tăng dần lúc mở span để giữ thứ tự cha trước con khi chốt vết."""
        with self._lock:
            self._seq += 1
            return self._seq

    @property
    def tracer(self) -> Tracer:
        """Tracer sở hữu vết này."""
        return self._tracer

    def dat_trang_thai_cuoi(self, trang_thai: str, *, ma_loi: str | None = None) -> None:
        """Cập nhật trạng thái cuối và mã lỗi an toàn (nếu có) của vết."""
        with self._lock:
            self.trang_thai_cuoi = trang_thai
            if ma_loi is not None:
                self.ma_loi = che_bi_mat(ma_loi)[:120]

    def cap_nhat_phien_ban(self, **thong_tin: str) -> None:
        """Bổ sung thông tin phiên bản prompt, mô hình, chính sách hoặc nguồn KB."""
        with self._lock:
            for key, value in thong_tin.items():
                if value:
                    self.phien_ban[str(key)] = che_bi_mat(str(value))

    def cong_token(
        self,
        token_vao: int,
        token_ra: int,
        *,
        mo_hinh: str | None = None,
        chi_phi: float | None = None,
    ) -> float:
        """Cộng dồn token vào/ra và chi phí ước tính của một lượt LLM."""
        in_tok = max(0, int(token_vao))
        out_tok = max(0, int(token_ra))
        cost = (
            float(chi_phi)
            if chi_phi is not None
            else tinh_chi_phi_uoc_tinh(mo_hinh, in_tok, out_tok, self._tracer.settings.bang_gia)
        )
        with self._lock:
            self.tong_token_vao += in_tok
            self.tong_token_ra += out_tok
            self.chi_phi_uoc_tinh += cost
        return cost

    def tang_so_tool(self, delta: int = 1) -> None:
        """Tăng bộ đếm lượt gọi công cụ trong vết."""
        with self._lock:
            self.so_tool += max(0, delta)

    def tang_so_bi_chan(self, delta: int = 1) -> None:
        """Tăng bộ đếm lần bị chặn kiểm chứng hoặc bảo mật trong vết."""
        with self._lock:
            self.so_bi_chan += max(0, delta)

    def cong_khoa_la(self, so_luong: int) -> None:
        """Ghi nhận số khoá thuộc tính lạ bị bỏ."""
        if so_luong <= 0:
            return
        with self._lock:
            self.so_khoa_la_bi_bo += so_luong
        self._tracer._cong_khoa_la(so_luong)

    def them_span(self, ban_ghi: SpanBanGhi, *, seq: int | None = None) -> bool:
        """Thêm span vào vết; vượt trần 200 span hoặc 256 KB thì gắn vet_bi_cat và bỏ."""
        try:
            encoded_len = len(ban_ghi.model_dump_json().encode("utf-8")) + 2
        except Exception as exc:
            _LOGGER.debug("Không đo được kích thước span (%s)", type(exc).__name__)
            return False
        with self._lock:
            if (
                self.vet_bi_cat
                or len(self._spans) >= MAX_SPANS_PER_TRACE
                or self._approx_bytes + encoded_len > MAX_TRACE_BYTES
            ):
                self.vet_bi_cat = True
                return False
            order = seq if seq is not None else self.cap_so_thu_tu()
            self._spans.append((order, ban_ghi))
            self._approx_bytes += encoded_len
            return True

    def bat_dau_node(self, ma: str) -> None:
        """Mở span loại node cho bước tiến trình `ma`."""
        with self._lock:
            if ma in self._open_nodes:
                self.ket_thuc_node(ma, trang_thai="ok")
            parent_id = span_hien_tai.get()
            ma_buoc = uuid.uuid4().hex[:16]
            seq = self.cap_so_thu_tu()
            attrs, dropped = loc_thuoc_tinh("node", {"ma_buoc_tien_trinh": ma})
            if dropped:
                self.cong_khoa_la(dropped)
            token = span_hien_tai.set(ma_buoc)
            self._open_nodes[ma] = _OpenNodeSpan(
                seq=seq,
                ma_buoc=ma_buoc,
                ma_buoc_cha=parent_id,
                ten=_safe_span_name(ma),
                bat_dau=self._dong_ho(),
                perf_start=time.perf_counter(),
                thuoc_tinh=attrs,
                span_token=token,
            )

    def ket_thuc_node(
        self,
        ma: str,
        *,
        trang_thai: str = "ok",
        thuoc_tinh_bo_sung: Mapping[str, Any] | None = None,
    ) -> None:
        """Đóng span loại node cho bước tiến trình `ma` và khôi phục span cha."""
        with self._lock:
            handle = self._open_nodes.pop(ma, None)
            if handle is None:
                merged: dict[str, Any] = {"ma_buoc_tien_trinh": ma}
                if thuoc_tinh_bo_sung:
                    merged.update(thuoc_tinh_bo_sung)
                attrs, dropped = loc_thuoc_tinh("node", merged)
                if dropped:
                    self.cong_khoa_la(dropped)
                self.them_span(
                    SpanBanGhi(
                        ma_vet=self.ma_vet,
                        ma_buoc=uuid.uuid4().hex[:16],
                        ma_buoc_cha=span_hien_tai.get(),
                        loai="node",
                        ten=_safe_span_name(ma),
                        bat_dau=self._dong_ho(),
                        thoi_gian_ms=0.0,
                        trang_thai=trang_thai,
                        thuoc_tinh=attrs,
                    )
                )
                return

            merged = dict(handle.thuoc_tinh)
            if thuoc_tinh_bo_sung:
                merged.update(thuoc_tinh_bo_sung)
            attrs, dropped = loc_thuoc_tinh("node", merged)
            if dropped:
                self.cong_khoa_la(dropped)
            elapsed_ms = max(0.0, (time.perf_counter() - handle.perf_start) * 1000.0)
            self.them_span(
                SpanBanGhi(
                    ma_vet=self.ma_vet,
                    ma_buoc=handle.ma_buoc,
                    ma_buoc_cha=handle.ma_buoc_cha,
                    loai="node",
                    ten=handle.ten,
                    bat_dau=handle.bat_dau,
                    thoi_gian_ms=elapsed_ms,
                    trang_thai=trang_thai,
                    thuoc_tinh=attrs,
                ),
                seq=handle.seq,
            )
            if handle.span_token is not None:
                try:
                    span_hien_tai.reset(handle.span_token)
                except ValueError:
                    span_hien_tai.set(handle.ma_buoc_cha)

    def dong_node_dang_mo(
        self,
        *,
        trang_thai: str = "loi",
        loai_ngoai_le: str | None = None,
    ) -> None:
        """Đóng mọi span node chưa kịp kết thúc khi xảy ra ngoại lệ hoặc lúc chốt vết."""
        with self._lock:
            open_keys = list(reversed(self._open_nodes.keys()))
            extra = {"loai_ngoai_le": loai_ngoai_le} if loai_ngoai_le else None
            for ma in open_keys:
                self.ket_thuc_node(ma, trang_thai=trang_thai, thuoc_tinh_bo_sung=extra)

    def chot(self) -> VetChay:
        """Đóng mọi span còn mở và dựng đối tượng VetChay hoàn chỉnh."""
        with self._lock:
            if self._open_nodes:
                status = "loi" if self.trang_thai_cuoi == "loi" else "ok"
                self.dong_node_dang_mo(trang_thai=status)
            ket_thuc = self._dong_ho()
            elapsed_ms = max(0.0, (time.perf_counter() - self._perf_start) * 1000.0)
            return VetChay(
                ma_vet=self.ma_vet,
                bat_dau=self.bat_dau,
                ket_thuc=ket_thuc,
                thoi_gian_ms=elapsed_ms,
                loai=self.loai,
                engine=self.engine,
                nguoi_dung_id=self.nguoi_dung_id,
                vai_tro=self.vai_tro,
                phien_id=self.phien_id,
                ca_bam=self.ca_bam,
                phien_ban=dict(self.phien_ban),
                trang_thai_cuoi=self.trang_thai_cuoi,
                tong_token_vao=self.tong_token_vao,
                tong_token_ra=self.tong_token_ra,
                chi_phi_uoc_tinh=self.chi_phi_uoc_tinh,
                so_tool=self.so_tool,
                so_bi_chan=self.so_bi_chan,
                ma_loi=self.ma_loi,
                muc_noi_dung=self.muc_noi_dung,
                vet_bi_cat=self.vet_bi_cat,
                so_khoa_la_bi_bo=self.so_khoa_la_bi_bo,
                cac_buoc=[item for _, item in sorted(self._spans, key=lambda pair: pair[0])],
            )


class _NoopSpan:
    """Span rỗng khi không có vết hiện hành; mọi thao tác bỏ qua im lặng."""

    ma_buoc: str = ""
    ma_buoc_cha: str | None = None

    def dat_thuoc_tinh(self, **thuoc_tinh: Any) -> None:
        del thuoc_tinh

    def dat_noi_dung(self, noi_dung: Mapping[str, Any] | None) -> None:
        del noi_dung

    def dat_trang_thai(self, trang_thai: str) -> None:
        del trang_thai

    def __enter__(self) -> _NoopSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        del exc_type, exc_val, exc_tb
        return False


class SpanDangChay:
    """Context manager cho một span lồng nhau, tự đo thời gian và trạng thái."""

    def __init__(
        self,
        vet: VetDangChay,
        loai: LoaiSpan,
        ten: str,
        thuoc_tinh: Mapping[str, Any],
    ) -> None:
        self._vet = vet
        self._loai: LoaiSpan = loai
        self._ten = _safe_span_name(ten)
        self.ma_buoc = uuid.uuid4().hex[:16]
        self.ma_buoc_cha: str | None = None
        self._seq: int = 0
        self._bat_dau: datetime | None = None
        self._perf_start: float = 0.0
        self._trang_thai = "ok"
        self._raw_attrs: dict[str, Any] = dict(thuoc_tinh)
        self._raw_content: dict[str, Any] = {}
        self._span_token: Token[str | None] | None = None

    def dat_thuoc_tinh(self, **thuoc_tinh: Any) -> None:
        """Gộp thêm thuộc tính (sẽ qua danh sách cho phép khi chốt span)."""
        self._raw_attrs.update(thuoc_tinh)

    def dat_noi_dung(self, noi_dung: Mapping[str, Any] | None) -> None:
        """Gộp nội dung đã che (chỉ giữ khi mức nội dung cho phép)."""
        if noi_dung and self._vet.muc_noi_dung != "sieu_du_lieu":
            try:
                cleaned = self._vet.che_noi_dung(noi_dung)
                if isinstance(cleaned, dict):
                    self._raw_content.update(cleaned)
            except Exception as exc:
                _LOGGER.debug("Bỏ nội dung khi che định danh lỗi (%s)", type(exc).__name__)

    def dat_trang_thai(self, trang_thai: str) -> None:
        """Gán trạng thái tường minh cho span (ok | loi | tu_choi | bo_qua)."""
        self._trang_thai = trang_thai

    def __enter__(self) -> SpanDangChay:
        self.ma_buoc_cha = span_hien_tai.get()
        self._seq = self._vet.cap_so_thu_tu()
        self._bat_dau = self._vet._dong_ho()
        self._perf_start = time.perf_counter()
        self._span_token = span_hien_tai.set(self.ma_buoc)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        del exc_val, exc_tb
        try:
            if self._span_token is not None:
                try:
                    span_hien_tai.reset(self._span_token)
                except ValueError:
                    span_hien_tai.set(self.ma_buoc_cha)
            if exc_type is not None:
                self._trang_thai = "loi"
                self._raw_attrs["loai_ngoai_le"] = exc_type.__name__
            elapsed_ms = max(0.0, (time.perf_counter() - self._perf_start) * 1000.0)
            attrs, dropped = loc_thuoc_tinh(self._loai, self._raw_attrs)
            if dropped:
                self._vet.cong_khoa_la(dropped)
            noi_dung = chuan_hoa_noi_dung(self._vet.muc_noi_dung, self._raw_content)
            ban_ghi = SpanBanGhi(
                ma_vet=self._vet.ma_vet,
                ma_buoc=self.ma_buoc,
                ma_buoc_cha=self.ma_buoc_cha,
                loai=self._loai,
                ten=self._ten,
                bat_dau=self._bat_dau if self._bat_dau is not None else self._vet._dong_ho(),
                thoi_gian_ms=elapsed_ms,
                trang_thai=self._trang_thai,
                thuoc_tinh=attrs,
                noi_dung=noi_dung,
            )
            self._vet.them_span(ban_ghi, seq=self._seq)
        except Exception as exc:
            _LOGGER.debug("Bỏ qua lỗi nội bộ khi đóng span (%s)", type(exc).__name__)
        return False


class _VetContextManager:
    """Context manager mở và chốt một vết; nếu tracer tắt thì làm no-op."""

    def __init__(
        self,
        tracer: Tracer | None,
        *,
        loai: LoaiVet,
        engine: str,
        ca_id: str | None = None,
        nguoi_dung_id: str | None = None,
        vai_tro: str | None = None,
        phien_id: str | None = None,
        phien_ban: Mapping[str, str] | None = None,
    ) -> None:
        self._tracer = tracer
        self._loai: LoaiVet = loai
        self._engine = engine
        self._ca_id = ca_id
        self._nguoi_dung_id = nguoi_dung_id
        self._vai_tro = vai_tro
        self._phien_id = phien_id
        self._phien_ban = phien_ban
        self._vet: VetDangChay | None = None
        self._vet_token: Token[VetDangChay | None] | None = None
        self._span_token: Token[str | None] | None = None

    def __enter__(self) -> VetDangChay | None:
        if self._tracer is None or not self._tracer.bat:
            return None
        try:
            vet = VetDangChay(
                tracer=self._tracer,
                loai=self._loai,
                engine=self._engine,
                ca_id=self._ca_id,
                nguoi_dung_id=self._nguoi_dung_id,
                vai_tro=self._vai_tro,
                phien_id=self._phien_id,
                phien_ban=self._phien_ban,
                dong_ho=self._tracer.dong_ho,
            )
            self._vet = vet
            self._vet_token = vet_hien_tai.set(vet)
            self._span_token = span_hien_tai.set(None)
            return vet
        except Exception as exc:
            _LOGGER.debug("Không mở được vết mới (%s)", type(exc).__name__)
            return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> Literal[False]:
        del exc_val, exc_tb
        vet = self._vet
        try:
            if vet is not None:
                if exc_type is not None:
                    vet.dat_trang_thai_cuoi("loi", ma_loi=exc_type.__name__)
                    vet.dong_node_dang_mo(trang_thai="loi", loai_ngoai_le=exc_type.__name__)
                record = vet.chot()
                assert self._tracer is not None
                self._tracer.gui_vet(record)
        except Exception as exc:
            _LOGGER.debug("Bỏ qua lỗi khi chốt và gửi vết (%s)", type(exc).__name__)
        finally:
            if self._span_token is not None:
                try:
                    span_hien_tai.reset(self._span_token)
                except ValueError:
                    span_hien_tai.set(None)
            if self._vet_token is not None:
                try:
                    vet_hien_tai.reset(self._vet_token)
                except ValueError:
                    vet_hien_tai.set(None)
        return False


class Tracer:
    """Bộ điều phối tracer giữ cấu hình, đích ghi JSONL và bộ đếm vận hành."""

    def __init__(
        self,
        settings: TracerSettings | None = None,
        *,
        sink: JsonlTraceSink | None = None,
        dong_ho: Callable[[], datetime] = vn_now,
        auto_cleanup: bool = False,
    ) -> None:
        resolved = settings if settings is not None else TracerSettings()
        assert_tracer_settings_allowed(resolved)
        self._settings = resolved
        self._dong_ho = dong_ho
        self._lock = Lock()
        self._so_khoa_la_bi_bo = 0
        self._sink: JsonlTraceSink | None
        if sink is not None:
            self._sink = sink
        elif resolved.bat:
            self._sink = JsonlTraceSink(
                _resolve_dir(resolved.thu_muc),
                hang_doi_toi_da=resolved.hang_doi_toi_da,
                kich_thuoc_tep_toi_da=resolved.kich_thuoc_tep_mb * 1024 * 1024,
                dong_ho=dong_ho,
            )
        else:
            self._sink = None
        if auto_cleanup and resolved.bat:
            self.don_qua_han_mot_lan()

    @property
    def settings(self) -> TracerSettings:
        """Cấu hình bất biến của tracer."""
        return self._settings

    @property
    def bat(self) -> bool:
        """Cờ bật/tắt ghi vết."""
        return self._settings.bat and self._sink is not None

    @property
    def dong_ho(self) -> Callable[[], datetime]:
        """Đồng hồ sinh mốc thời gian (giờ Việt Nam)."""
        return self._dong_ho

    @property
    def sink(self) -> JsonlTraceSink | None:
        """Đích ghi JSONL nếu tracer đang bật."""
        return self._sink

    @property
    def so_vet_bi_bo(self) -> int:
        """Tổng số vết bị bỏ do hàng đợi đầy hoặc tệp vượt giới hạn."""
        return self._sink.so_vet_bi_bo if self._sink is not None else 0

    @property
    def so_khoa_la_bi_bo(self) -> int:
        """Tổng số khoá thuộc tính lạ bị bỏ trên toàn bộ vết."""
        with self._lock:
            return self._so_khoa_la_bi_bo

    def _cong_khoa_la(self, so_luong: int) -> None:
        with self._lock:
            self._so_khoa_la_bi_bo += so_luong

    def gui_vet(self, vet: VetChay) -> bool:
        """Đưa bản ghi vết vào đích ghi JSONL."""
        if self._sink is None:
            return False
        return self._sink.gui(vet)

    def don_qua_han_mot_lan(self) -> int:
        """Dọn tệp vết quá hạn đúng một lần cho mỗi thư mục trong tiến trình."""
        if self._sink is None:
            return 0
        target = self._sink.thu_muc.resolve()
        with _DEFAULT_LOCK:
            if target in _CLEANED_DIRS:
                return 0
            _CLEANED_DIRS.add(target)
        return don_vet_qua_han(
            self._settings.so_ngay_luu,
            thu_muc=self._sink.thu_muc,
            dong_ho=self._dong_ho,
        )

    def bat_dau_vet(
        self,
        loai: LoaiVet,
        engine: str,
        *,
        ca_id: str | None = None,
        nguoi_dung_id: str | None = None,
        vai_tro: str | None = None,
        phien_id: str | None = None,
        phien_ban: Mapping[str, str] | None = None,
    ) -> _VetContextManager:
        """Mở context manager vết gắn với tracer này."""
        return _VetContextManager(
            self,
            loai=loai,
            engine=engine,
            ca_id=ca_id,
            nguoi_dung_id=nguoi_dung_id,
            vai_tro=vai_tro,
            phien_id=phien_id,
            phien_ban=phien_ban,
        )

    def flush(self, timeout: float = 2.0) -> bool:
        """Chờ luồng nền ghi xong mọi vết đang trong hàng đợi."""
        if self._sink is None:
            return True
        return self._sink.flush(timeout=timeout)

    def close(self, timeout: float = 2.0) -> None:
        """Xả hàng đợi và dừng luồng nền của đích ghi."""
        if self._sink is not None:
            self._sink.close(timeout=timeout)


def lay_tracer_mac_dinh() -> Tracer | None:
    """Lấy tracer mặc định của tiến trình nếu đã được khởi tạo."""
    with _DEFAULT_LOCK:
        return _DEFAULT_TRACER


def dat_tracer_mac_dinh(tracer: Tracer | None) -> Tracer | None:
    """Thay tracer mặc định của tiến trình và trả về bản cũ (phục vụ kiểm thử)."""
    global _DEFAULT_TRACER
    with _DEFAULT_LOCK:
        previous = _DEFAULT_TRACER
        _DEFAULT_TRACER = tracer
        return previous


def khoi_tao_tracer(
    settings: TracerSettings | None = None,
    *,
    sink: JsonlTraceSink | None = None,
    dong_ho: Callable[[], datetime] = vn_now,
    auto_cleanup: bool = True,
) -> Tracer:
    """Khởi tạo và gắn tracer mặc định cho tiến trình (dọn vết quá hạn một lần nếu bật)."""
    tracer = Tracer(settings, sink=sink, dong_ho=dong_ho, auto_cleanup=auto_cleanup)
    previous = dat_tracer_mac_dinh(tracer)
    if previous is not None and previous is not tracer:
        previous.close(timeout=1.0)
    return tracer


def xa_hang_doi_vet(timeout: float = 2.0) -> bool:
    """Xả hàng đợi của tracer mặc định nếu đang hoạt động."""
    tracer = lay_tracer_mac_dinh()
    if tracer is None:
        return True
    return tracer.flush(timeout=timeout)


def dong_tracer_mac_dinh(timeout: float = 2.0) -> None:
    """Đóng tracer mặc định gọn gàng khi kết thúc tiến trình."""
    tracer = dat_tracer_mac_dinh(None)
    if tracer is not None:
        tracer.close(timeout=timeout)


atexit.register(dong_tracer_mac_dinh)


def bat_dau_vet(
    loai: LoaiVet,
    engine: str,
    *,
    ca_id: str | None = None,
    nguoi_dung_id: str | None = None,
    vai_tro: str | None = None,
    phien_id: str | None = None,
    phien_ban: Mapping[str, str] | None = None,
    tracer: Tracer | None | object = _UNSET,
) -> _VetContextManager:
    """Mở vết bằng tracer chỉ định hoặc tracer mặc định; chưa khởi tạo thì làm no-op."""
    active_tracer = lay_tracer_mac_dinh() if tracer is _UNSET else tracer
    if not isinstance(active_tracer, Tracer):
        active_tracer = None
    return _VetContextManager(
        active_tracer,
        loai=loai,
        engine=engine,
        ca_id=ca_id,
        nguoi_dung_id=nguoi_dung_id,
        vai_tro=vai_tro,
        phien_id=phien_id,
        phien_ban=phien_ban,
    )


def span(loai: LoaiSpan, ten: str, **thuoc_tinh: Any) -> SpanDangChay | _NoopSpan:
    """Mở span lồng nhau trong vết hiện hành; không có vết thì trả về no-op."""
    vet = vet_hien_tai.get()
    if vet is None:
        return _NoopSpan()
    return SpanDangChay(vet, loai, ten, thuoc_tinh)


def ma_vet_hien_tai() -> str | None:
    """Trả mã vết UUID v4 hiện hành hoặc None nếu chưa mở vết."""
    vet = vet_hien_tai.get()
    return vet.ma_vet if vet is not None else None


def ghi_su_kien_bao_mat(
    loai_su_kien: str,
    *,
    nguon: str,
    ten_cong_cu: str | None = None,
    ma_loi: str | None = None,
) -> None:
    """Ghi một span sự kiện bảo mật (chèn lệnh, PII trong tham số, vượt quyền)."""
    vet = vet_hien_tai.get()
    if vet is None:
        return
    attrs: dict[str, Any] = {"loai_su_kien": loai_su_kien, "nguon": nguon}
    if ten_cong_cu is not None:
        attrs["ten_cong_cu"] = ten_cong_cu
    if ma_loi is not None:
        attrs["ma_loi"] = ma_loi
    with span("su_kien_bao_mat", loai_su_kien, **attrs) as s:
        s.dat_trang_thai("tu_choi")


def bat_dau_buoc_node(ma: str) -> None:
    """Mở span loại node gắn với sự kiện bat_dau của ghi_buoc."""
    vet = vet_hien_tai.get()
    if vet is None:
        return
    vet.bat_dau_node(ma)


def ket_thuc_buoc_node(
    ma: str,
    *,
    trang_thai: str = "ok",
    so_nguon: int | None = None,
    so_doan: int | None = None,
) -> None:
    """Đóng span loại node gắn với sự kiện xong/loi của ghi_buoc."""
    vet = vet_hien_tai.get()
    if vet is None:
        return
    extra: dict[str, Any] = {}
    if so_nguon is not None:
        extra["so_nguon"] = so_nguon
    if so_doan is not None:
        extra["so_doan"] = so_doan
    vet.ket_thuc_node(ma, trang_thai=trang_thai, thuoc_tinh_bo_sung=extra or None)


def dong_buoc_node_dang_chay(*, loai_ngoai_le: str | None = None) -> None:
    """Đóng các span node còn mở khi nút gặp ngoại lệ không mong muốn."""
    vet = vet_hien_tai.get()
    if vet is None:
        return
    vet.dong_node_dang_mo(trang_thai="loi", loai_ngoai_le=loai_ngoai_le)
