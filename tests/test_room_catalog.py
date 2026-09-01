"""룸 템플릿 카탈로그 (로드맵 W3).

**방이 열 개일 때는 한 판에 한 방만 봤으므로 개수가 뜻이 없었다.** 이제 한 런이 서로 다른
방 셋을 돌므로, 방의 수와 층별 분포가 그대로 체감이 된다.

여기서 지키는 것은 다섯이다.

1. **층마다 고를 방이 남는다.** 후보가 연쇄 길이보다 적으면 같은 방이 되풀이된다.
2. **격자가 규격대로다.** 줄 수·폭이 어긋나면 로더가 아니라 렌더러에서 터진다.
3. **자리가 걸을 수 있는 칸이다.** 벽에 세우면 개체가 처음부터 갇힌다.
4. **자리가 안 겹친다.** 겹치면 스냅샷이 어느 것을 가리키는지 알 수 없다.
5. **테두리가 막혀 있다.** 뚫리면 경로 탐색이 방 밖을 돈다.
"""

from game.app.progression.floors import read_floor_cap
from game.app.services.build_chain import list_floor_rooms
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import TILE_WALL, WALKABLE_TILES, load_room_templates

TEMPLATES = load_room_templates(ROOM_TEMPLATES_PATH)
ROOMS = {template.template_id: template for template in TEMPLATES}
# 한 런이 도는 방 수. `store/tickets.py` 의 값과 같아야 한다.
CHAIN_LENGTH = 3


def test_every_floor_has_more_rooms_than_a_chain_needs():
    """★ 후보가 연쇄 길이보다 적으면 한 판에 같은 방이 되풀이된다."""
    import json
    from pathlib import Path

    cap = read_floor_cap(json.loads(Path(BALANCE_PATH).read_text(encoding="utf-8")))
    for floor in range(1, cap + 1):
        found = list_floor_rooms(ROOMS, floor)
        assert len(found) > CHAIN_LENGTH, f"{floor}층 후보가 {len(found)}개뿐이다"


def test_every_floor_opens_at_least_one_new_room():
    """★ 층마다 **처음 열리는 방**이 있어야 한다.

    「후보가 셋보다 많다」만 보면 깊은 층이 통째로 비어도 통과한다 — 층 4~10 이 전부
    같은 방 목록을 보게 되고, 그러면 깊이 들어가는 것이 숫자만 바뀌는 일이 된다.
    실제로 그렇게 통과했다.
    """
    import json
    from pathlib import Path

    cap = read_floor_cap(json.loads(Path(BALANCE_PATH).read_text(encoding="utf-8")))
    gated = {template.min_floor for template in TEMPLATES}
    missing = [floor for floor in range(1, cap + 1) if floor not in gated]
    assert missing == [], f"이 층들에서 새로 열리는 방이 없다: {missing}"


def test_the_grid_is_rectangular():
    """★ 폭이 어긋나면 로더가 아니라 렌더러에서 터진다."""
    for template in TEMPLATES:
        widths = {len(row) for row in template.tiles}
        assert len(widths) == 1, f"{template.template_id}: 줄마다 폭이 다르다 {widths}"


def test_every_spawn_stands_on_a_walkable_tile():
    """★ 벽에 세우면 그 개체는 처음부터 갇힌다 — 전투가 성립하지 않는다."""
    for template in TEMPLATES:
        spots = [template.player_spawn, *(spawn.position for spawn in template.enemy_spawns)]
        for x, y in spots:
            tile = template.get_tile(x, y)
            assert tile in WALKABLE_TILES, f"{template.template_id}: ({x},{y}) 가 못 걷는 칸이다"


def test_no_two_entities_share_a_spawn():
    """★ 자리가 겹치면 스냅샷이 어느 것을 가리키는지 알 수 없다."""
    for template in TEMPLATES:
        spots = [template.player_spawn, *(spawn.position for spawn in template.enemy_spawns)]
        assert len(spots) == len(set(spots)), f"{template.template_id}: 자리가 겹친다"


def test_the_border_is_sealed_except_at_doors():
    """★ 테두리가 뚫리면 경로 탐색이 방 밖을 돈다.

    문은 예외다 — 문은 걸을 수 있는 칸이고, 방을 잇는 자리가 그것이다.
    """
    from game.schemas.room import TILE_DOOR

    for template in TEMPLATES:
        height = len(template.tiles)
        width = len(template.tiles[0])
        edges = (
            [(x, 0) for x in range(width)]
            + [(x, height - 1) for x in range(width)]
            + [(0, y) for y in range(height)]
            + [(width - 1, y) for y in range(height)]
        )
        for x, y in edges:
            tile = template.get_tile(x, y)
            assert tile in {TILE_WALL, TILE_DOOR}, f"{template.template_id}: 테두리 ({x},{y})"


def test_every_room_says_what_it_teaches():
    """★ 목적 없는 방은 배치가 아니라 낙서다 — 왜 이 지형인지 다음 사람이 못 읽는다."""
    for template in TEMPLATES:
        assert len(template.purpose.strip()) >= 10, f"{template.template_id}: 목적이 비었다"


def test_no_two_rooms_share_a_purpose():
    """★ 목적이 같은 방 둘은 하나로 족하다 — 개수만 늘고 겪는 것은 안 는다."""
    purposes = [template.purpose for template in TEMPLATES]
    assert len(purposes) == len(set(purposes))
