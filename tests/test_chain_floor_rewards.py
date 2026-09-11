"""층 경계에서 일어나는 두 가지 — 회복과 보상 (결정 #21, GDD §2.2).

**둘 다 골든이 안 덮는다.** 골든 연쇄는 `rooms_per_floor` 가 0 이라 층 경계가 한 번도
안 생긴다 — 층을 넘는 판은 골든에 없다. 그래서 TS 쪽에 층 회복이 **통째로 빠져 있는
것을 아무도 못 봤다** (2026-09-11): 파이썬은 층을 넘을 때 최대체력의 30% 를 돌려주는데
브라우저는 인계 HP 를 그대로 썼다. 같은 티켓이 브라우저에서 더 아픈 판으로 돌았다.

TS 짝은 `core/services/chainFloorParity.test.ts` 다 — 같은 값을 같은 이름으로 본다.
"""

import pytest

from game.app.services.run_battle import load_balance
from game.app.services.run_chain import run_room_chain
from game.config import BALANCE_PATH, BLOCKS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates

SEED = 4242
# 방 하나가 곧 한 층이다. 층 경계를 매 방 만들어야 이 시험이 볼 것이 생긴다.
ROOMS_PER_FLOOR = 1


@pytest.fixture(scope="module")
def parts():
    templates = {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}
    return {
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "rooms": templates,
    }


def run_chain(parts, rewards=None, rooms=3):
    """층 경계가 있는 연쇄를 돌린다.

    Args:
        parts: 밸런스·카탈로그·방.
        rewards: 고른 층 보상.
        rooms: 돌 방 수.

    Returns:
        (연쇄 결과, 방마다의 플레이어 상태).
    """
    seen: list[dict] = []

    def run_and_watch(engine):
        from game.app.services.run_battle import run_battle

        player = engine.state.entities["player"]
        seen.append(
            {
                "hp": player.hp,
                "hp_max": player.hp_max,
                "attack": player.attack,
                "cpu_budget": player.cpu_budget,
            }
        )
        return run_battle(engine)

    result = run_room_chain(
        tuple(parts["rooms"]["open_field"] for _ in range(rooms)),
        parts["balance"],
        parts["catalog"],
        None,
        {},
        SEED,
        rooms_per_floor=ROOMS_PER_FLOOR,
        rewards=rewards,
        run_room=run_and_watch,
    )
    return result, seen


def test_the_floor_heal_lands_between_floors(parts):
    """★ **층을 넘으면 돌려준다** (결정 #21).

    없을 때 18개 규칙표 중 아무도 2층을 못 넘었다 — 회복 수단이 물약뿐이라 30방을 도는
    동안 소진이 벽이 된다.
    """
    result, seen = run_chain(parts)
    # 이기든 지든 상관없다 — 두 방을 돌았으면 층 경계가 한 번 생긴 것이다.
    assert len(seen) >= 2
    # 2층에 들어설 때의 HP 는 1층을 끝낸 HP 보다 높거나, 이미 만피였다.
    first_end = result.per_room[0].player_hp
    assert seen[1]["hp"] > first_end or seen[1]["hp"] == seen[1]["hp_max"]


def test_a_reward_lands_from_the_next_floor(parts):
    """★ **고른 층에는 소급되지 않는다.** 같은 층에 얹히면 이미 끝난 판이 다시 돈다."""
    _, plain = run_chain(parts)
    _, boosted = run_chain(parts, rewards={1: "affix_attack"})
    assert boosted[0]["attack"] == plain[0]["attack"], "고른 층에 소급됐다"
    assert boosted[1]["attack"] == plain[1]["attack"] + 2


def test_vitality_raises_the_carried_body_too(parts):
    """★ 최대치만 늘리면 고른 그 순간에는 아무 일도 안 일어난다."""
    _, plain = run_chain(parts)
    _, boosted = run_chain(parts, rewards={1: "affix_vitality"})
    assert boosted[1]["hp_max"] == plain[1]["hp_max"] + 10
    assert boosted[1]["hp"] > plain[1]["hp"]


def test_a_core_reward_widens_the_budget_in_battle(parts):
    """★ CPU 는 규칙표의 한도이자 **개체의 값**이다 — 전투에도 실려야 한다."""
    _, plain = run_chain(parts)
    _, boosted = run_chain(parts, rewards={1: "module_core"})
    assert boosted[1]["cpu_budget"] == plain[1]["cpu_budget"] + 3
