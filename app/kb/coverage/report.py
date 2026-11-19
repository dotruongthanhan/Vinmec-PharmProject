"""Tính ma trận và tóm tắt hoàn toàn trên dữ liệu đã nạp."""

from collections import Counter, defaultdict
from collections.abc import Sequence

from app.kb.coverage.models import (
    DEFAULT_REQUIRED,
    SOURCE_COLUMNS,
    CaseCoverage,
    CoverageData,
    CoverageRow,
    CoverageSummary,
    IngredientGap,
)
from app.kb.names import normalize_key, strip_salt


def validate_required_sources(sources: Sequence[str]) -> list[str]:
    """Kiểm tên nguồn, giữ thứ tự và loại nguồn lặp."""
    unknown = set(sources) - SOURCE_COLUMNS.keys()
    if unknown:
        raise ValueError("nguon bat buoc khong hop le: " + ", ".join(sorted(unknown)))
    return list(dict.fromkeys(sources))


def calculate_coverage(
    data: CoverageData, *, required_sources: Sequence[str] = DEFAULT_REQUIRED
) -> tuple[list[CoverageRow], CoverageSummary]:
    """Đếm liên kết theo hoạt chất; không đọc tệp hoặc thay đổi đầu vào."""
    required = validate_required_sources(required_sources)
    chunks: Counter[str] = Counter()
    labels: dict[str, set[str]] = defaultdict(set)
    for chunk in data.doan_nhan:
        if chunk.nguon != "openfda":
            continue
        set_id = chunk.tai_lieu_id.removeprefix("openfda:")
        for identifier in set(chunk.hoat_chat_ids):
            chunks[identifier] += 1
            if set_id:
                labels[identifier].add(set_id)

    ndc_names = {key for name in data.ten_ndc for key in (normalize_key(name), strip_salt(name))}
    catalogs = {
        source: None if names is None else {normalize_key(name) for name in names}
        for source, names in (("livertox", data.ten_livertox), ("lactmed", data.ten_lactmed))
    }
    rows: list[CoverageRow] = []
    for ingredient in sorted(data.hoat_chat, key=lambda item: item.hoat_chat_id):
        identifier = ingredient.hoat_chat_id
        ddinter_id = ingredient.ddinter_id
        expected = data.tong_ddinter.get(ddinter_id) if ddinter_id else None
        complete = (
            data.so_dong_ddinter.get(ddinter_id, 0) == expected
            if ddinter_id and expected is not None
            else None
        )
        name = normalize_key(ingredient.ten_inn)
        optional = {
            f"co_{source}": None if names is None else name in names
            for source, names in catalogs.items()
        }
        row = CoverageRow(
            **ingredient.model_dump(exclude={"rxcui"}),
            co_rxcui=bool(ingredient.rxcui),
            ddinter_da_cao_du=complete,
            so_doan_nhan_fda=chunks[identifier],
            set_id_nhan_fda=sorted(labels[identifier]),
            co_ndc=bool(name) and name in ndc_names,
            **optional,
        )
        row.thieu = [source for source in required if not getattr(row, SOURCE_COLUMNS[source])]
        rows.append(row)

    case_rows = [row for row in rows if row.trong_ca_gia_lap]
    summary = CoverageSummary(
        so_hoat_chat=len(rows),
        nguon_bat_buoc=required,
        theo_cot={
            column: sum(bool(getattr(row, column)) for row in rows)
            for column in CoverageRow.model_fields
        },
        tong_so_che_pham_dav=sum(row.so_che_pham_dav for row in rows),
        tong_so_doan_nhan_fda=sum(row.so_doan_nhan_fda for row in rows),
        so_du_nguon_bat_buoc=sum(not row.thieu for row in rows),
        thieu_theo_nguon={source: sum(source in row.thieu for row in rows) for source in required},
        trang_thai_nguon={
            source: "chưa có nguồn" if names is None else "đã có nguồn"
            for source, names in catalogs.items()
        },
        trong_ca_gia_lap=CaseCoverage(
            so_hoat_chat=len(case_rows),
            so_du_nguon_bat_buoc=sum(not row.thieu for row in case_rows),
            thieu_theo_nguon={
                source: sum(source in row.thieu for row in case_rows) for source in required
            },
            hoat_chat_thieu=[
                IngredientGap(hoat_chat_id=row.hoat_chat_id, ten_inn=row.ten_inn, thieu=row.thieu)
                for row in case_rows
                if row.thieu
            ],
        ),
    )
    return rows, summary
