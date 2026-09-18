"""한 런이 도는 방 목록 (로드맵 W3).

**예전에는 같은 방을 세 번 이었다.** 방이 열 개 있어도 한 판에 한 종류만 봤고, 그래서
방을 늘려도 사람 눈에는 아무것도 안 늘었다 — 「맵에 베리에이션이 없다」의 진짜 원인이다.

여기서 지키는 것은 넷이다.

1. **첫 방은 고른 방을 존중한다.** 편집기에서 방을 고르는 것이 연습의 일부다.
2. **나머지는 겹치지 않는다.** 후보가 있는 한 다른 방이 나온다.
3. **그 층에 없는 방은 안 나온다.** `min_floor` 가 층 게이팅의 전부다.
4. **후보가 모자라도 연달아 같은 방을 두지 않는다.**
"""

import os

import pytest

from game.app.services.build_chain import build_room_chain, list_floor_rooms
from game.app.store.connection import DATABASE_URL_ENV
from game.schemas.room import RoomTemplate


def build_rooms(spec):
    """검사용 방 대응표를 만든다.

    Args:
        spec: id 에서 min_floor 로.

    Returns:
        방 id 에서 템플릿으로의 대응표.
    """
    return {
        key: RoomTemplate(
            template_id=key,
            purpose="검사용",
            tiles=(("FLOOR",),),
            player_spawn=(0, 0),
            enemy_spawns=(),
            min_floor=floor,
        )
        for key, floor in spec.items()
    }


def test_the_chosen_room_comes_first():
    """★ 고른 방이 안 나오면 「이 방을 상대로 규칙을 짜 본다」가 불가능해진다."""
    rooms = build_rooms({"a": 1, "b": 1, "c": 1})
    assert build_room_chain(rooms, 1, "b", 3)[0] == "b"


def test_the_rest_are_different_rooms():
    """★ 같은 방을 세 번 이으면 방을 늘려도 사람 눈에는 안 늘어난다."""
    rooms = build_rooms({"a": 1, "b": 1, "c": 1})
    for _try in range(20):
        picked = build_room_chain(rooms, 1, "a", 3)
        assert len(set(picked)) == 3, picked


def test_a_room_above_the_floor_never_appears():
    """★ `min_floor` 가 층 게이팅의 전부다 — 안 지키면 1층에서 10층 방이 나온다."""
    rooms = build_rooms({"shallow": 1, "deep": 9})
    for _try in range(20):
        assert "deep" not in build_room_chain(rooms, 1, "shallow", 3)


def test_a_chosen_room_out_of_reach_is_replaced():
    """★ 그 층에서 안 나오는 방을 골랐으면 그 층의 방으로 바꾼다.

    그대로 두면 층 게이팅을 방 고르기로 우회할 수 있다.
    """
    rooms = build_rooms({"shallow": 1, "deep": 9})
    assert "deep" not in build_room_chain(rooms, 1, "deep", 3)


def test_a_short_pool_never_repeats_back_to_back():
    """★ 후보가 모자라도 같은 방이 연달아 두 번 나오면 방을 늘린 것이 안 보인다."""
    rooms = build_rooms({"a": 1, "b": 1})
    for _try in range(30):
        picked = build_room_chain(rooms, 1, "a", 4)
        assert len(picked) == 4
        assert all(picked[i] != picked[i + 1] for i in range(len(picked) - 1)), picked


def test_an_empty_floor_falls_back_to_the_chosen_room():
    """★ 후보가 하나도 없으면 빈 목록을 주는 대신 고른 방을 잇는다.

    빈 목록을 주면 티켓이 방 없이 발급되고, 그 판은 시작조차 못 한다.
    """
    assert build_room_chain(build_rooms({"deep": 9}), 1, "deep", 3) == ("deep", "deep", "deep")


def test_the_candidate_list_is_sorted():
    """★ 정렬 안 하면 같은 난수가 실행마다 다른 방을 고른다 (R5 와 같은 이유)."""
    rooms = build_rooms({"c": 1, "a": 1, "b": 1})
    assert list_floor_rooms(rooms, 1) == ("a", "b", "c")


pytestmark_db = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


