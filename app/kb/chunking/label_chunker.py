"""Bo cat doan tai lieu nhan thuoc openFDA theo cau truc LabelSection."""

from __future__ import annotations

from app.config.settings import ChunkingSettings
from app.core.types import Chunk
from app.kb.chunking.base import (
    BaseChunker,
    build_embedding_text,
    make_chunk_id,
    make_parent_id,
)
from app.kb.names import DrugNameIndex
from app.kb.sources.openfda import LabelDocument, LabelTable


def _format_table_content(table: LabelTable) -> str:
    """Ket xuat bang thanh chuoi giu nguyen tieu de (neu co) va van_ban_phang."""
    if table.tieu_de:
        return f"{table.tieu_de}\n{table.van_ban_phang}"
    return table.van_ban_phang


class LabelChunker(BaseChunker):
    """Tach LabelDocument thanh danh sach Chunk tuan thu Chunker Protocol."""

    def __init__(
        self,
        settings: ChunkingSettings,
        names: DrugNameIndex | None = None,
    ) -> None:
        """Khoi tao LabelChunker voi cau hinh cat doan va chi muc ten thuoc (tuy chon)."""
        super().__init__(settings)
        self._names = names

    def _resolve_active_display(self, doc: LabelDocument) -> list[str]:
        if doc.ten_hoat_chat:
            return list(doc.ten_hoat_chat)
        if self._names is not None and doc.hoat_chat_ids:
            return self._names.inn_names(doc.hoat_chat_ids)
        if doc.hoat_chat_ids:
            return [hid.replace("_", " ") for hid in doc.hoat_chat_ids]
        return [doc.ten_goi.replace("_", " ")]

    def split(self, document: LabelDocument | dict) -> list[Chunk]:
        """Cat mot LabelDocument (hoac dict) thanh danh sach Chunk chuan."""
        doc = (
            document
            if isinstance(document, LabelDocument)
            else LabelDocument.model_validate(document)
        )
        actives = self._resolve_active_display(doc)
        seen_contents: set[str] = set()
        chunks: list[Chunk] = []

        for section in doc.sections:
            muc_cha_id = make_parent_id(doc.tai_lieu_id, section.duong_dan_muc)
            order_idx = 0

            for piece in self.chunk_text(section.van_ban):
                if piece in seen_contents:
                    continue
                seen_contents.add(piece)
                chunks.append(
                    Chunk(
                        doan_trich_id=make_chunk_id(
                            doc.tai_lieu_id,
                            section.duong_dan_muc,
                            order_idx,
                            piece,
                        ),
                        tai_lieu_id=doc.tai_lieu_id,
                        muc_cha_id=muc_cha_id,
                        nhom_nguon="nhan_thuoc",
                        nguon="openfda",
                        tang_tin_cay=3,
                        hoat_chat_ids=list(doc.hoat_chat_ids),
                        muc=section.muc,
                        duong_dan_muc=section.duong_dan_muc,
                        loai_noi_dung="van_ban",
                        ngon_ngu="en",
                        phien_ban_nguon=doc.phien_ban_nguon,
                        url_goc=doc.url_goc,
                        noi_dung_goc=piece,
                        noi_dung_nhung=build_embedding_text(
                            actives,
                            doc.ten_hien_thi,
                            section.duong_dan_muc,
                            piece,
                        ),
                    )
                )
                order_idx += 1

            for table in section.bang:
                table_text = _format_table_content(table)
                if not table_text or table_text in seen_contents:
                    continue
                seen_contents.add(table_text)
                chunks.append(
                    Chunk(
                        doan_trich_id=make_chunk_id(
                            doc.tai_lieu_id,
                            section.duong_dan_muc,
                            order_idx,
                            table_text,
                        ),
                        tai_lieu_id=doc.tai_lieu_id,
                        muc_cha_id=muc_cha_id,
                        nhom_nguon="nhan_thuoc",
                        nguon="openfda",
                        tang_tin_cay=3,
                        hoat_chat_ids=list(doc.hoat_chat_ids),
                        muc=section.muc,
                        duong_dan_muc=section.duong_dan_muc,
                        loai_noi_dung="bang",
                        ngon_ngu="en",
                        phien_ban_nguon=doc.phien_ban_nguon,
                        url_goc=doc.url_goc,
                        noi_dung_goc=table_text,
                        noi_dung_nhung=build_embedding_text(
                            actives,
                            doc.ten_hien_thi,
                            section.duong_dan_muc,
                            table_text,
                        ),
                    )
                )
                order_idx += 1

        return chunks
