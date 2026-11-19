"""Kiểm bộ phân tích và bộ cào DDInter bằng phản hồi thật đã lưu (không gọi mạng)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.kb.fetch.ddinter import Archive, Crawl, CrawlStopped, DDInterClient, stage_drugs
from app.kb.sources.ddinter_web import (
    ParseError,
    parse_drug,
    parse_pair,
    parse_row,
    parse_table,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ddinter"
WARFARIN, AMOXICILLIN = "DDInter1951", "DDInter83"


def blob(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_drug_page_warfarin() -> None:
    drug = parse_drug(blob("drug_warfarin.html"), WARFARIN)
    assert drug["ten"] == "Warfarin"
    assert "B01AA03" in drug["ma_atc"]
    assert drug["lien_ket"]


def test_drug_page_wrong_id_rejected() -> None:
    with pytest.raises(ParseError):
        parse_drug(blob("drug_warfarin.html"), "DDInter9")


def test_drug_drug_rows_map_level_and_mechanism() -> None:
    page = parse_table(blob("ddi_warfarin_p1.json"))
    rows = [parse_row("tuong_tac_thuoc", r, WARFARIN, "Warfarin") for r in page.data]
    first = rows[0]
    assert first["muc_do"] == "Major" and first["muc_do_so"] == 3
    assert first["co_che"] == ["Synergy"]
    assert first["ma_trang_cap"] == 3039
    assert (first["ddinter_id_a"], first["ddinter_id_b"]) == (WARFARIN, "DDInter9")
    assert first["cot_goc"]["level"] == 3


def test_unknown_level_is_an_error() -> None:
    row = {"drug_id": "DDInter9", "drug_name": "X", "interaction_id": 1, "level": 7}
    with pytest.raises(ParseError):
        parse_row("tuong_tac_thuoc", row, WARFARIN, "Warfarin")


def test_disease_rows() -> None:
    page = parse_table(blob("disease_warfarin.json"))
    rows = [parse_row("tuong_tac_benh", r, WARFARIN, "Warfarin") for r in page.data]
    assert len(rows) == 8 and rows[0]["ten_benh"] == "Hemorrhage"
    assert all(r["noi_dung"] and not r["noi_dung"].endswith(("...", "…")) for r in rows)
    assert all(r["muc_do"] in {"Major", "Moderate", "Minor", "Unknown"} for r in rows)


def test_food_rows() -> None:
    page = parse_table(blob("food_warfarin.json"))
    rows = {
        r["thuc_an"]: r
        for r in (parse_row("tuong_tac_thuc_an", x, WARFARIN, None) for x in page.data)
    }
    alcohol = rows["alcohol"]
    assert alcohol["mo_ta"] and alcohol["xu_tri"] and alcohol["co_che"] == ["Synergy"]


def test_empty_combination_table() -> None:
    assert parse_table(blob("multi_warfarin.json")).recordsTotal == 0


def test_table_rejects_bad_payload() -> None:
    with pytest.raises(ParseError):
        parse_table(b'{"error": "x"}')


def pair(number: int, b: str) -> dict[str, Any]:
    return {"ma_trang_cap": number, "ddinter_id_a": WARFARIN, "ddinter_id_b": b}


def test_pair_page_3039_full_sections() -> None:
    row = parse_pair(blob("interact_3039.html"), pair(3039, "DDInter9"))
    assert (row["muc_do"], row["co_che"]) == ("Major", ["Synergy"])
    assert row["hau_qua"] and row["xu_tri"] and row["cyp_tho"]
    assert len(row["tai_lieu"]) == 3
    assert row["thay_the_a"]["ma_atc"] == "B01A"
    assert len(row["thay_the_b"]["thuoc"]) == 34  # gồm phần ẩn sau "More"


def test_pair_page_24300_and_21901() -> None:
    moderate = parse_pair(blob("interact_24300.html"), pair(24300, AMOXICILLIN))
    assert moderate["muc_do"] == "Moderate" and moderate["co_che"] == ["Synergy"]
    assert moderate["hau_qua"].startswith("Penicillins may occasionally potentiate")
    major = parse_pair(blob("interact_21901.html"), pair(21901, "DDInter76"))
    assert major["muc_do"] == "Major" and major["co_che"] == ["Metabolism"]


def test_pair_page_wrong_pair_rejected() -> None:
    with pytest.raises(ParseError):
        parse_pair(blob("interact_3039.html"), pair(3039, "DDInter1"))


class FakeClient(DDInterClient):
    """Trả phản hồi thật đã lưu, đếm số lần gọi, không dùng mạng."""

    def __init__(self, fail_after: int | None = None) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.fail_after = fail_after

    def request(
        self, url: str, data: dict[str, str] | None = None, referer: str | None = None
    ) -> bytes:
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise CrawlStopped("dừng giả lập")
        start = None if data is None else data["start"]
        self.calls.append((url, start))
        if "drug-detail" in url:
            return blob("drug_warfarin.html")
        if "interact-with-dis" in url:
            return blob("disease_warfarin.json")
        if "interact-with-food" in url:
            return blob("food_warfarin.json")
        if "interact-with-multi" in url:
            return blob("multi_warfarin.json")
        return blob("ddi_warfarin_p1.json" if start == "0" else "ddi_warfarin_p2.json")


def test_pagination_and_resume(tmp_path: Path) -> None:
    archive = Archive(tmp_path)
    # Lần 1: dừng giữa chừng sau 3 yêu cầu (trang thuốc, trang POST 1 và 2 của thuốc–thuốc).
    first = FakeClient(fail_after=3)
    with pytest.raises(CrawlStopped):
        Crawl(archive, first, refresh=False).drugs([WARFARIN])
    assert len(first.calls) == 3
    # Lần 2: chạy tiếp, không gọi lại khoá đã có.
    second = FakeClient()
    crawl = Crawl(Archive(tmp_path), second, refresh=False)
    crawl.drugs([WARFARIN])
    assert not crawl.errors
    assert len(second.calls) == 3  # còn dis, food, multi
    assert all("drug-detail" not in u and "interact-with/" not in u for u, _ in second.calls)
    result = stage_drugs(Archive(tmp_path))
    counts = {r["bang"]: (r["so_dong"], r["tong"]) for r in result["dem"]}
    assert counts["tuong_tac_thuoc"] == (24, 24)
    assert counts["tuong_tac_benh"] == (8, 8)
    rows = [
        json.loads(line)
        for line in (tmp_path / "data/kb_staging/ddinter/tuong_tac_thuoc.jsonl")
        .read_text("utf-8")
        .splitlines()
    ]
    assert len(rows) == 24
