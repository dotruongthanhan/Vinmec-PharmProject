"""Mở rộng một đoạn đã trả thành các đoạn cùng mục cha."""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.agent.tools.base import CanCu, KetQuaCongCu, Tool, ToolContext
from app.agent.tools.tim_doan_nguon import NguonDoan, _cat_doan
from app.core.types import Chunk
from app.orchestration.ask import _source_label

_CHUNKS_PATH = Path(__file__).resolve().parents[3] / "data/kb_curated/chunks.jsonl"
_thu_tu: dict[str, int] | None = None
_khoa = Lock()
_MAX_NOI_DUNG = 6000
_GHI_CHU_THU_TU = "(thứ tự đoạn có thể không theo nhãn gốc)"
_DA_CAT = "(đã cắt bớt; chỉ trích phần hiển thị ở trên)"


def _load_order() -> dict[str, int]:
    """Nạp ánh xạ vị trí một lần, dùng chung giữa các lượt."""
    global _thu_tu
    with _khoa:
        if _thu_tu is None:
            mapping: dict[str, int] = {}
            if _CHUNKS_PATH.is_file():
                with _CHUNKS_PATH.open(encoding="utf-8") as stream:
                    for index, line in enumerate(stream):
                        if line.strip():
                            mapping[json.loads(line)["doan_trich_id"]] = index
            _thu_tu = mapping
        return _thu_tu


class ThamSoDocDoanMoRong(BaseModel):
    """Mã đoạn đã được trả trong lượt hiện tại."""

    model_config = ConfigDict(extra="forbid")
    doan_trich_id: Annotated[str, StringConstraints(pattern=r"^DT-[0-9a-f]{12}$", max_length=15)]

    @field_validator("doan_trich_id", mode="before")
    @classmethod
    def normalize_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().strip("[]").strip()
        return value


class DocDoanMoRong(Tool):
    """Đọc các đoạn cùng mục cha với một đoạn đã nhận."""

    ten: ClassVar[str] = "doc_doan_mo_rong"
    ten_hien_thi: ClassVar[str] = "Đọc thêm đoạn nguồn"
    mo_ta: ClassVar[str] = (
        "Mở các đoạn cùng mục cha của đoạn nguồn đã nhận trong lượt này; "
        "truyền doan_trich_id và trích loai=tai_lieu với mã đoạn hiển thị."
    )
    LuocDoThamSo: ClassVar[type[BaseModel]] = ThamSoDocDoanMoRong
    che_do_cho_phep: ClassVar[frozenset[str]] = frozenset({"ca", "chung"})
    chi_doan_da_tra: ClassVar[bool] = True
    so_can_cu_toi_da: ClassVar[int] = 12

    def __init__(self, nguon: NguonDoan | None) -> None:
        self._nguon = nguon

    def chay(
        self, tham_so: BaseModel, ctx: ToolContext, *, doan_goc: Chunk | None = None
    ) -> KetQuaCongCu:
        """Nạp các đoạn liên quan, không nhúng và không gọi mô hình."""
        assert isinstance(tham_so, ThamSoDocDoanMoRong)
        try:
            if doan_goc is None or doan_goc.doan_trich_id != tham_so.doan_trich_id:
                raise ValueError("Thiếu đoạn gốc")
            chunks = [doan_goc]
            if doan_goc.muc_cha_id is not None:
                if self._nguon is None:
                    raise ValueError("Thiếu nguồn")
                items = self._nguon.ingredient_items(set(doan_goc.hoat_chat_ids))
                by_id = {
                    c.doan_trich_id: c
                    for c, _ in items
                    if c.tai_lieu_id == doan_goc.tai_lieu_id and c.muc_cha_id == doan_goc.muc_cha_id
                }
                by_id[doan_goc.doan_trich_id] = doan_goc
                chunks = list(by_id.values())
            order = _load_order()
            fallback = any(c.doan_trich_id not in order for c in chunks)
            chunks.sort(key=lambda c: c.doan_trich_id if fallback else order[c.doan_trich_id])
            return self._render(chunks, doan_goc, fallback)
        except Exception:
            return KetQuaCongCu(
                trang_thai="loi", ma_loi="loi_cong_cu", noi_dung="Không đọc được đoạn nguồn."
            )

    @staticmethod
    def _render(chunks: list[Chunk], goc: Chunk, fallback: bool) -> KetQuaCongCu:
        header = (
            f"Nguồn: {_source_label(goc.nguon)} · {goc.duong_dan_muc} · "
            f"tầng tin cậy: {goc.tang_tin_cay} · {len(chunks)} đoạn"
        )
        if fallback:
            header += "\n" + _GHI_CHU_THU_TU
        index = next(i for i, c in enumerate(chunks) if c.doan_trich_id == goc.doan_trich_id)
        priority = [index]
        for distance in range(1, len(chunks)):
            priority.extend(i for i in (index + distance, index - distance) if 0 <= i < len(chunks))
        selected: dict[int, str] = {}

        def render() -> str:
            blocks = [header, *(selected[i] for i in sorted(selected))]
            missing = len(chunks) - len(selected)
            if missing:
                blocks.append(f"(mục còn {missing} đoạn chưa hiển thị)")
            return "\n\n".join(blocks)

        for i in priority:
            if len(selected) >= 12:
                break
            c = chunks[i]
            prefix = f"[doan_trich_id: {c.doan_trich_id}]\n"
            text = " ".join(c.noi_dung_goc.split())
            selected[i] = prefix + text
            if len(render()) > _MAX_NOI_DUNG:
                if i != index:
                    del selected[i]
                    continue
                selected[i] = prefix + "\n" + _DA_CAT
                available = max(0, _MAX_NOI_DUNG - len(render()))
                cut, _ = _cat_doan(text, available)
                if not cut and available:
                    cut = text[:available]
                selected[i] = prefix + cut + "\n" + _DA_CAT

        can_cu = [
            CanCu(
                loai="doan",
                ma=chunks[i].doan_trich_id,
                nhan=f"{_source_label(chunks[i].nguon)} · {chunks[i].duong_dan_muc}",
                doan=chunks[i],
            )
            for i in sorted(selected)
        ]
        return KetQuaCongCu(
            trang_thai="ok",
            noi_dung=render(),
            can_cu=can_cu,
            chi_tiet_tien_trinh=f"1 mục, {len(can_cu)} đoạn",
        )
