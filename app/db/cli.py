"""Lệnh dựng, nạp và kiểm; dry-run không đọc bí mật và không mở kết nối."""

import argparse
import sys
from pathlib import Path

import psycopg

from app.config.settings import get_secret, load_settings
from app.core.errors import ConfigError
from app.db import engine
from app.db.mapping import ACTIVE_DRUG_VIEW, SCHEMAS, TABLES
from app.db.sources import (
    Batch,
    SourceError,
    prepare,
    prepare_administrative,
    prepare_treatment_sheets,
    read_embeddings,
)

ROOT = Path(__file__).resolve().parents[2]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Lược đồ và nạp dữ liệu giả lập vào PostgreSQL")
    commands = result.add_subparsers(dest="command", required=True)
    for command in ("check", "schema", "verify"):
        commands.add_parser(command)
    administrative = commands.add_parser("hanh-chinh")
    administrative.add_argument("--dry-run", action="store_true")
    sheets = commands.add_parser("phieu-dieu-tri")
    sheets.add_argument("--dry-run", action="store_true")
    reset = commands.add_parser("reset")
    reset.add_argument("--yes", action="store_true")
    load = commands.add_parser("load")
    load.add_argument("group", choices=("cases", "kb", "ddinter", "embeddings"))
    load.add_argument("--dry-run", action="store_true")
    load.add_argument("--replace", action="store_true")
    all_command = commands.add_parser("all")
    all_command.add_argument("--dry-run", action="store_true")
    all_command.add_argument("--reset", action="store_true")
    all_command.add_argument("--yes", action="store_true")
    return result


def report(batches: list[Batch]) -> None:
    counts = engine.expected_counts(batches)
    active = set().union(*(batch.tables for batch in batches))
    print("Số dòng sẽ nạp (sau gộp khoá trùng):")
    for name in TABLES:
        if name in active:
            print(f"{name}: {counts[name]}")
    if "nghiep_vu.y_lenh" in active:
        print(f"{ACTIVE_DRUG_VIEW}: {counts[ACTIVE_DRUG_VIEW]} (view, không nạp trực tiếp)")
    print(f"Tổng dòng bị loại: {sum(len(batch.rejected) for batch in batches)}")
    outside: dict[str, set[str]] = {}
    for batch in batches:
        for code, aliases in batch.outside_kb.items():
            outside.setdefault(code, set()).update(aliases)
    for code, aliases in sorted(outside.items()):
        print(f"Ngoài KB, can_duyet=true: {code} ({', '.join(sorted(aliases))})")
    for batch in batches:
        for name in sorted(batch.tables):
            raw = batch.source_counts[name]
            unique = len(batch.rows[name])
            if raw != unique:
                print(f"{name}: đọc={raw}, sẽ nạp={unique}")
        for error in batch.rejected:
            print(f"LOẠI {error.bang} {error.nguon_tep}:{error.dong}: {error.ly_do}")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    reset = args.command == "reset" or bool(getattr(args, "reset", False))
    if reset and not args.yes:
        print(
            "Từ chối: cần --yes. Sẽ xoá toàn bộ bảng và dữ liệu trong "
            + ", ".join(SCHEMAS)
            + " (CASCADE)."
        )
        return 2
    try:
        if args.command == "phieu-dieu-tri":
            batch = prepare_treatment_sheets(ROOT)
            report([batch])
            if batch.rejected:
                raise SourceError("Có dòng nguồn bị loại; dừng trước kết nối")
            if args.dry_run:
                print("DRY-RUN: không kết nối cơ sở dữ liệu.")
                return 0
            settings = load_settings()
            url = get_secret(settings.database.url_env)
            with psycopg.connect(url, connect_timeout=10, autocommit=True) as connection:
                engine.load_treatment_sheets(connection, batch)
            return 0
        if args.command == "hanh-chinh":
            batch = prepare_administrative(ROOT)
            report([batch])
            if batch.rejected:
                raise SourceError("Có dòng hành chính bị loại; dừng trước kết nối")
            if args.dry_run:
                print("DRY-RUN: không kết nối cơ sở dữ liệu.")
                return 0
            settings = load_settings()
            url = get_secret(settings.database.url_env)
            with psycopg.connect(url, connect_timeout=10, autocommit=True) as connection:
                engine.load_administrative(connection, batch)
            return 0
        settings = load_settings()
        batches: list[Batch] = []
        embeddings = None
        if args.command in ("all", "verify"):
            batches = [prepare(group, ROOT) for group in ("cases", "kb", "ddinter")]
        elif args.command == "load":
            batches = [prepare("kb" if args.group == "embeddings" else args.group, ROOT)]
        if args.command in ("all", "verify") or (
            args.command == "load" and args.group == "embeddings"
        ):
            kb = next(batch for batch in batches if "tri_thuc.doan_trich" in batch.tables)
            embeddings = read_embeddings(
                kb.rows["tri_thuc.doan_trich"],
                ROOT / settings.embedding.cache_path,
                settings.embedding.active,
            )
        if batches:
            if args.command != "verify":
                report(
                    batches if not (args.command == "load" and args.group == "embeddings") else []
                )
            for batch in batches:
                batch.finish(ROOT / "data/runtime/nap_loi.jsonl")
        if embeddings is not None:
            for error in embeddings.rejected:
                print(f"LOẠI {error.bang} {error.dong}: {error.ly_do}")
            embeddings.finish(ROOT / "data/runtime/nap_loi.jsonl")
            print(
                f"Embedding từ bộ đệm: có={len(embeddings.vectors)}, chưa có={embeddings.missing}"
            )
        if getattr(args, "dry_run", False):
            print("DRY-RUN: không kết nối cơ sở dữ liệu.")
            return 0
        url = get_secret(settings.database.url_env)
        readonly = args.command in ("check", "verify")
        options = {"options": "-c default_transaction_read_only=on"} if readonly else {}
        with psycopg.connect(url, connect_timeout=10, autocommit=True, **options) as connection:
            if args.command == "check":
                engine.check(connection)
            elif args.command in ("schema", "reset"):
                engine.apply_schema(connection, ROOT, reset)
            elif args.command == "load":
                if args.group == "embeddings":
                    engine.load_embeddings(connection, embeddings, args.replace)
                else:
                    engine.load_batch(connection, batches[0], args.group, args.replace)
            elif args.command == "all":
                engine.apply_schema(connection, ROOT, reset)
                for group, batch in zip(("cases", "kb", "ddinter"), batches, strict=True):
                    engine.load_batch(connection, batch, group)
                engine.load_embeddings(connection, embeddings)
                return (
                    0
                    if engine.verify(connection, engine.expected_counts(batches), embeddings)
                    else 1
                )
            elif args.command == "verify":
                return (
                    0
                    if engine.verify(connection, engine.expected_counts(batches), embeddings)
                    else 1
                )
        return 0
    except (SourceError, ConfigError) as exc:
        print(f"Lỗi: {exc}")
        return 1
    except Exception as exc:
        # Không đưa str(exc), repr(exc), traceback hay DSN vào thông báo.
        print(f"Loi co so du lieu; may chu=***; loai={type(exc).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
