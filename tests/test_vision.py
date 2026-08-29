"""시야(LOS) 시스템 테스트 (GDD §4.1·§4.4, TDD §5.4).

실제 룸 템플릿(pillars·corridor·open_field)의 격자에서 시야가 막히고 뚫리는 것을
확인한다. 합성 격자는 템플릿에 없는 타일(가시덤불·파괴 가능 벽)에만 쓴다.
"""

import pytest

from game.app.core.rng import DeterministicRng
from game.app.grid.geometry import get_manhattan_distance
from game.app.grid.vision import (
    NO_COVER_DISTANCE,
    VisibilityMap,
    VisionCache,
    VisionGrid,
    build_visibility_map,
    calculate_cover_distance,
    check_cover,
    check_exposure,
    check_line_of_sight,
    check_visibility,
    find_cover_positions,
    find_nearest_cover,
    is_blocking_tile,
    list_visible_positions,
)
from game.app.simulation.state import WorldState
from game.config import ROOM_TEMPLATES_PATH
from game.schemas.room import (
    TILE_BREAKABLE_WALL,
    TILE_COVER,
    TILE_FLOOR,
    TILE_THORNS,
    TILE_WALL,
    WALKABLE_TILES,
    RoomTemplate,
    convert_rows_to_tiles,
    load_room_templates,
)

# templates.json 의 legend 와 같은 값. 합성 격자를 그 파일과 같은 글자로 그리기 위한 것이다.
LEGEND = {".": 0, "#": 1, "B": 2, ",": 3, "D": 4, "F": 5, "S": 6, "L": 7, "T": 8, "O": 9}

# pillars 의 기둥 좌표와 적 스폰. 방을 고쳐 이 값이 달라지면 테스트가 먼저 깨져야 한다.
PILLAR_ARCHER = (10, 2)
PILLAR_SUMMONER = (9, 4)


@pytest.fixture(scope="module")
def templates():
    return {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}


def wrap_template(template):
    return VisionGrid(template, template.width, template.height)


def make_grid(rows):
    template = RoomTemplate(
        template_id="synthetic",
        purpose="테스트용 합성 격자",
        tiles=convert_rows_to_tiles(rows, LEGEND),
        player_spawn=(1, 1),
        enemy_spawns=(),
    )
    return wrap_template(template)


def list_walkable(grid):
    return [
        (x, y)
        for y in range(grid.height)
        for x in range(grid.width)
        if grid.get_tile(x, y) in WALKABLE_TILES
    ]


# ── 무엇이 시야를 막는가 (GDD §4.4) ──────────────────────────────────────────


def test_blocking_tiles_are_wall_breakable_and_cover():
    assert is_blocking_tile(TILE_WALL)
    assert is_blocking_tile(TILE_BREAKABLE_WALL)
    assert is_blocking_tile(TILE_COVER)
    assert not is_blocking_tile(TILE_FLOOR)
    assert not is_blocking_tile(TILE_THORNS)


def test_thorns_do_not_block_line_of_sight():
    # 가시덤불은 이동만 늦춘다. 여기서 막으면 "느려지지만 보인다"는 설계가 사라진다.
    grid = make_grid(["#######", "#.,,,.#", "#######"])
    assert check_line_of_sight(grid, (1, 1), (5, 1))


def test_breakable_wall_blocks_until_destroyed():
    grid = make_grid(["#######", "#..B..#", "#######"])
    assert not check_line_of_sight(grid, (1, 1), (5, 1))


def test_destroyed_wall_opens_line_of_sight():
    # WorldState 의 타일 덮어쓰기를 읽는 경로. 벽을 부순 뒤 시야가 열려야 한다.
    template = RoomTemplate(
        template_id="synthetic",
        purpose="파괴 가능 벽",
        tiles=convert_rows_to_tiles(["#######", "#..B..#", "#######"], LEGEND),
        player_spawn=(1, 1),
        enemy_spawns=(),
    )
    state = WorldState(room=template, rng=DeterministicRng(1))
    grid = VisionGrid(state, template.width, template.height)
    assert not check_line_of_sight(grid, (1, 1), (5, 1))
    state.tile_overrides[(3, 1)] = TILE_FLOOR
    assert check_line_of_sight(grid, (1, 1), (5, 1))


