"""Sinh dữ liệu kiểm thử giả lập (HTML + PNG + nhãn) ngoại tuyến cho Chrome Extension."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tests/extension_api/fixtures"

_DEMO_HTML = """<!doctype html>
<html lang="vi">
<head><meta charset="utf-8"><title>Hồ sơ giả lập DEMO-02</title></head>
<body>
  <main>
    <details class="record-disclosure">
      <summary>I. Hành chính</summary>
      <dl>
        <dt>Họ và tên</dt><dd>Nguyễn Thị Giả Lập</dd>
        <dt>Ngày sinh</dt><dd>15/03/1951</dd>
        <dt>Tuổi</dt><dd>75</dd>
        <dt>Giới tính</dt><dd>Nữ</dd>
        <dt>Cân nặng</dt><dd>50 kg</dd>
        <dt>Chiều cao</dt><dd>155 cm</dd>
        <dt>Số thẻ BHYT</dt><dd>DN4010123456789</dd>
        <dt>CCCD</dt><dd>001051012345</dd>
        <dt>Điện thoại</dt><dd>0912345678</dd>
      </dl>
    </details>

    <details class="record-disclosure">
      <summary>II. Chẩn đoán</summary>
      <dl>
        <dt>Chẩn đoán chính</dt><dd>J18.9 - Viêm phổi</dd>
        <dt>Tình trạng dị ứng</dt><dd>Không dị ứng đã hỏi</dd>
      </dl>
    </details>

    <section aria-label="Cận lâm sàng">
      <h2>Xét nghiệm</h2>
      <table>
        <thead>
          <tr><th>Tên xét nghiệm</th><th>Kết quả</th><th>Đơn vị</th><th>Khoảng tham chiếu</th><th>Thời điểm</th></tr>
        </thead>
        <tbody>
          <tr><td>Creatinin máu</td><td>212</td><td>umol/L</td><td>44 - 80</td><td>10/11/2026 05:30</td></tr>
          <tr><td>Creatinin máu</td><td>150</td><td>umol/L</td><td>44 - 80</td><td>07/11/2026 05:30</td></tr>
        </tbody>
      </table>
    </section>

    <section aria-label="Diễn biến">
      <h2>Phiếu điều trị</h2>
      <p>BS Nguyễn Văn An khám: Người bệnh viêm phổi nội trú, creatinin tăng từ 150 lên 212 umol/L.</p>
    </section>

    <aside id="finding-rule-1" data-testid="ai-review-drawer">
      <h3>Thẩm định</h3>
      <p>Không được lấy sẵn nhận định này khi trích xuất DOM!</p>
    </aside>
  </main>
</body>
</html>
"""

_SCHEMA_LABELS = [
    {"ten_nhan": "Họ và tên", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
    {"ten_nhan": "Ngày sinh", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
    {"ten_nhan": "Số thẻ BHYT", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
    {"ten_nhan": "Tuổi", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
    {"ten_nhan": "Giới tính", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
    {"ten_nhan": "Cân nặng", "kieu_dom": "dt_dd", "ngu_canh_muc": "I. Hành chính"},
    {"ten_nhan": "Chẩn đoán chính", "kieu_dom": "dt_dd", "ngu_canh_muc": "II. Chẩn đoán"},
    {"ten_nhan": "Creatinin máu", "kieu_dom": "table_th", "ngu_canh_muc": "Cận lâm sàng"},
]


def make_png_bytes(width: int = 32, height: int = 32) -> bytes:
    """Tạo ảnh PNG nhị phân hợp lệ không cần Pillow."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", crc)

    raw_rows = b"".join(b"\x00" + (b"\xf8\xfa\xfc\xff" * width) for _ in range(height))
    ihdr = struct.pack("!IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw_rows, level=6))
        + chunk(b"IEND", b"")
    )


def generate_all(output_dir: Path | None = None) -> Path:
    """Ghi toàn bộ tệp fixture kiểm thử extension vào thư mục đích."""
    target = output_dir or _FIXTURES_DIR
    target.mkdir(parents=True, exist_ok=True)
    (target / "emr_demo02_sanitized.html").write_text(_DEMO_HTML, encoding="utf-8")
    (target / "schema_demo_labels.json").write_text(
        json.dumps(_SCHEMA_LABELS, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (target / "oh_demo02.png").write_bytes(make_png_bytes())
    (target / "corrupt_not_image.png").write_bytes(b"NOT_A_REAL_PNG_FILE_PAYLOAD")
    return target


if __name__ == "__main__":
    generate_all()