def templates_for_floor(floor):
    """그 층에 설 수 있는 방 템플릿들.

    Args:
        floor: 층.

    Returns:
        템플릿 딕셔너리들. 보스 방은 뺀다 — 그 자리는 따로 정해진다.
    """
    import json

    from game.config import ROOM_TEMPLATES_PATH

    raw = json.loads(ROOM_TEMPLATES_PATH.read_text(encoding="utf-8"))
    rooms = raw.get("templates") or raw.get("rooms") or []
    return [one for one in rooms if one.get("min_floor", 1) <= floor and one["id"] != "boss_hall"]


@pytestmark_db
def test_the_ticket_carries_a_varied_chain():
    """★ 티켓이 같은 방 세 개를 주면 화면도 같은 방을 세 번 돈다.

    화면은 `issued.roomIds` 를 그대로 쓰므로, 여기서 안 갈라 주면 아무 데서도 안 갈린다.
    """
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as client:
        token = client.post("/api/account").json()["token"]
        issued = client.post(
            "/api/ticket", json={"room_id": "open_field"}, headers={"X-Game-Token": token}
        ).json()
    per_floor = int(issued["rooms_per_floor"])
    assert issued["room_ids"][0] == "open_field"
    # **하강 전체가 실린다.** 1층에서 마지막 층까지, 층당 같은 수의 방이다.
    #
    # **층수를 박지 않는다.** 여기 `10` 이 박혀 있던 동안 2막이 `max_floor` 를 15 로
    # 올렸고(`6c1658c 층이 실제로 오른다`), 이 단언만 옛 막에 남아 빨갛게 서 있었다 —
    # `tools/check_all.sh` 가 pytest 를 안 돌려서 게이트도 못 봤다. 정본에서 읽으면
    # 3막이 열려도 같은 것을 계속 지킨다.
    from game.api.deps import get_context
    from game.app.progression.floors import (
        FIRST_FLOOR,
        read_floor_bosses,
        read_floor_cap,
    )

    floors = read_floor_cap(get_context().balance) - FIRST_FLOOR + 1
    assert len(issued["room_ids"]) == per_floor * floors
    # 겹치지 않는 것은 **한 층 안에서**다. 층이 다르면 같은 방이 다시 나와도 된다 —
    # 층마다 적이 세지므로 같은 지형이 다른 판이 된다.
    #
    # **후보가 방 수보다 적으면 하나는 되풀이된다.** `build_room_chain` 이 처음부터 그렇게
    # 적어 두었다 — 「후보가 모자라면 그때만 되풀이하되 바로 앞 방과는 다르게 둔다」.
    # 1장을 신규에게 열어 주려고 후보를 넷으로 줄이면서(기둥 숲·네거리를 2장으로) 그
    # 경우가 실제로 생겼고, 이 검사가 **코드의 계약보다 엄해서** 빨개졌다. 계약대로 본다:
    # 후보가 넉넉하면 전부 다르고, 모자라면 **적어도 연달아 같지는 않다.**
    first = issued["room_ids"][:per_floor]
    floor_one_rooms = {room["id"] for room in templates_for_floor(1)}
    if len(floor_one_rooms) >= per_floor:
        assert len(set(first)) == len(first)
    else:
        assert len(set(first)) == len(floor_one_rooms), first
    assert all(first[i] != first[i + 1] for i in range(len(first) - 1)), first
    # 마지막은 **마지막 막의** 보스 방이다.
    #
    # 여기 `boss_hall` 이 박혀 있었는데, 2막이 열리며 `floor_bosses` 가 둘이 되어
    # (10장 장승 · 15장 원귀) 하강의 끝이 `wraith_hall` 로 바뀌었다. `read_floor_bosses`
    # 의 독스트링이 예고한 그대로다 — "막이 늘면 보스도 는다".
    #
    # **1막의 끝이 남아 있는지도 함께 본다.** 그 독스트링이 막으려던 사고가 "2막을 열면
    # 장승이 10장에서 15장으로 옮겨 가 1막의 끝이 사라진다" 였다. 끝만 보면 그 사고가
    # 나도 이 검사는 초록이다.
    bosses = read_floor_bosses(get_context().balance)
    last_floor, last_boss = bosses[-1]
    assert issued["room_ids"][-1] == last_boss
    for floor, room in bosses:
        # 그 층의 마지막 자리에 선다 (`build_room_chain`).
        index = (floor - FIRST_FLOOR + 1) * per_floor - 1
        assert issued["room_ids"][index] == room, (floor, room, issued["room_ids"][index])
    assert last_floor == read_floor_cap(get_context().balance)


