"""결정론 난수원의 골든 테스트 (TDD §10, R5).

여기서 하는 일은 "난수가 그럴듯한가"가 아니라 "수열이 어제와 똑같은가"다. 이 값들이
바뀌면 저장된 리플레이·데일리 챌린지·골든 던전이 전부 재현되지 않는다. 값을 고치기
전에 그 사실을 먼저 확인할 것.
"""

import pytest

from game.app.core.rng import MASK_64, DeterministicRng, get_label_hash

# 참조 구현(Steele et al., 2014)과 대조한 값이다. seed 0 의 첫 출력
# 0xE220A8397B1DCDAF 가 SplitMix64 의 공개된 기준값과 일치한다.
SEED_0_FIRST_4 = [
    16294208416658607535,
    7960286522194355700,
    487617019471545679,
    17909611376780542444,
]
SEED_12345_FIRST_8 = [
    2454886589211414944,
    3778200017661327597,
    2205171434679333405,
    3248800117070709450,
    9350289611492784363,
    6217189988962137646,
    2262534019502804546,
    7959005890829367068,
]
FNV_OFFSET_BASIS = 14695981039346656037


def test_seed_0_matches_reference_implementation():
    rng = DeterministicRng(0)
    assert [rng.get_uint64() for _ in range(4)] == SEED_0_FIRST_4


def test_golden_sequence_is_stable():
    rng = DeterministicRng(12345)
    assert [rng.get_uint64() for _ in range(8)] == SEED_12345_FIRST_8


def test_same_seed_gives_same_sequence():
    first = DeterministicRng(777)
    second = DeterministicRng(777)
    assert [first.get_uint64() for _ in range(50)] == [second.get_uint64() for _ in range(50)]


def test_different_seeds_diverge():
    first = DeterministicRng(1)
    second = DeterministicRng(2)
    assert first.get_uint64() != second.get_uint64()


def test_reset_replays_from_the_start():
    rng = DeterministicRng(555)
    before = [rng.get_uint64() for _ in range(5)]
    rng.reset()
    assert [rng.get_uint64() for _ in range(5)] == before


def test_seed_property_survives_masking():
    rng = DeterministicRng(-1)
    assert rng.seed == MASK_64


def test_output_stays_in_uint64_range():
    rng = DeterministicRng(31337)
    for _ in range(200):
        value = rng.get_uint64()
        assert 0 <= value <= MASK_64


@pytest.mark.parametrize("bound", [1, 2, 3, 7, 8, 100, 1000])
def test_get_below_stays_in_range(bound):
    rng = DeterministicRng(4242)
    for _ in range(200):
        assert 0 <= rng.get_below(bound) < bound


@pytest.mark.parametrize("bound", [0, -1, -100])
def test_get_below_rejects_non_positive_bound(bound):
    with pytest.raises(ValueError, match="1 이상"):
        DeterministicRng(0).get_below(bound)


def test_get_below_covers_every_value():
    # 편향 검사가 아니라 도달성 검사다. 마스크 후 버리는 방식이 특정 값을 영영
    # 내지 못하는 실수를 잡는다.
    rng = DeterministicRng(9)
    seen = {rng.get_below(6) for _ in range(400)}
    assert seen == {0, 1, 2, 3, 4, 5}


def test_get_range_includes_both_ends():
    rng = DeterministicRng(2024)
    seen = {rng.get_range(1, 6) for _ in range(400)}
    assert seen == {1, 2, 3, 4, 5, 6}


def test_get_range_allows_single_value_span():
    assert DeterministicRng(0).get_range(5, 5) == 5


def test_get_range_rejects_inverted_span():
    with pytest.raises(ValueError, match="high 가 low 보다 작다"):
        DeterministicRng(0).get_range(10, 3)


def test_get_choice_returns_a_member():
    items = ["goblin_rusher", "goblin_archer", "goblin_summoner"]
    rng = DeterministicRng(88)
    for _ in range(100):
        assert rng.get_choice(items) in items


def test_get_choice_rejects_empty_sequence():
    with pytest.raises(ValueError, match="빈 시퀀스"):
        DeterministicRng(0).get_choice([])


def test_create_stream_does_not_advance_parent():
    parent = DeterministicRng(42)
    parent.create_stream("floor:2/node:5/loot")
    assert parent.get_uint64() == DeterministicRng(42).get_uint64()


def test_create_stream_is_reproducible():
    first = DeterministicRng(42).create_stream("floor:2")
    second = DeterministicRng(42).create_stream("floor:2")
    assert [first.get_uint64() for _ in range(10)] == [second.get_uint64() for _ in range(10)]


def test_create_stream_separates_labels():
    loot = DeterministicRng(42).create_stream("floor:2/node:5/loot")
    rooms = DeterministicRng(42).create_stream("floor:2/node:5/rooms")
    assert loot.get_uint64() != rooms.get_uint64()


def test_label_hash_is_process_independent():
    # 파이썬 내장 hash() 였다면 이 값이 실행마다 달라진다. 그것이 이 함수가
    # 따로 있는 이유다.
    assert get_label_hash("") == FNV_OFFSET_BASIS
    assert get_label_hash("floor:2") == 10348716804830686677
