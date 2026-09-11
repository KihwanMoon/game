"""주문서 셋이 하는 일 (2026-09-11 결정).

**「종류를 늘려 달라」에 칸을 늘려 답하지 않았다.** 칸을 늘리면 들고 갈 수 있는 것이
느는 것이지 고를 것이 느는 것이 아니다. 칸은 그대로 주문서 한 칸이고, **거기 무엇을
끼웠느냐가 `USE_ITEM[태그]` 를 정한다** — 그래서 「무엇을 들고 갈까」가 선택이 된다.

여기서 지키는 것은 셋이다.

1. **유지시간이 상수다.** 규칙표를 짜는 사람이 몇 틱인지 알고 써야 한다 (실제 요청).
2. **겹쳐 쓰면 「불가」다.** 이미 걸린 위에 또 쓰면 남은 틱이 덮이고 충전만 탄다.
3. **피해는 `apply_damage` 하나를 거친다.** 직접 HP 를 깎으면 방어 태세·시전 취소·
   피격자별 로그가 조용히 빠지고, 사후 분석의 피해 지도에서 화염이 안 보인다.
"""

import pytest

from game.app.rules.rule_vm import RuleVm
from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation import scrolls
from game.app.simulation.abilities import ITEM_SCROLL
from game.app.simulation.plan import FREE_ITEMS, STATUS_GUARD, PlannedAction
from game.config import BALANCE_PATH, BLOCKS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import Condition, Rule, RuleSet, Term

PLAYER = "player"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


