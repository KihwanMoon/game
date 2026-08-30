"""제출 재시뮬 — 서버가 무엇으로 다시 계산하는가 (T2·T8, 결정 #13).

**여기서 지키는 것은 하나다: 브라우저가 돈 판과 서버가 다시 도는 판이 같아야 한다.**
어긋나면 제출이 반려되는 것이 아니라 **틀린 결과가 확정되고**, 그것이 경험치·전리품·
순위로 흘러간다.

재시뮬의 입력은 전부 **티켓**에서 온다. 제출이 실어 오면 유리한 값으로 바꿔 보낼 수
있다 — 방 목록은 쉬운 방으로, 로드아웃은 강한 캐릭터로.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

ROOM_ID = "corridor"


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    return client.post("/api/account").json()["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def build_ruleset():
    return {"ruleset_id": "probe", "version": 1, "rules": []}


def build_winning_ruleset():
    """방을 실제로 이기는 규칙표. 연쇄 검사는 이것이라야 뒷 방까지 돈다."""
    import json

    from game.config import G0_RULESETS_PATH

    raw = json.loads(G0_RULESETS_PATH.read_text(encoding="utf-8"))
    return next(item for item in raw["rulesets"] if item["ruleset_id"] == "g0_kite")


def test_verification_uses_the_ticket_loadout(client, token):
    """★ 서버 재시뮬이 로드아웃을 **실제로 쓴다** (결정 #13).

    이 자리가 실제로 비어 있었다. `evaluate_submission` 이 로드아웃을 인자로 받아 놓고
    `build_engine` 에 넘기지 않아, 서버는 맨몸으로 다시 돌렸다. 그러면 제출이 반려되는
    것이 아니라 **틀린 결과가 확정된다** — 장비를 끼고 이긴 판이 진 것으로 기록되고,
    그 결과가 경험치·전리품·순위로 흘러간다.
    """
    from game.api.deps import get_context
    from game.app.services.verify_run import evaluate_submission
    from game.schemas.loadout import PlayerLoadout

    player = get_context().balance["player"]
    args = (
        get_context(),
        build_ruleset(),
        ROOM_ID,
        4242,
        int(player["cpu_budget"]),
        int(player["rule_slots"]),
    )
    bare = evaluate_submission(*args)
    geared = evaluate_submission(
        *args,
        loadout=PlayerLoadout(
            hp_max=400,
            attack=60,
            defense=30,
            attack_range=4,
            initiative=90,
            cpu_budget=int(player["cpu_budget"]),
            rule_slots=int(player["rule_slots"]),
            skill_power_pct=100,
            skills=("ATTACK", "SKILL_1", "SKILL_2"),
        ),
    )
    assert geared != bare


def test_ticket_carries_the_room_chain(client, token):
    """★ 티켓이 방 목록을 싣는다 (로드맵 W3).

    브라우저가 이 목록대로 이어 돌고 서버가 같은 목록으로 재시뮬한다. 비면 브라우저는
    세 방을 도는데 서버는 한 방만 계산해, 이긴 판이 진 것으로 확정된다.
    """
    body = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": 1}, headers=build_headers(token)
    ).json()
    assert len(body["room_ids"]) > 1
    assert body["room_ids"][0] == body["room_id"]


def test_verification_runs_every_room_in_the_chain(client, token):
    """★ 서버 재시뮬이 방 목록 전부를 돈다.

    한 방만 돌면 두 방을 이기고 세 번째에서 진 판이 "1방 승리" 로 확정된다.
    """
    from game.api.deps import get_context
    from game.app.services.verify_run import evaluate_submission

    player = get_context().balance["player"]
    args = (
        get_context(),
        build_winning_ruleset(),
        ROOM_ID,
        4242,
        int(player["cpu_budget"]),
        int(player["rule_slots"]),
    )
    one_room = evaluate_submission(*args, room_ids=(ROOM_ID,))
    three_rooms = evaluate_submission(*args, room_ids=(ROOM_ID, ROOM_ID, ROOM_ID))
    # **이기는 규칙표라야 뒷 방이 돈다.** 첫 방에서 지는 규칙표로 재면 한 방만 도는
    # 코드와 구별되지 않아, 통과해도 아무것도 증명하지 못한다.
    assert one_room.outcome == "PLAYER_WIN"
    assert three_rooms.ticks > one_room.ticks


def test_verification_falls_back_to_one_room(client, token):
    """구버전 티켓에는 목록이 없다. 그때는 방 하나만 돈다 — 없는 것을 셋으로 채우면
    그 티켓으로 돈 판과 서버 재시뮬이 갈린다."""
    from game.api.deps import get_context
    from game.app.services.verify_run import evaluate_submission

    player = get_context().balance["player"]
    args = (
        get_context(),
        build_ruleset(),
        ROOM_ID,
        4242,
        int(player["cpu_budget"]),
        int(player["rule_slots"]),
    )
    assert evaluate_submission(*args) == evaluate_submission(*args, room_ids=(ROOM_ID,))