# ── 실제 룸 템플릿에서의 차단·관통 ───────────────────────────────────────────


def test_corridor_wall_blocks_line_of_sight(templates):
    # corridor 의 y=3 행은 가운데 벽 두 칸(x=5,6)이 막고 있다.
    grid = wrap_template(templates["corridor"])
    assert not check_line_of_sight(grid, (1, 3), (9, 3))
    assert not check_line_of_sight(grid, (1, 3), (9, 6))


def test_corridor_open_row_keeps_line_of_sight(templates):
    # y=4 는 방을 가로지르는 유일한 통로다. 여기서만 사격형이 반대편을 본다.
    grid = wrap_template(templates["corridor"])
    assert check_line_of_sight(grid, (1, 4), (10, 4))


def test_pillars_cover_blocks_line_of_sight(templates):
    grid = wrap_template(templates["pillars"])
    # (3,2) 기둥이 좌우를 끊는다.
    assert not check_line_of_sight(grid, (2, 2), (4, 2))
    # (5,4)·(6,4) 가운데 기둥 쌍이 방을 가로지르는 사선을 끊는다.
    assert not check_line_of_sight(grid, (4, 4), (7, 4))
    # 같은 행이라도 기둥이 없는 y=3 은 뚫린다.
    assert check_line_of_sight(grid, (2, 3), (9, 3))


def test_line_of_sight_to_self_is_open(templates):
    grid = wrap_template(templates["pillars"])
    assert check_line_of_sight(grid, (1, 4), (1, 4))


def test_line_of_sight_is_symmetric(templates):
    # A 가 B 를 보면 B 도 A 를 봐야 한다. 깨지면 규칙표로 설명할 수 없는 피격이 생긴다.
    for name in ("pillars", "corridor", "spring_bait"):
        grid = wrap_template(templates[name])
        cells = list_walkable(grid)
        for origin in cells:
            for target in cells:
                forward = check_line_of_sight(grid, origin, target)
                backward = check_line_of_sight(grid, target, origin)
                assert forward == backward, f"{name}: {origin}<->{target}"


# ── 가시성 맵 사전 계산과 조회 (TDD §5.4) ────────────────────────────────────


def test_visibility_map_matches_direct_check(templates):
    grid = wrap_template(templates["pillars"])
    origin = (1, 4)
    vision_map = build_visibility_map(grid, origin)
    for y in range(grid.height):
        for x in range(grid.width):
            expected = check_line_of_sight(grid, origin, (x, y))
            assert check_visibility(vision_map, (x, y)) is expected


def test_visibility_map_respects_max_range(templates):
    grid = wrap_template(templates["open_field"])
    origin = (5, 4)
    limited = build_visibility_map(grid, origin, max_range=3)
    for position in list_visible_positions(limited):
        assert get_manhattan_distance(origin, position) <= 3
    # (1,4) 는 맨해튼 4 라 사거리 3 의 맵에서는 빠지고, 사거리 없는 맵에서는 보인다.
    assert check_visibility(limited, (1, 4)) is False
    assert check_visibility(build_visibility_map(grid, origin), (1, 4)) is True


def test_visible_positions_are_row_major_ordered():
    vision_map = VisibilityMap(origin=(0, 0), visible=frozenset({(2, 1), (0, 0), (1, 1), (3, 0)}))
    assert list_visible_positions(vision_map) == ((0, 0), (3, 0), (1, 1), (2, 1))


# ── 관측자별 캐시 갱신 ───────────────────────────────────────────────────────


def test_vision_cache_reuses_map_while_viewer_stands_still(templates):
    cache = VisionCache(grid=wrap_template(templates["pillars"]))
    first = cache.register("e1", (1, 4))
    assert cache.refresh("e1", (1, 4)) is first


