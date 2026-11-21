"""Theo dõi tiến trình các bước phân tích AI trong bộ nhớ, an toàn đa luồng và ngữ cảnh."""

import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_PROGRESS_STEPS = 40
MAX_PROGRESS_TEXT_LEN = 160

TrangThaiBuoc = Literal["cho", "dang_chay", "xong", "loi", "bo_qua"]


def _clip_str(value: str) -> str:
    """Cắt chuỗi theo trần độ dài hiển thị."""
    return value[:MAX_PROGRESS_TEXT_LEN]


def _clip_opt(value: str | None) -> str | None:
    """Cắt chuỗi tuỳ chọn theo trần độ dài hiển thị."""
    if value is None:
        return None
    return value[:MAX_PROGRESS_TEXT_LEN]


class NguonTomTat(BaseModel):
    """Tóm tắt số đoạn lấy được theo từng nhãn nguồn công khai."""

    model_config = ConfigDict(extra="forbid")

    nhan: str
    so_doan: int = Field(ge=0)

    @field_validator("nhan", mode="before")
    @classmethod
    def _clip_nhan(cls, value: object) -> object:
        """Cắt nhãn nguồn tối đa 160 ký tự."""
        if isinstance(value, str):
            return _clip_str(value)
        return value


class BuocTienTrinh(BaseModel):
    """Ảnh chụp một bước tiến trình phân tích AI tại thời điểm truy vấn."""

    model_config = ConfigDict(extra="forbid")

    ma: str
    ten: str
    trang_thai: TrangThaiBuoc = "cho"
    chi_tiet: str | None = None
    nguon: list[NguonTomTat] = Field(default_factory=list)
    thoi_gian_ms: float | None = None
    ly_do: str | None = None
    goi_y: str | None = None

    @field_validator("ma", "ten", "chi_tiet", "ly_do", "goi_y", mode="before")
    @classmethod
    def _clip_strings(cls, value: object) -> object:
        """Cắt mọi chuỗi mô tả bước tối đa 160 ký tự."""
        if isinstance(value, str):
            return _clip_str(value)
        return value


@dataclass
class _StepRecord:
    """Bản ghi nội bộ có thể thay đổi của một bước trong Tiến trình."""

    ma: str
    ten: str
    trang_thai: TrangThaiBuoc = "cho"
    chi_tiet: str | None = None
    nguon: list[NguonTomTat] = field(default_factory=list)
    bat_dau: float | None = None
    ket_thuc: float | None = None
    thoi_gian_ms: float | None = None
    ly_do: str | None = None
    goi_y: str | None = None


