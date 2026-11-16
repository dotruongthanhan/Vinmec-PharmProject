"""Kiểm thử lưu và đọc phản hồi dược sĩ dưới dạng JSONL."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.feedback import PhanHoi, load_feedback, save_feedback


def test_save_and_load_feedback_roundtrip_utf8(tmp_path: Path) -> None:
    """Ghi 2 phản hồi và đọc lại đúng dữ liệu kèm dấu tiếng Việt trong lý do."""
    feedback_path = tmp_path / "nested" / "phan_hoi.jsonl"
    tz_vn = timezone(timedelta(hours=7))

    item_1 = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, 9, 30, tzinfo=tz_vn),
        ca_id="DEMO-02",
        ma_luat="lieu_than_can_chinh",
        yeu_to=6,
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        phan_hoi="dong_y",
        ly_do="Đồng ý giảm liều Meropenem theo CrCl 16,0 mL/min",
    )
    item_2 = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, 9, 35, tzinfo=tz_vn),
        ca_id="DEMO-05",
        ma_luat="lich_dung_thieu_lieu",
        yeu_to=7,
        chi_tiet_y_lenh_id=["CT-DEMO05-01"],
        phan_hoi="can_sua",
        ly_do="Đã trao đổi với bác sĩ bổ sung cữ tối 20:00",
    )

    save_feedback(item_1, path=feedback_path)
    save_feedback(item_2, path=feedback_path)

    loaded = load_feedback(path=feedback_path)
    assert loaded == [item_1, item_2]
    assert loaded[0].ly_do == "Đồng ý giảm liều Meropenem theo CrCl 16,0 mL/min"
    assert loaded[1].ly_do == "Đã trao đổi với bác sĩ bổ sung cữ tối 20:00"


def test_load_feedback_missing_file_returns_empty(tmp_path: Path) -> None:
    """Tệp phản hồi chưa tồn tại thì load_feedback trả danh sách rỗng."""
    assert load_feedback(tmp_path / "khong_ton_tai.jsonl") == []


def test_save_and_load_feedback_with_nhom_ly_do(tmp_path: Path) -> None:
    """Trường nhom_ly_do được lưu và đọc lại đầy đủ qua JSONL."""
    feedback_path = tmp_path / "phan_hoi.jsonl"
    tz_vn = timezone(timedelta(hours=7))
    item = PhanHoi(
        thoi_diem=datetime(2026, 11, 16, 10, 15, tzinfo=tz_vn),
        ca_id="DEMO-02",
        ma_luat="lieu_than_can_chinh",
        yeu_to=6,
        chi_tiet_y_lenh_id=["CT-DEMO02-01"],
        phan_hoi="bac_bo",
        nhom_ly_do="khong_phu_hop_lam_sang",
        ly_do="Đang chạy thận nhân tạo chu kỳ",
    )

    save_feedback(item, path=feedback_path)
    loaded = load_feedback(path=feedback_path)

    assert len(loaded) == 1
    assert loaded[0].nhom_ly_do == "khong_phu_hop_lam_sang"
    assert loaded[0].ly_do == "Đang chạy thận nhân tạo chu kỳ"


def test_load_feedback_legacy_jsonl_without_nhom_ly_do(tmp_path: Path) -> None:
    """Dòng JSONL cũ không có nhom_ly_do vẫn đọc được với giá trị None."""
    feedback_path = tmp_path / "legacy.jsonl"
    legacy_line = (
        '{"thoi_diem":"2026-11-16T09:30:00+07:00","ca_id":"DEMO-02",'
        '"ma_luat":"lieu_than_can_chinh","yeu_to":6,'
        '"chi_tiet_y_lenh_id":["CT-DEMO02-01"],"phan_hoi":"dong_y","ly_do":null}\n'
    )
    feedback_path.write_text(legacy_line, encoding="utf-8")

    loaded = load_feedback(path=feedback_path)

    assert len(loaded) == 1
    assert loaded[0].phan_hoi == "dong_y"
    assert loaded[0].nhom_ly_do is None
