"""텔레그래프(예고 공격) 테스트 (GDD §4.2, TDD §4.1 페이즈 2).

핵심은 두 가지다 — 예고 타일 위에 남아 있으면 맞고 비켜서면 안 맞는가, 그리고
같은 시드가 같은 결과를 내는가(R5). 앞은 회피 규칙이 성립하는지를, 뒤는 그 결과가
리플레이로 재현되는지를 본다.
"""

import pytest

from game.app.core.event_log import EventLog
from game.app.core.rng import DeterministicRng
from game.app.simulation.plan import PHASE_TELEGRAPH
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.app.simulation.telegraph import (
    DEFAULT_LEAD_TICKS,
    MIN_LEAD_TICKS,
    TelegraphBoard,
    build_blast_tiles,
)
from game.config import ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

BLAST_DAMAGE = 7
START_HP = 30
SAFE_TILE = (2, 6)
BLAST_CENTER = (5, 4)
LONG_LEAD_TICKS = 3


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


def make_state(templates, seed=12345):
    """빈 open_field 방 하나를 만든다."""
    return WorldState(room=templates["open_field"], rng=DeterministicRng(seed))


def add_entity(state, entity_id, position, faction=FACTION_PLAYER):
    """테스트용 엔티티를 방에 놓는다."""
    entity = Entity(
        entity_id=entity_id,
        kind_id="dummy",
        faction=faction,
        position=position,
        hp=START_HP,
        hp_max=START_HP,
        attack=5,
        defense=2,
        attack_range=1,
        initiative=10,
    )
    state.entities[entity_id] = entity
    return entity


def run_ticks(board, state, log, count):
    """count 틱만큼 TELEGRAPH 페이즈를 돌린다."""
    fired = []
    for _ in range(count):
        state.tick += 1
        fired.extend(board.run_countdown(state, log))
    return tuple(fired)


# ── 카운트다운과 발동 ────────────────────────────────────────────────────────


