"""격자·길찾기·시야의 기준값을 JSON 으로 내보낸다 (게이트 G3).

Phase 3 의 TypeScript 코어는 파이썬 코어와 같은 답을 내야 한다. 눈으로 대조하면 회귀를
놓치므로 파이썬 쪽 출력을 파일로 고정해 두고 TS 테스트가 그 파일을 읽어 대조한다.
기준의 정본은 언제나 파이썬 코어다.

여기 담기는 것은 순서가 결과를 가르는 자리들이다 — 거리장의 BFS 방문 순서, 같은 거리의
이웃 중 어느 쪽을 고르는가, 가시 좌표의 행 우선 정렬, 엄폐 후보의 동률 처리. 값 하나가
아니라 순서가 어긋나도 잡히도록 목록을 통째로 적는다 (R5).

격자는 타일 ID 배열을 그대로 실어 자족적으로 만든다. TS 쪽이 legend 를 다시 해석하면
대조 대상이 아니라 대조 도구가 갈라질 수 있기 때문이다.

    uv run python -m scripts.export_grid_golden
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from game.app.core.rng import DeterministicRng
from game.app.grid.geometry import (
    NEIGHBOR_OFFSETS,
    STEP_OFFSETS,
    get_manhattan_distance,
    iter_neighbors,
    iter_steps,
)
from game.app.grid.vision import (
    VisionGrid,
    build_visibility_map,
    calculate_cover_distance,
    check_cover,
    check_exposure,
    find_cover_positions,
    find_nearest_cover,
    list_visible_positions,
)
from game.app.pathfinding.distance_field import build_distance_field, find_next_step
from game.app.simulation.state import WorldState
from game.config import ROOM_TEMPLATES_PATH
from game.schemas.room import RoomTemplate, convert_rows_to_tiles, load_room_templates

Position = tuple[int, int]

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/golden/grid_golden.json"

# 거리장은 세계 상태를 통해 타일을 읽는다. 이 스크립트는 난수를 쓰지 않지만 WorldState 가
# 난수원을 요구하므로 고정 시드를 넣는다.
RNG_SEED = 0

# templates.json 의 legend 와 같은 값. 합성 격자를 그 파일과 같은 글자로 그리기 위한 것이다.
LEGEND = {".": 0, "#": 1, "B": 2, ",": 3, "D": 4, "F": 5, "S": 6, "L": 7, "T": 8, "O": 9}

# 룸 템플릿에 없는 타일을 확인하려고 손으로 그린 격자. 가시덤불(,)은 시야를 막지 않고
# 파괴 가능 벽(B)은 막는다 — 둘을 한 화면에 놓아야 그 차이가 대조에 남는다.
SYNTHETIC_ROWS = {
    "thorn_line": (
        "############",
        "#..........#",
        "#,,,,,,,,,,#",
        "#..........#",
        "#....D.....#",
        "#..........#",
        "#,,,,,,,,,,#",
        "#..........#",
        "############",
    ),
    "breakable_wall": (
        "############",
        "#....B.....#",
        "#....B.....#",
        "#....B.....#",
        "#....B..D..#",
        "#....B.....#",
        "#..........#",
        "#....O.....#",
        "############",
    ),
}

# 합성 격자의 시작점·위협·목표. 방마다 다르게 두면 대조가 격자별로 따로 갈라진다.
SYNTHETIC_SPAWN = (1, 4)
SYNTHETIC_THREATS = ((10, 1), (10, 7))
SYNTHETIC_GOALS = ((8, 4),)

# 모든 격자에 같은 시점을 넣어 본다. 벽 안·모서리·한가운데를 섞었다.
PROBE_ORIGINS: tuple[Position, ...] = ((1, 1), (1, 4), (5, 4), (10, 7))

# 사거리 제한 표본. None 은 방 전체다.
PROBE_RANGES: tuple[int | None, ...] = (None, 4)

# 거리장 내리막을 물어볼 자리. 목표 위·닿을 수 없는 벽 안도 넣는다.
PROBE_STEPS: tuple[Position, ...] = ((1, 1), (1, 4), (5, 4), (6, 2), (10, 7), (0, 0))

# 좌표 연산 표본. 음수와 같은 좌표를 포함한다.
MANHATTAN_PAIRS: tuple[tuple[Position, Position], ...] = (
    ((0, 0), (0, 0)),
    ((0, 0), (3, 4)),
    ((3, 4), (0, 0)),
    ((-2, 5), (5, -2)),
    ((11, 8), (1, 4)),
)

# 이웃 나열 표본.
OFFSET_ORIGINS: tuple[Position, ...] = ((0, 0), (5, 4), (-1, -1), (11, 8))


@dataclass(frozen=True)
class GridCase:
    """대조할 격자 하나와 그 위에서 물어볼 것들."""

    name: str
    template: RoomTemplate
    threats: tuple[Position, ...]
    goals: tuple[Position, ...]


def format_position(position: Position) -> str:
    """좌표를 `x,y` 키 문자열로 바꾼다.

    배열 대신 문자열로 적는 이유는 두 가지다. indent 를 준 JSON 에서 두 원소 배열이
    네 줄로 벌어져 파일이 열 배로 커지고, TS 쪽이 좌표를 집합·대응표에 넣을 때 쓰는
    키가 정확히 이 형식이라 대조 시 변환이 한 번 줄어든다.

    Args:
        position: 바꿀 좌표.

    Returns:
        `x,y` 형태의 문자열.
    """
    return f"{position[0]},{position[1]}"


def format_positions(positions: tuple[Position, ...]) -> list[str]:
    """좌표들을 키 문자열 목록으로 바꾼다.

    Args:
        positions: 바꿀 좌표들.

    Returns:
        `x,y` 문자열의 목록. 받은 순서를 그대로 지킨다.
    """
    return [format_position(position) for position in positions]


def build_synthetic_template(name: str, rows: tuple[str, ...]) -> RoomTemplate:
    """합성 격자를 룸 템플릿으로 만든다.

    Args:
        name: 템플릿 id.
        rows: 한 글자가 한 칸인 행들.

    Returns:
        적 스폰이 없는 템플릿.
    """
    return RoomTemplate(
        template_id=name,
        purpose="골든 대조용 합성 격자",
        tiles=convert_rows_to_tiles(list(rows), LEGEND),
        player_spawn=SYNTHETIC_SPAWN,
        enemy_spawns=(),
    )


def build_grid_cases() -> tuple[GridCase, ...]:
    """대조할 격자 목록을 만든다.

    Returns:
        룸 템플릿 전부와 합성 격자들.
    """
    cases = [
        GridCase(
            name=template.template_id,
            template=template,
            threats=tuple(spawn.position for spawn in template.enemy_spawns),
            goals=tuple(spawn.position for spawn in template.enemy_spawns),
        )
        for template in load_room_templates(ROOM_TEMPLATES_PATH)
    ]
    cases.extend(
        GridCase(
            name=name,
            template=build_synthetic_template(name, rows),
            threats=SYNTHETIC_THREATS,
            goals=SYNTHETIC_GOALS,
        )
        for name, rows in SYNTHETIC_ROWS.items()
    )
    return tuple(cases)


def build_geometry_cases() -> dict[str, Any]:
    """방향과 거리의 기준값을 만든다.

    Returns:
        오프셋 순서와 거리·이웃 표본.
    """
    return {
        "step_offsets": [list(offset) for offset in STEP_OFFSETS],
        "neighbor_offsets": [list(offset) for offset in NEIGHBOR_OFFSETS],
        "manhattan": [
            {
                "origin": format_position(origin),
                "target": format_position(target),
                "distance": get_manhattan_distance(origin, target),
            }
            for origin, target in MANHATTAN_PAIRS
        ],
        "steps": [
            {"origin": format_position(origin), "cells": format_positions(iter_steps(origin))}
            for origin in OFFSET_ORIGINS
        ],
        "neighbors": [
            {"origin": format_position(origin), "cells": format_positions(iter_neighbors(origin))}
            for origin in OFFSET_ORIGINS
        ],
    }


def build_visibility_cases(grid: VisionGrid) -> list[dict[str, Any]]:
    """시점별 가시성 맵을 만든다.

    Args:
        grid: 타일을 읽을 격자.

    Returns:
        시점·사거리와 보이는 칸들(행 우선)의 목록.
    """
    return [
        {
            "origin": format_position(origin),
            "max_range": max_range,
            "visible": format_positions(
                list_visible_positions(build_visibility_map(grid, origin, max_range))
            ),
        }
        for origin in PROBE_ORIGINS
        for max_range in PROBE_RANGES
    ]


def build_exposure_cases(grid: VisionGrid, threats: tuple[Position, ...]) -> list[dict[str, Any]]:
    """노출·엄폐 판정을 만든다.

    Args:
        grid: 타일을 읽을 격자.
        threats: 위협 좌표들.

    Returns:
        칸별 노출 여부와 엄폐 여부.
    """
    return [
        {
            "position": format_position(origin),
            "is_exposed": check_exposure(grid, origin, threats),
            "is_covered": check_cover(grid, origin, threats),
        }
        for origin in PROBE_ORIGINS
    ]


def build_cover_cases(grid: VisionGrid, threats: tuple[Position, ...]) -> dict[str, Any]:
    """엄폐 후보와 가장 가까운 엄폐 칸을 만든다.

    점유 칸이 있는 경우도 함께 낸다. 후보에서 한 칸이 빠지면 동률 처리가 다른 답을
    고르므로, 그 갈림이 대조에 남아야 한다.

    Args:
        grid: 타일을 읽을 격자.
        threats: 위협 좌표들.

    Returns:
        점유 없는 경우와 위협 칸을 점유로 넣은 경우의 결과.
    """
    occupied = frozenset(threats)
    return {
        "threats": format_positions(threats),
        "occupied": format_positions(threats),
        "positions": format_positions(find_cover_positions(grid, threats)),
        "positions_with_occupied": format_positions(find_cover_positions(grid, threats, occupied)),
        "nearest": [
            {
                "origin": format_position(origin),
                "position": _format_optional_position(find_nearest_cover(grid, origin, threats)),
                "distance": calculate_cover_distance(grid, origin, threats),
                "position_with_occupied": _format_optional_position(
                    find_nearest_cover(grid, origin, threats, occupied)
                ),
                "distance_with_occupied": calculate_cover_distance(grid, origin, threats, occupied),
            }
            for origin in PROBE_ORIGINS
        ],
    }


def _format_optional_position(position: Position | None) -> str | None:
    """좌표가 있으면 키 문자열로, 없으면 None 으로 바꾼다.

    Args:
        position: 바꿀 좌표. 없을 수 있다.

    Returns:
        `x,y` 문자열 또는 None.
    """
    return None if position is None else format_position(position)


def build_distance_field_cases(
    state: WorldState, goals: tuple[Position, ...], blocked: tuple[Position, ...]
) -> dict[str, Any]:
    """거리장 하나와 그 위의 내리막 한 걸음을 만든다.

    entries 는 BFS 방문 순서 그대로다. 값만 같고 순서가 다르면 같은 구현이 아니다 (R5).

    Args:
        state: 타일을 읽을 세계 상태.
        goals: 거리 0 이 되는 목표 칸들.
        blocked: 통행 불가로 취급할 추가 칸.

    Returns:
        목표·차단 칸과 거리장 항목, 내리막 결과.
    """
    field = build_distance_field(state, goals, frozenset(blocked))
    return {
        "goals": format_positions(goals),
        "blocked": format_positions(blocked),
        "entries": [
            {"cell": format_position(cell), "distance": distance}
            for cell, distance in field.items()
        ],
        "next_steps": [
            {
                "origin": format_position(origin),
                "step": _format_optional_position(find_next_step(field, origin)),
            }
            for origin in PROBE_STEPS
        ],
    }


def build_grid_document(case: GridCase) -> dict[str, Any]:
    """격자 하나의 기준값 전체를 만든다.

    Args:
        case: 대조할 격자와 질문들.

    Returns:
        타일과 시야·엄폐·거리장 결과를 담은 딕셔너리.
    """
    template = case.template
    grid = VisionGrid(template, template.width, template.height)
    state = WorldState(room=template, rng=DeterministicRng(RNG_SEED))
    return {
        "name": case.name,
        "width": template.width,
        "height": template.height,
        "tiles": [list(row) for row in template.tiles],
        "visibility": build_visibility_cases(grid),
        "exposure": build_exposure_cases(grid, case.threats),
        "cover": build_cover_cases(grid, case.threats),
        "distance_fields": [
            build_distance_field_cases(state, case.goals, ()),
            build_distance_field_cases(state, case.goals, case.threats),
        ],
    }


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    return {
        "_comment": [
            "파이썬 코어(grid·pathfinding)에서 생성한 기준값이다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_grid_golden",
            "좌표는 `x,y` 문자열이다. 좌표 목록은 순서까지 기준이다 — 값이 같아도 순서가",
            "다르면 구현이 갈라진 것이다. 거리장 entries 는 BFS 방문 순서 그대로다.",
        ],
        "geometry": build_geometry_cases(),
        "grids": [build_grid_document(case) for case in build_grid_cases()],
    }


def export_grid_golden(target_path: Path) -> Path:
    """기준값을 파일로 쓴다.

    Args:
        target_path: 쓸 경로. 상위 디렉터리가 없으면 만든다.

    Returns:
        쓴 경로.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    document = build_golden_document()
    target_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return target_path


def main() -> None:
    """기준값을 기본 경로에 내보낸다."""
    written = export_grid_golden(GOLDEN_PATH)
    print(f"기준값을 썼다: {written}")


if __name__ == "__main__":
    main()
