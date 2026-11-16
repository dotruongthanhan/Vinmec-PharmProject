"""Ghép BM25 và véc-tơ, xếp hạng lại và xử lý đường lui."""

from typing import Literal

from pydantic import BaseModel

from app.core.errors import ProviderError
from app.core.interfaces import Embedder, KeywordIndex, Reranker, VectorStore
from app.core.types import Chunk, RetrievalQuery, ScoredChunk
from app.retrieval.fusion import rrf


class RetrievalOutcome(BaseModel):
    """Kết quả cùng chế độ thực tế và cảnh báo."""

    ket_qua: list[ScoredChunk]
    che_do: Literal["lai", "tu_khoa"]
    canh_bao: list[str]


class HybridRetriever:
    """Tiêm bốn phụ thuộc để truy xuất và xếp hạng nguồn."""

    def __init__(
        self,
        embedder: Embedder,
        reranker: Reranker,
        vector_store: VectorStore,
        keyword_index: KeywordIndex,
        rrf_k: int,
        rerank_min_score: float,
    ) -> None:
        self.embedder = embedder
        self.reranker = reranker
        self.vector_store = vector_store
        self.keyword_index = keyword_index
        self.rrf_k = rrf_k
        self.rerank_min_score = rerank_min_score
        self.canh_bao: list[str] = []

    def retrieve(self, query: RetrievalQuery) -> list[ScoredChunk]:
        """Trả danh sách theo giao diện Retriever."""
        return self.retrieve_detailed(query).ket_qua

    def retrieve_detailed(self, query: RetrievalQuery) -> RetrievalOutcome:
        """Lọc cùng điều kiện, trộn hạng và không để lỗi nhà cung cấp thoát ra."""
        warnings = list(self.canh_bao)
        mode: Literal["lai", "tu_khoa"] = "lai"
        chunks: dict[str, Chunk] = {}
        keyword_rankings: list[list[str]] = []
        vector_rankings: list[list[str]] = []

        def record(results: list[ScoredChunk]) -> list[str]:
            for result in results:
                chunks[result.chunk.doan_trich_id] = result.chunk
            return [result.chunk.doan_trich_id for result in results]

        for text in query.van_ban:
            keyword_rankings.append(
                record(self.keyword_index.search(text, query.k_query, query.bo_loc))
            )
        try:
            for text in query.van_ban:
                vector = self.embedder.embed_query(text)
                vector_rankings.append(
                    record(self.vector_store.search(vector, query.k_query, query.bo_loc))
                )
        except ProviderError:
            vector_rankings = []
            mode = "tu_khoa"
            warnings.append("Nhúng lỗi; đang chạy chế độ từ khoá.")
        rankings = []
        for index, keyword_ranking in enumerate(keyword_rankings):
            rankings.append(keyword_ranking)
            if vector_rankings:
                rankings.append(vector_rankings[index])
        fused = rrf(rankings, self.rrf_k)[: max(0, query.k_query)]
        candidates = [chunks[chunk_id] for chunk_id, _ in fused]
        results: list[ScoredChunk] = []
        if candidates and query.k_rerank > 0:
            try:
                ranked = self.reranker.rerank(
                    query.van_ban[0],
                    [chunk.noi_dung_nhung for chunk in candidates],
                    query.k_rerank,
                )
            except ProviderError:
                mode = "tu_khoa"
                warnings.append("Xếp hạng lại lỗi; dùng thứ tự RRF, bỏ qua ngưỡng điểm.")
                results = [
                    ScoredChunk(chunk=chunks[chunk_id], diem=score, nguon_diem="rrf")
                    for chunk_id, score in fused[: query.k_rerank]
                ]
            else:
                ranked = sorted(ranked, key=lambda item: item[1], reverse=True)[: query.k_rerank]
                results = [
                    ScoredChunk(chunk=candidates[index], diem=score, nguon_diem="xep_hang_lai")
                    for index, score in ranked
                    if score >= self.rerank_min_score
                ]
                results.sort(key=lambda item: item.chunk.tang_tin_cay)
        return RetrievalOutcome(ket_qua=results, che_do=mode, canh_bao=warnings)
