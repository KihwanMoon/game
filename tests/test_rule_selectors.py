"""셀렉터 테스트 — 조건보다 먼저 대상을 푼다 (F-1, 블록 목록 v4).

`test_rule_vm.py` 에서 갈라 나왔다. 셀렉터가 누구를 고르느냐가 조건의 좌변을 정하므로,
여기가 틀리면 조건식은 맞는데 답이 틀리는 형태로 드러난다 — 가장 짚기 어려운 실패다.
"""

import pytest

from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import (
    build_engine,
    load_balance,
)
from game.app.simulation.selectors import resolve_target
from game.app.simulation.state import FACTION_ENEMY
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import (
    Condition,
    Rule,
    RuleSet,
    Term,
    load_rulesets,
)


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def rooms():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


@pytest.fixture(scope="module")
def rulesets():
    return load_rulesets(G0_RULESETS_PATH)


@pytest.fixture
def engine(rooms, balance):
    return build_engine(rooms["open_field"], balance, seed=12345)


def make_rule(priority, lhs, cmp_op, rhs, action, target=None, param=None, cost=1, flag=None):
    return Rule(
        priority=priority,
        conditions=Condition(op="SINGLE", terms=(Term(lhs, cmp_op, rhs, param),)),
        action=action,
        target=target,
        set_flag=flag,
        cpu_cost=cost,
    )


# ── 셀렉터 (F-1: 조건보다 먼저 푼다) ─────────────────────────────────────────


def test_nearest_selector_picks_the_closest(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    picked = resolve_target("NEAREST", player, engine.state, kinds)
    assert picked is not None
    assert picked.faction != player.faction


def test_lowest_hp_selector_picks_the_weakest(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    weakest = next(e for e in engine.state.entities.values() if e.faction != player.faction)
    weakest.hp = 1
    picked = resolve_target("LOWEST_HP", player, engine.state, kinds)
    assert picked.entity_id == weakest.entity_id


def test_type_selector_filters_by_enemy_type(rooms, balance):
    # open_field 에는 돌진형만 나오므로 소환사가 있는 방을 쓴다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    local = build_engine(rooms["pillars"], balance, seed=1)
    player = local.state.entities["player"]
    picked = resolve_target("TYPE_SUMMONER", player, local.state, kinds)
    assert picked is not None
    assert kinds[picked.kind_id] == "SUMMONER"


def test_selector_returns_none_when_nobody_matches(engine, balance):
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    player = engine.state.entities["player"]
    # 보스는 이 방에 없다. 없는 대상을 고르라는 규칙은 발동하면 안 된다.
    assert resolve_target("BOSS", player, engine.state, kinds) is None


# ── 아군 셀렉터 (블록 목록 v4) ───────────────────────────────────────────────


def test_ally_selector_picks_the_most_wounded_ally(engine, balance):
    # GDD §5 치유형의 '아군 HP% 낮으면 회복' 이 성립하는 자리다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    enemies = [e for e in engine.state.entities.values() if e.faction == FACTION_ENEMY]
    healer, hurt = enemies[0], enemies[1]
    hurt.hp = 5
    picked = resolve_target("ALLY_WOUNDED", healer, engine.state, kinds)
    assert picked is not None
    assert picked.entity_id == hurt.entity_id
    assert picked.faction == healer.faction


def test_ally_selector_skips_untouched_allies(engine, balance):
    # 만피 아군을 고르면 HEAL 이 회복량 0 으로 끝나고 쿨타임도 걸리지 않아
    # 그 규칙이 매 틱 참인 채로 치유형을 굳힌다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    healer = next(e for e in engine.state.entities.values() if e.faction == FACTION_ENEMY)
    assert resolve_target("ALLY_WOUNDED", healer, engine.state, kinds) is None


def test_ally_selector_never_picks_the_actor(engine, balance):
    # 자기 회복은 USE_POTION 의 자리다. 자신을 후보로 두면 아군이 없는 판에서도
    # HEAL 이 무한 포션처럼 돈다.
    kinds = {k["id"]: k["type"] for k in balance["enemies"]}
    healer = next(e for e in engine.state.entities.values() if e.faction == FACTION_ENEMY)
    for other in tuple(engine.state.entities.values()):
        if other.faction == FACTION_ENEMY and other is not healer:
            other.hp = 0
    healer.hp = 1
    assert resolve_target("ALLY_WOUNDED", healer, engine.state, kinds) is None


def test_validator_rejects_a_selector_from_the_wrong_faction(catalog):
    # `HEAL @NEAREST` 는 적을 회복하고 `ATTACK @ALLY_WOUNDED` 는 아군을 때린다.
    # 문법으로는 만들어지므로 검증기가 막지 않으면 규칙표가 조용히 반대로 돈다.
    heal = make_rule(1, "self_hp_percent", "<", 50, "HEAL", target="NEAREST")
    problems = validate_ruleset(RuleSet("x", 1, (heal,)), catalog, 99, 5)
    assert any("아군 셀렉터가 필요하다" in p for p in problems)
    hit = make_rule(1, "self_hp_percent", "<", 50, "ATTACK", target="ALLY_WOUNDED")
    problems = validate_ruleset(RuleSet("x", 1, (hit,)), catalog, 99, 5)
    assert any("적대 셀렉터가 필요하다" in p for p in problems)


def test_validator_accepts_the_matching_faction(catalog):
    heal = make_rule(1, "self_hp_percent", "<", 50, "HEAL", target="ALLY_WOUNDED")
    assert validate_ruleset(RuleSet("x", 1, (heal,)), catalog, 99, 5) == []
