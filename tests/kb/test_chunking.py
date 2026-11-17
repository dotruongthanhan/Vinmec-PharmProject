"""Kiem thu bo cat doan BaseChunker va LabelChunker."""

from __future__ import annotations

from app.config.settings import ChunkingSettings
from app.core.interfaces import Chunker
from app.kb.chunking.label_chunker import LabelChunker
from app.kb.sources.openfda import LabelDocument, LabelSection, LabelTable


def _make_settings(
    target_chars: int = 300,
    max_chars: int = 450,
    min_chars: int = 100,
    overlap_sentences: int = 1,
) -> ChunkingSettings:
    return ChunkingSettings(
        target_chars=target_chars,
        max_chars=max_chars,
        min_chars=min_chars,
        overlap_sentences=overlap_sentences,
        parent_max_chars=1500,
    )


def _make_doc(
    sections: list[LabelSection],
    hoat_chat_ids: list[str] | None = None,
    ten_hoat_chat: list[str] | None = None,
) -> LabelDocument:
    return LabelDocument(
        tai_lieu_id="openfda:test-set-001",
        ten_goi="meropenem",
        hoat_chat_ids=hoat_chat_ids if hoat_chat_ids is not None else ["meropenem"],
        ten_hoat_chat=ten_hoat_chat if ten_hoat_chat is not None else ["meropenem"],
        set_id="test-set-001",
        phien_ban_nguon="20250610",
        url_goc="https://api.fda.gov/drug/label.json?search=set_id:test-set-001",
        ten_hien_thi="Nhãn FDA SynthTest (10/06/2025)",
        sections=sections,
    )


def test_chunker_protocol_and_metadata_fields() -> None:
    settings = _make_settings()
    chunker = LabelChunker(settings)
    assert isinstance(chunker, Chunker)

    text = (
        "Administer 500 mg intravenously every 8 hours for complicated skin infections "
        "in adult patients with normal renal clearance."
    )
    doc = _make_doc(
        sections=[
            LabelSection(
                muc="lieu",
                duong_dan_muc="Dosage and Administration > 2.1 Adult Patients",
                truong_goc="dosage_and_administration",
                van_ban=text,
            )
        ],
        hoat_chat_ids=["amoxicillin", "clavulanic_acid"],
        ten_hoat_chat=["amoxicillin", "clavulanic acid"],
    )
    chunks = chunker.split(doc)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.doan_trich_id.startswith("DT-")
    assert len(c.muc_cha_id or "") == 16
    assert c.nhom_nguon == "nhan_thuoc"
    assert c.nguon == "openfda"
    assert c.tang_tin_cay == 3
    assert c.ngon_ngu == "en"
    assert c.loai_noi_dung == "van_ban"
    assert c.noi_dung_goc == text
    assert c.noi_dung_goc in doc.sections[0].van_ban
    expected_prefix = (
        "[amoxicillin + clavulanic acid | "
        "Nhãn FDA SynthTest (10/06/2025) | "
        "Dosage and Administration > 2.1 Adult Patients]\n"
    )
    assert c.noi_dung_nhung.startswith(expected_prefix)
    assert c.noi_dung_nhung.endswith(text)


def test_short_sentences_and_short_tail_are_merged() -> None:
    settings = _make_settings(target_chars=300, max_chars=450, min_chars=120)
    chunker = LabelChunker(settings)

    s1 = "First clinical sentence describing indication for bacterial infection."
    s2 = "Second clinical sentence describing intravenous dosing every eight hours."
    s3 = "Third sentence giving short warning."
    sec_text = f"{s1} {s2} {s3}"
    assert len(sec_text) < settings.target_chars

    doc = _make_doc(
        [
            LabelSection(
                muc="chi_dinh",
                duong_dan_muc="Indications",
                truong_goc="indications_and_usage",
                van_ban=sec_text,
            )
        ]
    )
    chunks = chunker.split(doc)
    assert len(chunks) == 1
    assert chunks[0].noi_dung_goc == sec_text

    # Doan cuoi ngan hon min_chars trong van ban co phan tach bang \n\n se gop vao doan truoc.
    para1 = "A" * 260 + "."
    para2 = "Short tail paragraph under min chars."
    para_doc = _make_doc(
        [
            LabelSection(
                muc="canh_bao",
                duong_dan_muc="Warnings",
                truong_goc="warnings_and_cautions",
                van_ban=f"{para1}\n\n{para2}",
            )
        ]
    )
    para_chunks = chunker.split(para_doc)
    assert len(para_chunks) == 1
    assert para2 in para_chunks[0].noi_dung_goc


