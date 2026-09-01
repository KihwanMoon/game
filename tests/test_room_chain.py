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
    assert issued["room_ids"][0] == "open_field"
    assert len(set(issued["room_ids"])) == len(issued["room_ids"])
