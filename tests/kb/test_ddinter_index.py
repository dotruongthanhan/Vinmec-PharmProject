"""Kiểm thử đọc, gộp cặp và nối hoạt chất cho nguồn DDInter 2.0."""

from __future__ import annotations

import json
from pathlib import Path

from app.kb.names import DrugNameIndex
from app.kb.sources.ddinter_index import (
    ALL_CSV_COLUMNS,
    build_ingredient_bridge,
    load_ddinter_pairs,
)

_ROOT = Path(__file__).resolve().parents[2]
_HOAT_CHAT_PATH = _ROOT / "data" / "kb" / "hoat_chat.json"


def test_load_and_dedupe_5col_and_10col_csvs(tmp_path: Path) -> None:
    csv_a = tmp_path / "ddinter_downloads_code_B.csv"
    csv_a.write_text(
        "DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level\n"
        "DDInter1951,Warfarin,DDInter138,Aspirin,Moderate\n"
        "DDInter1,Metformin,DDInter2,Cimetidine,Unknown\n",
        encoding="utf-8",
    )

    csv_b = tmp_path / "ddinter_downloads_code_C.csv"
    csv_b.write_text(
        ",".join(ALL_CSV_COLUMNS)
        + "\n"
        + 'DDInter138,Aspirin,DDInter1951,Warfarin,Major,DDI001,"Synergistic effect; Metabolism",'
        + '"Increased bleeding risk.","Monitor INR closely.","[1] Smith 2020\n[2] Jones 2021"\n',
        encoding="utf-8",
    )

    pairs, names, counts = load_ddinter_pairs(tmp_path)
    assert counts == {
        "ddinter_downloads_code_B.csv": 2,
        "ddinter_downloads_code_C.csv": 1,
    }
    assert names["DDInter1951"] == "Warfarin"
    assert len(pairs) == 2

    warfarin_aspirin = next(p for p in pairs if p.interaction_id == "DDI001")
    assert warfarin_aspirin.ddinter_id_1 == "DDInter138"
    assert warfarin_aspirin.ddinter_id_2 == "DDInter1951"
    assert warfarin_aspirin.level == "Major"
    assert warfarin_aspirin.co_muc_lech is True
    assert warfarin_aspirin.source_files == [
        "ddinter_downloads_code_B.csv",
        "ddinter_downloads_code_C.csv",
    ]
    assert warfarin_aspirin.mechanism == ["Synergistic effect", "Metabolism"]
    assert warfarin_aspirin.interaction_text == "Increased bleeding risk."
    assert warfarin_aspirin.management_text == "Monitor INR closely."
    assert warfarin_aspirin.references == ["[1] Smith 2020", "[2] Jones 2021"]


def test_build_ingredient_bridge_with_openfda_metadata(tmp_path: Path) -> None:
    openfda_dir = tmp_path / "openfda"
    openfda_dir.mkdir()
    (openfda_dir / "warfarin.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "openfda": {
                            "rxcui": ["11289"],
                            "pharm_class_epc": ["Vitamin K Antagonist [EPC]"],
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    names = DrugNameIndex.load(_HOAT_CHAT_PATH)
    bridge = build_ingredient_bridge(
        names,
        {
            "DDInter1951": "Warfarin",
            "DDInter138": "Aspirin",
            "DDInter999": "Imipenem",
            "DDInter888": "Metoprolol succinate",
        },
        openfda_dir=openfda_dir,
    )

    assert bridge.ddinter_by_hoat_chat["warfarin"] == ["DDInter1951"]
    assert bridge.ddinter_by_hoat_chat["imipenem"] == ["DDInter999"]
    assert bridge.ddinter_by_hoat_chat["metoprolol"] == ["DDInter888"]
    assert bridge.hoat_chat_by_ddinter["DDInter1951"] == ["warfarin"]
    assert bridge.rxcui_by_hoat_chat["warfarin"] == ["11289"]
    assert bridge.epc_by_hoat_chat["warfarin"] == ["Vitamin K Antagonist [EPC]"]
    assert "dabigatran" in bridge.unmatched_hoat_chat