# 층마다 어느 보스가 서는가 (2026-09-17). 하나가 아니라 쌍들인 것은 막이 둘이기 때문이다.
BOSSES = ((10, "boss_hall"),)


def build_boss_rooms():
    """보스 방까지 있는 검사용 대응표.

    Returns:
        방 id 에서 템플릿으로의 대응표.
    """
    return build_rooms({"a": 1, "b": 1, "c": 1, "d": 1, "boss_hall": 10})


def test_the_boss_room_comes_last_on_the_boss_floor():
    """★ 보스가 중간에 있으면 잡고도 잡몹 방이 남아 「깼다」가 마지막 사건이 아니게 된다."""
    for _try in range(20):
        picked = build_room_chain(build_boss_rooms(), 10, "a", 3, BOSSES)
        assert len(picked) == 3
        assert picked[-1] == "boss_hall", picked
        assert "boss_hall" not in picked[:-1]


def test_the_boss_room_never_appears_on_other_floors():
    """★ 보스 층이 아닌 데서 만나면 「10층에 보스」가 거짓이 된다."""
    for floor in (1, 5, 9):
        for _try in range(10):
            assert "boss_hall" not in build_room_chain(build_boss_rooms(), floor, "a", 3, BOSSES)


def test_the_boss_room_is_not_a_normal_candidate():
    """★ 일반 후보에 섞이면 한 판에 보스를 두 번 만난다."""
    assert "boss_hall" not in list_floor_rooms(build_boss_rooms(), 10, frozenset({"boss_hall"}))


def test_a_chain_without_a_boss_stays_the_same_length():
    """★ 보스를 안 두는 층에서 길이가 줄면 방 하나가 통째로 사라진다."""
    picked = build_room_chain(build_boss_rooms(), 3, "a", 3, BOSSES)
    assert len(picked) == 3


def test_a_descent_covers_every_floor_to_the_boss():
    """★ 하강이 중간에 끊기면 「10층에 보스」에 닿을 길이 없다."""
    from game.app.services.build_chain import build_descent

    picked = build_descent(build_boss_rooms(), 1, "a", 3, 10, BOSSES)
    assert len(picked) == 3 * 10
    assert picked[-1] == "boss_hall"
    assert picked.count("boss_hall") == 1


def test_a_descent_from_a_deeper_floor_is_shorter():
    """★ 5층에서 시작하면 5~10층만 돈다 — 지나온 층을 다시 돌면 하강이 아니다."""
    from game.app.services.build_chain import build_descent

    assert len(build_descent(build_boss_rooms(), 5, "a", 3, 10, BOSSES)) == 3 * 6


def test_the_chosen_room_opens_only_the_first_floor():
    """★ 고른 방이 층마다 되풀이되면 하강이 같은 방의 반복이 된다."""
    from game.app.services.build_chain import build_descent

    picked = build_descent(build_boss_rooms(), 1, "a", 3, 10, BOSSES)
    assert picked[0] == "a"
    # 2층의 첫 방까지 "a" 로 고정되면 안 된다. 서른 방 중 하나뿐일 리는 없으므로
    # 여러 번 돌려 한 번이라도 달라지는지 본다.
    assert any(
        build_descent(build_boss_rooms(), 1, "a", 3, 10, BOSSES)[3] != "a" for _try in range(20)
    )


def test_the_room_floor_comes_from_the_index():
    """★ 방 순번에서 층을 판다. **TS 와 같은 식이어야 한다** (G3).

    갈리면 적의 HP·공격력이 갈리고, 화면이 이긴 판을 서버가 진 것으로 확정한다.
    """
    from game.app.services.build_chain import resolve_room_floor

    assert resolve_room_floor(1, 0, 3) == 1
    assert resolve_room_floor(1, 2, 3) == 1
    assert resolve_room_floor(1, 3, 3) == 2
    assert resolve_room_floor(1, 29, 3) == 10
    # 0 이면 전체가 한 층이다 — 구버전 티켓이 그 길로 온다.
    assert resolve_room_floor(4, 7, 0) == 4
