"""플레이어가 예고를 건다 (설계/5_스킬 §10, 도입 순서 H3).

**메테오는 이미 있었다 — 방향만 반대였다.** 자폭형 몬스터가 하던 것이 정확히 그것이고
(`abilities.register_blast` 의 「즉발 광역기 대신 예고를 건다」), 없던 것은 **스킬이
예고를 정하는 길**이었다. 예고가 개체 종류에만 달려 있으면 그것은 그 종류의 성질이라
플레이어가 쓸 수 없다.

여기서 보는 것은 셋이다 — 스킬이 예고를 정하면 그것이 먼저인가, 피해가 시전 시점에
얼어붙는가, 그리고 **아무 스킬도 예고를 안 쓰는 지금 동작이 그대로인가**.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.app.skills.catalog import SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

METEOR = "METEOR"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_probe(balance, templates, telegraph=0, radius=3, coef=200):
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=radius),
        coef_pct=coef,
        telegraph=telegraph,
    )
    return engine, engine.state.entities["player"]


def build_plan():
    return PlannedAction(entity_id="player", action_id="USE_SKILL", skill_id=METEOR)


def test_a_skill_with_a_telegraph_registers_instead_of_striking(balance, templates):
    """★ **이것이 H3 의 전부다.** 즉발 대신 붉은 칸이 먼저 뜬다."""
    engine, _player = build_probe(balance, templates, telegraph=3)
    engine.apply_actions((build_plan(),))
    active = engine.telegraphs.list_active()
    assert len(active) == 1
    assert active[0].skill_id == METEOR
    assert active[0].remaining_ticks == 3


def test_the_radius_comes_from_the_shape(balance, templates):
    """★ 반경도 데이터다 — 상수로 돌면 데이터를 고쳐도 안 달라진다."""
    engine, player = build_probe(balance, templates, telegraph=2, radius=1)
    engine.apply_actions((build_plan(),))
    tiles = engine.telegraphs.list_active()[0].tiles
    assert all(abs(x - player.position[0]) + abs(y - player.position[1]) <= 1 for x, y in tiles)


def test_the_damage_freezes_at_cast_time(balance, templates):
    """★ **발동 시점에 다시 계산하면 그 사이의 버프가 회피 판정에 섞인다.**

    예고 피해는 방어력 감쇠를 안 거치는 고정값이라(`telegraph.py` 머리말), 「누가
    걸었는가」는 반영되고 「그 뒤에 무슨 일이 있었는가」는 안 반영돼야 한다.
    """
    engine, player = build_probe(balance, templates, telegraph=2, coef=200)
    before = player.attack
    engine.apply_actions((build_plan(),))
    frozen = engine.telegraphs.list_active()[0].damage
    assert frozen == before * 2
    player.attack = before * 10
    assert engine.telegraphs.list_active()[0].damage == frozen


def test_a_skill_without_a_telegraph_still_strikes_now(balance, templates):
    """★ **지금 동작이 그대로여야 한다.** 어느 스킬도 예고를 안 쓰므로 골든이 안 깨진다."""
    engine, _player = build_probe(balance, templates, telegraph=0)
    engine.apply_actions((build_plan(),))
    assert engine.telegraphs.list_active() == ()


def test_the_caster_sees_its_own_cast(balance, templates):
    """★ `self_is_casting` 이 없으면 「마법을 버리고 후퇴」를 지을 수 없다 (§10.3).

    시전을 잠그지 않고 취소되게 했으므로, 취소가 선택이 되려면 규칙표가 물을 수 있어야
    한다 — 못 물으면 잠그는 것과 같아진다.
    """
    from game.app.simulation.perception import build_snapshot

    engine, player = build_probe(balance, templates, telegraph=3)
    engine.apply_actions((build_plan(),))
    engine.state.tick = 1
    engine.run_telegraph()
    snapshot = build_snapshot(
        engine.state, player, engine.config.kind_types, board=engine.telegraphs
    )
    assert snapshot.values["self_is_casting"] is True


# ── 시전 취소 (H4) ──────────────────────────────────────────────────────


def build_casting(balance, templates, **switches):
    """예고를 건 상태의 엔진을 만든다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=2),
        coef_pct=200,
        telegraph=3,
        **switches,
    )
    engine.apply_actions((build_plan(),))
    assert len(engine.telegraphs.list_active()) == 1
    return engine, engine.state.entities["player"]


