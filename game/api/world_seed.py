"""층에 지속 몬스터를 심는다 (설계/6_몬스터 §1).

**이 길이 없었다.** `create_monster` 를 아무도 안 불러, 세계에는 옛 경로가 남긴 1층
개체 넷뿐이었고 깊은 층은 영영 비어 있었다 — 스냅샷도 도감도 되찾기도 그 위에 서 있는데
그 바닥이 없었다.

층을 처음 방문할 때(티켓 발급) 그 층의 방 배치에서 자리를 뽑아 심는다. `zone_floor`
와 `entity_slot` 이 유일 키라 두 번 심어도 늘어나지 않는다.
"""

from psycopg_pool import ConnectionPool

from game.app.store.monsters import create_monster, list_monsters
from game.schemas.monster_snapshot import build_entity_id
from game.schemas.room import RoomTemplate

# 한 층에 심는 지속 몬스터 수의 상한. 전부 심으면 방 하나가 통째로 지속 개체가 되어
# 층을 다시 돌 때마다 같은 얼굴만 본다 — 일부만 지속이고 나머지는 매번 새로 뜬다.
MAX_PERSISTENT_PER_FLOOR = 3


def apply_floor_seed(
    pool: ConnectionPool, rooms: dict[str, RoomTemplate], room_ids: tuple[str, ...], floor: int
) -> int:
    """이 층에 지속 몬스터가 없으면 심는다.

    **자리는 방 배치에서 온다.** entity_slot 이 `{종류}_{순번}` 이라 방 배치가 붙이는
    이름과 같아야 스냅샷이 그 개체를 덮어쓴다 — 이름이 갈리면 얼려 둔 상태가 아무에게도
    적용되지 않고 그 사실이 조용히 넘어간다.

    Args:
        pool: 연결 풀.
        rooms: 방 id 에서 템플릿으로.
        room_ids: 이 층에서 돌 방들.
        floor: 대상 층.

    Returns:
        새로 심은 개체 수.
    """
    if list_monsters(pool, floor):
        return 0
    planted = 0
    for room_id in room_ids:
        template = rooms.get(room_id)
        if template is None:
            continue
        for index, spawn in enumerate(template.enemy_spawns):
            if planted >= MAX_PERSISTENT_PER_FLOOR:
                return planted
            record = create_monster(
                pool,
                spawn.kind,
                "NORMAL",
                floor,
                build_entity_id(spawn.kind, index),
            )
            if record is not None:
                planted += 1
    return planted