def build_probe(balance, templates, tag, charges=1):
    """주문서 한 종류를 들린 플레이어와 엔진을 만든다.

    Args:
        balance: 밸런스 절.
        templates: 방 템플릿 표.
        tag: 들릴 주문서 태그.
        charges: 들릴 충전 수.

    Returns:
        (엔진, 플레이어).
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities[PLAYER]
    player.consumables[tag] = charges
    return engine, player


def use_scroll(engine, tag, rule_index=1):
    """주문서 한 장을 쓰는 계획을 실행한다.

    Args:
        engine: 엔진.
        tag: 쓸 주문서 태그.
        rule_index: 로그에 실릴 규칙 번호.
    """
    engine.apply_actions(
        (
            PlannedAction(
                entity_id=PLAYER,
                action_id="USE_ITEM",
                item_kind=tag,
                rule_index=rule_index,
                expr=f"USE_ITEM[{tag}]",
            ),
        )
    )


# ── 유지시간이 규칙표가 아는 값이다 ────────────────────────────────────


def test_focus_lasts_a_number_of_ticks_the_ruleset_can_count(balance, templates):
    """★ **유지시간이 상수다** (실제 요청: 「유지시간이 명확해야 규칙에 넣을 수 있다」).

    등급이 바꾸는 것은 충전 수와 끼고 있는 동안의 접사뿐이다. 유지 틱이 아이템마다
    다르면 같은 규칙표가 **무엇을 끼웠느냐에 따라 다르게 돈다.**
    """
    engine, player = build_probe(balance, templates, scrolls.ITEM_FOCUS)
    use_scroll(engine, scrolls.ITEM_FOCUS)
    assert player.statuses[scrolls.STATUS_FOCUS] == scrolls.FOCUS_TICKS


def test_focus_reaches_one_tile_farther(balance, templates):
    """★ **사거리를 읽는 자리가 하나다.** 규칙표·폴백·시야·타격이 같은 값을 본다.

    한 곳에만 반영하면 규칙은 참인데 공격이 안 닿거나, 닿는데 규칙이 거짓이 된다 —
    둘 다 쓰는 사람에게는 「왜 안 때리지」로만 보인다.
    """
    engine, player = build_probe(balance, templates, scrolls.ITEM_FOCUS)
    base = scrolls.read_reach(player)
    use_scroll(engine, scrolls.ITEM_FOCUS)
    assert scrolls.read_reach(player) == base + scrolls.FOCUS_RANGE_BONUS


def test_focus_wears_off(balance, templates):
    """★ 걸어 둔 것은 **반드시 풀린다.** 안 풀리면 한 장이 판 전체를 산다."""
    engine, player = build_probe(balance, templates, scrolls.ITEM_FOCUS)
    use_scroll(engine, scrolls.ITEM_FOCUS)
    for _ in range(scrolls.FOCUS_TICKS + 1):
        engine.run_upkeep()
    assert scrolls.read_reach(player) == player.attack_range


# ── 겹쳐 쓰기는 「불가」다 ──────────────────────────────────────────────


def test_a_second_focus_is_blocked_not_burned(balance, templates, catalog):
    """★ **겹쳐 쓰면 충전만 탄다** (실제 요청).

    이미 걸려 있는데 또 쓰면 남은 틱이 덮일 뿐이고 그 사실은 로그에도 안 남는다.
    「불가」로 잡으면 **다음 규칙이 기회를 얻는다** — 소모품이 없을 때와 같은 자리다.
    """
    engine, player = build_probe(balance, templates, scrolls.ITEM_FOCUS, charges=2)
    player.statuses[scrolls.STATUS_FOCUS] = scrolls.FOCUS_TICKS
    always = Condition(op="SINGLE", terms=(Term("self_hp_percent", ">", 0, None),))
    ruleset = RuleSet(
        ruleset_id="scroll_probe",
        version=1,
        rules=(
            Rule(
                priority=1,
                conditions=always,
                action="USE_ITEM",
                action_param=scrolls.ITEM_FOCUS,
            ),
            Rule(priority=2, conditions=always, action="HOLD"),
        ),
    )
    vm = RuleVm(ruleset, catalog, engine.config.kind_types)
    plan = vm.plan_action(player, engine.build_perceptions()[PLAYER], engine.state)
    assert plan.action_id == "HOLD"
    assert any("이미 걸림" in one.reason for one in plan.blocked)


def test_an_instant_scroll_is_never_blocked(balance, templates):
    """★ **즉발은 겹칠 것이 없다.** 남는 상태가 없으므로 두 번 연달아 쓸 수 있다."""
    _engine, player = build_probe(balance, templates, scrolls.ITEM_BLINK, charges=2)
    assert scrolls.check_already_held(player, scrolls.ITEM_BLINK) is False
    assert scrolls.check_already_held(player, scrolls.ITEM_FLAME) is False


# ── 보호 주문서는 틱을 안 쓴다 (2026-09-11 실측) ───────────────────────


def test_the_guard_scroll_does_not_spend_the_tick(balance, templates, catalog):
    """★ **같은 기제면 같은 규칙이다.**

    보호 주문서는 방벽과 똑같은 `GUARD` 상태를 똑같은 값으로 거는데, 한쪽만 틱을 내면
    세계에 규칙이 둘이 된다. 실측도 같은 말을 했다 — 층 배치 80런에서 보호 주문서를 쓰는
    규칙표가 기준(57%)보다 **낮은** 47% 였다: 켜는 데 낸 한 틱이 2틱 50% 보다 컸다.

    그래서 규칙표는 켜고 끄는 것만 정하고, 그 틱의 행동은 **다음 규칙이 정한다.**
    """
    engine, player = build_probe(balance, templates, "SCROLL")
    always = Condition(op="SINGLE", terms=(Term("self_hp_percent", ">", 0, None),))
    ruleset = RuleSet(
        ruleset_id="guard_probe",
        version=1,
        rules=(
            Rule(priority=1, conditions=always, action="USE_ITEM", action_param="SCROLL"),
            Rule(priority=2, conditions=always, action="HOLD"),
        ),
    )
    vm = RuleVm(ruleset, catalog, engine.config.kind_types)
    plan = vm.plan_action(player, engine.build_perceptions()[PLAYER], engine.state)
    assert plan.action_id == "HOLD", "주문서가 그 틱의 행동을 먹었다"
    assert plan.free_items == ("SCROLL",)


def test_the_free_scroll_still_burns_a_charge(balance, templates):
    """★ **공짜인 것은 틱이지 장수가 아니다.**

    스킬은 쿨타임만 내지만 주문서는 충전을 낸다 — 그것이 안 타면 한 장이 판 전체를 산다.
    """
    engine, player = build_probe(balance, templates, "SCROLL", charges=2)
    engine.actions.apply_item(player, PlannedAction(entity_id=PLAYER, action_id="HOLD"), "SCROLL")
    assert player.consumables["SCROLL"] == 1
    assert player.statuses[STATUS_GUARD] > 0


def test_the_instant_scrolls_still_cost_the_tick(balance, templates):
    """★ **즉발은 그 자체가 행동이다.** 공짜가 되는 것은 켜 두고 기다리는 것뿐이다."""
    assert scrolls.ITEM_BLINK not in FREE_ITEMS
    assert scrolls.ITEM_FLAME not in FREE_ITEMS
    assert scrolls.ITEM_FOCUS not in FREE_ITEMS
    # 실행기가 아는 태그와 같은 글자여야 한다 — 갈리면 「공짜」가 아무 데도 안 걸린다.
    assert ITEM_SCROLL in FREE_ITEMS


# ── 순간이동 ───────────────────────────────────────────────────────────


def test_blink_opens_a_gap_that_one_step_cannot(balance, templates):
    """★ **이동이 한 칸씩인 세계라 포위를 푸는 유일한 수단이다.**

    `RETREAT` 는 한 칸이고 적도 한 칸 따라오므로 거리가 안 벌어진다.
    """
    engine, player = build_probe(balance, templates, scrolls.ITEM_BLINK)
    hostiles = engine.state.list_hostiles(player)
    near_before = min(
        abs(player.position[0] - one.position[0]) + abs(player.position[1] - one.position[1])
        for one in hostiles
    )
    use_scroll(engine, scrolls.ITEM_BLINK)
    near_after = min(
        abs(player.position[0] - one.position[0]) + abs(player.position[1] - one.position[1])
        for one in hostiles
    )
    assert near_after > near_before
    assert player.consumables[scrolls.ITEM_BLINK] == 0


def test_blink_keeps_the_charge_when_there_is_nowhere_to_go(balance, templates):
    """★ **못 쓴 장은 안 탄다.** 그냥 사라지면 「주문서가 왜 벌써 없지」로만 보인다."""
    engine, player = build_probe(balance, templates, scrolls.ITEM_BLINK)
    # 적을 전부 치우면 물러설 이유가 없다 — `find_blink_spot` 이 None 을 낸다.
    for other in engine.state.list_hostiles(player):
        other.hp = 0
    use_scroll(engine, scrolls.ITEM_BLINK)
    assert player.consumables[scrolls.ITEM_BLINK] == 1


# ── 화염 ───────────────────────────────────────────────────────────────


def test_flame_burns_everyone_within_the_radius(balance, templates):
    """★ **예고가 없는 것이 이 주문서의 전부다.**

    마법은 전부 예고를 쓰므로(설계/5_스킬 §10) 「비켜설 틈을 안 주는 광역」은 소모품만
    할 수 있는 일이고, 대가는 충전 수다.
    """
    engine, player = build_probe(balance, templates, scrolls.ITEM_FLAME)
    victim = engine.state.list_hostiles(player)[0]
    victim.position = player.position[0] + 1, player.position[1]
    before = victim.hp
    use_scroll(engine, scrolls.ITEM_FLAME)
    assert victim.hp < before
    assert engine.telegraphs.list_active() == ()


def test_flame_damage_goes_through_the_one_damage_gate(balance, templates):
    """★ **피해 지도에 화염이 보여야 한다.**

    직접 HP 를 깎으면 방어 태세·시전 취소·피격자별 로그가 조용히 빠진다. 로그에 그
    피격자 줄이 없으면 사후 분석은 「아무 일도 없었다」고 말한다 (P1).
    """
    engine, player = build_probe(balance, templates, scrolls.ITEM_FLAME)
    victim = engine.state.list_hostiles(player)[0]
    victim.position = player.position[0] + 1, player.position[1]
    use_scroll(engine, scrolls.ITEM_FLAME, rule_index=3)
    hits = [
        one
        for one in engine.log.entries
        if victim.entity_id in one.outcome and one.entity_id == PLAYER
    ]
    assert hits, "피격자별 줄이 없다 — 피해 지도에서 화염이 안 보인다"
    assert hits[-1].rule == 3


def test_flame_keeps_the_charge_with_nobody_in_range(balance, templates):
    """★ 빈 허공에 쓴 한 장은 **안 탄다.**"""
    engine, player = build_probe(balance, templates, scrolls.ITEM_FLAME)
    for other in engine.state.list_hostiles(player):
        other.position = (0, 0)
        other.hp = 0
    use_scroll(engine, scrolls.ITEM_FLAME)
    assert player.consumables[scrolls.ITEM_FLAME] == 1
