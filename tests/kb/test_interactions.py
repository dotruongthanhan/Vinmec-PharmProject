"""Kiểm thử xây dựng kho tri thức tuong_tac.jsonl và đối chiếu nhãn openFDA."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.types import Chunk
from app.kb.interactions import build_interactions
from app.kb.sources.ddinter_index import ALL_CSV_COLUMNS
from app.rules.interaction import load_interaction_rules

_ROOT = Path(__file__).resolve().parents[2]
_HOAT_CHAT_PATH = _ROOT / "data" / "kb" / "hoat_chat.json"


def _make_chunk(
    chunk_id: str,
    hc_ids: list[str],
    muc: str,
    text: str,
) -> Chunk:
    return Chunk(
        doan_trich_id=chunk_id,
        tai_lieu_id="fda_warfarin_v1",
        muc_cha_id=None,
        nhom_nguon="openfda",
        nguon="openfda_drug_label",
        tang_tin_cay=4,
        hoat_chat_ids=hc_ids,
        muc=muc,
        duong_dan_muc=f"7 DRUG INTERACTIONS > {chunk_id}",
        loai_noi_dung="van_ban",
        ngon_ngu="en",
        phien_ban_nguon="2026-01-01",
        url_goc="https://api.fda.gov/drug/label.json",
        noi_dung_goc=text,
        noi_dung_nhung=text,
    )


def test_build_interactions_generates_jsonl_and_fda_links(tmp_path: Path) -> None:
    ddinter_dir = tmp_path / "ddinter"
    ddinter_dir.mkdir()
    csv_path = ddinter_dir / "ddinter_downloads_code_B.csv"
    csv_path.write_text(
        ",".join(ALL_CSV_COLUMNS)
        + "\n"
        + 'DDInter1951,Warfarin,DDInter943,Ibuprofen,Major,DDI-WI,"Synergistic effect",'
        + '"Concomitant use increases hemorrhage risk.","Avoid or monitor INR.","[1] Ref 1"\n'
        + 'DDInter79,Amlodipine,DDInter1951,Warfarin,Unknown,DDI-AW,"",,,\n'
        + 'DDInter999,NonExistentDrugXYZ,DDInter1951,Warfarin,Major,DDI-XX,"",,,\n',
        encoding="utf-8",
    )

    chunks_path = tmp_path / "chunks.jsonl"
    chunks = [
        _make_chunk(
            "CK-WARF-TT",
            ["warfarin"],
            "tuong_tac",
            "Concomitant ibuprofen or NSAIDs increase bleeding risk.",
        ),
        _make_chunk(
            "CK-WARF-PARTIAL",
            ["warfarin"],
            "tuong_tac",
            "Do not match ibuprofenoid fakeword inside substring.",
        ),
        _make_chunk(
            "CK-WARF-DOSE",
            ["warfarin"],
            "lieu",
            "Ibuprofen mention in dosage should not be linked.",
        ),
    ]
    chunks_path.write_text(
        "\n".join(c.model_dump_json() for c in chunks) + "\n",
        encoding="utf-8",
    )

    out_path = tmp_path / "tuong_tac.jsonl"
    reports_dir = tmp_path / "reports"
    book, bridge, report = build_interactions(
        ddinter_dir=ddinter_dir,
        chunks_path=chunks_path,
        names_path=_HOAT_CHAT_PATH,
        openfda_dir=None,
        out_path=out_path,
        reports_dir=reports_dir,
    )

    assert len(book.tuong_tac) == 2
    assert report["pairs_built"] == 2
    assert report["pairs_with_fda_citations"] == 1
    assert Path(str(report["report_path"])).is_file()

    reloaded = load_interaction_rules(out_path)
    wi = reloaded.lookup("warfarin", "ibuprofen")
    assert wi is not None
    assert wi.tuong_tac_id == "TT-ibuprofen-warfarin"
    assert wi.muc_do == "nghiem_trong"
    assert wi.tang_tin_cay == 4
    assert wi.co_che == ["Synergistic effect"]
    assert wi.trich_dan_nhan_fda == ["CK-WARF-TT"]

    aw = reloaded.lookup("amlodipine", "warfarin")
    assert aw is not None
    assert aw.muc_do == "chua_ro"
    assert aw.tang_tin_cay == 3
    rep_data = json.loads(Path(str(report["report_path"])).read_text(encoding="utf-8"))
    assert rep_data["pairs_built"] == 2
