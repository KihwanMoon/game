"""W6 배선 회귀 — 새 모듈이 7페이즈 안에서 실제로 도는가.

각 모듈의 단위 테스트는 test_vision·test_telegraph·test_pressure 가 이미 본다.
여기서 보는 것은 **엔진이 그것을 부르는가** 다. 부르지 않으면 모듈 테스트는 통과하는데
게임은 아무것도 달라지지 않는다 — 통합에서 가장 흔한 실패 방식이다.
"""

import pytest

from game.app.grid.vision import VisionGrid, check_exposure, find_cover_positions
from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import assign_enemy_policies, build_engine, load_balance
from game.app.simulation.actions import DEFERRED_ACTIONS
from game.app.simulation.perception import DEFERRED_BLOCKS
from game.app.simulation.plan import PlannedAction
from game.app.simulation.selectors import resolve_target
from game.app.simulation.state import FACTION_ENEMY, Entity
from game.config import BALANCE_PATH, BLOCKS_PATH, ENEMY_RULESETS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

BOMBER_KIND = "bomb_slime"
SUMMON_EVERY_TICKS = 3


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture(scope="module")
def enemy_rulesets():
    return load_rulesets(ENEMY_RULESETS_PATH)


def make_plan(entity_id, action_id, target_id=None):
    return PlannedAction(entity_id=entity_id, action_id=action_id, target_id=target_id)


def add_bomber(engine, position):
    stats = engine.config.enemy_stats[BOMBER_KIND]
    bomber = Entity(
        entity_id="bomber_x",
        kind_id=BOMBER_KIND,
        faction=FACTION_ENEMY,
        position=position,
        hp=stats["hp_max"],
        hp_max=stats["hp_max"],
        attack=stats["attack"],
        defense=stats["defense"],
        attack_range=stats["attack_range"],
        initiative=stats["initiative"],
    )
    engine.state.entities[bomber.entity_id] = bomber
    return bomber


# ── 미구현 표 (통합의 판정 기준) ─────────────────────────────────────────────


def test_deferred_tables_are_empty_after_integration():
    # 값이 생겼는데 표에 남아 있으면 "미구현" 이라는 계약이 거짓말이 된다.
    assert DEFERRED_BLOCKS == {}
    assert DEFERRED_ACTIONS == {}


# ── UPKEEP: 압력 ─────────────────────────────────────────────────────────────


def test_spring_pools_are_filled_when_the_room_is_built(templates, balance):
    # 채우지 않으면 생명의 샘이 회복을 한 점도 내지 못한다.
    engine = build_engine(templates["spring_bait"], balance, seed=3)
    assert engine.state.spring_pools
    assert min(engine.state.spring_pools.values()) > 0


def test_hunter_appears_after_the_room_limit(templates, balance, catalog, enemy_rulesets):
    engine = build_engine(templates["open_field"], balance, seed=3)
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    engine.pressure.room_ticks = balance["anti_abuse"]["hunter_spawn_tick"]
    engine.state.tick = 1
    engine.run_upkeep()

    hunters = [e for e in engine.state.list_actors() if "_h" in e.entity_id]
    assert len(hunters) == 1
    # 규칙표를 붙이지 않으면 접근만 하고 공격하지 않아 압력이 되지 못한다.
    assert hunters[0].entity_id in engine.policies


