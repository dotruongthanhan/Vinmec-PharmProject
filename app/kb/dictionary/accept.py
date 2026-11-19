"""Lọc ứng viên để tự nhận và đo trên tên đã có nhãn."""

from pathlib import Path

from pydantic import BaseModel

from app.kb.dictionary.catalog import CandidateName, Catalog
from app.kb.dictionary.rules_extra import RulesConfig, vitamin_code
from app.kb.dictionary.storage import read_jsonl
from app.kb.names import normalize_key


class RankedCandidate(CandidateName):
    ten_chinh: str
    diem_nhung: float
    diem_ky_tu: float
    diem_ket_hop: float
    hang: int


class Ranking(BaseModel):
    khoa_chuan_hoa: str
    mo_hinh: str
    ung_vien: list[RankedCandidate]


def candidate_path(root: Path, mode: str) -> Path:
    suffix = "_fake" if mode == "fake" else ""
    return root / "kb_reports" / f"T52_ung_vien{suffix}.jsonl"


def can_accept(
    candidates: list[RankedCandidate],
    embedding: float,
    spelling: float,
    margin: float,
) -> bool:
    if not candidates:
        return False
    winner = candidates[0]
    if winner.diem_nhung <= embedding or winner.diem_ky_tu <= spelling:
        return False
    if len(candidates) > 1 and winner.diem_ket_hop - candidates[1].diem_ket_hop < margin:
        return False
    win_prefixes = {normalize_key(name)[:4] for name in (winner.ten, winner.ten_chinh)}
    win_groups = {code[:5] for code in winner.ma_atc if len(code) >= 5}
    for other in candidates[1:]:
        if winner.diem_ket_hop - other.diem_ket_hop > margin:
            continue
        prefixes = {normalize_key(name)[:4] for name in (other.ten, other.ten_chinh)}
        groups = {code[:5] for code in other.ma_atc if len(code) >= 5}
        if win_groups & groups or any(len(prefix) == 4 for prefix in win_prefixes & prefixes):
            return False
    return True


def eligible(
    key: str,
    winner: RankedCandidate,
    catalog: Catalog,
    config: RulesConfig,
    *,
    hide_exact: bool = False,
) -> CandidateName | None:
    if vitamin_code(key, config) or key in catalog.pins or not winner.rxcui:
        return None
    entry = catalog.by_code(winner.rxcui)
    if not entry or (
        entry.tty != winner.tty
        and not (
            winner.tty == "KB"
            and any(
                alias.tty == "KB" and alias.rxcui == winner.rxcui
                for alias in catalog.by_key.get(normalize_key(winner.ten), ())
            )
        )
    ):
        return None
    if not hide_exact and any(
        other.identity != entry.identity for other in catalog.exact_entries(key)
    ):
        return None
    if entry.tty == "PIN" and catalog.pin_base(winner.rxcui)[0] is None:
        return None
    if len(catalog.by_rx.get(winner.rxcui, ())) > 1:
        return None
    return entry


def load_auto_picks(root: Path, catalog: Catalog, config: RulesConfig) -> dict[str, CandidateName]:
    path = candidate_path(root, "that")
    if not config.tu_nhan_ngu_nghia or not path.is_file():
        return {}
    from app.config.settings import load_settings

    model = load_settings().embedding.active
    picks = {}
    for row in read_jsonl(path):
        ranking = Ranking.model_validate(row)
        if ranking.mo_hinh != model or not can_accept(
            ranking.ung_vien,
            config.nguong_nhung,
            config.nguong_ky_tu,
            config.chenh_toi_thieu,
        ):
            continue
        if entry := eligible(ranking.khoa_chuan_hoa, ranking.ung_vien[0], catalog, config):
            picks[ranking.khoa_chuan_hoa] = entry
    return picks
