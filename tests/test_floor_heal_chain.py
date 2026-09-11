"""층을 넘을 때 돌려주는 회복 (결정 #21).

**이 규칙이 브라우저에만 없었다** (2026-09-11). 파이썬 연쇄는 층을 넘을 때 최대체력의
30% 를 돌려주는데 TS `ChainCursor` 는 인계 HP 를 그대로 썼다 — 같은 티켓이 브라우저에서
더 아픈 판으로 돌았다는 뜻이고, 하강이 깊어질수록 벌어진다 (G3).

**골든이 이 자리를 안 덮는다.** 골든 연쇄는 `rooms_per_floor` 가 0 이라 층 경계가 한
번도 안 생긴다 — 층을 넘는 판이 골든에 하나도 없다.

TS 짝은 `core/services/chainFloorParity.test.ts` 다 — 같은 값을 같은 이름으로 본다.
"""

import pytest

from game.app.progression.floors import read_floor_heal_pct, resolve_floor_heal
from game.app.services.run_battle import load_balance, run_battle
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


def run_chain(parts, rooms=3):
    """층 경계가 있는 연쇄를 돌린다.

    Args:
        parts: 밸런스·카탈로그·방.
        rooms: 돌 방 수.

    Returns:
        방마다 (들어설 때 HP, 끝낼 때 HP, 최대체력).
    """
    seen: list[tuple[int, int, int]] = []

    def run_and_watch(engine):
        player = engine.state.entities["player"]
        opened = player.hp
        result = run_battle(engine)
        seen.append((opened, result.player_hp, player.hp_max))
        return result

    run_room_chain(
        tuple(parts["rooms"]["open_field"] for _ in range(rooms)),
        parts["balance"],
        parts["catalog"],
        None,
        {},
        SEED,
        rooms_per_floor=ROOMS_PER_FLOOR,
        run_room=run_and_watch,
    )
    return seen


def test_the_next_floor_opens_with_the_healed_body(parts):
    """★ 다음 층은 「끝낸 HP + 최대치의 몇 퍼센트」로 연다.

    회복이 있는 이유는 실측이다 — 없을 때 18개 규칙표 중 **아무도 2층을 못 넘었다.**
    회복 수단이 물약 두 개뿐이라 30방을 도는 동안 소진이 벽이 된다.
    """
    heal_pct = read_floor_heal_pct(parts["balance"])
    assert heal_pct > 0, "밸런스에 회복 퍼센트가 없다"
    seen = run_chain(parts)
    assert len(seen) >= 2
    _opened, closed, hp_max = seen[0]
    assert seen[1][0] == resolve_floor_heal(closed, hp_max, heal_pct)


def test_the_heal_never_exceeds_the_maximum():
    """★ 최대치를 안 넘는다."""
    assert resolve_floor_heal(95, 100, 30) == 100


def test_the_heal_floors_the_division():
    """★ 정수 내림이다 — 부동소수를 쓰면 두 코어가 마지막 자리에서 갈린다 (R5)."""
    assert resolve_floor_heal(10, 33, 30) == 19


def test_an_unset_percent_gives_nothing():
    """★ 안 적혀 있으면 0 이다 — **모르면 안 준다.**"""
    assert read_floor_heal_pct({}) == 0
    assert resolve_floor_heal(10, 100, 0) == 10
