"""한 방에 그림자 하나만 세운다 (설계/6_몬스터, 2026-09-06).

**밀집이 난이도를 통째로 올렸다.** 그림자는 빈 스폰 자리가 있는 만큼 섰고, 자리 이름이
`{종류}_{순번}` 이라 방을 안 담는다 — 그래서 한 방의 `bomb_slime_0·_1·_2` 가 모두 차면
**그림자 셋이 같은 방에** 섰다. 실측으로 4층에 열한 마리였다.

일반 지속 몬스터는 층당 셋이 상한인데(`MAX_PERSISTENT_PER_FLOOR`) 그림자만 상한이 없었다.

**저장은 그대로 두고 출현만 고른다.** 스무 마리를 계속 들고 있되(순위표가 그 뜻이다),
한 판에는 방마다 하나만 나온다 — 「특별한 조우」가 되려면 여럿이면 안 된다.

**고르는 것은 티켓을 낼 때다.** 골라 둔 것이 티켓에 얼어붙으므로 재시뮬은 같은 판을
본다 — 굴림이 코어 밖이라 R5 를 안 건드리는 것도 전리품 굴림과 같은 자리다 (결정 #02).
"""

from collections.abc import Callable
from dataclasses import replace

from game.app.bots.doppel import check_is_doppel
from game.app.store.monsters import MonsterRecord
from game.schemas.monster_snapshot import build_entity_id
from game.schemas.room import RoomTemplate


def list_room_slots(rooms: dict[str, RoomTemplate], room_id: str) -> tuple[str, ...]:
    """방 하나의 스폰 자리 이름들.

    Args:
        rooms: 방 템플릿 대응표.
        room_id: 볼 방.

    Returns:
        자리 이름들. 없는 방이면 빈 튜플.
    """
    template = rooms.get(room_id)
    if template is None:
        return ()
    return tuple(
        build_entity_id(spawn.kind, index) for index, spawn in enumerate(template.enemy_spawns)
    )


def list_floor_rooms(room_ids: tuple[str, ...], rooms_per_floor: int, step: int) -> tuple[str, ...]:
    """그 층이 도는 방들.

    Args:
        room_ids: 하강 전체의 방 목록.
        rooms_per_floor: 층 하나에 드는 방 수. 0 이면 전체가 한 층이다.
        step: 시작 층에서 몇 층 아래인가.

    Returns:
        방 id 들.
    """
    if rooms_per_floor <= 0:
        return room_ids if step == 0 else ()
    start = step * rooms_per_floor
    return room_ids[start : start + rooms_per_floor]


def build_room_doppels(
    records: list[MonsterRecord],
    rooms: dict[str, RoomTemplate],
    room_ids: tuple[str, ...],
    rooms_per_floor: int,
    start_floor: int,
    roll: Callable[[int], int],
) -> list[MonsterRecord]:
    """층마다 방당 그림자 하나만 남기고, 그 방의 자리에 앉힌다.

    **같은 그림자가 두 방에 나오지 않는다.** 뽑은 것은 그 층에서 빼므로 한 하강에 한 번만
    만난다 — 두 번 나오면 목숨을 두 번 깎게 되고, 그것은 「세 번 만나되 약해진다」는
    설계와 어긋난다.

    **여느 몬스터는 안 건드린다.** 층당 셋 상한은 이미 `apply_floor_seed` 가 지킨다.

    Args:
        records: 이 하강이 쓸 지속 몬스터들.
        rooms: 방 템플릿 대응표.
        room_ids: 하강 전체의 방 목록.
        rooms_per_floor: 층 하나에 드는 방 수.
        start_floor: 하강이 시작한 층.
        roll: `n` 을 받아 `0..n-1` 을 주는 굴림. 0 이하면 부르지 않는다.

    Returns:
        추린 레코드들. 여느 몬스터가 먼저, 고른 그림자가 뒤에 온다.
    """
    plain = [record for record in records if not check_is_doppel(record.catalog_id)]
    shadows = [record for record in records if check_is_doppel(record.catalog_id)]
    if not shadows:
        return plain

    picked: list[MonsterRecord] = []
    span = max(1, len(room_ids) // max(1, rooms_per_floor)) if rooms_per_floor > 0 else 1
    for step in range(span):
        floor = start_floor + step
        # **정렬해서 돈다.** 순서가 굴림에 새어 들어가면 같은 티켓이 두 번 다른 판을
        # 낸다 — 조회 순서는 보장되지 않는다 (R5 와 같은 이유).
        pool = sorted(
            (record for record in shadows if record.zone_floor == floor),
            key=lambda record: record.record_id,
        )
        for room_id in list_floor_rooms(room_ids, rooms_per_floor, step):
            slots = list_room_slots(rooms, room_id)
            if not pool or not slots:
                continue
            chosen = pool.pop(roll(len(pool)))
            # **그 방의 자리에 앉힌다.** 저장된 자리는 다른 방의 것일 수 있고, 그러면
            # 스냅샷이 아무에게도 안 붙어 개체는 있는데 아무도 못 만난다.
            picked.append(replace(chosen, entity_slot=slots[roll(len(slots))]))
    return plain + picked
