"""1장이 신규에게 들어갈 자리를 남기는가 (결정 #35 의 네 번째 축).

`monsters/growth` 머리글은 「저층 몬스터가 무한히 크면 **신규 플레이어가 들어갈 자리가
없다**」고 적고, 층 격리·레벨 상한·처치 감쇠·성장률 체감 넷으로 막는다고 했다. 그런데
**그 넷으로는 안 됐다** (2026-09-16 실측).

1장 상한은 5 이고, 레벨 5 몬스터는 레벨 1 플레이어에게 스탯 +24% 에 규칙칸 +1, cpu +2
인 상대다. 게다가 지속 몬스터는 플레이어를 이기면 레벨이 오른다 — **신규가 1장에서
죽을수록 1장이 더 세지는 되먹임**이라, 상한이 있어도 시간이 갈수록 신규가 못 들어온다.

그래서 축을 하나 더 걸었다: 1장에서는 **방문자 레벨 근처로 눌러서** 만난다. 저장된
레벨은 안 건드리므로 성장·처치 감쇠·도감이 전부 하던 대로 돈다.
"""

from game.app.monsters.growth import (
    NEWCOMER_FLOOR,
    NEWCOMER_LEVEL_HEADROOM,
    get_level_cap,
    resolve_effective_level,
)


def test_a_newcomer_meets_a_level_within_reach() -> None:
    """레벨 1 이 1장 상한짜리를 만나도 반 걸음 앞까지만 만난다."""
    cap = get_level_cap(NEWCOMER_FLOOR)
    met = resolve_effective_level(cap, NEWCOMER_FLOOR, 1)
    assert met == 1 + NEWCOMER_LEVEL_HEADROOM
    # 누르지 않으면 이것을 만났다. 눌린 쪽이 실제로 더 낮아야 한다 — 같으면 축이 없는 것이다.
    assert met < cap


def test_the_damping_lifts_as_the_player_grows() -> None:
    """플레이어가 크면 눌림이 저절로 풀린다 — 「초반에만」이 자동으로 성립한다."""
    cap = get_level_cap(NEWCOMER_FLOOR)
    met = [resolve_effective_level(cap, NEWCOMER_FLOOR, level) for level in range(1, 8)]
    # 단조 증가하다가 상한에서 멈춘다.
    assert met == sorted(met)
    assert met[-1] == cap


def test_the_stored_level_is_never_raised() -> None:
    """약한 개체를 센 플레이어에 맞춰 올리지 않는다 — 누르기지 맞추기가 아니다."""
    assert resolve_effective_level(1, NEWCOMER_FLOOR, 9) == 1


def test_deeper_floors_keep_their_teeth() -> None:
    """깊은 층은 안 누른다 — 「준비하고 오는 곳」이라는 뜻이 남아야 한다."""
    for floor in (NEWCOMER_FLOOR + 1, 5, 10):
        assert resolve_effective_level(get_level_cap(floor), floor, 1) == get_level_cap(floor)


def test_an_unknown_visitor_gets_the_world_as_it_is() -> None:
    """방문자를 모르면 안 누른다.

    **모를 때 눌러 주면 그것이 빠져나갈 구멍이 된다.** 레벨을 안 싣는 경로가 생기는
    순간 그 경로가 가장 쉬운 길이 된다.
    """
    assert resolve_effective_level(5, NEWCOMER_FLOOR, None) == 5


def test_the_floor_never_drops_below_the_first_level() -> None:
    """0 레벨 몬스터는 없다."""
    assert resolve_effective_level(3, NEWCOMER_FLOOR, 0) >= 1
    assert resolve_effective_level(3, NEWCOMER_FLOOR, -5) >= 1
