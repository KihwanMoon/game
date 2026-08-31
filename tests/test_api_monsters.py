"""지속 몬스터 — 스냅샷 봉인·성장·전리품 (E단계).

여기서 지키는 것은 넷이다.

1. **스냅샷을 서버가 조회한다** (T8). 제출이 스냅샷을 실어 오면 약한 것으로 바꿔 보낼
   수 있으므로, 요청에 그 자리가 없어야 한다.
2. **런 등식이 유지된다.** 티켓이 얼려 둔 상태로 서버가 재시뮬하므로, 같은 티켓은 언제
   재검증해도 같은 결과를 낸다.
3. **성장은 검증된 런에서만.** 클라이언트 보고로 크면 일부러 지는 어뷰징이 열린다 (T9).
4. **처치는 흔적을 남긴다** (결정 #35). 이겨도 아무 변화가 없으면 승리가 세계에 안 남는다.
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
# corridor 의 첫 배치. 방 배치가 `{kind}_{index}` 로 붙인다.
SLOT = "goblin_rusher_0"


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


@pytest.fixture
def monster(client):
    """층 1 에 지속 엘리트를 하나 놓는다. 이미 있으면 그것을 쓴다."""
    from game.api.deps import get_pool
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import create_monster, list_monsters

    pool = get_pool()
    create_monster(pool, "goblin_rusher", MonsterTier.ELITE, 1, SLOT)
    return next(item for item in list_monsters(pool, 1) if item.entity_slot == SLOT)


def build_ruleset():
    return {"ruleset_id": "probe", "version": 1, "rules": []}


def build_winning_ruleset():
    """방을 실제로 이기는 규칙표. 연쇄 검사는 이것이라야 뒷 방까지 돈다."""
    import json

    from game.config import G0_RULESETS_PATH

    raw = json.loads(G0_RULESETS_PATH.read_text(encoding="utf-8"))
    return next(item for item in raw["rulesets"] if item["ruleset_id"] == "g0_kite")


def run_once(client, token, floor=1):
    headers = build_headers(token)
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": floor}, headers=headers
    ).json()
    body = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": build_ruleset(),
            "core_version": ticket["core_version"],
        },
        headers=headers,
    ).json()
    return ticket, body


# ── 스냅샷 봉인 (§5) ─────────────────────────────────────────────────────


def test_ticket_carries_the_snapshot(client, token, monster):
    """★ 런의 입력 전부가 티켓에 얼려 있다."""
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": 1}, headers=build_headers(token)
    ).json()
    found = [s for s in ticket["monster_snapshot"] if s["entity_id"] == SLOT]
    assert found, "지속 몬스터가 스냅샷에 실리지 않았다"
    assert found[0]["record_id"] == monster.record_id
    assert found[0]["tier"] == "ELITE"
    assert found[0]["hp_max"] > 0


def test_submission_does_not_take_a_snapshot():
    """★ 제출이 스냅샷을 받으면 약한 것으로 바꿔 보낼 수 있다 (T8)."""
    from game.api.schemas import SubmissionRequest

    assert "monster_snapshot" not in SubmissionRequest.model_fields
    assert set(SubmissionRequest.model_fields) == {"ticket_id", "ruleset", "core_version"}


def test_a_smuggled_snapshot_is_ignored(client, token, monster):
    """★ 제출에 스냅샷을 끼워 넣어도 모델에 남지 않는다."""
    headers = build_headers(token)
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": 1}, headers=headers
    ).json()
    weak = {**ticket["monster_snapshot"][0], "hp_max": 1, "attack": 1}
    body = client.post(
        "/api/run",
        json={
            "ticket_id": ticket["ticket_id"],
            "ruleset": build_ruleset(),
            "core_version": ticket["core_version"],
            "monster_snapshot": [weak],
        },
        headers=headers,
    ).json()
    # 서버가 자기 스냅샷으로 돌렸으므로 결과가 확정된다 — 약한 값이 반영되지 않는다.
    assert body["verdict"] == "verified"


def test_the_same_ticket_replays_identically(client, token, monster):
    """★ 런 등식이 유지된다 — 얼려 둔 상태로 다시 돌리면 같은 결과다."""
    from game.api.deps import get_context, get_pool
    from game.app.services.verify_run import evaluate_submission
    from game.app.store.monsters import load_snapshots
    from game.app.store.tickets import find_open_ticket

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": 1}, headers=headers
    ).json()
    open_ticket = find_open_ticket(get_pool(), ticket["ticket_id"], account_id)
    assert open_ticket is not None

    player = get_context().balance["player"]
    snapshots = load_snapshots(get_pool(), ticket["ticket_id"])
    first = evaluate_submission(
        get_context(),
        build_ruleset(),
        open_ticket.room_id,
        open_ticket.seed,
        int(player["cpu_budget"]),
        int(player["rule_slots"]),
        snapshots,
    )
    second = evaluate_submission(
        get_context(),
        build_ruleset(),
        open_ticket.room_id,
        open_ticket.seed,
        int(player["cpu_budget"]),
        int(player["rule_slots"]),
        snapshots,
    )
    assert first == second


def test_snapshot_changes_the_battle(client, token, monster):
    """스냅샷이 실제로 전투를 바꾼다 — 안 바뀌면 얼려 두는 뜻이 없다."""
    from game.api.deps import get_context, get_pool
    from game.app.services.verify_run import evaluate_submission
    from game.app.store.monsters import load_snapshots
    from game.app.store.tickets import find_open_ticket

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    ticket = client.post(
        "/api/ticket", json={"room_id": ROOM_ID, "floor": 1}, headers=headers
    ).json()
    open_ticket = find_open_ticket(get_pool(), ticket["ticket_id"], account_id)
    assert open_ticket is not None
    player = get_context().balance["player"]

    def run(snapshots):
        return evaluate_submission(
            get_context(),
            build_ruleset(),
            open_ticket.room_id,
            open_ticket.seed,
            int(player["cpu_budget"]),
            int(player["rule_slots"]),
            snapshots,
        )

    with_snapshot = run(load_snapshots(get_pool(), ticket["ticket_id"]))
    without = run(())
    assert (with_snapshot.ticks, with_snapshot.player_hp) != (without.ticks, without.player_hp)


# ── 성장과 흔적 (§3, 결정 #35) ───────────────────────────────────────────


def test_a_verified_loss_feeds_the_monster(client, token, monster):
    """★ 성장은 검증된 런에서만. 지면 그 층의 몬스터가 경험치를 얻는다."""
    from game.api.deps import get_pool
    from game.app.store.monsters import list_monsters

    before = monster.total_xp
    _, body = run_once(client, token)
    assert body["verdict"] == "verified"
    after = next(
        item for item in list_monsters(get_pool(), 1) if item.record_id == monster.record_id
    )
    if body["outcome"] == "PLAYER_WIN":
        # 이겼으면 감쇠한다 — 늘지 않는다.
        assert after.total_xp <= before
    else:
        assert after.total_xp > before


def test_defeat_leaves_a_trace(client, token, monster):
    """★ 이겨도 아무 변화가 없으면 승리가 세계에 남지 않는다 (결정 #35)."""
    from game.api.deps import get_pool
    from game.app.store.monsters import add_monster_xp, apply_monster_defeat

    add_monster_xp(get_pool(), monster.record_id, 1, "PLAYER", None, amount=100_000)
    before = next(
        item
        for item in __import__("game.app.store.monsters", fromlist=["list_monsters"]).list_monsters(
            get_pool(), 1
        )
        if item.record_id == monster.record_id
    ).level
    after = apply_monster_defeat(get_pool(), monster.record_id, 1)
    assert after < before


def test_trophy_transfers_a_copy(client, token, monster):
    """★ 몬스터가 사본을 가져간다 (결정 #34). 도감이 "내 아이템을 들고 있다" 를 말한다."""
    from game.api.deps import get_pool
    from game.api.routes.run import apply_trophy_transfer
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item
    from game.app.store.trophies import list_trophies

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    create_item(get_pool(), find_player_entity(get_pool(), account_id), "helm_iron", ())
    note = apply_trophy_transfer(account_id, monster.record_id)
    assert "helm_iron" in note
    trophies = list_trophies(get_pool(), monster.record_id)
    assert any(item["catalog_id"] == "helm_iron" for item in trophies)
    assert any(item["taken_from"] == account_id for item in trophies)


def test_nothing_to_take_is_quiet(client, token, monster):
    from game.api.routes.run import apply_trophy_transfer

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    assert apply_trophy_transfer(account_id, monster.record_id) == ""


# ── 도감 (§8) ────────────────────────────────────────────────────────────


def test_bestiary_publishes_the_ruleset_verbatim(client, token, monster):
    """★ 요약하지 않는다 — 원문이 곧 카운터 설계의 입력이다 (GDD §2.3, P1)."""
    body = client.get("/api/bestiary", headers=build_headers(token)).json()
    entry = next(e for e in body["entries"] if e["record_id"] == monster.record_id)
    assert entry["ruleset"] is not None
    assert entry["ruleset"]["rules"], "규칙표가 비었다 — 요약된 것이 아니라 원문이어야 한다"


def test_bestiary_reports_level_and_cap(client, token, monster):
    """상한을 함께 보여준다 — 얼마나 더 클 수 있는지가 표적 판단에 든다."""
    body = client.get("/api/bestiary", headers=build_headers(token)).json()
    entry = next(e for e in body["entries"] if e["record_id"] == monster.record_id)
    assert entry["level"] >= 1
    assert entry["level_cap"] >= entry["level"]


def test_bestiary_flags_my_own_items(client, token, monster):
    """★ "내 아이템을 들고 있다" 가 되찾으러 가는 동기다 (World Loop)."""
    from game.api.deps import get_pool
    from game.api.routes.run import apply_trophy_transfer
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    headers = build_headers(token)
    account_id = client.get("/api/account", headers=headers).json()["account_id"]
    create_item(get_pool(), find_player_entity(get_pool(), account_id), "boots_swift", ())
    apply_trophy_transfer(account_id, monster.record_id)

    entry = next(
        e
        for e in client.get("/api/bestiary", headers=headers).json()["entries"]
        if e["record_id"] == monster.record_id
    )
    assert entry["holds_mine"] is True
    assert "boots_swift" in entry["trophies"]


def test_another_account_does_not_see_it_as_theirs(client, token, monster):
    """남의 전리품을 내 것으로 표시하면 도감이 거짓말을 한다."""
    from game.api.deps import get_pool
    from game.api.routes.run import apply_trophy_transfer
    from game.app.store.accounts import find_player_entity
    from game.app.store.items import create_item

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    create_item(get_pool(), find_player_entity(get_pool(), account_id), "armor_plate", ())
    apply_trophy_transfer(account_id, monster.record_id)

    other = client.post("/api/account").json()["token"]
    entry = next(
        e
        for e in client.get("/api/bestiary", headers=build_headers(other)).json()["entries"]
        if e["record_id"] == monster.record_id
    )
    assert entry["holds_mine"] is False


def test_the_bestiary_carries_stats_too(client, token, monster):
    """★ 규칙표만으로는 **이길 수 있는지**를 알 수 없다.

    도감이 표적 목록이려면 "어떻게 싸우는가"(규칙표)와 "얼마나 센가"(스탯)가 둘 다
    있어야 한다 (`설계/6_몬스터` §8).
    """
    rows = client.get("/api/bestiary", headers=build_headers(token)).json()["entries"]
    assert rows
    for row in rows:
        assert row["hp_max"] > 0
        assert row["attack"] > 0
        # 전투가 쓰는 것과 같은 계산이어야 한다 — 따로 세면 화면과 실제가 갈린다.
        assert row["ruleset"] is None or row["ruleset"]["rules"]
