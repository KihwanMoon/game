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


def test_chain_bolt_hops_between_nearby_enemies(balance, templates):
    """★ **직선이 아니라 연쇄다** (2026-09-17 요청).

    예전에는 겨눈 대상 **뒤로** 뻗는 직선이라, 적이 일렬로 설 때만 두 명을 맞혔다 —
    1층 배치에서 그 줄이 잘 안 서서 전도 막대를 끼고도 35% 였다 (§10.6 실측).
    이제는 겨눈 대상에서 가까운 적으로 튄다: **뭉친 적을 벌한다.**
    """
    # **적이 셋인 방을 고른다.** `open_field` 는 둘뿐이라 「튄 자리에서 또 튄다」를
    # 잴 수 없다 — 그 한 칸이 이 형태의 전부다.
    engine = build_engine(templates["chapel"], balance, seed=3)
    player = engine.state.entities["player"]
    target, *others = engine.state.list_hostiles(player)
    assert len(others) >= 2, "연쇄를 재려면 적이 셋은 있어야 한다"
    # 두 칸씩 떨어뜨리되 **꺾어서** 놓는다. 일직선이면 예전 `LINE` 도 통과한다.
    base_x, base_y = target.position
    others[0].position = (base_x + 2, base_y)
    others[1].position = (base_x + 2, base_y + 2)
    engine.apply_actions((cast_plan("CHAIN_BOLT", target.entity_id),))
    one = engine.telegraphs.list_active()[0]
    assert one.remaining_ticks == 1
    assert target.position in one.tiles
    assert others[0].position in one.tiles, "두 칸 안의 적으로 튀어야 한다"
    assert others[1].position in one.tiles, "튄 자리에서 또 튀어야 한다"


def test_chain_bolt_stops_where_the_enemies_stop(balance, templates):
    """★ **닿을 적이 없으면 거기서 끝난다** — 빈 칸을 칠하지 않는다.

    직선은 적이 없어도 네 칸을 칠했다. 연쇄는 적이 있는 칸만 칠하므로, 흩어진
    배치에서는 한 명만 맞는다 — 그것이 이 형태가 파는 거래다.
    """
    engine, player, target = build_real(balance, templates)
    # 나머지를 전부 멀리 치운다. 튈 곳이 없다.
    others = [one for one in engine.state.list_hostiles(player) if one is not target]
    for index, other in enumerate(others):
        other.position = (1, 1 + index)
    target.position = (player.position[0] + 4, player.position[1])
    engine.apply_actions((cast_plan("CHAIN_BOLT", target.entity_id),))
    assert engine.telegraphs.list_active()[0].tiles == (target.position,)


def test_chain_bolt_without_a_target_hits_nobody(balance, templates):
    """★ 겨눈 것이 없으면 안 튄다. 자기 발밑을 지지지 않는다."""
    engine, _player, _target = build_real(balance, templates)
    engine.apply_actions((cast_plan("CHAIN_BOLT", ""),))
    assert engine.telegraphs.list_active()[0].tiles == ()


def test_frost_field_roots_instead_of_slowing(balance, templates):
    """★ **장판 대신 공격이고, 둔화 대신 이동불가다** (2026-09-17 요청).

    예전에는 반경 2 에 둔화 3틱이었다. 둔화는 「얼마나 느려지는가」를 물었고, 그 답이
    사격형에게는 아무것도 아니었다 — 안 움직여도 때리기 때문이다 (§10.10). 그래서
    행동 전체를 늦추게 고쳤는데, 그러면 이번에는 기절과 다를 바가 없어졌다.

    이제 묻는 것은 「어디에 묶이는가」다. 이동만 막으므로 **도망치려는 쪽**에만 걸리고,
    붙어서 때리는 쪽은 그대로 때린다. 한 틱뿐이라 값이 싸고, 넓어서 여럿에게 걸린다.

    자기 오사는 그대로다 — 내가 밟으면 나도 묶인다.
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
    assert target.statuses["ROOT"] == 1
    assert player.statuses["ROOT"] == 1
    assert "SLOW" not in target.statuses, "둔화는 더 이상 이 스킬의 것이 아니다"


def test_frost_field_now_covers_a_wider_ring(balance, templates):
    """★ **넓어졌다** (요청: 「넓은 범위에」). 반경 2 에서 3 으로 간다.

    한 틱짜리 이동불가는 넓지 않으면 값을 못 한다 — 좁으면 그 한 틱에 묶을 수 있는
    적이 한둘이고, 그 둘은 이미 내 앞에 붙어 있어 묶어도 도망치지 않는다.
    """
    engine, _player, target = build_real(balance, templates)
    engine.apply_actions((cast_plan("FROST_FIELD", target.entity_id),))
    # 반경 3 의 맨해튼 원은 25칸이다. 벽·방 밖은 걸러지므로 그 이하로 나온다.
    assert 0 < len(engine.telegraphs.list_active()[0].tiles) <= 25


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
