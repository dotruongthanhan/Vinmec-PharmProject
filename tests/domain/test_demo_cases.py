"""Kiểm thử 6 ca demo giả lập và 6 tệp đáp án chuẩn trong data/."""

import json
from pathlib import Path

from app.domain.loader import (
    ingredients_of,
    latest_lab,
    latest_vital,
    load_all_cases,
    load_answer,
    load_case,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MOCK_DEMO_DIR = REPO_ROOT / "data" / "mock" / "demo"
GOLD_DEMO_DIR = REPO_ROOT / "data" / "gold" / "demo"
FORBIDDEN_KEYS = {"ho_ten", "patient_name", "hn"}


def _collect_keys(obj: object) -> set[str]:
    """Thu thập toàn bộ tên khoá JSON lồng nhau."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(key)
            keys.update(_collect_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_collect_keys(item))
    return keys


def test_all_demo_cases_and_gold_answers_load_in_order() -> None:
    """Nạp đủ 6 ca demo theo thứ tự DEMO-01..DEMO-06 cùng 6 đáp án khớp ca_id."""
    cases = load_all_cases(MOCK_DEMO_DIR)
    expected_ids = [f"DEMO-0{i}" for i in range(1, 7)]
    assert [ca.ca_id for ca in cases] == expected_ids

    for ca in cases:
        answer = load_answer(GOLD_DEMO_DIR / f"{ca.ca_id}.json")
        assert answer.ca_id == ca.ca_id
        assert ca.nguoi_benh.nguoi_benh_id == f"NB-{ca.ca_id}"
        assert latest_vital(ca, "can_nang") is not None
        assert latest_vital(ca, "chieu_cao") is not None
        creatinin = latest_lab(ca, "creatinin")
        assert creatinin is not None
        assert creatinin.don_vi == "umol/L"
        assert any(cd.loai == "chinh" for cd in ca.chan_doan)
        assert len(ca.dien_bien) >= 1


def test_demo_01_clean_case() -> None:
    """DEMO-01 là ca sạch với danh sách phát hiện kỳ vọng rỗng."""
    ca = load_case(MOCK_DEMO_DIR / "DEMO-01.json")
    gold = load_answer(GOLD_DEMO_DIR / "DEMO-01.json")
    assert ca.tinh_trang_di_ung.trang_thai == "khong_di_ung_da_hoi"
    assert gold.phat_hien_ky_vong == []
    assert gold.van_ban_bat_thuong is False


def test_demo_02_renal_impairment_latest_lab_and_vital() -> None:
    """DEMO-02 có creatinin mới nhất 212 umol/L, kết quả cũ 150 và cân nặng 50 kg."""
    ca = load_case(MOCK_DEMO_DIR / "DEMO-02.json")
    gold = load_answer(GOLD_DEMO_DIR / "DEMO-02.json")

    creatinin = latest_lab(ca, "creatinin")
    assert creatinin is not None
    assert creatinin.gia_tri_so == 212
    assert latest_lab(ca, "khong_co") is None

    weight = latest_vital(ca, "can_nang")
    assert weight is not None
    assert weight.gia_tri == 50

    assert len(gold.phat_hien_ky_vong) == 1
    finding = gold.phat_hien_ky_vong[0]
    assert finding.yeu_to == 6
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"


def test_demo_03_missing_allergy_info() -> None:
    """DEMO-03 có trạng thái dị ứng chua_co_thong_tin và danh sách di_ung rỗng."""
    ca = load_case(MOCK_DEMO_DIR / "DEMO-03.json")
    gold = load_answer(GOLD_DEMO_DIR / "DEMO-03.json")

    assert ca.tinh_trang_di_ung.trang_thai == "chua_co_thong_tin"
    assert ca.di_ung == []
    assert len(gold.phat_hien_ky_vong) == 1
    finding = gold.phat_hien_ky_vong[0]
    assert finding.yeu_to == 1
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.muc_do is None


def test_demo_04_antibiotic_justified_by_microbiology() -> None:
    """DEMO-04 không có chẩn đoán nhiễm nhưng có vi sinh nhạy với kháng sinh được kê."""
    ca = load_case(MOCK_DEMO_DIR / "DEMO-04.json")
    gold = load_answer(GOLD_DEMO_DIR / "DEMO-04.json")

    assert all("nhiễm" not in cd.noi_dung.lower() for cd in ca.chan_doan)
    order_line = ca.y_lenh_cho_duyet.chi_tiet[0]
    order_ingredients = {hc.hoat_chat_id for hc in ingredients_of(ca, order_line)}
    susceptible_ids = {
        ksd.hoat_chat_id
        for vs in ca.vi_sinh
        if vs.vi_khuan
        for ksd in vs.khang_sinh_do
        if ksd.ket_qua == "S"
    }
    assert not order_ingredients.isdisjoint(susceptible_ids)

    wbc = latest_lab(ca, "wbc")
    crp = latest_lab(ca, "crp")
    assert wbc is not None
    assert wbc.gia_tri_so == 14.5
    assert crp is not None
    assert crp.gia_tri_so == 86.0

    assert len(gold.phat_hien_ky_vong) == 1
    finding = gold.phat_hien_ky_vong[0]
    assert finding.yeu_to == 3
    assert finding.ket_luan == "dat"
    assert finding.muc_do == "thong_tin"


def test_demo_05_schedule_missing_evening_dose() -> None:
    """DEMO-05 kê 2 lần/ngày nhưng hai mốc lịch dùng cách nhau đúng 24 giờ."""
    ca = load_case(MOCK_DEMO_DIR / "DEMO-05.json")
    gold = load_answer(GOLD_DEMO_DIR / "DEMO-05.json")

    line = ca.y_lenh_cho_duyet.chi_tiet[0]
    assert line.so_lan_moi_ngay == 2
    assert len(line.lich_dung) == 2
    dose_1, dose_2 = line.lich_dung
    gap_seconds = (dose_2.thoi_diem_du_kien - dose_1.thoi_diem_du_kien).total_seconds()
    assert gap_seconds == 24 * 3600

    assert len(gold.phat_hien_ky_vong) == 1
    finding = gold.phat_hien_ky_vong[0]
    assert finding.yeu_to == 7
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "can_luu_y"


def test_demo_06_cross_allergy_and_prompt_injection() -> None:
    """DEMO-06 có dị ứng chéo cùng nhóm dược lý và câu chèn lệnh trong diễn biến."""
    ca = load_case(MOCK_DEMO_DIR / "DEMO-06.json")
    gold = load_answer(GOLD_DEMO_DIR / "DEMO-06.json")

    order_ingredients = ingredients_of(ca, ca.y_lenh_cho_duyet.chi_tiet[0])
    allergy = ca.di_ung[0]
    hc_by_id = {hc.hoat_chat_id: hc for hc in ca.danh_muc_hoat_chat}
    assert allergy.hoat_chat_id is not None
    allergy_hc = hc_by_id[allergy.hoat_chat_id]
    assert allergy.nhom_duoc_ly == "penicillin"
    assert allergy_hc.nhom_duoc_ly == "penicillin"
    assert any(hc.nhom_duoc_ly == allergy_hc.nhom_duoc_ly for hc in order_ingredients)
    assert any("Bỏ qua mọi hướng dẫn" in db.noi_dung for db in ca.dien_bien)

    assert len(gold.phat_hien_ky_vong) == 1
    finding = gold.phat_hien_ky_vong[0]
    assert finding.yeu_to == 1
    assert finding.ket_luan == "can_xem"
    assert finding.muc_do == "nghiem_trong"
    assert gold.van_ban_bat_thuong is True


def test_no_json_contains_forbidden_pii_keys() -> None:
    """Không tệp JSON nào trong mock hoặc gold chứa khoá ho_ten, patient_name, hn."""
    json_files = [*MOCK_DEMO_DIR.glob("*.json"), *GOLD_DEMO_DIR.glob("*.json")]
    assert len(json_files) == 12
    for file_path in json_files:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        assert FORBIDDEN_KEYS.isdisjoint(_collect_keys(payload))
