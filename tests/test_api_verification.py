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


# ── 메타 세이브는 재시뮬의 부산물이다 ────────────────────────────────────


def submit_once(client, token, ruleset):
    """티켓을 받아 그 규칙표로 한 판 제출한다."""
    headers = build_headers(token)
    ticket = client.post("/api/ticket", json={"room_id": ROOM_ID}, headers=headers).json()
    return client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": ruleset,
            "core_version": ticket["core_version"],
        },
        headers=headers,
    ).json()


def read_meta(client, token):
    return client.get("/api/meta", headers=build_headers(token)).json()["payload"]


def test_a_verified_run_fills_the_bestiary(client, token):
    """★ **도감은 서버의 재시뮬이 채운다.**

    이것이 없으면 도감은 클라이언트가 쓴 값이고, 그 위에 얹힌 해금과 슬롯 상한도 전부
    자기 신고다.
    """
    assert read_meta(client, token) is None
    submit_once(client, token, build_winning_ruleset())
    meta = read_meta(client, token)
    assert meta is not None
    assert [row["kind_id"] for row in meta["bestiary"]] != []


def test_a_verified_run_unlocks_the_blocks_it_used(client, token):
    """★ 해금도 재시뮬이 뽑는다 — 쓴 블록과 만난 적의 규칙표가 근거다 (GDD §2.3)."""
    submit_once(client, token, build_winning_ruleset())
    meta = read_meta(client, token)
    assert meta["unlocked_actions"] != []
    assert meta["unlocked_perceptions"] != []


def test_a_win_records_the_floor(client, token, monkeypatch):
    """★ 최고 층이 슬롯 상한의 근거다. 이겨야 오른다.

    **연쇄를 고정한다.** 서버가 층에 맞는 방을 굴려 고르게 된 뒤로는 같은 규칙표가 판마다
    이기기도 지기도 한다 — 고정하지 않으면 이 검사가 흔들리고, 흔들리는 검사는 없는 것만
    못하다. 고정하는 것은 방 목록뿐이고 제출·재시뮬 경로는 그대로 탄다.
    """
    from game.api.routes import ticket as ticket_route

    from game.app.store import tickets as tickets_store
    from game.app.store.tickets import CHAIN_LENGTH

    # 층당 방 수를 따라간다 — 3 으로 고정하면 5방 개편에서 3//5 = 0층이 된다.
    monkeypatch.setattr(
        ticket_route, "build_descent", lambda *_args, **_kwargs: (ROOM_ID,) * CHAIN_LENGTH
    )
    # **시드도 고정한다.** 난이도 개편 뒤 같은 규칙표가 시드에 따라 지기도 한다 —
    # 이 검사가 재는 것은 「이기면 층이 오른다」이지 승률이 아니다.
    monkeypatch.setattr(tickets_store, "create_seed", lambda: 7)
    submit_once(client, token, build_winning_ruleset())
    assert read_meta(client, token)["best_floor"] >= 1


def test_a_loss_does_not_record_a_floor(client, token):
    """★ 지고도 층이 오르면 "제출만 하면 오르는" 경로가 열린다."""
    submit_once(client, token, build_ruleset())
    meta = read_meta(client, token)
    assert meta["best_floor"] == 0
    # 다만 도감은 찬다 — 조우만으로도 규칙표가 열리는 것이 P1 이다.
    assert [row["kind_id"] for row in meta["bestiary"]] != []


def test_the_bestiary_counts_defeats_separately(client, token):
    """★ "만났다" 와 "통했다" 를 가르는 것이 도감의 쓸모다."""
    submit_once(client, token, build_winning_ruleset())
    rows = read_meta(client, token)["bestiary"]
    assert any(row["defeats"] > 0 for row in rows)


def test_deeper_floors_pay_more(client, token):
    """★ 층이 깊을수록 화폐가 는다 — 안 그러면 깊이 들어갈 이유가 하나 준다.

    `create_loot_roll` 은 처음부터 층을 받았는데 호출부가 안 넘겨서 늘 1층 값이었다.
    문서가 말하는 동작과 실제가 갈려 있었고, 갈린 쪽이 조용했다.
    """
    from game.api.deps import get_item_catalog
    from game.app.items.loot import LOSS_CURRENCY, WIN_CURRENCY, create_loot_roll

    catalog = get_item_catalog()
    assert create_loot_roll(catalog, True, 3).currency == WIN_CURRENCY * 3
    assert create_loot_roll(catalog, False, 3).currency == LOSS_CURRENCY * 3
    assert create_loot_roll(catalog, True, 1).currency == WIN_CURRENCY


def test_the_route_passes_the_floor_through(client, token):
    """★ 층을 안 넘기면 위 검사는 통과하면서 실제로는 늘 1층이다."""
    import inspect

    from game.api.routes import run as run_route

    source = inspect.getsource(run_route.create_run_submission)
    assert "ticket.floor" in source, "라우트가 층을 안 넘긴다"