def test_another_action_cancels_a_cast(balance, templates):
    """★ **취소가 벌이 아니라 선택이다** (§10.3).

    잠그면 그 틱 동안 규칙표가 안 도는데, 규칙표가 주인공인 게임에서 무결정 구간은
    그 자체로 손해다. 잠그는 대신 다른 행동이 끊게 하면 무엇을 할지는 규칙표가 정한다.
    """
    engine, player = build_casting(balance, templates, cancel_on_act=True)
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="APPROACH"),))
    assert engine.telegraphs.list_active() == ()


def test_a_cast_that_is_not_interruptible_survives_an_action(balance, templates):
    """★ **기본은 안 끊긴다.** 전부에 걸면 자폭형이 다음 틱에 움직이며 스스로 취소해

    영영 안 터진다 — 지금 콘텐츠의 뜻이 통째로 바뀐다. 켜는 것은 스킬 데이터다.
    """
    engine, player = build_casting(balance, templates)
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="APPROACH"),))
    assert len(engine.telegraphs.list_active()) == 1


def test_holding_keeps_the_cast(balance, templates):
    """★ **「포기하지 않는다」를 적을 칸이 규칙표에 있어야 한다** (§10.3).

    §10.3 은 취소를 벌이 아니라 선택으로 두겠다고 했는데, 버티기까지 취소 사유면 답의
    한쪽이 아예 표현되지 않는다 — 규칙표가 무엇을 적든 마법은 언제나 포기된다.

    실측이 그것을 그대로 보여 줬다: focus_lowest_guard 뼈대(1층 60런 46%)에서 2번 한
    줄만 마법으로 바꾸니 1% 였고, 로그에는 `T001 예고 16칸 · T002 예고 취소 → 다른
    행동` 이 매 판 찍혀 있었다. 예고를 쓰는 스킬이 **어느 규칙표에서도 한 번도 안
    터지고 있었다.**
    """
    engine, player = build_casting(balance, templates, cancel_on_act=True)
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="HOLD"),))
    assert len(engine.telegraphs.list_active()) == 1


def test_setting_a_flag_keeps_the_cast(balance, templates):
    """★ 깃발은 세계를 안 건드린다. 끊으면 「시전 중에는 기록도 못 한다」가 된다."""
    engine, player = build_casting(balance, templates, cancel_on_act=True)
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="SET_FLAG"),))
    assert len(engine.telegraphs.list_active()) == 1


def test_being_hit_cancels_a_cast(balance, templates):
    """★ 「안전한 자리에서 쏘는가」를 규칙표에 묻는 자리다 — 카이팅과 결합한다."""
    engine, player = build_casting(balance, templates, cancel_on_hit=True)
    engine.actions.apply_damage(player, 5, "ACT", "시험", "e1")
    assert engine.telegraphs.list_active() == ()


def test_a_fully_blocked_hit_does_not_cancel(balance, templates):
    """★ **막아 낸 피해로 끊기면 방어가 벌이 된다.** 실제로 깎였을 때만 본다."""
    engine, player = build_casting(balance, templates, cancel_on_hit=True)
    engine.actions.apply_damage(player, 0, "ACT", "시험", "e1")
    assert len(engine.telegraphs.list_active()) == 1


def test_the_cancel_is_written_down(balance, templates):
    """★ 조용히 사라지면 「내 마법이 어디 갔지」가 된다 (P1)."""
    engine, player = build_casting(balance, templates, cancel_on_act=True)
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="APPROACH"),))
    lines = [
        one for one in engine.log.entries if "예고 취소" in one.expr or "예고 취소" in one.outcome
    ]
    assert lines, "취소가 로그에 안 남았다"


# ── 마법 셋 (H5) ────────────────────────────────────────────────────────


