"""한 방에 그림자 하나만 세운다 (설계/6_몬스터, 2026-09-06).

**밀집이 난이도를 통째로 올렸다.** 그림자는 빈 스폰 자리가 있는 만큼 섰고, 자리 이름이
`{종류}_{순번}` 이라 방을 안 담는다 — 그래서 한 방의 `bomb_slime_0·_1·_2` 가 모두 차면
**그림자 셋이 같은 방에** 섰다. 실측으로 4층에 열한 마리였다.

일반 지속 몬스터는 층당 셋이 상한인데(`MAX_PERSISTENT_PER_FLOOR`) 그림자만 상한이 없었다.

**그림자는 층에 귀속이다.** 그 층에서 죽은 빌드가 그 층을 지킨다 — 방에 매어 두면
「이 층의 주인」이 아니라 「저 방의 몹」이 된다.

**규칙은 「한 방에 하나」다** (2026-09-06). 저장은 그대로 두고(스무 마리 — 순위표가 그
뜻이다) 한 판에는 방마다 하나씩 나온다. 방이 다르면 다른 그림자를 만난다.

층당 하나로 두었던 앞 판은 개념이 어긋났다 — 세는 단위가 층이면 방이 다섯인 층과 셋인
층에서 「한 방에 몇을 만나는가」가 달라진다.

**자리는 방 배치에 없는 전용 이름을 쓴다** (`doppel_{개체id}`). 방 배치의 자리를 덮어쓰면
그 자리가 있는 방에만 설 수 있는데, 다섯 방의 적 구성이 서로 달라 실측으로 두세 방에만
섰다 — 전용 이름이면 `room_extras` 가 그 방에 **더해 준다.**

**어느 방인지는 스냅샷이 싣는다** (`room_index`). 자리 이름에 방이 안 담기던 때는 방마다
아무 자리나 골랐다가 둘이 한 방에 보였다 (실제 신고).

**목숨은 판당 한 번만 깎인다.** 스냅샷에 개체가 하나이므로 여러 방에서 만나도 결산은
한 번이다 — 다섯 방에서 다섯 번 죽는 것이 아니다.

**고르는 것은 티켓을 낼 때다.** 골라 둔 것이 티켓에 얼어붙으므로 재시뮬은 같은 판을
본다 — 굴림이 코어 밖이라 R5 를 안 건드리는 것도 전리품 굴림과 같은 자리다 (결정 #02).
"""

from collections.abc import Callable
from dataclasses import replace

from game.app.bots.doppel import build_doppel_slot, check_is_doppel
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
    room_ids: tuple[str, ...],
    rooms_per_floor: int,
    start_floor: int,
    roll: Callable[[int], int],
) -> list[MonsterRecord]:
    """**방마다 그림자 하나씩** 세우고, 방 배치에 없는 전용 자리를 준다.

    **한 방에 하나가 규칙이다.** 세는 단위가 층이면 방이 다섯인 층과 셋인 층에서 「한
    방에 몇을 만나는가」가 달라진다.

    **전용 자리라 어느 방에든 설 수 있다.** `room_extras` 가 방 배치에 없는 자리를 그
    방에 더해 주고, `room_index` 가 어느 방인지를 정한다.

    **여느 지속 개체와 안 겹친다.** 자리 이름이 `doppel_{개체id}` 라 방 템플릿의
    `{종류}_{순번}` 과 부딪히지 않는다.

    **여느 몬스터는 안 건드린다.** 층당 셋 상한은 이미 `apply_floor_seed` 가 지킨다.

    Args:
        records: 이 하강이 쓸 지속 몬스터들.
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
    # **올림으로 센다.** 내림으로 자르면 방 수가 딱 안 떨어지는 마지막 층이 통째로
    # 빠지는데, 그것이 보스층이다 — 심는 쪽(`apply_floor_seed`)은 올림으로 돌므로
    # 거기만 그림자가 영영 안 서게 된다.
    span = -(-len(room_ids) // rooms_per_floor) if rooms_per_floor > 0 else 1
    for step in range(span):
        floor = start_floor + step
        # **정렬해서 돈다.** 순서가 굴림에 새어 들어가면 같은 티켓이 두 번 다른 판을
        # 낸다 — 조회 순서는 보장되지 않는다 (R5 와 같은 이유).
        pool = sorted(
            (record for record in shadows if record.zone_floor == floor),
            key=lambda record: record.record_id,
        )
        offset = step * rooms_per_floor if rooms_per_floor > 0 else 0
        for slot_index in range(len(list_floor_rooms(room_ids, rooms_per_floor, step))):
            if not pool:
                break
            # **뽑은 것은 뺀다.** 같은 그림자를 두 방에서 만나면 목숨을 두 번 깎게 되고,
            # 그것은 「세 번 만나되 약해진다」는 설계와 어긋난다.
            chosen = pool.pop(roll(len(pool)))
            picked.append(
                replace(
                    chosen,
                    entity_slot=build_doppel_slot(chosen.record_id),
                    room_index=offset + slot_index,
                )
            )
    return plain + picked
