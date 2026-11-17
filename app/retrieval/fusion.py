"""Trộn hạng nghịch đảo với thứ tự hoà điểm ổn định."""


def rrf(rankings: list[list[str]], k: int) -> list[tuple[str, float]]:
    """Cộng điểm mỗi mã một lần trên mỗi danh sách, hạng bắt đầu từ 1."""
    if k < 0:
        raise ValueError("k phải >= 0")
    scores: dict[str, float] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for rank, chunk_id in enumerate(ranking, start=1):
            if chunk_id not in seen:
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
                seen.add(chunk_id)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
