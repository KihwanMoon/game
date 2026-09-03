"""도플갱어는 전리품을 만들지 않는다 — DB 가 필요한 두 길목 (결정 #02·#34, T11).

종 판정과 드롭 굴림은 `test_doppel_loot` 가 본다. 여기는 **강탈과 되찾기** 다 — 둘 다
지속 몬스터 상태를 읽으므로 DB 가 있어야 돈다.

아이템이 도플갱어를 거쳐 사람에게 갈 수 있는 길이 셋이고, 하나라도 열려 있으면 봇을
여럿 돌려 죽이는 것이 최적 파밍이 된다.
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


def build_doppel_pair():
    """도플갱어 하나와 일반 몬스터 하나를 스냅샷으로 짠다.

    Returns:
        (도플갱어, 일반) 순의 스냅샷들. **도플갱어를 첫 자리에 둔다** — 강탈이 첫 개체를
        고르므로, 뒤에 두면 건너뛰는지 아닌지가 드러나지 않는다.
    """
    from game.app.bots.doppel import DOPPEL_KIND_ID
    from game.schemas.monster_snapshot import MonsterSnapshot

    def build(record_id, kind_id, tier):
        return MonsterSnapshot(
            entity_id=f"{kind_id}_{record_id}",
            record_id=record_id,
            kind_id=kind_id,
            tier=tier,
            level=3,
            hp_max=10,
            attack=1,
            defense=0,
            rule_slots=0,
            cpu_budget=0,
        )

    return (build(9001, DOPPEL_KIND_ID, "ELITE"), build(9002, "goblin_rusher", "NORMAL"))


def build_probe_ticket():
    """검사용 티켓 하나.

    Returns:
        1층짜리 티켓.
    """
    from game.app.store.tickets import IssuedTicket

    return IssuedTicket(
        ticket_id="doppel-probe",
        seed=1,
        room_id=ROOM_ID,
        floor=1,
        mode="PRACTICE",
        core_version="probe",
    )


def test_a_doppel_never_takes_a_players_gear(client, token, monkeypatch):
    """★ 길 2 — 전리품 강탈. 도플갱어는 사람의 장비 사본을 갖지 않는다.

    들면 그 순간 「내 것을 들고 있는 개체」가 되고, 되찾기(길 3)가 그 위에 길을 낸다 —
    봇이 벌어 둔 장비가 사람에게 흘러가는 통로이며, 봇을 죽이는 것이 최적 파밍이 된다.
    """
    from game.api import monster_service
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun

    holders = []
    monkeypatch.setattr(monster_service, "load_snapshots", lambda *_a, **_k: build_doppel_pair())
    monkeypatch.setattr(
        monster_service,
        "apply_trophy_transfer",
        lambda _account, record_id: holders.append(record_id) or "",
    )
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    monster_service.apply_monster_outcome(
        build_probe_ticket(),
        1,
        VerifiedRun("PLAYER_LOSS", 10, 0, VERDICT_VERIFIED, ""),
        account_id,
    )
    # 첫 자리의 도플갱어를 건너뛰고 뒤의 일반 몬스터가 가져갔다.
    assert holders == [9002]


def test_a_doppel_gives_nothing_back(client, token, monkeypatch):
    """★ 길 3 — 되찾기. 도플갱어에서는 아무것도 돌려받지 않는다."""
    from game.api import monster_service
    from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun

    asked = []
    monkeypatch.setattr(monster_service, "load_snapshots", lambda *_a, **_k: build_doppel_pair())
    monkeypatch.setattr(
        monster_service,
        "apply_recovery",
        lambda _pool, record_id, *_a: asked.append(record_id) or (),
    )
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    monster_service.apply_monster_outcome(
        build_probe_ticket(),
        1,
        VerifiedRun("PLAYER_WIN", 10, 50, VERDICT_VERIFIED, ""),
        account_id,
    )
    assert asked == [9002]