def test_floor_scale_raises_enemy_attack_only(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    player_attack = engine.state.entities["player"].attack
    engine.pressure.floor_ticks = 500
    engine.state.tick = 1
    engine.run_upkeep()

    enemies = [e for e in engine.state.list_actors() if e.faction == FACTION_ENEMY]
    assert all(e.attack > balance["enemies"][0]["attack"] for e in enemies)
    assert engine.state.entities["player"].attack == player_attack


# ── TELEGRAPH ────────────────────────────────────────────────────────────────


def test_telegraph_phase_counts_down_and_fires(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    caster = engine.state.list_hostiles(player)[0]
    engine.telegraphs.register(
        caster.entity_id, "AREA_ATTACK", (player.position,), damage=9, lead_ticks=2
    )

    engine.state.tick = 1
    engine.run_telegraph()
    assert player.hp == player.hp_max, "예고는 등록된 틱에 터지지 않는다"

    engine.state.tick = 2
    engine.run_telegraph()
    assert player.hp == player.hp_max - 9


def test_area_attack_of_a_bomber_becomes_a_telegraph(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    bomber = add_bomber(engine, (2, 4))
    engine.actions.apply_area_attack(bomber, make_plan(bomber.entity_id, "AREA_ATTACK"))
    assert len(engine.telegraphs.list_active()) == 1
    assert engine.state.entities["player"].hp == 100, "예고형은 즉발로 때리지 않는다"


def test_self_destruct_kills_the_caster(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    bomber = add_bomber(engine, (2, 4))
    engine.actions.apply_area_attack(bomber, make_plan(bomber.entity_id, "AREA_ATTACK"))
    for tick in range(1, 5):
        engine.state.tick = tick
        engine.run_telegraph()
    assert not bomber.is_alive, "자폭형이 살아남으면 무한 폭탄이 된다"


def test_casting_selector_can_pick_a_caster(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    bomber = add_bomber(engine, (2, 4))
    engine.actions.apply_area_attack(bomber, make_plan(bomber.entity_id, "AREA_ATTACK"))
    engine.state.tick = 1
    engine.run_telegraph()

    player = engine.state.entities["player"]
    picked = resolve_target("CASTING", player, engine.state, engine.config.kind_types)
    assert picked is not None
    assert picked.entity_id == bomber.entity_id


# ── PERCEPTION ───────────────────────────────────────────────────────────────


def test_los_perceptions_have_values(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    snapshot = engine.build_perceptions()["player"]
    assert isinstance(snapshot.read("self_exposed_to_los"), bool)
    assert isinstance(snapshot.read("cover_wall_distance"), int)
    assert snapshot.read("self_on_hazard_telegraph") is False


def test_visible_enemy_count_is_narrowed_by_line_of_sight(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    player.position = (2, 2)  # 같은 행에 엄폐 기둥이 둘 있다
    for enemy in engine.state.list_actors():
        if enemy.faction == FACTION_ENEMY:
            enemy.position = (10, 2)
            break
    snapshot = engine.build_perceptions()["player"]
    assert snapshot.read("visible_enemy_count") < len(engine.state.list_hostiles(player))


def test_hazard_perception_follows_the_board(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    caster = engine.state.list_hostiles(player)[0]
    engine.telegraphs.register(
        caster.entity_id, "AREA_ATTACK", (player.position,), damage=9, lead_ticks=1
    )
    assert engine.build_perceptions()["player"].read("self_on_hazard_telegraph") is True


# ── ACT ──────────────────────────────────────────────────────────────────────


def test_ranged_attack_needs_line_of_sight(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    target = engine.state.list_hostiles(player)[0]
    player.position = (2, 2)
    target.position = (4, 2)  # (3, 2) 가 엄폐 기둥이다
    before = target.hp
    engine.actions.apply_attack(player, make_plan("player", "SKILL_2", target.entity_id))
    assert target.hp == before
    assert "시야 없음" in engine.log.entries[-1].outcome


def test_ranged_attack_lands_when_the_line_is_clear(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    target = engine.state.list_hostiles(player)[0]
    player.position = (2, 1)
    target.position = (4, 1)  # 1행은 전부 바닥이다
    engine.actions.apply_attack(player, make_plan("player", "SKILL_2", target.entity_id))
    assert target.hp < target.hp_max


def test_using_a_skill_starts_its_cooldown(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    target = engine.state.list_hostiles(player)[0]
    player.position = (2, 1)
    target.position = (4, 1)
    engine.actions.apply_attack(player, make_plan("player", "SKILL_2", target.entity_id))
    expected = next(s["cooldown"] for s in balance["skills"] if s["id"] == "SKILL_2")
    assert player.cooldowns["SKILL_2"] == expected


def test_a_failed_attack_does_not_start_a_cooldown(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    target = engine.state.list_hostiles(player)[0]
    player.position = (2, 2)
    target.position = (4, 2)
    engine.actions.apply_attack(player, make_plan("player", "SKILL_2", target.entity_id))
    assert player.cooldowns.get("SKILL_2", 0) == 0


def test_move_to_cover_is_no_longer_deferred(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    player.position = (2, 4)
    for index, enemy in enumerate(engine.state.list_hostiles(player)):
        enemy.hp = 0 if index else enemy.hp
        if not index:
            enemy.position = (10, 4)

    grid = VisionGrid(engine.state, engine.state.room.width, engine.state.room.height)
    threats = tuple(e.position for e in engine.state.list_hostiles(player))
    assert find_cover_positions(grid, threats), "이 방에는 엄폐 칸이 있어야 한다"

    engine.actions.apply_move(player, make_plan("player", "MOVE_TO_COVER"))
    assert "미구현" not in engine.log.entries[-1].outcome


def test_move_to_cover_says_so_when_already_hidden(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    player = engine.state.entities["player"]
    hostiles = engine.state.list_hostiles(player)
    for enemy in hostiles[1:]:
        enemy.hp = 0
    hostiles[0].position = (10, 2)
    player.position = (2, 2)

    grid = VisionGrid(engine.state, engine.state.room.width, engine.state.room.height)
    assert not check_exposure(grid, player.position, (hostiles[0].position,))
    engine.actions.apply_move(player, make_plan("player", "MOVE_TO_COVER"))
    assert engine.log.entries[-1].outcome == "이미 엄폐 중"


def test_approach_never_stacks_two_entities_on_one_tile(templates, balance):
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    target = engine.state.list_hostiles(player)[0]
    player.position = (4, 4)
    target.position = (5, 4)
    engine.actions.apply_move(player, make_plan("player", "APPROACH", target.entity_id))
    assert player.position != target.position


# ── SUMMON ───────────────────────────────────────────────────────────────────


def test_summon_creates_a_minion_and_starts_the_cooldown(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    summoner = next(e for e in engine.state.list_actors() if e.kind_id == "goblin_summoner")
    engine.actions.apply_summon(summoner, make_plan(summoner.entity_id, "SUMMON"))

    minions = [e for e in engine.state.list_actors() if e.summoner_id == summoner.entity_id]
    assert len(minions) == 1
    assert summoner.cooldowns["SUMMON"] == SUMMON_EVERY_TICKS


def test_summon_stops_at_the_concurrent_cap(templates, balance):
    engine = build_engine(templates["pillars"], balance, seed=3)
    summoner = next(e for e in engine.state.list_actors() if e.kind_id == "goblin_summoner")
    cap = engine.config.summon_rules[summoner.kind_id]["max_alive"]
    for _ in range(cap + 3):
        engine.actions.apply_summon(summoner, make_plan(summoner.entity_id, "SUMMON"))

    minions = [e for e in engine.state.list_actors() if e.summoner_id == summoner.entity_id]
    assert len(minions) <= cap


def test_a_summoned_minion_fights_with_its_own_ruleset(templates, balance, catalog, enemy_rulesets):
    engine = build_engine(templates["pillars"], balance, seed=3)
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    summoner = next(e for e in engine.state.list_actors() if e.kind_id == "goblin_summoner")
    engine.actions.apply_summon(summoner, make_plan(summoner.entity_id, "SUMMON"))
    engine.register_newcomers()

    minion = next(e for e in engine.state.list_actors() if e.summoner_id == summoner.entity_id)
    assert minion.entity_id in engine.policies


def test_summon_cooldown_lets_the_next_rule_run(templates, balance, catalog, enemy_rulesets):
    # 쿨타임이 배선되지 않으면 [2] SUMMON 이 매 틱 참이라 [3] ATTACK 이 죽은 규칙이 된다.
    engine = build_engine(templates["pillars"], balance, seed=3)
    engine.policies["player"] = build_rule_vm(
        enemy_rulesets["ai_rusher"], catalog, engine.config.kind_types
    )
    assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
    for _ in range(40):
        engine.run_tick()

    summoner_rules = {
        entry.rule
        for entry in engine.log.entries
        if entry.entity_id.startswith("goblin_summoner") and entry.phase == "DECIDE"
    }
    assert {2, 3} <= summoner_rules, "소환과 대안 공격이 모두 돌아야 한다"


# ── 결정론 ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("room_id", ["pillars", "spring_bait"])
def test_the_wired_engine_is_still_reproducible(
    templates, balance, catalog, enemy_rulesets, room_id
):
    def run_once():
        engine = build_engine(templates[room_id], balance, seed=777)
        assign_enemy_policies(engine, balance, catalog, enemy_rulesets)
        from game.app.services.run_battle import run_battle

        return run_battle(engine)

    first, second = run_once(), run_once()
    assert first.log_lines == second.log_lines
