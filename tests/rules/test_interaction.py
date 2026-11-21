"""Kiểm ma trận và luật yếu tố 4 bằng chỉ mục giả lập thu nhỏ."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.domain.loader import load_case
from app.domain.models import CaBenh, ChiTietYLenh, HoatChat, ThanhPhan, Thuoc
from app.kb.interactions import InteractionStore
from app.kb.interactions.build import INDEX_PATH, build_index
from app.kb.resolver import DrugResolver
from app.rules.interaction import build_interaction_matrix, check
from tests.kb.test_interactions import write_sources


def create_dependencies(tmp_path: Path) -> tuple[DrugResolver, InteractionStore]:
    write_sources(tmp_path)
    build_index(tmp_path)
    index = tmp_path / "resolver.sqlite"
    with closing(sqlite3.connect(index)) as db:
        db.executescript("""
            CREATE TABLE hoat_chat(hoat_chat_id, ten_inn, ten_viet, ma_atc_json, loai, ddinter_id);
            CREATE TABLE dong_nghia(khoa_chuan_hoa, hoat_chat_id, loai);
            CREATE TABLE chuyen_ma_ca(ma_ca, hoat_chat_id);
            CREATE TABLE thuoc(khoa_ten_thuoc, thuoc_id);
            CREATE TABLE thuoc_thanh_phan(thuoc_id, hoat_chat_id, ham_luong, don_vi);
        """)
        for name, ddinter, kind in [
            ("alpha", "A", "thuoc"),
            ("beta", "B", "thuoc"),
            ("gamma", "C", "thuoc"),
            ("delta", "D", "thuoc"),
            ("missing", None, "thuoc"),
            ("saline", None, "dich_truyen_dien_giai"),
        ]:
            db.execute(
                "INSERT INTO hoat_chat VALUES (?, ?, NULL, '[]', ?, ?)", (name, name, kind, ddinter)
            )
            db.execute("INSERT INTO dong_nghia VALUES (?, ?, 'inn')", (name, name))
        db.commit()
    return DrugResolver.from_index(index), InteractionStore.from_path(tmp_path / INDEX_PATH)


@pytest.fixture
def dependencies(tmp_path: Path) -> tuple[DrugResolver, InteractionStore]:
    return create_dependencies(tmp_path)


@pytest.mark.parametrize(
    ("severity", "matrix_level", "finding_level", "conclusion", "wording"),
    [
        ("Major", "nghiem_trong", "nghiem_trong", "can_xem", "tương tác mức nặng"),
        ("Moderate", "can_luu_y", "can_luu_y", "can_xem", "tương tác mức trung bình"),
        ("Minor", "can_luu_y", "thong_tin", "can_xem", "tương tác mức nhẹ"),
        ("Unknown", "thieu_du_lieu", None, "khong_du_du_lieu", "chưa đủ dữ liệu tương tác"),
    ],
)
def test_other_source_levels_are_not_promoted_or_lost(
    dependencies: tuple[DrugResolver, InteractionStore],
    tmp_path: Path,
    severity: str,
    matrix_level: str,
    finding_level: str | None,
    conclusion: str,
    wording: str,
) -> None:
    resolver, _ = dependencies
    with closing(sqlite3.connect(tmp_path / INDEX_PATH)) as db:
        db.execute("UPDATE cap SET muc_do=?, co_che_json='[\"Distribution\"]'", (severity,))
        db.commit()
    store = InteractionStore.from_path(tmp_path / INDEX_PATH)
    ca = make_case(["alpha", "beta"])
    pair = build_interaction_matrix(ca, resolver, store).cap[0]
    assert pair.muc == matrix_level
    (finding,) = check(ca, resolver, store)
    assert finding.muc_do == finding_level and finding.ket_luan == conclusion
    assert finding.mo_ta.startswith(f"alpha × beta: {wording}")
    assert finding.mo_ta.endswith(". Nguồn sàng lọc, cần đối chiếu nhãn.")
    assert finding.mo_ta.count("alpha") == finding.mo_ta.count("beta") == 1
    record = store.pair("A", "B")
    assert record is not None and record.muc_do == severity
    if severity == "Unknown":
        for text in (pair.tom_tat, pair.ly_do, finding.mo_ta, *finding.thong_tin_con_thieu):
            assert text is not None and "chưa rõ" in text and "Unknown" in text
            assert text.count("(") == text.count(")") == 1
        assert pair.ly_do == "DDInter ghi mức chưa rõ (Unknown)"
        assert finding.mo_ta == (
            "alpha × beta: chưa đủ dữ liệu tương tác: DDInter ghi mức chưa rõ (Unknown). "
            "Nguồn sàng lọc, cần đối chiếu nhãn."
        )
        assert "chưa rõ (DDInter: Unknown)" in finding.can_cu[0].mo_ta
    else:
        assert finding.mo_ta == (
            f"alpha × beta: {wording} (DDInter: {severity}, cơ chế Distribution). "
            "Nguồn sàng lọc, cần đối chiếu nhãn."
        )
        assert pair.tom_tat is not None and wording in pair.tom_tat


def make_case(names: list[str], active: list[str] | None = None) -> CaBenh:
    ca = load_case(Path("data/mock/demo/DEMO-02.json"))
    ca.y_lenh_cho_duyet.chi_tiet = [
        ChiTietYLenh(
            chi_tiet_y_lenh_id=f"P{i}",
            ten_tu_do=name,
            trang_thai_dong="pending",
            bat_dau=ca.y_lenh_cho_duyet.thoi_diem_ke,
        )
        for i, name in enumerate(names)
    ]
    ca.thuoc_dang_dung = [
        ChiTietYLenh(
            chi_tiet_y_lenh_id=f"A{i}",
            ten_tu_do=name,
            trang_thai_dong="active",
            bat_dau=ca.y_lenh_cho_duyet.thoi_diem_ke,
        )
        for i, name in enumerate(active or [])
    ]
    return ca


def test_major_and_combination_take_highest_and_keep_source(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["alpha + missing", "beta"])
    matrix = build_interaction_matrix(ca, resolver, store)
    assert matrix.cap[0].muc == "nghiem_trong"
    (finding,) = check(ca, resolver, store)
    assert finding.yeu_to == 4 and finding.muc_do == "nghiem_trong"
    assert finding.chi_tiet_y_lenh_id == ["P0", "P1"]
    assert finding.mo_ta.startswith("alpha + missing × beta: tương tác mức nặng")
    assert finding.mo_ta.count("alpha + missing") == finding.mo_ta.count("beta") == 1
    assert "alpha × beta" in finding.can_cu[0].mo_ta
    assert "sàng lọc, cần đối chiếu nhãn" in finding.mo_ta.lower()
    assert "Fixture highest" in finding.can_cu[0].mo_ta
    assert "Fixture reference" in finding.can_cu[0].mo_ta
    assert "https://example.invalid/2" in finding.can_cu[0].mo_ta
    assert "chống chỉ định" not in finding.mo_ta.lower()
    reverse = build_interaction_matrix(make_case(["beta", "alpha + missing"]), resolver, store)
    assert reverse.cap[0].muc == matrix.cap[0].muc


@pytest.mark.parametrize(
    ("names", "level", "reason"),
    [
        (["missing", "alpha"], "thieu_du_lieu", "ddinter_id"),
        (["unknown", "alpha"], "thieu_du_lieu", "không khớp tên"),
        (["alpha + unknown", "delta"], "thieu_du_lieu", "unknown"),
        (["saline", "alpha"], "khong_ap_dung", "dịch truyền"),
        (["alpha", "alpha"], "khong_ap_dung", "trùng hoạt chất – xem yếu tố 2"),
        (["alpha", "delta"], "khong_phat_hien", None),
        (["alpha", "gamma"], "thieu_du_lieu", "danh sách ddinter chưa cào đủ"),
    ],
)
def test_pair_levels_do_not_claim_absence_without_complete_data(
    dependencies: tuple,
    names: list[str],
    level: str,
    reason: str | None,
) -> None:
    resolver, store = dependencies
    ca = make_case(names)
    matrix = build_interaction_matrix(ca, resolver, store)
    assert matrix.cap[0].muc == level
    if reason:
        assert reason in matrix.cap[0].ly_do.lower()
    findings = check(ca, resolver, store)
    assert len(findings) == 1
    if level == "thieu_du_lieu":
        assert findings[0].ket_luan == "khong_du_du_lieu"
        assert findings[0].muc_do is None and findings[0].thong_tin_con_thieu
    else:
        assert findings[0].ket_luan == "dat"


def test_active_pairs_display_without_creating_findings(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["saline"], ["alpha", "beta"])
    matrix = build_interaction_matrix(ca, resolver, store)
    assert [row.nhom for row in matrix.thuoc] == ["cho_duyet", "dang_dung", "dang_dung"]
    assert len(matrix.cap) == 3 and matrix.cap[-1].muc == "nghiem_trong"
    assert matrix.cap[-1].nhan_dinh_id is None
    assert [row.ket_luan for row in check(ca, resolver, store)] == ["dat"]
    assert matrix.thuc_an[0].muc == "chua_ro"


def test_stopped_lines_are_not_resolved(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["alpha"], ["beta"])
    ca.thuoc_dang_dung[0].trang_thai_dong = "discontinued"
    assert not build_interaction_matrix(ca, resolver, store).cap
    assert check(ca, resolver, store)[0].ket_luan == "dat"


def test_missing_indexes_are_silent_and_warn(caplog: pytest.LogCaptureFixture) -> None:
    assert check(make_case(["alpha", "beta"]), None, None) == []
    assert "chỉ mục" in caplog.text.lower()


def test_missing_code_keeps_both_known_ingredients_with_brand_labels(dependencies: tuple) -> None:
    resolver, store = dependencies
    ca = make_case(["Brand Alpha", "Brand Beta"])
    ca.danh_muc_hoat_chat.extend(
        [
            HoatChat(hoat_chat_id="missing", ten_hoat_chat="missing"),
            HoatChat(hoat_chat_id="beta", ten_hoat_chat="beta"),
        ]
    )
    ca.danh_muc_thuoc.extend(
        [
            Thuoc(
                thuoc_id="brand-a",
                ten_thuoc="Brand Alpha",
                thanh_phan=[ThanhPhan(hoat_chat_id="missing")],
            ),
            Thuoc(
                thuoc_id="brand-b",
                ten_thuoc="Brand Beta",
                thanh_phan=[ThanhPhan(hoat_chat_id="beta")],
            ),
        ]
    )
    for line, identifier in zip(ca.y_lenh_cho_duyet.chi_tiet, ("brand-a", "brand-b"), strict=True):
        line.thuoc_id = identifier
    (finding,) = check(ca, resolver, store)
    assert finding.ket_luan == "khong_du_du_lieu"
    assert "chưa có dữ liệu DDInter cho missing (thiếu ddinter_id)" in finding.mo_ta
    assert finding.mo_ta.count("Brand Alpha") == finding.mo_ta.count("Brand Beta") == 1
    matrix = build_interaction_matrix(ca, resolver, store)
    assert [row.hoat_chat for row in matrix.thuoc] == [["missing"], ["beta"]]


@pytest.mark.parametrize(
    ("names", "reason"),
    [
        (["missing", "beta"], "chưa có dữ liệu DDInter (thiếu ddinter_id)"),
        (["unrecognized", "beta"], "chưa phân giải đủ hoạt chất"),
        (["alpha", "gamma"], "danh sách DDInter chưa cào đủ hoặc chưa có dữ liệu thuốc"),
    ],
)
def test_missing_data_explains_reason_without_repeating_drug_names(
    dependencies: tuple[DrugResolver, InteractionStore], names: list[str], reason: str
) -> None:
    resolver, store = dependencies
    (finding,) = check(make_case(names), resolver, store)
    assert finding.ket_luan == "khong_du_du_lieu"
    assert finding.mo_ta.startswith(f"{' × '.join(names)}: chưa đủ dữ liệu tương tác")
    assert reason in finding.mo_ta
    assert finding.mo_ta.count("(") == finding.mo_ta.count(")") <= 1
    assert all(finding.mo_ta.count(name) == 1 for name in names)
    assert finding.mo_ta.endswith(". Nguồn sàng lọc, cần đối chiếu nhãn.")


def test_single_effective_drug_has_no_pair_to_screen(
    dependencies: tuple[DrugResolver, InteractionStore],
) -> None:
    resolver, store = dependencies
    ca = make_case(["alpha"], ["beta"])
    ca.thuoc_dang_dung[0].trang_thai_dong = "discontinued"
    (finding,) = check(ca, resolver, store)
    assert finding.ket_luan == "dat" and finding.muc_do == "thong_tin"
    assert finding.mo_ta == (
        "Y lệnh chỉ có một thuốc đang hiệu lực, không có cặp để đối chiếu tương tác."
    )
    assert "đối chiếu nhãn" not in finding.mo_ta


@pytest.mark.parametrize("active", [["delta"], ["delta", "delta"]])
def test_no_interaction_counts_only_checked_pairs_with_pending_lines(
    dependencies: tuple[DrugResolver, InteractionStore], active: list[str]
) -> None:
    resolver, store = dependencies
    (finding,) = check(make_case(["alpha"], active), resolver, store)
    assert finding.ket_luan == "dat"
    assert finding.mo_ta == (
        f"Đã đối chiếu {len(active)} cặp thuốc, không phát hiện tương tác trong dữ liệu DDInter. "
        "Nguồn sàng lọc, cần đối chiếu nhãn."
    )


@pytest.mark.parametrize("pending", [[], ["saline"]])
def test_active_only_interaction_is_not_described_as_absent(
    dependencies: tuple[DrugResolver, InteractionStore], pending: list[str]
) -> None:
    resolver, store = dependencies
    (finding,) = check(make_case(pending, ["alpha", "beta"]), resolver, store)
    assert finding.ket_luan == "dat"
    assert "không có cặp" in finding.mo_ta.lower()
    assert "không phát hiện" not in finding.mo_ta
    assert "đối chiếu nhãn" not in finding.mo_ta
