"""한 런이 도는 방 목록을 정한다 (로드맵 W3, 설계/6_몬스터 §3).

**예전에는 같은 방을 세 번 이었다.** 방이 열 개 있어도 한 판에 한 종류만 봤고, 그래서
방을 늘려도 사람 눈에는 아무것도 안 늘었다.

**서버가 정한다.** 기기가 정하면 쉬운 방만 골라 담을 수 있고(T2), 서버는 다른 방들을
재시뮬하게 된다. 정한 목록은 티켓에 얼려 두므로 제출은 그 목록으로만 검증된다.

`secrets` 를 쓰는 것은 R5 위반이 아니다 — 목록을 티켓에 얼려 두므로 런 등식의 입력은
여전히 (시드, 규칙표, 코어버전, 스냅샷, 로드아웃, **방 목록**) 이다. 굴림이 코어 밖에
있다는 점에서 전리품과 같은 자리다.
"""

import secrets

from game.schemas.room import RoomTemplate


def list_floor_rooms(
    rooms: dict[str, RoomTemplate], floor: int, boss_room_id: str = ""
) -> tuple[str, ...]:
    """그 층에서 **일반 전투로** 나올 수 있는 방을 모은다.

    Args:
        rooms: 방 id 에서 템플릿으로의 대응표.
        floor: 지금 층.
        boss_room_id: 보스 방. 일반 후보에서 뺀다 — 섞이면 보스를 두 번 만나거나,
            보스 층이 아닌 자리에서 만나게 된다.

    Returns:
        id 순으로 정렬된 방 id 들. **정렬해서 돌려준다** — 딕셔너리 순회 순서에 기대면
        같은 난수가 실행마다 다른 방을 고른다.
    """
    return tuple(
        sorted(
            key for key, room in rooms.items() if room.min_floor <= floor and key != boss_room_id
        )
    )


def build_room_chain(
    rooms: dict[str, RoomTemplate],
    floor: int,
    first_room_id: str,
    length: int,
    boss_room_id: str = "",
    boss_floor: int = 0,
) -> tuple[str, ...]:
    """이 런이 돌 방 목록을 만든다.

    **첫 방은 고른 방을 존중한다.** 편집기에서 방을 고르는 것은 연습의 일부이고, 첫
    방까지 서버가 정하면 "이 방을 상대로 규칙을 짜 본다" 가 불가능해진다. 그 층에서
    안 나오는 방을 골랐으면 그 층의 방으로 바꾼다.

    **나머지는 겹치지 않게 고른다.** 후보가 모자라면 그때만 되풀이하되 **바로 앞 방과는
    다르게** 둔다 — 같은 방이 연달아 두 번 나오면 방을 늘린 것이 안 보인다.

    **보스 층에서는 마지막이 보스 방이다.** 중간에 두면 보스를 잡고도 잡몹 방이 남아,
    「깼다」가 마지막 사건이 아니게 된다.

    Args:
        rooms: 방 id 에서 템플릿으로의 대응표.
        floor: 지금 층. `min_floor` 가 이보다 높은 방은 안 나온다.
        first_room_id: 고른 방.
        length: 이을 방 수.
        boss_room_id: 보스 방. 보스 층의 마지막 자리에 선다.
        boss_floor: 보스가 서는 층. 0 이면 보스를 안 둔다.

    Returns:
        방 id 들. 길이는 `length` 이며, 후보가 하나도 없으면 고른 방을 그대로 잇는다.
    """
    is_boss_run = bool(boss_room_id) and boss_room_id in rooms and floor == boss_floor
    normal_length = max(1, length - 1) if is_boss_run else length
    candidates = list_floor_rooms(rooms, floor, boss_room_id)
    if not candidates:
        return tuple(first_room_id for _step in range(max(1, length)))
    picked = [first_room_id if first_room_id in candidates else candidates[0]]
    while len(picked) < normal_length:
        fresh = [name for name in candidates if name not in picked]
        pool = fresh or [name for name in candidates if name != picked[-1]] or list(candidates)
        picked.append(pool[secrets.randbelow(len(pool))])
    if is_boss_run:
        picked.append(boss_room_id)
    return tuple(picked)
