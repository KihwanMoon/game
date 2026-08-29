"""생명의 샘 잔여량 테스트 (GDD §7 회복 타일 어뷰징, 로드맵 W7).

`test_pressure.py` 에서 갈라 나왔다 — 검사 대상 모듈이
`game/app/simulation/springs.py` 로 갈라진 것과 같은 경계다.

총 회복량이 곧 상한인가, 다 쓴 샘이 사라지는가, 초기화가 재충전이 되지 않는가를 본다.
"""

import pytest

from game.app.core.event_log import EventLog
from game.app.core.rng import DeterministicRng
from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PHASE_RESOLVE
from game.app.simulation.springs import (
    DEFAULT_SPRING_POOL,
    apply_spring_drain,
    init_spring_pools,
    list_tiles_of_kind,
    remove_drained_springs,
)
from game.app.simulation.state import WorldState
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import TILE_DOOR, TILE_FLOOR, TILE_SPRING, load_room_templates

SEED = 12345
SPRING_TILE = (6, 4)
OPEN_FIELD_DOORS = ((0, 4), (11, 4))
SMALL_POOL = 5
SPRING_REGEN_PER_TICK = 2
PLAYER_HP = 50


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


def make_state(templates, template_id="open_field", seed=SEED):
    """빈 방 하나를 만든다."""
    return WorldState(room=templates[template_id], rng=DeterministicRng(seed))


def test_spring_pools_start_empty_without_init(templates):
    # 초기화가 없으면 샘이 회복을 한 점도 내지 못한다. 그것이 이 함수의 존재 이유다.
    state = make_state(templates, "spring_bait")
    assert list_tiles_of_kind(state, TILE_SPRING) == (SPRING_TILE,)
    assert state.spring_pools == {}


def test_init_fills_every_spring(templates):
    state = make_state(templates, "spring_bait")
    assert init_spring_pools(state) == 1
    assert state.spring_pools[SPRING_TILE] == DEFAULT_SPRING_POOL


def test_init_does_not_refill_a_used_spring(templates):
    # 방 중간에 다시 부르면 무한 회복이 되어 차단이 무의미해진다.
    state = make_state(templates, "spring_bait")
    init_spring_pools(state, SMALL_POOL)
    apply_spring_drain(state, SPRING_TILE, SMALL_POOL)

    assert init_spring_pools(state, SMALL_POOL) == 0
    assert state.spring_pools[SPRING_TILE] == 0


def test_drain_gives_only_what_remains(templates):
    state = make_state(templates, "spring_bait")
    init_spring_pools(state, SMALL_POOL)

    assert apply_spring_drain(state, SPRING_TILE, 3) == 3
    assert apply_spring_drain(state, SPRING_TILE, 3) == 2
    assert apply_spring_drain(state, SPRING_TILE, 3) == 0
    assert state.spring_pools[SPRING_TILE] == 0


def test_drain_on_a_dry_tile_is_zero(templates):
    state = make_state(templates, "spring_bait")
    assert apply_spring_drain(state, SPRING_TILE, 3) == 0


def test_drained_spring_disappears(templates):
    state = make_state(templates, "spring_bait")
    init_spring_pools(state, SMALL_POOL)
    log = EventLog()

    assert remove_drained_springs(state, log) == ()
    apply_spring_drain(state, SPRING_TILE, SMALL_POOL)

    assert remove_drained_springs(state, log) == (SPRING_TILE,)
    assert state.get_tile(*SPRING_TILE) == TILE_FLOOR
    assert log.entries[-1].phase == PHASE_RESOLVE
    # 소멸한 뒤에는 더 이상 샘 타일이 아니므로 다시 잡히지 않는다.
    assert remove_drained_springs(state, log) == ()


def test_regen_stops_when_the_pool_runs_out(templates, balance):
    # 엔진의 회복 경로를 통해 본다 — 총 회복량이 곧 상한이다 (GDD §7).
    engine = build_engine(templates["spring_bait"], balance, seed=SEED)
    player = engine.state.entities["player"]
    player.position = SPRING_TILE
    player.hp = PLAYER_HP
    # build_engine 이 이미 기본 잔여량을 채웠다. 상한을 보려면 덮어써야 한다 —
    # init_spring_pools 는 값이 있는 좌표를 건드리지 않는다.
    engine.state.spring_pools[SPRING_TILE] = SMALL_POOL

    for _ in range(SMALL_POOL + SPRING_REGEN_PER_TICK):
        engine.state.tick += 1
        engine.run_upkeep()

    assert player.hp == PLAYER_HP + SMALL_POOL
    assert engine.state.spring_pools[SPRING_TILE] == 0


def test_doors_are_not_springs(templates):
    state = make_state(templates)
    assert list_tiles_of_kind(state, TILE_DOOR) == OPEN_FIELD_DOORS
    assert list_tiles_of_kind(state, TILE_SPRING) == ()