class TienTrinh:
    """Bộ ghi danh sách bước tiến trình theo thứ tự nối thêm, an toàn đa luồng."""

    def __init__(self, bat_dau: float | None = None) -> None:
        self._lock = RLock()
        self._bat_dau: float = bat_dau if bat_dau is not None else time.perf_counter()
        self._ket_thuc: float | None = None
        self._steps: list[_StepRecord] = []
        self._index: dict[str, int] = {}

    @property
    def thoi_diem_bat_dau(self) -> float:
        """Mốc `perf_counter()` lúc khởi tạo tiến trình."""
        return self._bat_dau

    @property
    def thoi_diem_ket_thuc(self) -> float | None:
        """Mốc `perf_counter()` lúc chốt tiến trình hoặc None nếu đang chạy."""
        with self._lock:
            return self._ket_thuc

    def _append_unlocked(self, ma: str, ten: str) -> _StepRecord | None:
        """Thêm bước mới nếu chưa tồn tại và chưa vượt trần 40 bước."""
        clipped_ma = _clip_str(ma)
        if clipped_ma in self._index or len(self._steps) >= MAX_PROGRESS_STEPS:
            return None
        record = _StepRecord(ma=clipped_ma, ten=_clip_str(ten))
        self._index[clipped_ma] = len(self._steps)
        self._steps.append(record)
        return record

    def dang_ky(self, ma: str, ten: str) -> None:
        """Đăng ký sẵn một bước ở trạng thái chờ."""
        with self._lock:
            self._append_unlocked(ma, ten)

    def them(self, ma: str, ten: str) -> None:
        """Nối thêm bước mới; vượt trần 40 bước thì bỏ qua im lặng."""
        with self._lock:
            self._append_unlocked(ma, ten)

    def bat_dau(self, ma: str, chi_tiet: str | None = None) -> None:
        """Đánh dấu bước bắt đầu chạy và ghi mốc thời gian."""
        with self._lock:
            clipped_ma = _clip_str(ma)
            idx = self._index.get(clipped_ma)
            if idx is None:
                record = self._append_unlocked(clipped_ma, clipped_ma)
                if record is None:
                    return
            else:
                record = self._steps[idx]
            record.trang_thai = "dang_chay"
            record.bat_dau = time.perf_counter()
            record.ket_thuc = None
            record.thoi_gian_ms = None
            record.chi_tiet = _clip_opt(chi_tiet)
            record.ly_do = None
            record.goi_y = None

    def xong(
        self,
        ma: str,
        chi_tiet: str | None = None,
        nguon: list[NguonTomTat] | None = None,
    ) -> None:
        """Đánh dấu bước hoàn tất và chốt thời lượng chạy."""
        with self._lock:
            idx = self._index.get(_clip_str(ma))
            if idx is None:
                return
            record = self._steps[idx]
            now = time.perf_counter()
            if record.bat_dau is None:
                record.bat_dau = now
            record.trang_thai = "xong"
            record.ket_thuc = now
            record.thoi_gian_ms = max(0.0, (now - record.bat_dau) * 1000.0)
            record.chi_tiet = _clip_opt(chi_tiet)
            record.nguon = (
                [NguonTomTat(nhan=item.nhan, so_doan=item.so_doan) for item in nguon]
                if nguon
                else []
            )
            record.ly_do = None
            record.goi_y = None

    def loi(self, ma: str, ly_do: str, goi_y: str | None = None) -> None:
        """Đánh dấu bước lỗi kèm lý do an toàn và gợi ý cho dược sĩ."""
        with self._lock:
            idx = self._index.get(_clip_str(ma))
            if idx is None:
                return
            record = self._steps[idx]
            now = time.perf_counter()
            if record.bat_dau is None:
                record.bat_dau = now
            record.trang_thai = "loi"
            record.ket_thuc = now
            record.thoi_gian_ms = max(0.0, (now - record.bat_dau) * 1000.0)
            record.chi_tiet = None
            record.ly_do = _clip_opt(ly_do)
            record.goi_y = _clip_opt(goi_y)

    def dang_chay_ma(self) -> str | None:
        """Trả mã bước đang ở trạng thái dang_chay gần nhất nếu có."""
        with self._lock:
            for record in reversed(self._steps):
                if record.trang_thai == "dang_chay":
                    return record.ma
            return None

    def chot(self, thanh_cong: bool) -> None:
        """Chốt toàn bộ bước còn chờ hoặc đang chạy khi tác vụ kết thúc."""
        with self._lock:
            now = time.perf_counter()
            if self._ket_thuc is None:
                self._ket_thuc = now
            end_time = self._ket_thuc
            for record in self._steps:
                if record.trang_thai == "cho":
                    record.trang_thai = "bo_qua"
                    record.thoi_gian_ms = None
                elif record.trang_thai == "dang_chay":
                    if record.bat_dau is None:
                        record.bat_dau = end_time
                    record.ket_thuc = end_time
                    record.thoi_gian_ms = max(0.0, (end_time - record.bat_dau) * 1000.0)
                    if thanh_cong:
                        record.trang_thai = "xong"
                    else:
                        record.trang_thai = "loi"
                        if record.ly_do is None:
                            record.ly_do = "Bước phân tích không hoàn tất"
                        if record.goi_y is None:
                            record.goi_y = "Bảng luật vẫn dùng được; bấm Thử lại sau ít phút"

    def chup(self, now: float | None = None) -> list[BuocTienTrinh]:
        """Trả bản sao danh sách bước hiện tại; bước đang chạy có thời gian tới `now`."""
        with self._lock:
            current = (
                now
                if now is not None
                else (self._ket_thuc if self._ket_thuc is not None else time.perf_counter())
            )
            snapshot: list[BuocTienTrinh] = []
            for record in self._steps:
                if record.trang_thai == "dang_chay" and record.bat_dau is not None:
                    elapsed_ms: float | None = max(0.0, (current - record.bat_dau) * 1000.0)
                else:
                    elapsed_ms = record.thoi_gian_ms
                snapshot.append(
                    BuocTienTrinh(
                        ma=record.ma,
                        ten=record.ten,
                        trang_thai=record.trang_thai,
                        chi_tiet=record.chi_tiet,
                        nguon=[NguonTomTat(nhan=n.nhan, so_doan=n.so_doan) for n in record.nguon],
                        thoi_gian_ms=elapsed_ms,
                        ly_do=record.ly_do,
                        goi_y=record.goi_y,
                    )
                )
            return snapshot

    def tong_ms(self, now: float | None = None) -> float:
        """Tổng thời gian chạy (ms) tới thời điểm `now` hoặc lúc kết thúc."""
        with self._lock:
            current = (
                now
                if now is not None
                else (self._ket_thuc if self._ket_thuc is not None else time.perf_counter())
            )
            return max(0.0, (current - self._bat_dau) * 1000.0)


tien_trinh_hien_tai: ContextVar[TienTrinh | None] = ContextVar(
    "tien_trinh_hien_tai",
    default=None,
)


def ghi_buoc(
    hanh_dong: Literal["dang_ky", "them", "bat_dau", "xong", "loi"],
    ma: str,
    *,
    ten: str | None = None,
    chi_tiet: str | None = None,
    nguon: list[NguonTomTat] | None = None,
    ly_do: str | None = None,
    goi_y: str | None = None,
) -> None:
    """Ghi sự kiện vào bộ tiến trình trong ContextVar nếu có; không có thì bỏ qua."""
    tracker = tien_trinh_hien_tai.get()
    if tracker is None:
        return
    if hanh_dong == "dang_ky":
        tracker.dang_ky(ma, ten if ten is not None else ma)
    elif hanh_dong == "them":
        tracker.them(ma, ten if ten is not None else ma)
    elif hanh_dong == "bat_dau":
        tracker.bat_dau(ma, chi_tiet=chi_tiet)
    elif hanh_dong == "xong":
        tracker.xong(ma, chi_tiet=chi_tiet, nguon=nguon)
    elif hanh_dong == "loi":
        tracker.loi(ma, ly_do=ly_do or "Bước phân tích gặp lỗi", goi_y=goi_y)