def test_long_text_splits_with_overlap_and_protects_abbreviations() -> None:
    settings = _make_settings(target_chars=260, max_chars=360, min_chars=80, overlap_sentences=1)
    chunker = LabelChunker(settings)

    sentences = [
        "CrCl 10-25 mL/min: administer 500 mg every 12 hours by infusion, e.g. over 30 min.",
        "Adjust initial dose to 1.5 mg per kg, i.e. weight-based calculation vs. fixed dose.",
        "See Table No. 2 for detailed pediatric infusion concentrations and timing rules.",
        "Monitor renal clearance daily before continuing high-dose carbapenem maintenance.",
        "Hemodialysis removes approximately 50% of active metabolite after four hours.",
    ]
    long_text = " ".join(sentences)
    other_text = (
        "Separate contraindications section describing beta-lactam hypersensitivity "
        "without sharing sentences from previous section."
    )
    doc = _make_doc(
        [
            LabelSection(
                muc="lieu",
                duong_dan_muc="2.1 Dosing",
                truong_goc="dosage_and_administration",
                van_ban=long_text,
            ),
            LabelSection(
                muc="chong_chi_dinh",
                duong_dan_muc="4 Contraindications",
                truong_goc="contraindications",
                van_ban=other_text,
            ),
        ]
    )
    chunks = chunker.split(doc)
    dosing_chunks = [c for c in chunks if c.muc == "lieu"]
    contra_chunks = [c for c in chunks if c.muc == "chong_chi_dinh"]

    assert len(dosing_chunks) >= 2
    assert len(contra_chunks) == 1
    for c in dosing_chunks:
        assert len(c.noi_dung_goc) <= settings.max_chars
        assert c.noi_dung_goc in long_text

    # Dam bao khong cat giua cac cum duoc bao ve.
    full_joined = "\n".join(c.noi_dung_goc for c in dosing_chunks)
    assert "e.g. over 30 min." in full_joined
    assert "i.e. weight-based calculation vs. fixed dose." in full_joined
    assert "Table No. 2" in full_joined

    # Hai doan ke nhau trong cung muc phai chong lan dung 1 cau cuoi doan truoc.
    first_chunk_sents = [s for s in sentences if s in dosing_chunks[0].noi_dung_goc]
    assert first_chunk_sents[-1] in dosing_chunks[1].noi_dung_goc

    # Khong chong lan sang LabelSection khac.
    for sent in sentences:
        assert sent not in contra_chunks[0].noi_dung_goc


def test_tables_never_split_and_duplicates_are_removed() -> None:
    settings = _make_settings(target_chars=150, max_chars=250, min_chars=60)
    chunker = LabelChunker(settings)

    large_table_text = "\n".join(
        [f"Row {i} | Meropenem {i * 100} mg | Every 8 hours by IV infusion" for i in range(1, 15)]
    )
    assert len(large_table_text) > settings.max_chars

    dup_sentence = (
        "Duplicate warning paragraph intentionally repeated across two sections "
        "to verify per-document deduplication keeps the first occurrence only."
    )
    doc = _make_doc(
        [
            LabelSection(
                muc="lieu_than",
                duong_dan_muc="2.2 Renal Impairment",
                truong_goc="dosage_and_administration",
                van_ban=dup_sentence,
                bang=[
                    LabelTable(
                        tieu_de="Table 1. Long Dosing Grid",
                        cot=["Row", "Dose", "Schedule"],
                        dong=[["Row 1", "100 mg", "Every 8 hours"]],
                        van_ban_phang=large_table_text,
                    )
                ],
            ),
            LabelSection(
                muc="canh_bao",
                duong_dan_muc="5 Warnings",
                truong_goc="warnings_and_cautions",
                van_ban=dup_sentence,
            ),
        ]
    )
    chunks = chunker.split(doc)
    table_chunks = [c for c in chunks if c.loai_noi_dung == "bang"]
    text_chunks = [c for c in chunks if c.loai_noi_dung == "van_ban"]

    assert len(table_chunks) == 1
    assert len(table_chunks[0].noi_dung_goc) > settings.max_chars
    assert large_table_text in table_chunks[0].noi_dung_goc
    assert len(text_chunks) == 1

    # Chay lai lan 2 phai ra cung ID xac dinh.
    chunks_repeat = chunker.split(doc)
    assert [c.doan_trich_id for c in chunks] == [c.doan_trich_id for c in chunks_repeat]
