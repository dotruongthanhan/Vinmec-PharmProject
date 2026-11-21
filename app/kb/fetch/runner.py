"""Chạy tải theo danh mục, giữ manifest và ghi kết quả từng nguồn."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.kb.fetch.client import FDAClient, FetchError, MalformedResponseError
from app.kb.fetch.labels import (
    DrugSpec,
    build_queries,
    build_query,
    label_matches,
    label_rejection_reason,
    ndc_matches,
    ndc_rejection_reason,
    select_label,
)


@dataclass(frozen=True)
class _TieredResult:
    """Kết quả thử truy vấn nhiều bậc cho một nhãn hoặc một thuốc NDC."""

    trang_thai: str
    saved: dict[str, Any] | None
    selected: dict[str, Any]
    so_ung_vien: int
    truy_van: str
    bac_truy_van: int | None = None
    ly_do_loai: list[dict[str, Any]] = field(default_factory=list)


def json_bytes(value: object) -> bytes:
    """Tuần tự hóa JSON xác định với UTF-8 và xuống dòng LF."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_config(path: Path) -> list[DrugSpec]:
    """Đọc cấu hình, từ chối mã hoặc đường dùng trùng/không hợp lệ."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    specs = [DrugSpec.model_validate(entry) for entry in data]
    if len({spec.ma for spec in specs}) != len(specs):
        raise ValueError("Mã hoạt chất bị trùng trong cấu hình")
    for spec in specs:
        if len(set(spec.duong_dung)) != len(spec.duong_dung):
            raise ValueError(f"Đường dùng bị trùng: {spec.ma}")
        if any(
            not route or not all(c.isupper() or c in " ,-" for c in route)
            for route in spec.duong_dung
        ):
            raise ValueError(f"Đường dùng không hợp lệ: {spec.ma}")
    return specs


def label_path(spec: DrugSpec, route: str) -> str:
    """Giữ tên cũ nếu chỉ có một đường dùng."""
    suffix = "" if len(spec.duong_dung) == 1 else "__" + route.lower().replace(" ", "_")
    return f"openfda/{spec.ma}{suffix}.json"


def _ndc_products(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    products: dict[str, dict[str, Any]] = {}
    for record in records:
        raw_ings = record.get("active_ingredients") or []
        raw_routes = record.get("route") or []
        strengths = sorted(
            [
                {"hoat_chat": item.get("name"), "ham_luong": item.get("strength")}
                for item in raw_ings
                if isinstance(item, dict)
            ],
            key=lambda item: json.dumps(item, sort_keys=True),
        )
        row = {
            "ten_biet_duoc": record.get("brand_name"),
            "ten_chung": record.get("generic_name"),
            "ham_luong": strengths,
            "dang_bao_che": record.get("dosage_form"),
            "duong_dung": sorted(
                {str(item) for item in raw_routes if isinstance(item, str) and item.strip()}
            ),
        }
        products[json.dumps(row, sort_keys=True, ensure_ascii=False)] = row
    return [products[key] for key in sorted(products)]


def _fetch_ndc_pages(client: FDAClient, query: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    skip = 0
    expected_total: int | None = None
    while True:
        payload = client.get("ndc", query, limit=100, skip=skip)
        batch = payload["results"]
        if expected_total is None:
            try:
                expected_total = int(
                    payload.get("meta", {}).get("results", {}).get("total", len(batch))
                )
            except (ValueError, TypeError, AttributeError):
                raise MalformedResponseError(
                    "Phản hồi NDC có meta.results.total không hợp lệ"
                ) from None
        if not batch and skip < expected_total:
            raise MalformedResponseError(
                "NDC chưa tải đủ: trang rỗng trước tổng số bản ghi đã biết"
            )
        records.extend(batch)
        skip += len(batch)
        if skip >= expected_total:
            break
        if not batch or skip > 25000:
            raise MalformedResponseError(
                "NDC chưa tải đủ: vượt giới hạn phân trang hoặc trang rỗng"
            )
    return records


def _candidate_label_id(entry: dict[str, Any]) -> str:
    set_id = entry.get("set_id")
    if isinstance(set_id, str) and set_id.strip():
        return set_id.strip()
    meta = entry.get("openfda")
    if isinstance(meta, dict):
        for field_name in ("generic_name", "brand_name"):
            values = meta.get(field_name)
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, str) and item.strip():
                        return item.strip()
    return "khong_ro"


def _fetch_label_tiered(client: FDAClient, spec: DrugSpec, route: str) -> _TieredResult:
    queries = build_queries(spec, route, ndc=False)
    saw_results = False
    total_candidates = 0
    rejected: list[dict[str, Any]] = []
    for tier, query in queries:
        payload = client.get("label", query, limit=25)
        candidates = payload["results"][:25]
        if not candidates:
            continue
        saw_results = True
        total_candidates += len(candidates)
        selected = select_label(candidates, spec, route)
        if selected is not None:
            # Giữ nguyên đối tượng nhãn; chỉ thu results còn nhãn đã chọn.
            saved = {**payload, "results": [selected]}
            return _TieredResult(
                trang_thai="da_lay",
                saved=saved,
                selected=selected,
                so_ung_vien=len(candidates),
                truy_van=query,
                bac_truy_van=tier,
            )
        for cand in candidates:
            if len(rejected) >= 3:
                break
            reason = label_rejection_reason(cand, spec, route) or "không qua quy tắc chọn"
            cand_id = _candidate_label_id(cand)
            rejected.append({"ung_vien": cand_id, "bac": tier, "ly_do": reason})
    status = "khong_co_ung_vien_hop_le" if saw_results else "khong_tim_thay"
    return _TieredResult(
        trang_thai=status,
        saved=None,
        selected={},
        so_ung_vien=total_candidates,
        truy_van=queries[0][1],
        ly_do_loai=rejected,
    )


def _fetch_ndc_tiered(client: FDAClient, spec: DrugSpec) -> _TieredResult:
    queries = build_queries(spec, None, ndc=True)
    saw_results = False
    total_candidates = 0
    rejected: list[dict[str, Any]] = []
    for tier, query in queries:
        records = _fetch_ndc_pages(client, query)
        if not records:
            continue
        saw_results = True
        total_candidates += len(records)
        valid_records = [rec for rec in records if ndc_matches(rec, spec)]
        if valid_records:
            saved = {"san_pham": _ndc_products(valid_records)}
            return _TieredResult(
                trang_thai="da_lay",
                saved=saved,
                selected={},
                so_ung_vien=len(records),
                truy_van=query,
                bac_truy_van=tier,
            )
        for rec in records:
            if len(rejected) >= 3:
                break
            reason = ndc_rejection_reason(rec, spec) or "không qua quy tắc chọn"
            rec_id = str(rec.get("product_ndc") or rec.get("generic_name") or "khong_ro")
            rejected.append({"ung_vien": rec_id, "bac": tier, "ly_do": reason})
    status = "khong_co_ung_vien_hop_le" if saw_results else "khong_tim_thay"
    return _TieredResult(
        trang_thai=status,
        saved=None,
        selected={},
        so_ung_vien=total_candidates,
        truy_van=queries[0][1],
        ly_do_loai=rejected,
    )


def fetch_sources(
    kind: str,
    specs: list[DrugSpec],
    sources_dir: Path,
    client: FDAClient,
    *,
    refresh: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Tải từng mục độc lập; lỗi một mục không dừng cả lượt."""
    manifest_path = sources_dir / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {"tep": []}
    )
    entries = manifest if isinstance(manifest, list) else manifest["tep"]
    outcomes: list[dict[str, Any]] = []
    changed = False
    for spec in specs:
        routes: list[str | None] = list(spec.duong_dung) if kind == "openfda" else [None]
        for route in routes:
            relative = label_path(spec, route) if route else f"openfda_ndc/{spec.ma}.json"
            path = sources_dir / relative
            queries = build_queries(spec, route, ndc=kind == "ndc")
            query = build_query(spec, route, ndc=kind == "ndc")
            row: dict[str, Any] = {
                "ma": spec.ma,
                "duong_dung": route,
                "duong_dan": relative,
                "truy_van": query,
            }
            old = next((entry for entry in entries if entry.get("duong_dan") == relative), None)
            matches = False
            if old and path.is_file() and not refresh:
                raw = path.read_bytes()
                matches = hashlib.sha256(raw).hexdigest() == old.get("sha256")
                if matches and route:
                    try:
                        matches = label_matches(json.loads(raw)["results"][0], spec, route)
                    except (KeyError, IndexError, ValueError, TypeError):
                        matches = False
            if dry_run:
                row["trang_thai"] = "bo_qua" if matches else "se_lay"
                outcomes.append(row)
                continue
            if matches:
                row["trang_thai"] = "bo_qua"
                outcomes.append(row)
                continue
            try:
                if route:
                    result = _fetch_label_tiered(client, spec, route)
                else:
                    result = _fetch_ndc_tiered(client, spec)
                if result.trang_thai == "khong_tim_thay":
                    row["trang_thai"] = "khong_tim_thay"
                    row["so_ung_vien"] = 0
                    row["cac_truy_van"] = [q for _, q in queries]
                    row["ly_do"] = "API trả 404 ở mọi bậc"
                    outcomes.append(row)
                    continue
                if result.trang_thai == "khong_co_ung_vien_hop_le":
                    row["trang_thai"] = "khong_co_ung_vien_hop_le"
                    row["so_ung_vien"] = result.so_ung_vien
                    row["cac_truy_van"] = [q for _, q in queries]
                    row["ly_do_loai"] = result.ly_do_loai
                    row["ly_do"] = "; ".join(
                        f"{item['ung_vien']} (bậc {item['bac']}): {item['ly_do']}"
                        for item in result.ly_do_loai
                    )
                    outcomes.append(row)
                    continue
                assert result.saved is not None and result.bac_truy_van is not None
                raw = json_bytes(result.saved)
                meta = result.selected.get("openfda") or {}
                entry = {
                    "duong_dan": relative,
                    "nguon": "openfda_drug_label" if route else "openfda_ndc",
                    "tang_tin_cay": 3,
                    "giay_phep": "Public domain (FDA)",
                    "ten_goi": spec.ma,
                    "hoat_chat": spec.hoat_chat,
                    "generic_name": meta.get("generic_name") or [spec.hoat_chat],
                    "brand_name": meta.get("brand_name") or [],
                    "set_id": result.selected.get("set_id"),
                    "effective_time": result.selected.get("effective_time"),
                    "phien_ban_nguon": result.selected.get("effective_time"),
                    "duong_dung": [route]
                    if route
                    else sorted({r for p in result.saved["san_pham"] for r in p["duong_dung"]}),
                    "bac_truy_van": result.bac_truy_van,
                    "truy_van": result.truy_van,
                    "url_goc": f"https://api.fda.gov/drug/{'label' if route else 'ndc'}.json",
                    "ngay_lay": datetime.now(UTC).date().isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "kich_thuoc": len(raw),
                    "so_ung_vien": result.so_ung_vien,
                }
                if old and old.get("sha256") == entry["sha256"] and old.get("ngay_lay"):
                    entry["ngay_lay"] = old["ngay_lay"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                if old is not None:
                    entries[entries.index(old)] = entry
                else:
                    entries.append(entry)
                row["trang_thai"] = "da_lay"
                row["truy_van"] = result.truy_van
                row["bac_truy_van"] = result.bac_truy_van
                row["so_ung_vien"] = result.so_ung_vien
                changed = True
            except (MalformedResponseError, ValueError, KeyError, TypeError, AttributeError) as exc:
                row["trang_thai"] = "phan_hoi_sai_cau_truc"
                row["ly_do"] = (
                    str(exc)
                    if isinstance(exc, MalformedResponseError)
                    else f"Dữ liệu không hợp lệ ({type(exc).__name__})"
                )
            except FetchError as exc:
                row["trang_thai"] = "loi_ket_noi"
                row["ly_do"] = str(exc)
            outcomes.append(row)
        if kind == "openfda" and len(spec.duong_dung) > 1 and not dry_run:
            completed = {
                row["duong_dung"]
                for row in outcomes
                if row["ma"] == spec.ma and row["trang_thai"] in {"da_lay", "bo_qua"}
            }
            if completed == set(spec.duong_dung):
                # Giữ tệp gốc cũ trên đĩa, chỉ thôi nạp khi đủ nhãn thay thế.
                legacy_path = f"openfda/{spec.ma}.json"
                legacy = [entry for entry in entries if entry.get("duong_dan") == legacy_path]
                for entry in legacy:
                    entries.remove(entry)
                    changed = True
    if changed:
        entries.sort(key=lambda entry: str(entry.get("duong_dan", "")))
        manifest_path.write_bytes(json_bytes(manifest))
    return outcomes


def run_dictionary_fetch(kind: str, root: Path, *, refresh: bool = False) -> dict[str, Any]:
    """Đồng bộ nguồn riêng của từ điển mà không ghi manifest openFDA."""
    import httpx

    from app.kb.dictionary.axis import Inputs, match_counts, mock_unmatched, resolve_names
    from app.kb.dictionary.http import SourceHTTP
    from app.kb.sources.dav import fetch_dav
    from app.kb.sources.rxnav import RxNav

    with httpx.Client(timeout=30.0, follow_redirects=False) as http:
        if kind == "dav":
            result = fetch_dav(
                SourceHTTP(http, 1.0),
                root / "kb_sources/dav",
                root / "kb_staging/tu_dien/dav_thuoc.jsonl",
                refresh=refresh,
            )
            return {
                key: result[key]
                for key in (
                    "trang_thai",
                    "totalCount",
                    "so_trang",
                    "so_id_duy_nhat",
                    "thoi_gian_giay",
                )
            }
        inputs = Inputs(root)
        source = root / "kb_sources/rxnav"
        rxnav = RxNav(source, SourceHTTP(http, 0.2), refresh=refresh)
        error = None
        try:
            matches, _ = resolve_names(inputs, rxnav)
        except FetchError as exc:
            error = str(exc)
            matches, _ = resolve_names(inputs, RxNav(source))
        if not error and inputs.dav_manifest.get("trang_thai") != "xong":
            error = "Thiếu lượt tải DAV đầy đủ để tra toàn bộ tên"
        counts = {
            "so_ten_tra": len(matches),
            "so_phan_hoi_tra_ten_rxnav": sum(
                "/rxcui.json?" in file["url"] for file in rxnav.files.values()
            ),
            "so_ten_theo_cach_khop": match_counts(matches),
            "hoat_chat_ca_gia_lap_chua_khop": mock_unmatched(inputs, matches),
        }
        status = "chua_xong" if error else "xong"
        rxnav.manifest(status, counts, error=error)
        return {"trang_thai": status, **counts, "loi": error}