def test_telegraph_fires_after_lead_ticks(templates):
    state = make_state(templates)
    boss = add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    victim = add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register(boss.entity_id, "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, DEFAULT_LEAD_TICKS)

    # 예고를 낸 틱에는 터지지 않는다. 회피할 틈이 곧 예고의 존재 이유다.
    run_ticks(board, state, log, DEFAULT_LEAD_TICKS - 1)
    assert victim.hp == START_HP
    assert board.list_active()

    fired = run_ticks(board, state, log, 1)
    assert len(fired) == 1
    assert victim.hp == START_HP - BLAST_DAMAGE
    assert board.list_active() == ()


def test_dodged_entity_takes_no_damage(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    stayer = add_entity(state, "stayer", BLAST_CENTER)
    dodger = add_entity(state, "dodger", (4, 4))
    board = TelegraphBoard()
    log = EventLog()

    tiles = build_blast_tiles(BLAST_CENTER, 1)
    board.register("boss", "SLAM", tiles, BLAST_DAMAGE, DEFAULT_LEAD_TICKS)

    run_ticks(board, state, log, DEFAULT_LEAD_TICKS - 1)
    dodger.position = SAFE_TILE  # 반경 밖으로 비켜선다

    run_ticks(board, state, log, 1)
    assert stayer.hp == START_HP - BLAST_DAMAGE
    assert dodger.hp == START_HP


def test_blast_hits_every_faction_on_the_tile(templates):
    # 예고는 좌표에 떨어진다. 시전자의 아군도 맞아야 통로 유인이 전술이 된다.
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    ally = add_entity(state, "minion", BLAST_CENTER, FACTION_ENEMY)
    hero = add_entity(state, "hero", (5, 5))
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", build_blast_tiles(BLAST_CENTER, 1), BLAST_DAMAGE, MIN_LEAD_TICKS)
    run_ticks(board, state, log, MIN_LEAD_TICKS)

    assert ally.hp == START_HP - BLAST_DAMAGE
    assert hero.hp == START_HP - BLAST_DAMAGE


def test_empty_blast_is_logged_as_dodge(templates):
    # 아무 일도 없었다는 사실이 규칙표를 고칠 때 가장 필요한 정보다 (P1).
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    run_ticks(board, state, log, MIN_LEAD_TICKS)

    lines = [e for e in log.entries if e.phase == PHASE_TELEGRAPH]
    assert len(lines) == 1
    assert "회피" in lines[0].outcome
    assert lines[0].delta is None


def test_blast_logs_damage_delta(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    run_ticks(board, state, log, MIN_LEAD_TICKS)

    entry = log.entries[-1]
    assert entry.phase == PHASE_TELEGRAPH
    assert entry.entity_id == "boss"
    assert entry.delta == -BLAST_DAMAGE


def test_lead_ticks_never_drops_below_minimum(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    victim = add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, 0)
    assert board.list_active()[0].remaining_ticks == MIN_LEAD_TICKS
    run_ticks(board, state, log, MIN_LEAD_TICKS)
    assert victim.hp == START_HP - BLAST_DAMAGE


def test_damage_ignores_defense(templates):
    # 방어력으로 버틸 수 있으면 `위험 예고 타일 위에 있는가` 가 전술이 아니게 된다.
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    tank = add_entity(state, "tank", BLAST_CENTER)
    tank.defense = 999
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    run_ticks(board, state, log, MIN_LEAD_TICKS)
    assert tank.hp == START_HP - BLAST_DAMAGE


def test_hp_never_goes_below_zero(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    victim = add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), START_HP * 2, MIN_LEAD_TICKS)
    run_ticks(board, state, log, MIN_LEAD_TICKS)
    assert victim.hp == 0
    assert not victim.is_alive


# ── 시전자 사망 ─────────────────────────────────────────────────────────────


def test_caster_death_cancels_telegraph(templates):
    # 시전자를 먼저 죽이는 것도 예고에 대한 정답이어야 한다.
    state = make_state(templates)
    boss = add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    victim = add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, LONG_LEAD_TICKS)
    run_ticks(board, state, log, 1)
    boss.hp = 0

    run_ticks(board, state, log, LONG_LEAD_TICKS)
    assert victim.hp == START_HP
    assert board.list_active() == ()
    assert log.entries[-1].outcome == "시전자 사망"


def test_unstoppable_telegraph_fires_after_caster_death(templates):
    state = make_state(templates)
    boss = add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    victim = add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register(
        "boss",
        "SELF_DESTRUCT",
        (BLAST_CENTER,),
        BLAST_DAMAGE,
        DEFAULT_LEAD_TICKS,
        cancel_on_death=False,
    )
    boss.hp = 0
    run_ticks(board, state, log, DEFAULT_LEAD_TICKS)
    assert victim.hp == START_HP - BLAST_DAMAGE


# ── 폭발 범위 ───────────────────────────────────────────────────────────────


def test_blast_tiles_use_manhattan_radius():
    tiles = build_blast_tiles((5, 4), 1)
    assert tiles == ((4, 4), (5, 3), (5, 4), (5, 5), (6, 4))
    # 대각은 맨해튼 거리 2 라 반경 1 에 들지 않는다 (F-5 결정).
    assert (4, 3) not in tiles


def test_blast_tiles_of_radius_zero_is_one_cell():
    assert build_blast_tiles((5, 4), 0) == ((5, 4),)


# ── 결정론 (R5) ─────────────────────────────────────────────────────────────


def create_scenario(templates, seed):
    """시드로 폭발 지점을 골라 3틱 돌리고 로그와 HP 를 돌려준다."""
    state = make_state(templates, seed)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    for index in range(3):
        add_entity(state, f"hero_{index}", (3 + index, 4))
    board = TelegraphBoard()
    log = EventLog()

    candidates = ((3, 4), (4, 4), (5, 4))
    for _ in range(2):
        center = state.rng.get_choice(candidates)
        board.register("boss", "SLAM", build_blast_tiles(center, 1), BLAST_DAMAGE, MIN_LEAD_TICKS)
        run_ticks(board, state, log, 1)
    hp_map = tuple((e.entity_id, e.hp) for e in state.list_actors())
    return log.format_lines(), hp_map


def test_same_seed_gives_same_result(templates):
    assert create_scenario(templates, 12345) == create_scenario(templates, 12345)


def test_telegraph_id_is_stable_across_runs():
    first = TelegraphBoard()
    second = TelegraphBoard()
    for board in (first, second):
        board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
        board.register("boss", "SLAM", (SAFE_TILE,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    ids = [t.telegraph_id for t in first.list_active()]
    assert ids == [t.telegraph_id for t in second.list_active()]
    assert len(set(ids)) == len(ids)


def test_simultaneous_blasts_fire_in_registration_order(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    add_entity(state, "victim", BLAST_CENTER)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "FIRST", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    board.register("boss", "SECOND", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    fired = run_ticks(board, state, log, MIN_LEAD_TICKS)

    assert [t.skill_id for t in fired] == ["FIRST", "SECOND"]
    assert [e.expr.split()[0] for e in log.entries] == ["FIRST", "SECOND"]
