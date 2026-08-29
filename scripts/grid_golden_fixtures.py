"""격자 기준값이 쓰는 표본 격자와 좌표 표기 (게이트 G3).

`export_grid_golden.py` 에서 갈라 나왔다. 여기 있는 것은 **어디를 재는가** — 합성 격자,
탐침 좌표, 그리고 좌표를 JSON 문자열로 옮기는 규칙이다. 실제로 코어를 불러 답을 받아
적는 것은 `export_grid_golden.py` 쪽이다.

좌표를 문자열로 적는 이유는 JSON 객체의 키가 문자열뿐이기 때문이고, 그 표기를 한 곳에
두는 이유는 파이썬과 TS 가 같은 글자를 써야 대조가 성립하기 때문이다.
"""

from dataclasses import dataclass

from game.schemas.room import RoomTemplate, convert_rows_to_tiles

Position = tuple[int, int]

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
