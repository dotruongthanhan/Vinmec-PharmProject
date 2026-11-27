from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.errors import ProviderError
from app.providers.key_router import KeyRouter


def test_rotation_cooldown_and_recovery() -> None:
    now = [0.0]
    router = KeyRouter(["a", "b", "c"], monotonic=lambda: now[0])
    assert [router.chon()[0] for _ in range(4)] == [1, 2, 3, 1]
    router.bao_ket_qua(2, 429)
    assert [router.chon()[0] for _ in range(2)] == [3, 1]
    now[0] = 60
    assert router.chon()[0] == 2
    router.bao_ket_qua(2, 429, 5)
    now[0] = 65
    assert router.chon()[0] == 3
    router.bao_ket_qua(2, 429)
    now[0] = 964
    assert [router.chon()[0] for _ in range(2)] == [1, 3]
    now[0] = 965
    assert router.chon()[0] == 1
    assert router.chon()[0] == 2


def test_disabled_and_all_resting_do_not_leak() -> None:
    router = KeyRouter(["secret-one", "secret-two"], monotonic=lambda: 0)
    router.bao_ket_qua(1, 403)
    router.bao_ket_qua(2, 429, 5)
    with pytest.raises(ProviderError, match="5 giây") as exc:
        router.chon()
    assert exc.value.retryable
    assert all(
        k not in repr(router) + str(router) + str(exc.value) for k in ["secret-one", "secret-two"]
    )


def test_concurrent_selection() -> None:
    router = KeyRouter(["a", "b", "c"])
    with ThreadPoolExecutor(max_workers=10) as pool:
        values = list(pool.map(lambda _: router.chon()[0], range(100)))
    counts = [values.count(i) for i in (1, 2, 3)]
    assert max(counts) - min(counts) <= 1


def test_wait_for_key_respects_cap_and_deadline() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        now[0] += delay

    router = KeyRouter(["a", "b"], monotonic=lambda: now[0], sleep=sleep)
    for number in (1, 2):
        router.bao_ket_qua(number, 429, 5)
    with pytest.raises(ProviderError):
        router.chon(cho_toi_da_giay=70, han_chot=3)
    assert sleeps == []
    assert router.chon(cho_toi_da_giay=70, han_chot=10)[0] == 1
    assert sleeps == [5]
    for number in (1, 2):
        router.bao_ket_qua(number, 429, 90)
    with pytest.raises(ProviderError):
        router.chon(cho_toi_da_giay=70)
    assert sleeps == [5]
