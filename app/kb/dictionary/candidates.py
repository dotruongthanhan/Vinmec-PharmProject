"""Tìm ứng viên bằng véc-tơ trong bộ nhớ và trigram ký tự."""

from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from itertools import product
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from app.config.settings import load_settings
from app.core.interfaces import Embedder
from app.kb.dictionary.accept import RankedCandidate, Ranking, can_accept, candidate_path, eligible
from app.kb.dictionary.catalog import CandidateName, Catalog, baseline
from app.kb.dictionary.review import queue
from app.kb.dictionary.rules_extra import RulesConfig, load_rules
from app.kb.dictionary.split import has_strength
from app.kb.dictionary.storage import Row, write_json, write_jsonl
from app.providers.cached_embedder import CachedEmbedder
from app.providers.embedder_factory import build_embedder
from app.providers.fakes import HashEmbedder
from app.providers.http import create_client

BATCH_SIZE = 128


@contextmanager
def open_embedder(root: Path, mode: str) -> Iterator[tuple[Embedder, str]]:
    if mode == "fake":
        yield HashEmbedder(), "HashEmbedder"
        return
    settings = load_settings()
    embedding = settings.embedding
    if embedding.provider not in ("gemini", "openrouter"):
        raise ValueError("Che do that can settings.embedding.provider=gemini hoac openrouter")
    with create_client() as client:
        yield (
            CachedEmbedder(
                build_embedder(settings, client),
                root / "cache/embeddings_tu_dien.sqlite",
                model_id=embedding.active,
            ),
            embedding.active,
        )


def _trigrams(key: str) -> set[str]:
    padded = f"  {key}  "
    return {padded[i : i + 3] for i in range(len(padded) - 2)}


def _embed(embedder: Embedder, keys: list[str]) -> NDArray[np.float32]:
    vectors = np.empty((len(keys), embedder.dimensions), dtype=np.float32)
    for start in range(0, len(keys), BATCH_SIZE):
        batch = keys[start : start + BATCH_SIZE]
        vectors[start : start + len(batch)] = embedder.embed_documents(batch)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    np.divide(vectors, norms, out=vectors, where=norms != 0)
    return vectors


def rank_names(
    catalog: Catalog,
    keys: list[str],
    embedder: Embedder,
    model: str,
    *,
    hide_exact: bool = False,
) -> Iterator[Ranking]:
    """Lấy tối đa năm mã khác nhau bằng điểm cao nhất trên các tên của mỗi mã."""
    names: list[tuple[str, CandidateName]] = []
    for key, entries in sorted(catalog.by_key.items()):
        unique: dict[tuple[str, str], CandidateName] = {}
        for entry in sorted(
            entries, key=lambda e: (e.identity, e.tty != "PIN", e.tty != "IN", e.ten)
        ):
            unique.setdefault(entry.identity, entry)
        names.extend((key, entry) for entry in unique.values())
    if not names:
        for key in keys:
            yield Ranking(khoa_chuan_hoa=key, mo_hinh=model, ung_vien=[])
        return

    vector_keys = sorted({key for key, _ in names} | set(keys))
    index = {key: i for i, key in enumerate(vector_keys)}
    vectors = _embed(embedder, vector_keys)
    name_indices = np.array([index[key] for key, _ in names])
    docs = (
        vectors
        if len(names) == len(vector_keys) and np.all(name_indices == np.arange(len(vector_keys)))
        else vectors[name_indices]
    )
    by_identity: dict[tuple[str, str], list[int]] = defaultdict(list)
    by_trigram: dict[str, list[int]] = defaultdict(list)
    lengths: dict[int, list[int]] = defaultdict(list)
    by_key: dict[str, list[int]] = defaultdict(list)
    trigram_counts = []
    for i, (key, entry) in enumerate(names):
        by_key[key].append(i)
        by_identity[entry.identity].append(i)
        trigrams = _trigrams(key)
        lengths[len(key)].append(i)
        trigram_counts.append(len(trigrams))
        for gram in trigrams:
            by_trigram[gram].append(i)

    for start in range(0, len(keys), BATCH_SIZE):
        block = keys[start : start + BATCH_SIZE]
        similarities = vectors[[index[key] for key in block]] @ docs.T
        np.clip(similarities, -1, 1, out=similarities)
        for key, cosine in zip(block, similarities, strict=True):
            grams = _trigrams(key)
            shared: dict[int, int] = defaultdict(int)
            for gram in grams:
                for idx in by_trigram.get(gram, []):
                    shared[idx] += 1
            size = len(key)
            spelling = np.empty(len(names), dtype=np.float64)
            # Jaccard và tỷ số độ dài tính bằng kiểu dữ liệu và phép tính chuẩn.
            for length, indices in lengths.items():
                spelling[indices] = 0.15 * min(size, length) / max(size, length)
            for i, count in shared.items():
                spelling[i] += 0.85 * count / (len(grams) + trigram_counts[i] - count)
            combined = (cosine + spelling) / 2
            if hide_exact:
                combined[by_key.get(key, [])] = -np.inf
            picks = []
            for number in range(min(5, len(by_identity))):
                i = int(combined.argmax())
                if not np.isfinite(combined[i]):
                    break
                entry = names[i][1]
                canonical = (
                    catalog.by_code(entry.rxcui)
                    if entry.rxcui
                    else catalog.axes.get(entry.hoat_chat_id)
                )
                picks.append(
                    RankedCandidate(
                        **entry.model_dump(),
                        ten_chinh=(
                            canonical.ten
                            if canonical and not has_strength(canonical.ten)
                            else entry.ten
                        ),
                        diem_nhung=float(cosine[i]),
                        diem_ky_tu=float(spelling[i]),
                        diem_ket_hop=float(combined[i]),
                        hang=number + 1,
                    )
                )
                combined[by_identity[entry.identity]] = -np.inf
            yield Ranking(khoa_chuan_hoa=key, mo_hinh=model, ung_vien=picks)


