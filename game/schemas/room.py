"""룸 템플릿 — 손으로 그린 12x9 그리드 (GDD §4.4, TDD §7.2).

템플릿 JSON 은 사람이 그리는 자리라 ASCII 로 적혀 있다. 런타임 형식은 TDD §3.4 가
정한 숫자 배열이며 이 모듈이 legend 로 변환한다.

TDD §7.2 는 생성 직후 flood fill 로 `시작점 -> 모든 문` 도달 가능성을 확인하고 실패 시
재생성하라고 요구한다. 손으로 그린 템플릿도 같은 검사를 받아야 한다 — 벽 하나 잘못
찍으면 클리어 불가능한 방이 되고, 그것은 규칙 설계 실패와 구분되지 않는다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

TILE_FLOOR = 0
TILE_WALL = 1
TILE_BREAKABLE_WALL = 2
TILE_THORNS = 3
TILE_DOOR = 4
TILE_SPRING = 5
TILE_STAIRS = 6
TILE_LAVA = 7
TILE_TRAP = 8
TILE_COVER = 9

# 진입 시점에 지나갈 수 있는 타일. 파괴 가능 벽(2)은 부수기 전에는 막혀 있으므로
# 도달성 검사에서 통로로 세지 않는다 — 통로로 세면 부술 수단이 없는 규칙표가 갇힌다.
WALKABLE_TILES = frozenset(
    {TILE_FLOOR, TILE_THORNS, TILE_DOOR, TILE_SPRING, TILE_STAIRS, TILE_LAVA, TILE_TRAP}
)

# 상하좌우만 센다. 대각 이동이 허용되더라도 4방향으로 닿으면 8방향으로도 닿으므로
# 이쪽이 더 엄격한 검사다. 이동 방향 수는 아직 정해지지 않았다 (W1 에서 확정).
STEP_OFFSETS = ((0, -1), (0, 1), (-1, 0), (1, 0))

# 층 번호는 1부터 센다. min_floor 의 기본값이자 층 깊이 스케일의 기준이며
# (simulation/scaling.py), 두 곳이 각자 1 을 적으면 한쪽만 고쳐질 수 있다.
FIRST_FLOOR = 1


@dataclass(frozen=True)
class EnemySpawn:
    """어떤 적이 어디서 나오는가 (TDD §3.4)."""

    kind: str
    position: tuple[int, int]


@dataclass(frozen=True)
class RoomTemplate:
    """룸 템플릿 하나. tiles 는 [y][x] 순서다."""

    template_id: str
    purpose: str
    tiles: tuple[tuple[int, ...], ...]
    player_spawn: tuple[int, int]
    enemy_spawns: tuple[EnemySpawn, ...]
    # 이 방이 나올 수 있는 가장 얕은 층. 난이도 곡선을 적 스탯이 아니라 "어느 층에
    # 나오는가" 로 표현하는 자리다 — 정예와 사제가 층 1 에 흩뿌려지면 첫 방에서 배울
    # 것이 없어진다. 층 배치(build_floor)가 이 값으로 후보를 거른다.
    min_floor: int = FIRST_FLOOR

    @property
    def width(self) -> int:
        """가로 칸 수."""
        return len(self.tiles[0])

    @property
    def height(self) -> int:
        """세로 칸 수."""
        return len(self.tiles)

    def get_tile(self, x: int, y: int) -> int:
        """좌표의 타일 ID 를 돌려준다.

        Args:
            x: 가로 좌표.
            y: 세로 좌표.

        Returns:
            타일 ID. 격자 밖이면 벽으로 취급해 TILE_WALL.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return TILE_WALL
        return self.tiles[y][x]


def convert_rows_to_tiles(rows: list[str], legend: dict[str, int]) -> tuple[tuple[int, ...], ...]:
    """ASCII 행들을 타일 ID 격자로 바꾼다.

    Args:
        rows: 한 글자가 한 칸인 문자열 목록.
        legend: 글자에서 타일 ID 로의 대응표.

    Returns:
        [y][x] 순서의 타일 격자.

    Raises:
        KeyError: legend 에 없는 글자가 있는 경우.
    """
    return tuple(tuple(legend[char] for char in row) for row in rows)


def check_room_reachability(template: RoomTemplate) -> list[str]:
    """시작점에서 모든 문·계단과 적 스폰에 닿는지 확인한다 (TDD §7.2).

    Args:
        template: 검사할 템플릿.

    Returns:
        문제 설명 목록. 이상이 없으면 빈 리스트.
    """
    problems: list[str] = []
    start = template.player_spawn
    if template.get_tile(*start) not in WALKABLE_TILES:
        return [f"{template.template_id}: 플레이어 시작점 {start} 이 통행 불가 타일이다"]

    reached = {start}
    frontier = [start]
    while frontier:
        x, y = frontier.pop()
        for dx, dy in STEP_OFFSETS:
            step = (x + dx, y + dy)
            if step in reached or template.get_tile(*step) not in WALKABLE_TILES:
                continue
            reached.add(step)
            frontier.append(step)

    exits = [
        (x, y)
        for y in range(template.height)
        for x in range(template.width)
        if template.get_tile(x, y) in {TILE_DOOR, TILE_STAIRS}
    ]
    if not exits:
        problems.append(f"{template.template_id}: 문도 계단도 없다")
    problems.extend(
        f"{template.template_id}: 출구 {pos} 에 시작점에서 닿을 수 없다"
        for pos in exits
        if pos not in reached
    )
    problems.extend(
        f"{template.template_id}: 적 스폰 {spawn.position} 에 시작점에서 닿을 수 없다"
        for spawn in template.enemy_spawns
        if spawn.position not in reached
    )
    return problems


def load_room_templates(source_path: Path) -> tuple[RoomTemplate, ...]:
    """룸 템플릿 JSON 을 읽어 변환한다.

    Args:
        source_path: templates.json 경로.

    Returns:
        선언된 크기와 일치하는 템플릿들.

    Raises:
        ValueError: 크기가 선언과 다르거나 min_floor 가 FIRST_FLOOR 미만인 템플릿이
            있는 경우.
    """
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    legend = raw["legend"]
    width, height = raw["size"]

    templates: list[RoomTemplate] = []
    for item in raw["templates"]:
        tiles = convert_rows_to_tiles(item["rows"], legend)
        if len(tiles) != height or any(len(row) != width for row in tiles):
            raise ValueError(f"{item['id']}: 크기가 선언({width}x{height})과 다르다")
        min_floor = int(item.get("min_floor", FIRST_FLOOR))
        if min_floor < FIRST_FLOOR:
            raise ValueError(f"{item['id']}: min_floor 는 {FIRST_FLOOR} 이상이어야 한다")
        templates.append(
            RoomTemplate(
                template_id=item["id"],
                purpose=item["purpose"],
                tiles=tiles,
                player_spawn=tuple(item["player_spawn"]),
                enemy_spawns=tuple(
                    EnemySpawn(kind=spawn["kind"], position=tuple(spawn["pos"]))
                    for spawn in item["enemy_spawns"]
                ),
                min_floor=min_floor,
            )
        )
    return tuple(templates)
