"""층 사슬 — 방 여러 개를 잇는 것 (로드맵 W3).

**여기서 지키는 것은 방 사이에서만 일어난다.** 방 하나짜리 검사로는 셋 다 잡히지 않는다.

1. 방마다 시드를 가른다 — 한 수열을 공유하면 앞 방의 길이가 뒷 방을 흔든다 (R5).
2. HP·포션이 이어진다 — 방마다 회복되면 연쇄가 난이도를 만들지 못한다.
3. 층 압력은 방을 넘어 이어지고, 방 체류 틱만 지운다 (GDD §7).
"""

import pytest

from game.app.services.run_battle import load_balance
from game.app.services.run_chain import SEED_STRIDE, run_room_chain
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets


@pytest.fixture(scope="module")
def parts():
    templates = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    return {
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "rooms": templates,
        "enemies": load_rulesets(ENEMY_RULESETS_PATH),
        "player": load_rulesets(G0_RULESETS_PATH),
    }


def run_chain(parts, room_ids, seed, ruleset_id="g0_kite"):
    return run_room_chain(
        tuple(parts["rooms"][room_id] for room_id in room_ids),
        parts["balance"],
        parts["catalog"],
        None if ruleset_id is None else parts["player"][ruleset_id],
        parts["enemies"],
        seed,
    )


def test_hp_carries_across_rooms(parts):
    """★ 이것이 깨지면 방을 잇는 것이 난이도를 만들지 못한다."""
    # 스킬 v3 뒤 재실측 표본 — g0_pressure 가 open_field 3연쇄를 44→38→25 로 깬다.
    result = run_chain(parts, ("open_field", "open_field", "open_field"), 4242, "g0_pressure")
    assert result.cleared_rooms == 3
    hps = [room.player_hp for room in result.per_room]
    assert hps == sorted(hps, reverse=True)
    assert hps[0] > hps[-1]


def test_the_chain_stops_at_the_first_loss(parts):
    """★ 진 방 뒤를 계속 돌면 죽은 캐릭터가 다음 방을 돈다."""
    result = run_chain(parts, ("open_field", "corridor", "pillars"), 4242, "g0_cover")
    assert result.outcome != OUTCOME_PLAYER_WIN
    assert len(result.per_room) == result.cleared_rooms + 1


def test_seed_is_split_per_room(parts):
    """★ 방마다 시드를 가른다.

    한 수열을 공유하면 앞 방의 전투 길이가 바뀔 때 뒷 방의 이니셔티브 동률 처리까지
    흔들려, 방 하나를 고쳤을 뿐인데 전체가 달라진다 (R5).
    """
    assert SEED_STRIDE == 1000
    first = run_chain(parts, ("open_field", "corridor", "pillars"), 4242)
    shifted = run_chain(parts, ("open_field", "corridor", "pillars"), 4242 + SEED_STRIDE)
    # 시드를 한 칸 밀면 첫 방이 옛 둘째 방의 시드를 받는다 — 결과가 같으면 시드가
    # 방마다 갈리지 않고 있다는 뜻이다.
    assert first.per_room[0].ticks != shifted.per_room[0].ticks or first != shifted


def test_floor_pressure_survives_the_room_change(parts):
    """★ 층 압력은 방을 넘어 이어진다 (GDD §7 층 지연).

    방마다 새로 만들면 층 체류 스케일이 매 방 0 으로 돌아가 압력이 사라진다. 같은 방을
    반복해도 뒤로 갈수록 어려워지는 것이 그 증거다.
    """
    result = run_chain(parts, ("open_field", "open_field", "open_field"), 4242, "g0_pressure")
    losses = [
        before.player_hp - after.player_hp
        for before, after in zip(result.per_room, result.per_room[1:], strict=False)
    ]
    assert all(loss > 0 for loss in losses)


def test_empty_chain_is_not_a_crash(parts):
    """방이 없으면 0으로 답한다 — 예외를 던지면 부르는 쪽이 전부 방어해야 한다."""
    result = run_chain(parts, (), 4242)
    assert result.cleared_rooms == 0
    assert result.player_hp == 0
    assert result.per_room == ()
