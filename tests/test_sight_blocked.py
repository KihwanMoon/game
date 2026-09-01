"""시야에 막힌 원거리 공격 (GDD §4.1, 결정 #04).

**캐릭터가 굳어 서 있던 자리다.** 사거리 안에 있는데 엄폐물이 시야를 끊으면, 공격은
「시야 없음 — 틱 낭비」로 끝나고 **조건은 다음 틱에도 참이다.** 같은 규칙이 영원히 다시
뽑히고, 플레이어는 자기 캐릭터가 적을 마주 보고 아무것도 안 하는 것을 본다.

고침은 새 문법이 아니다. **소모품이 없을 때와 같은 자리에서 「불가」로 막는다** — 조건은
참인데 수단이 없다. 그러면 다음 규칙이 기회를 얻고, 없으면 기본 행동이 돈다.

규칙 상태 4종(참·발동 / 참·미발동 / 불가 / 거짓) 중 세 번째다.
"""

from game.app.core.rng import DeterministicRng
from game.app.grid.vision import VisionGrid, check_line_of_sight
from game.app.rules.rule_vm import check_sight_blocked
from game.app.simulation.state import Entity, WorldState
from game.config import ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

ROOMS = {template.template_id: template for template in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_pair(room_id, origin, spot, attack_range):
    """한 방에 둘을 세운다.

    Args:
        room_id: 방 id.
        origin: 공격자 자리.
        spot: 대상 자리.
        attack_range: 공격자의 사거리.

    Returns:
        (세계, 공격자, 대상).
    """
    state = WorldState(room=ROOMS[room_id], rng=DeterministicRng(1))
    actor = Entity(
        entity_id="player",
        kind_id="player",
        faction="player",
        position=origin,
        hp=100,
        hp_max=100,
        attack=10,
        defense=0,
        attack_range=attack_range,
        initiative=50,
    )
    target = Entity(
        entity_id="e1",
        kind_id="goblin_rusher",
        faction="enemy",
        position=spot,
        hp=40,
        hp_max=40,
        attack=8,
        defense=0,
        attack_range=1,
        initiative=60,
    )
    state.entities["player"] = actor
    state.entities["e1"] = target
    return state, actor, target


def find_blocked_pair():
    """엄폐물이 사이를 막는 두 자리를 찾는다.

    Returns:
        (방 id, 공격자 자리, 대상 자리). 사거리 안이면서 시야가 막힌 짝이다.
    """
    room = ROOMS["pillars"]
    grid = VisionGrid(WorldState(room=room, rng=DeterministicRng(1)), room.width, room.height)
    spots = [
        (x, y) for y in range(room.height) for x in range(room.width) if room.get_tile(x, y) in {0}
    ]
    for origin in spots:
        for spot in spots:
            gap = abs(origin[0] - spot[0]) + abs(origin[1] - spot[1])
            if 2 <= gap <= 4 and not check_line_of_sight(grid, origin, spot):
                return "pillars", origin, spot
    raise AssertionError("엄폐물이 시야를 끊는 짝이 없다 — 방 배치가 바뀌었다")


def test_a_ranged_attack_without_sight_is_blocked():
    """★ 사거리 안이어도 시야가 막히면 「불가」다 — 안 막으면 그 자리에서 굳는다."""
    room_id, origin, spot = find_blocked_pair()
    state, actor, target = build_pair(room_id, origin, spot, attack_range=5)
    assert check_sight_blocked("ATTACK", actor, target, state)


def test_a_melee_attack_never_asks_about_sight():
    """★ 근접에 시야를 물으면 벽 모서리에서 근접 공격이 안 나간다.

    인접한 칸에 「보이는가」를 묻는 것은 뜻이 없다.
    """
    room_id, origin, spot = find_blocked_pair()
    state, actor, target = build_pair(room_id, origin, spot, attack_range=1)
    assert not check_sight_blocked("ATTACK", actor, target, state)


def test_a_clear_line_is_not_blocked():
    """★ 뚫린 시야까지 막으면 원거리가 아무것도 못 한다."""
    state, actor, target = build_pair("open_field", (1, 4), (5, 4), attack_range=5)
    assert not check_sight_blocked("ATTACK", actor, target, state)


def test_only_attacks_are_gated():
    """★ 이동·대기까지 막으면 시야가 없을 때 다가갈 방법이 사라진다."""
    room_id, origin, spot = find_blocked_pair()
    state, actor, target = build_pair(room_id, origin, spot, attack_range=5)
    assert not check_sight_blocked("MOVE_TO", actor, target, state)
    assert not check_sight_blocked("HOLD", actor, target, state)


def test_no_target_is_not_blocked():
    """★ 대상이 없는 것은 「거짓」이지 「불가」가 아니다 — 둘을 섞으면 로그가 거짓말한다."""
    room_id, origin, spot = find_blocked_pair()
    state, actor, _target = build_pair(room_id, origin, spot, attack_range=5)
    assert not check_sight_blocked("ATTACK", actor, None, state)
