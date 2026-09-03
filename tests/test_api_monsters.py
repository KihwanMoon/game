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

# 성장 상한 검사가 쓰는 자리. 방 템플릿에 없는 이름이라 다른 검사의 전투에 안 끼어든다.
GROWTH_SLOT = "growth_cap_probe"
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
    """★ 제출이 스냅샷을 받으면 약한 것으로 바꿔 보낼 수 있다 (T8).

    **`floor` 는 결과가 아니라 「어디까지 확인해 달라」는 주장이다.** 서버가 그 층까지
    **처음부터** 다시 돌려 확정하므로 깊게 적어 봐야 더 많이 시뮬될 뿐이고, 얕게 적으면
    그 층 보상만 받는다 — 어느 쪽도 이득이 없다. 결과·시드·방·스냅샷을 받을 자리는
    여전히 없다.
    """
    from game.api.schemas import SubmissionRequest

    assert "monster_snapshot" not in SubmissionRequest.model_fields
    assert set(SubmissionRequest.model_fields) == {
        "ticket_id",
        "ruleset",
        "core_version",
        "floor",
    }


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
    from game.app.monsters.growth import get_level_cap
    from game.app.services.verify_run import evaluate_submission
    from game.app.store.monsters import load_snapshots, set_monster_level
    from game.app.store.tickets import find_open_ticket

    # **레벨을 이 검사가 정한다.** 앞선 검사들이 먹이고 잡아 온 레벨을 그대로 물려받으면,
    # 어느 날 그 값이 템플릿 기본값과 비슷해져 두 판이 같은 틱에 끝난다 — 그러면 이
    # 검사는 「스냅샷이 전투를 안 바꾼다」고 거짓 신고를 한다. 실제로 그렇게 깨졌다.
    set_monster_level(get_pool(), monster.record_id, get_level_cap(1))
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


def test_snapshot_changes_the_battle(client, token, monster, monkeypatch):
    """스냅샷이 실제로 전투를 바꾼다 — 안 바뀌면 얼려 두는 뜻이 없다.

    **시드를 못 박는다.** 티켓이 시드를 굴리게 된 뒤로는 어떤 시드에서 두 판이 같은 틱에
    끝나는 일이 생기고, 그때 이 검사는 「스냅샷이 전투를 안 바꾼다」고 거짓 신고를 한다.
    """
    from game.app.store import tickets as tickets_store

    monkeypatch.setattr(tickets_store, "create_seed", lambda: 12345)
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


def test_growth_stops_at_the_floor_cap(client):
    """★ 상한이 실제로 건다 — 한때 안 걸렸다.

    사는 층을 `max(티켓 층, 레벨)` 로 파생하던 때가 있었다. 레벨이 층을 올리고, 오른 층이
    상한(`층 × 5`)을 올리고, 올라간 상한이 레벨을 더 올린다 — 되먹임 고리라 상한이 영영
    안 걸렸고, 1층 개체가 레벨 12까지 자랐다. 그 개체를 만난 플레이어는 이길 수 없는
    판을 받는다 (결정 #35 가 막으려던 바로 그것).
    """
    from game.api.deps import get_pool
    from game.api.monster_service import resolve_home_floor
    from game.app.monsters.growth import get_level_cap
    from game.app.monsters.tiers import MonsterTier
    from game.app.store.monsters import (
        add_monster_xp,
        create_monster,
        list_monsters,
        set_monster_level,
    )
    from game.app.store.tickets import IssuedTicket
    from game.schemas.monster_snapshot import MonsterSnapshot

    pool = get_pool()
    # **제 슬롯을 쓴다.** 방 템플릿의 자리를 키우면 그 개체로 싸우는 다른 검사가
    # 덩달아 달라진다 — 실제로 `test_snapshot_changes_the_battle` 이 그렇게 깨졌다.
    create_monster(pool, "goblin_rusher", MonsterTier.ELITE, 1, GROWTH_SLOT)
    probe = next(item for item in list_monsters(pool, 1) if item.entity_slot == GROWTH_SLOT)
    # 앞선 실행이 남긴 레벨을 지운다. 안 그러면 두 번째 실행부터 이미 상한이라 무의미하다.
    set_monster_level(pool, probe.record_id, 1)
    cap = get_level_cap(1)
    # 상한을 넘기고도 남을 만큼 먹인다. 고리가 살아 있으면 여기서 상한을 넘어간다.
    for _feed in range(40):
        home = resolve_home_floor(
            pool,
            MonsterSnapshot(
                entity_id=GROWTH_SLOT,
                record_id=probe.record_id,
                kind_id=probe.catalog_id,
                tier=probe.tier,
                level=probe.level,
                hp_max=1,
                attack=1,
                defense=0,
                rule_slots=0,
                cpu_budget=0,
            ),
            IssuedTicket(
                ticket_id="probe",
                seed=1,
                room_id=ROOM_ID,
                floor=1,
                mode="PRACTICE",
                core_version="probe",
            ),
        )
        assert home == 1
        assert add_monster_xp(pool, probe.record_id, home, "PLAYER", None) <= cap


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
    from game.api.monster_service import apply_trophy_transfer
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
    from game.api.monster_service import apply_trophy_transfer

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    assert apply_trophy_transfer(account_id, monster.record_id) == ""
