"""Không nạp bí mật từ tệp môi trường khi chạy kiểm thử; bỏ qua test cần dữ liệu cục bộ."""

import os
from pathlib import Path

import pytest

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

_ROOT = Path(__file__).resolve().parents[1]
_TRA_CUU = "data/kb_curated/tra_cuu/tra_cuu.sqlite"
_DDINTER = "data/kb_curated/tuong_tac/ddinter.sqlite"
_CHUNKS = "data/kb_curated/chunks.jsonl"
_NGUON = "data/kb_sources/manifest.json"
_DDINTER_CSV = "data/kb_sources/ddinter/*.csv"
_API_MAU = "data/kb_sources/openfda_api_mau"
_NDC = "data/kb_sources/openfda_ndc"

# Các tệp dưới data/kb_curated, data/kb_sources... không nằm trên git (người dùng tự quản lý).
# Bảng: đường dẫn test (từ thư mục gốc) -> (tên hàm test hoặc None là cả tệp, tệp dữ liệu cần).
_CAN_DU_LIEU: list[tuple[str, frozenset[str] | None, tuple[str, ...]]] = [
    ("tests/api/test_interaction_runtime.py", None, (_TRA_CUU, _DDINTER)),
    ("tests/api/test_routes.py", frozenset({"test_demo02_detail"}), (_TRA_CUU, _DDINTER)),
    (
        "tests/db/test_cli.py",
        frozenset({"test_dry_run_never_connects[kb]", "test_dry_run_never_connects[embeddings]"}),
        (_NGUON, _CHUNKS),
    ),
    (
        "tests/db/test_cli.py",
        frozenset({"test_dry_run_never_connects[ddinter]"}),
        (_NGUON, _DDINTER_CSV),
    ),
    (
        "tests/db/test_loading.py",
        frozenset({"test_ddinter_counts_copy_and_upsert"}),
        (_NGUON, _DDINTER_CSV),
    ),
    (
        "tests/db/test_loading.py",
        frozenset({"test_bad_catalog_row_is_logged_without_aborting_below_limit"}),
        (_NGUON, _CHUNKS),
    ),
    (
        "tests/db/test_mapping.py",
        frozenset({"test_kb_preserves_every_chunk_field_and_renal_values"}),
        (_NGUON, _CHUNKS),
    ),
    ("tests/db/test_reader.py", frozenset({"test_cache_refresh_and_review"}), (_TRA_CUU, _DDINTER)),
    ("tests/kb/test_build.py", frozenset({"test_build_real_meropenem_smoke"}), (_NGUON,)),
    ("tests/kb/test_dictionary_split.py", frozenset({"test_split_real_ndc"}), (_NDC,)),
    (
        "tests/kb/test_names.py",
        frozenset({"test_hoat_chat_json_unique_and_covers_all_manifest_labels"}),
        (_NGUON,),
    ),
    ("tests/kb/test_openfda_fetch.py", None, (_API_MAU,)),
    ("tests/kb/test_openfda_source.py", frozenset({"test_load_real_meropenem_label"}), (_NGUON,)),
    (
        "tests/rules/test_duplicate_resolver.py",
        frozenset({"test_augmentin_and_amoxicillin_use_axis_instead_of_case_codes"}),
        (_TRA_CUU,),
    ),
    ("tests/rules/test_duplicate_runtime.py", None, (_TRA_CUU,)),
]


def _has_data(path: str) -> bool:
    """Kiểm tra đường dẫn tồn tại hoặc mẫu glob có ít nhất một tệp khớp."""
    if "*" in path:
        return any(candidate.is_file() for candidate in _ROOT.glob(path))
    return (_ROOT / path).exists()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Gắn marker can_du_lieu theo bảng trên rồi bỏ qua test nếu thiếu tệp cần."""
    for item in items:
        relative = Path(str(item.path)).resolve().relative_to(_ROOT).as_posix()
        original_name = getattr(item, "originalname", None) or item.name
        for file, names, paths in _CAN_DU_LIEU:
            if relative == file and (names is None or item.name in names or original_name in names):
                item.add_marker(pytest.mark.can_du_lieu(*paths))
        marker = item.get_closest_marker("can_du_lieu")
        if marker is None:
            continue
        missing = [path for path in marker.args if not _has_data(path)]
        if missing:
            reason = f"thiếu {', '.join(missing)}, xem docs/chay-tren-may-moi.md"
            item.add_marker(pytest.mark.skip(reason=reason))
