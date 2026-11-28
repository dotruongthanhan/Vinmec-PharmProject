# T61-fix-2 – Test nhúng không phụ thuộc hồ sơ cấu hình; định dạng

Agent: agy `gemini-4-hydrogen-high`. **Không gọi shell, không gọi mạng.**

## Lỗi (CI GitHub run 44472791553, cả Ubuntu và Windows)

```
FAILED tests/providers/test_gemini_embed.py::test_build_embedder_uses_get_secret_and_selects_provider
AssertionError: assert 'fake' == 'gemini'   (dòng 242)
```

- CI đặt `CDSS_PROFILE=test`. `config/settings.test.yaml` chọn nhà cung cấp nhúng `fake`.
- Test gọi `load_settings()` không truyền hồ sơ, nên trên CI đọc phải cấu hình `test`. Máy Khải không đặt biến này nên ra `dev`.

## Sửa

1. Trong `tests/providers/test_gemini_embed.py`, test phải tự chọn cấu hình nó cần. Hai cách:
   - truyền hồ sơ rõ ràng, `load_settings("dev")`;
   - hoặc dựng `Settings` với `embedding.provider="gemini"` bằng `model_copy`.

   Rà các test khác trong tệp và trong `tests/retrieval/test_embed_corpus.py` có cùng giả định thì sửa luôn.
2. Định dạng lại theo `ruff format`, giữ nguyên logic:
   - `app/retrieval/embed_corpus.py` (khoảng dòng 85);
   - `tests/conftest.py` (khoảng dòng 81).

## Phạm vi

- **Được sửa:** `tests/providers/test_gemini_embed.py`, `tests/retrieval/test_embed_corpus.py`, `app/retrieval/embed_corpus.py` (chỉ định dạng), `tests/conftest.py` (chỉ định dạng), mục "## T61-fix-2" cuối `plan/reports/T61.md`.
- **Cấm:** tệp khác. Riêng `app/rules/**`, `app/kb/resolver/**` đang có task T63 chạy song song.
- Không commit.

## Nghiệm thu (Claude chạy)

Hai lệnh đều phải 0 trượt:

```
CDSS_PROFILE=test uv run pytest -q -p no:cacheprovider tests/providers tests/retrieval
uv run pytest -q -p no:cacheprovider tests/providers tests/retrieval
```

`ruff format --check` các tệp sửa phải qua.