def find_candidates(root: Path, mode: str, *, dry_run: bool = False) -> Row:
    _, _, _, catalog = baseline(root)
    keys = sorted(queue(root))
    summary = {"so_ten": len(keys), "so_khoa_trong_kho": len(catalog.by_key), "embedder": mode}
    if dry_run:
        return {**summary, "dry_run": True}
    with open_embedder(root, mode) as (embedder, model):
        write_jsonl(
            candidate_path(root, mode),
            (ranking.model_dump() for ranking in rank_names(catalog, keys, embedder, model)),
        )
        return {**summary, "mo_hinh": model}


def _evaluate_grid(
    labels: dict[str, str],
    rankings: list[Ranking],
    catalog: Catalog,
    config: RulesConfig,
) -> list[Row]:
    eligible_rankings = [
        record
        for record in rankings
        if record.ung_vien
        and eligible(
            record.khoa_chuan_hoa,
            record.ung_vien[0],
            catalog,
            config,
            hide_exact=True,
        )
    ]
    grid = []
    for embedding, spelling, margin in product(
        sorted({0.60, 0.85, 0.95, 0.99, config.nguong_nhung}),
        sorted({0.65, 0.80, 0.95, 0.99, config.nguong_ky_tu}),
        sorted({0.03, 0.05, 0.10, 0.15, config.chenh_toi_thieu}),
    ):
        correct = errors = 0
        for record in eligible_rankings:
            if not can_accept(record.ung_vien, embedding, spelling, margin):
                continue
            winner = record.ung_vien[0]
            code = winner.rxcui
            if winner.tty == "PIN":
                base, _, _ = catalog.pin_base(code)
                code = base.rxcui
            if code == labels[record.khoa_chuan_hoa]:
                correct += 1
            else:
                errors += 1
        accepted = correct + errors
        grid.append(
            {
                "nguong_nhung": embedding,
                "nguong_ky_tu": spelling,
                "chenh_toi_thieu": margin,
                "so_dung": correct,
                "so_sai": errors,
                "so_tu_nhan": accepted,
                "do_dung": correct / accepted if accepted else None,
                "do_phu": accepted / len(labels) if labels else 0.0,
            }
        )
    return grid


def calibrate(root: Path, mode: str, *, dry_run: bool = False) -> Row:
    _, matches, identities, catalog = baseline(root)
    labels = {
        key: identities[match.hoat_chat_id].rxcui
        for key, match in matches.items()
        if match.hoat_chat_id in identities
    }
    summary: Row = {"so_ten_co_nhan": len(labels), "embedder": mode}
    if dry_run:
        return {**summary, "dry_run": True}
    with open_embedder(root, mode) as (embedder, model):
        rankings = list(rank_names(catalog, sorted(labels), embedder, model, hide_exact=True))
    grid = _evaluate_grid(labels, rankings, catalog, load_rules())
    zero_errors = [row for row in grid if not row["so_sai"] and row["so_tu_nhan"]]
    best = max(
        zero_errors,
        key=lambda row: (
            row["so_tu_nhan"],
            row["nguong_nhung"],
            row["nguong_ky_tu"],
            row["chenh_toi_thieu"],
        ),
        default=None,
    )
    summary.update(
        {
            "mo_hinh": model,
            "so_do_co_y_nghia": mode != "fake",
            "de_xuat_0_loi": best,
            "so_cau_hinh": len(grid),
        }
    )
    write_json(root / "kb_reports/T52_hieu_chuan.json", {**summary, "luoi": grid})
    return summary
