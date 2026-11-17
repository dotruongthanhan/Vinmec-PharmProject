import pytest

from app.retrieval.fusion import rrf


def test_rrf_hand_computed_scores_and_single_list_members() -> None:
    results = rrf([["a", "b", "c"], ["b", "a", "d"]], 60)
    assert [key for key, _ in results] == ["a", "b", "c", "d"]
    assert [score for _, score in results] == pytest.approx(
        [1 / 61 + 1 / 62, 1 / 62 + 1 / 61, 1 / 63, 1 / 63]
    )


def test_rrf_empty_and_first_appearance_ties() -> None:
    assert rrf([], 60) == []
    assert rrf([[], []], 60) == []
    assert rrf([["z"], ["a"]], 60) == [("z", 1 / 61), ("a", 1 / 61)]
