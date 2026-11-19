"""Đọc và ghi các tệp dữ liệu của từ điển."""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.kb.fetch.runner import json_bytes

Row = dict[str, Any]


def store(path: Path, content: bytes) -> None:
    """Ghi nguyên tử để lượt chạy sau không đọc phải tệp dở."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temp = Path(handle.name)
        try:
            handle.write(content)
        except BaseException:
            handle.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        # Windows: đích có thể bị giữ chốc lát bởi trình đọc hoặc quét virus.
        for attempt in range(10):
            try:
                temp.replace(path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.2 * (attempt + 1))
    finally:
        temp.unlink(missing_ok=True)


def read_json(path: Path) -> Row:
    return json.loads(path.read_bytes())


def write_json(path: Path, value: object) -> None:
    store(path, json_bytes(value))


def read_jsonl(path: Path) -> list[Row]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: Iterable[Row]) -> None:
    store(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode())