def test_vision_cache_recomputes_after_move(templates):
    cache = VisionCache(grid=wrap_template(templates["pillars"]))
    first = cache.register("e1", (1, 4))
    moved = cache.refresh("e1", (2, 4))
    assert moved is not first
    assert moved.origin == (2, 4)
    assert cache.read("e1") is moved


def test_vision_cache_answers_visibility(templates):
    cache = VisionCache(grid=wrap_template(templates["corridor"]))
    cache.register("archer", (10, 4))
    assert cache.check("archer", (1, 4)) is True
    assert cache.check("archer", (1, 3)) is False


def test_vision_cache_refuses_unknown_viewer(templates):
    # 등록되지 않은 관측자를 False 로 답하면 버그와 정상 판정이 구분되지 않는다.
    cache = VisionCache(grid=wrap_template(templates["pillars"]))
    assert cache.read("ghost") is None
    with pytest.raises(KeyError):
        cache.check("ghost", (1, 4))


def test_vision_cache_drops_dead_viewer(templates):
    cache = VisionCache(grid=wrap_template(templates["pillars"]))
    cache.register("e1", (1, 4))
    cache.drop("e1")
    cache.drop("e1")
    assert cache.read("e1") is None


# ── 엄폐 판정과 MOVE_TO_COVER 목표 ───────────────────────────────────────────


def test_cover_positions_are_hidden_from_every_threat(templates):
    grid = wrap_template(templates["pillars"])
    threats = (PILLAR_ARCHER, PILLAR_SUMMONER)
    covered = find_cover_positions(grid, threats)
    assert covered
    for position in covered:
        assert check_cover(grid, position, threats)
        assert not check_exposure(grid, position, threats)


def test_cover_positions_are_complete(templates):
    # 엄폐 칸 목록에 빠진 칸은 전부 실제로 노출돼 있어야 한다.
    grid = wrap_template(templates["pillars"])
    threats = (PILLAR_ARCHER,)
    covered = set(find_cover_positions(grid, threats))
    for position in list_walkable(grid):
        if position not in covered:
            assert check_exposure(grid, position, threats)


def test_open_field_offers_no_cover(templates):
    # 이 방의 존재 이유가 "엄폐가 없어 포위가 성립한다" 이다. 엄폐가 생기면 설계가 깨진다.
    grid = wrap_template(templates["open_field"])
    threats = ((9, 2),)
    assert find_cover_positions(grid, threats) == ()
    assert find_nearest_cover(grid, (1, 4), threats) is None
    assert calculate_cover_distance(grid, (1, 4), threats) == NO_COVER_DISTANCE


def test_cover_needs_a_threat(templates):
    grid = wrap_template(templates["pillars"])
    assert check_exposure(grid, (1, 4), ()) is False
    assert check_cover(grid, (1, 4), ()) is True
    assert find_cover_positions(grid, ()) == ()


def test_nearest_cover_is_the_closest_hidden_cell(templates):
    grid = wrap_template(templates["corridor"])
    origin = (1, 4)
    threats = ((10, 4),)
    assert check_exposure(grid, origin, threats)
    nearest = find_nearest_cover(grid, origin, threats)
    distance = calculate_cover_distance(grid, origin, threats)
    assert nearest is not None
    assert distance == get_manhattan_distance(origin, nearest)
    assert distance == min(
        get_manhattan_distance(origin, position) for position in find_cover_positions(grid, threats)
    )


def test_cover_distance_is_zero_when_already_hidden(templates):
    grid = wrap_template(templates["pillars"])
    threats = (PILLAR_ARCHER,)
    assert check_cover(grid, (1, 4), threats)
    assert calculate_cover_distance(grid, (1, 4), threats) == 0


def test_occupied_cells_are_not_offered_as_cover(templates):
    grid = wrap_template(templates["corridor"])
    origin = (1, 4)
    threats = ((10, 4),)
    taken = find_nearest_cover(grid, origin, threats)
    assert taken is not None
    later = find_nearest_cover(grid, origin, threats, occupied=frozenset({taken}))
    assert later is not None
    assert later != taken