def build_real(balance, templates):
    """실제 카탈로그로 엔진을 세운다. 시험용 스킬을 안 꽂는다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    target = next(iter(engine.state.list_hostiles(player)))
    return engine, player, target


def cast_plan(skill_id, target_id):
    return PlannedAction(
        entity_id="player", action_id="USE_SKILL", skill_id=skill_id, target_id=target_id
    )


def test_meteor_stands_for_three_ticks(balance, templates):
    """★ **강함의 대가가 희귀도가 아니라 예고다** (§10).

    반경 3 이 3틱 붉게 서 있고, 그동안 적은 비켜설 수 있다. 칸 수가 17 에서 21 로
    는 것은 **중심이 시전자 발밑에서 겨눈 곳으로 옮겨 갔기 때문이다** — 예전에는
    자폭형에서 물려받은 자리라 10칸 밖 적에게 던진 메테오가 제 발밑에서 터졌다.
    """
    engine, player, target = build_real(balance, templates)
    engine.apply_actions((cast_plan("METEOR", target.entity_id),))
    one = engine.telegraphs.list_active()[0]
    assert len(one.tiles) == 21
    assert one.remaining_ticks == 3
    assert player.position not in one.tiles, "제 발밑에서 터지면 마법이 자해가 된다"


def test_chain_bolt_reaches_toward_the_target(balance, templates):
    """★ **`LINE` 이 P2 를 증명하는 자리다** — 적을 일렬로 세우게 만든다."""
    engine, _player, target = build_real(balance, templates)
    engine.apply_actions((cast_plan("CHAIN_BOLT", target.entity_id),))
    one = engine.telegraphs.list_active()[0]
    assert 0 < len(one.tiles) <= 4
    assert one.remaining_ticks == 1


def test_chain_bolt_without_a_target_hits_nobody(balance, templates):
    """★ 방향이 없으면 안 뻗는다. 자기 발밑을 지지지 않는다."""
    engine, _player, _target = build_real(balance, templates)
    engine.apply_actions((cast_plan("CHAIN_BOLT", ""),))
    assert engine.telegraphs.list_active()[0].tiles == ()


def test_frost_field_slows_and_now_also_bites(balance, templates):
    """★ **피해 0 이었다 — 실측이 그것을 접었다** (§10.10).

    설계는 「피해 0 인 스킬이 성립하는가」를 물으려고 이 스킬을 넣었고 `effects` 가
    그래서 생겼다. 그런데 활 카이팅 기준선 84% 위에서 한 줄만 서리 장판으로 바꾸니
    61% 였고, 예고를 1틱으로 줄여도 76% · 둔화를 5틱으로 늘려도 74% 였다 — 기준선을
    넘는 유일한 변형이 「피해 60%」였다. `SLOW` 가 이동만 늦춰서(사격형에게는 효과가
    없다) 2틱을 내고 사기에는 값이 안 맞았던 것이다.

    **여전히 화력 스킬이 아니다.** 메테오의 220% 에 견주면 3분의 1 이고, 이 표가 파는
    것은 그대로 「도망칠 길을 막을 것인가」다. 자기 오사도 그대로라 내가 밟으면 나도
    느려지고, 이제는 맞기도 한다.
    """
    engine, player, target = build_real(balance, templates)
    target.position = (player.position[0] + 1, player.position[1])
    engine.apply_actions((cast_plan("FROST_FIELD", target.entity_id),))
    frozen = engine.telegraphs.list_active()[0].damage
    assert frozen == player.attack * 60 // 100
    before = target.hp
    for tick in (1, 2, 3):
        engine.state.tick = tick
        engine.run_telegraph()
    assert target.hp == before - frozen
    assert target.statuses["SLOW"] == 3
    assert player.statuses["SLOW"] == 3


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


# ── 둔화가 행동을 늦춘다 (2026-09-10 결정) ──────────────────────────────


def test_a_slowed_entity_does_not_act_at_all(balance, templates):
    """★ **이동만이 아니다.** 사격형에게 효과가 없던 것이 이 한 줄이었다.

    `SLOW` 가 이동 경로에서만 걸릴 때는 안 움직여도 때리는 적에게 아무 일도 안 났고,
    이미 붙은 돌진형에게도 없었다. 서리 장판이 피해 0 으로는 어느 표에서도 값을 못 한
    원인이 그것이다 (설계/5_스킬 §10.10).
    """
    engine = build_engine(templates["corridor"], balance, seed=3)
    player = engine.state.entities["player"]
    target = next(one for one in engine.state.list_hostiles(player))
    target.position = (player.position[0] + 1, player.position[1])
    player.statuses["SLOW"] = 4

    before = target.hp
    engine.state.tick = 1  # 홀수 틱이 쉬는 틱이다
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="ATTACK", target_id=target.entity_id),)
    )
    assert target.hp == before, "쉬는 틱에 때렸다"

    engine.state.tick = 2
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="ATTACK", target_id=target.entity_id),)
    )
    assert target.hp < before, "쉬지 않는 틱에도 못 때렸다"


def test_resting_does_not_cancel_a_cast(balance, templates):
    """★ **쉬는 틱은 「다른 행동」이 아니다.**

    예고를 끊는 것은 다른 행동을 했다는 사실인데(§10.3), 둔화로 쉰 틱은 아무 행동도
    안 한 틱이다. 여기서 끊으면 둔화 한 번이 마법을 통째로 지운다.
    """
    engine, player = build_casting(balance, templates, cancel_on_act=True)
    player.statuses["SLOW"] = 4
    engine.state.tick = 1
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="APPROACH"),))
    assert len(engine.telegraphs.list_active()) == 1
