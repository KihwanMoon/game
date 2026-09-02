"""한 런이 도는 방 목록을 정한다 (로드맵 W3, 설계/6_몬스터 §3).

**예전에는 같은 방을 세 번 이었다.** 방이 열 개 있어도 한 판에 한 종류만 봤고, 그래서
방을 늘려도 사람 눈에는 아무것도 안 늘었다.

**서버가 정한다.** 기기가 정하면 쉬운 방만 골라 담을 수 있고(T2), 서버는 다른 방들을
재시뮬하게 된다. 정한 목록은 티켓에 얼려 두므로 제출은 그 목록으로만 검증된다.

**한 런이 하강 전체다.** 시작 층부터 마지막 층까지의 방을 한 티켓에 다 담는다 — 층마다
따로 제출하면 층 사이에 인계되는 HP 를 클라이언트가 보고하게 되고, 그러면 "나는 만피로
시작했다" 를 적어 보내는 것이 곧 진행이 된다 (T9). 한 티켓으로 전체를 재시뮬하는 것이
그것을 막는 유일한 방법이다.

`secrets` 를 쓰는 것은 R5 위반이 아니다 — 목록을 티켓에 얼려 두므로 런 등식의 입력은
여전히 (시드, 규칙표, 코어버전, 스냅샷, 로드아웃, **방 목록**) 이다. 굴림이 코어 밖에
있다는 점에서 전리품과 같은 자리다.
"""

import secrets
from collections.abc import Callable

from game.schemas.room import RoomTemplate

# 후보 하나를 고르는 것. 상한을 받아 `[0, 상한)` 을 돌려준다.
#
# **기본값은 `secrets` 다.** 방 고르기는 티켓을 낼 때 딱 한 번 돌고 그 결과가 얼려지므로
# 시드가 필요 없고, 오히려 시드에서 파생하면 시드를 아는 클라이언트가 방 목록을 미리
# 알게 된다. 갈아 끼울 수 있게 둔 것은 **밸런스 배치** 때문이다 — 최악 시드를 적어 놓고
# 재현할 수 없으면 그 숫자로 고칠 곳을 못 찾는다 (P1).
PickBelow = Callable[[int], int]


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
    pick: PickBelow = secrets.randbelow,
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
        pick: 후보를 고르는 것. 기본은 `secrets` 이고, 밸런스 배치가 재현 가능한 것으로
            갈아 끼운다.

    Returns:
        방 id 들. 길이는 `length` 이며, 후보가 하나도 없으면 고른 방을 그대로 잇는다.
    """
    is_boss_run = bool(boss_room_id) and boss_room_id in rooms and floor == boss_floor
    normal_length = max(1, length - 1) if is_boss_run else length
    candidates = list_floor_rooms(rooms, floor, boss_room_id)
    if not candidates:
        return tuple(first_room_id for _step in range(max(1, length)))
    picked = [first_room_id if first_room_id in candidates else candidates[pick(len(candidates))]]
    while len(picked) < normal_length:
        fresh = [name for name in candidates if name not in picked]
        pool = fresh or [name for name in candidates if name != picked[-1]] or list(candidates)
        picked.append(pool[pick(len(pool))])
    if is_boss_run:
        picked.append(boss_room_id)
    return tuple(picked)


def build_descent(
    rooms: dict[str, RoomTemplate],
    start_floor: int,
    first_room_id: str,
    rooms_per_floor: int,
    boss_room_id: str = "",
    boss_floor: int = 0,
    pick: PickBelow = secrets.randbelow,
) -> tuple[str, ...]:
    """시작 층부터 마지막 층까지의 방을 한 줄로 잇는다.

    층마다 `build_room_chain` 을 부르고 이어 붙인다. 방 순번에서 층을 파생할 수 있어야
    하므로 **층마다 같은 수의 방**이 들어간다 — 층마다 다르면 순번만으로는 몇 층인지 알
    수 없고, 그 값을 따로 실어 나르면 클라이언트가 고쳐 보낼 자리가 생긴다.

    Args:
        rooms: 방 id 에서 템플릿으로의 대응표.
        start_floor: 시작 층.
        first_room_id: 고른 방. 첫 층의 첫 방으로 선다.
        rooms_per_floor: 층 하나에 드는 방 수.
        boss_room_id: 보스 방.
        boss_floor: 보스가 서는 층. 여기가 하강의 끝이다.
        pick: 후보를 고르는 것. 기본은 `secrets` 다.

    Returns:
        방 id 들. 길이는 `(끝 층 - 시작 층 + 1) * rooms_per_floor` 다.
    """
    last_floor = max(start_floor, boss_floor)
    picked: list[str] = []
    for floor in range(start_floor, last_floor + 1):
        # 첫 층만 고른 방으로 연다. 이후 층은 서버가 전부 고른다 — 고른 방이 층마다
        # 되풀이되면 하강이 같은 방의 반복이 된다.
        opener = first_room_id if floor == start_floor else ""
        picked.extend(
            build_room_chain(rooms, floor, opener, rooms_per_floor, boss_room_id, boss_floor, pick)
        )
    return tuple(picked)


def resolve_room_floor(start_floor: int, index: int, rooms_per_floor: int) -> int:
    """방 순번에서 그 방이 선 층을 낸다.

    **두 코어가 같은 식을 써야 한다** (G3). 층이 갈리면 적의 HP·공격력이 갈리고, 화면이
    이긴 판을 서버가 진 것으로 확정한다.

    Args:
        start_floor: 시작 층.
        index: 방 순번. 0 부터 센다.
        rooms_per_floor: 층 하나에 드는 방 수.

    Returns:
        그 방이 선 층.
    """
    if rooms_per_floor <= 0:
        return start_floor
    return start_floor + max(0, index) // rooms_per_floor
