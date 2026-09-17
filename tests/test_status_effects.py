"""상태이상이 실제로 일을 하는가 — 둔화·이동불가·독.

`test_player_telegraph.py` 에서 갈라 나왔다. 400줄 상한이 계기였지만 가르는 선은
책임이다 (§4) — 저쪽은 **예고가 어떻게 서고 언제 끊기는가**이고 여기는 **걸린 뒤에
무슨 일이 일어나는가**다.

셋의 역사가 이 파일의 주제다. 세 상태가 전부 **인지 변수 목록에는 있는데 세계에는
없던** 때를 지났다.

    SLOW   이동만 늦췄다 → 행동 전체를 늦춘다 (2026-09-10)
    ROOT   없었다        → 이동만 통째로 막는다 (2026-09-17)
    POISON 아무도 안 걸었다 → 유지 단계가 매 틱 깎는다 (2026-09-17)

물어볼 수는 있는데 참이 되는 길이 없는 항은 규칙표에서 **거짓과 구별되지 않는다.**
그것이 이 셋을 각각 고친 이유이고, 여기서 지키는 것이다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_real(balance, templates):
    """실제 카탈로그로 엔진을 세운다. 시험용 스킬을 안 꽂는다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    target = next(iter(engine.state.list_hostiles(player)))
    return engine, player, target


def test_slow_halves_movement(balance, templates):
    """★ **둔화가 일을 한다** (GDD §211 의 「이동 2틱 소모」).

    없으면 `SLOW` 는 인지 변수에만 있고 걸어도 아무 일이 없다 — 서리 장판이 빈
    껍데기가 되는 자리다.
    """
    engine, player, target = build_real(balance, templates)
    player.statuses["SLOW"] = 9
    moved = 0
    for tick in range(6):
        engine.state.tick = tick
        before = player.position
        engine.apply_actions(
            (PlannedAction(entity_id="player", action_id="APPROACH", target_id=target.entity_id),)
        )
        moved += player.position != before
    assert moved == 3


def test_poison_bites_every_tick_for_exactly_its_duration(balance, templates):
    """★ **독이 처음으로 일을 한다** (2026-09-17).

    `POISON` 은 인지 변수 목록에 처음부터 있었는데 **거는 것도 깎는 것도 없었다** —
    규칙표가 「내 상태이상[중독]」을 물을 수 있었고 그 답은 영영 거짓이었다. 물어볼 수는
    있는데 참이 되는 길이 세계에 없는 항이 그것이다.

    **적어 둔 틱 수만큼 정확히 아프다.** 깎은 뒤 값을 보면 5 라고 적고 네 틱만 아프고,
    그러면 데이터의 수와 실제가 갈려 밸런스를 잴 수가 없다.
    """
    engine, player, _target = build_real(balance, templates)
    player.statuses["POISON"] = 3
    before = player.hp
    for tick in range(1, 6):
        engine.state.tick = tick
        engine.run_upkeep()
    # 세 틱 × 3 = 9. 네 번째·다섯 번째 틱에는 안 아프다.
    assert before - player.hp == 9
    assert player.statuses["POISON"] == 0


def test_poison_passes_the_same_door_as_lava(balance, templates):
    """★ 독이 어느 감쇠를 지나는지 못 박는다.

    **방어력은 안 거치고 방벽은 거친다.** 전투 수식은 `_apply_strike` 안에 있어 독이
    안 지나고, 방벽은 `apply_damage` 안에 있어 지난다 — 용암과 완전히 같은 문이다.
    그래서 방벽에 답이 하나 더 생긴다: 독을 반으로 줄인다.

    값을 못 박아 두는 이유는 이것이 **우연히 그런 것으로 보이기 때문**이다. 둘 중 한
    감쇠가 자리를 옮기는 날 여기가 먼저 빨개져야 한다.
    """
    engine, player, _target = build_real(balance, templates)
    player.statuses["POISON"] = 1
    player.statuses["GUARD"] = 5
    before = player.hp
    engine.state.tick = 1
    engine.run_upkeep()
    # 방벽 50% — 3 이 1 이 된다 (정수 내림, R5).
    assert before - player.hp == 1


def test_root_stops_the_feet_but_not_the_hands(balance, templates):
    """★ **이동불가는 기절이 아니다** (2026-09-17).

    둔화는 행동 전체를 반으로 늦추고 기절은 전부 막는다. 이것은 **이동만** 막는다 —
    그래서 도망치려는 쪽에만 걸리고, 붙어서 때리는 쪽은 그대로 때린다. 두 상태를
    가르는 이유가 이 한 줄이다: 이것이 참이 아니면 `ROOT` 는 `STUN` 의 다른 이름이다.
    """
    engine, player, target = build_real(balance, templates)
    target.position = (player.position[0] + 1, player.position[1])
    player.statuses["ROOT"] = 1
    before_position = player.position
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="APPROACH", target_id=target.entity_id),)
    )
    assert player.position == before_position, "묶였는데 움직였다"
    before_hp = target.hp
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="ATTACK", target_id=target.entity_id),)
    )
    assert target.hp < before_hp, "묶였다고 손까지 묶으면 그것은 기절이다"


def test_root_lasts_exactly_one_tick(balance, templates):
    """★ **한 틱이다.** 유지 단계가 한 번 돌면 풀린다 — 값이 싼 대신 짧다."""
    engine, player, _target = build_real(balance, templates)
    player.statuses["ROOT"] = 1
    engine.run_upkeep()
    assert player.statuses["ROOT"] == 0


def test_a_longer_slow_is_not_overwritten(balance, templates):
    """★ 짧은 것으로 덮으면 뒤에 온 약한 장판이 앞의 강한 것을 지운다."""
    from game.app.simulation.telegraph_effects import apply_blast_effects
    from game.app.skills.catalog import SkillEffect

    engine, player, _target = build_real(balance, templates)
    player.statuses["SLOW"] = 5
    telegraph = engine.telegraphs.register(
        caster_id="player",
        skill_id="FROST_FIELD",
        tiles=(player.position,),
        damage=0,
        effects=(SkillEffect(kind="STATUS", status="SLOW", duration=2),),
    )
    apply_blast_effects(engine.telegraphs, engine.state, engine.log, telegraph, player)
    assert player.statuses["SLOW"] == 5
