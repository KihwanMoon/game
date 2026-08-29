"""예고 행동을 플레이어가 읽을 수 있는가 (GDD §6.2, design/README.md ThreatNotice).

`test_telegraph.py` 에서 갈라 나왔다 — 앞쪽은 "예고가 규칙대로 터지는가", 여기는 "터지기
전에 인지와 화면에 드러나는가" 다. 드러나지 않으면 회피는 운이 된다 (P1).
"""

import pytest

from game.app.core.event_log import EventLog
from game.app.core.rng import DeterministicRng
from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER, Entity, WorldState
from game.app.simulation.telegraph import (
    DEFAULT_LEAD_TICKS,
    FORESIGHT_FLAG,
    GLYPH_IMMINENT,
    GLYPH_PENDING,
    MIN_LEAD_TICKS,
    PREDICTOR_BONUS_TICKS,
    TONE_DANGER,
    TONE_NEUTRAL,
    VISIBLE_TICKS,
    TelegraphBoard,
    build_threat_notice,
    get_foresight_ticks,
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


# ── 인지 폭과 예측 회로 (GDD §6.2) ──────────────────────────────────────────


def test_telegraph_is_invisible_before_the_window(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, LONG_LEAD_TICKS)
    assert not board.is_marked(BLAST_CENTER)
    assert board.get_remaining(BLAST_CENTER) is None

    run_ticks(board, state, log, LONG_LEAD_TICKS - VISIBLE_TICKS)
    assert board.is_marked(BLAST_CENTER)
    assert board.get_remaining(BLAST_CENTER) == VISIBLE_TICKS


def test_predictor_sees_one_tick_earlier(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, LONG_LEAD_TICKS)
    run_ticks(board, state, log, LONG_LEAD_TICKS - VISIBLE_TICKS - PREDICTOR_BONUS_TICKS)

    assert not board.is_marked(BLAST_CENTER)
    assert board.is_marked(BLAST_CENTER, foresight_ticks=PREDICTOR_BONUS_TICKS)
    assert board.get_remaining(BLAST_CENTER, foresight_ticks=PREDICTOR_BONUS_TICKS) == (
        VISIBLE_TICKS + PREDICTOR_BONUS_TICKS
    )


def test_full_display_telegraph_is_visible_from_registration():
    # GDD §4.2 의 "N틱 전에 붉게 표시" 는 인지 폭을 lead 와 같게 잡은 경우다.
    board = TelegraphBoard()
    board.register(
        "boss",
        "SLAM",
        (BLAST_CENTER,),
        BLAST_DAMAGE,
        LONG_LEAD_TICKS,
        visible_ticks=LONG_LEAD_TICKS,
    )
    assert board.is_marked(BLAST_CENTER)
    assert board.get_remaining(BLAST_CENTER) == LONG_LEAD_TICKS


def test_foresight_comes_from_the_flag(templates):
    state = make_state(templates)
    plain = add_entity(state, "plain", (3, 3))
    seer = add_entity(state, "seer", (4, 3))
    seer.flags[FORESIGHT_FLAG] = True

    assert get_foresight_ticks(plain) == 0
    assert get_foresight_ticks(seer) == PREDICTOR_BONUS_TICKS


def test_marked_tiles_are_sorted_and_deduplicated(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", ((5, 4), (4, 4), (5, 4)), BLAST_DAMAGE, MIN_LEAD_TICKS)
    board.register("boss", "SLAM2", ((4, 4), (3, 4)), BLAST_DAMAGE, MIN_LEAD_TICKS)

    assert board.list_active()[0].tiles == ((4, 4), (5, 4))
    assert board.list_marked() == ((3, 4), (4, 4), (5, 4))
    assert board.list_marked(foresight_ticks=0) == board.list_marked()
    run_ticks(board, state, log, MIN_LEAD_TICKS)
    assert board.list_marked() == ()


def test_nearest_telegraph_wins_on_overlap():
    board = TelegraphBoard()

    board.register("boss", "SLOW", (BLAST_CENTER,), BLAST_DAMAGE, LONG_LEAD_TICKS)
    board.register("boss", "FAST", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)

    # 가장 급한 예고를 낸다 — 더 먼 예고를 보고 안심하면 회피 판단이 늦는다.
    assert board.get_remaining(BLAST_CENTER, foresight_ticks=LONG_LEAD_TICKS) == MIN_LEAD_TICKS


def test_caster_is_reported_as_casting(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    board = TelegraphBoard()
    log = EventLog()

    assert not board.is_casting("boss")
    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, DEFAULT_LEAD_TICKS)
    # 예고 타일이 아직 보이지 않아도 시전 동작은 보인다.
    assert not board.is_marked(BLAST_CENTER)
    assert board.is_casting("boss")

    run_ticks(board, state, log, DEFAULT_LEAD_TICKS)
    assert not board.is_casting("boss")


# ── 경고 배너 (design/README.md ThreatNotice) ───────────────────────────────


def test_threat_notice_is_none_when_safe():
    board = TelegraphBoard()
    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, MIN_LEAD_TICKS)
    assert build_threat_notice(board, SAFE_TILE) is None


def test_threat_notice_carries_remaining_ticks(templates):
    state = make_state(templates)
    add_entity(state, "boss", (7, 4), FACTION_ENEMY)
    board = TelegraphBoard()
    log = EventLog()

    board.register("boss", "SLAM", (BLAST_CENTER,), BLAST_DAMAGE, LONG_LEAD_TICKS)
    pending = build_threat_notice(board, BLAST_CENTER, foresight_ticks=LONG_LEAD_TICKS)
    assert pending.ticks == LONG_LEAD_TICKS
    assert pending.tone == TONE_NEUTRAL
    assert pending.glyph == GLYPH_PENDING

    run_ticks(board, state, log, LONG_LEAD_TICKS - 1)
    imminent = build_threat_notice(board, BLAST_CENTER)
    assert imminent.ticks == 1
    assert imminent.tone == TONE_DANGER
    assert imminent.glyph == GLYPH_IMMINENT
    assert "1" in imminent.text
