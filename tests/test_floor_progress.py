"""층 진행 (설계/6_몬스터 §3).

**층 스케일 수식은 처음부터 있었는데 한 번도 발동한 적이 없었다.** 클라이언트가 티켓
요청에 층을 안 실어서 늘 1층이었다. 층당 HP +25%·공격 +20% 가 코드에 있는데 게임에는
없던 셈이다.

여기서 지키는 것은 넷이다.

1. **층을 서버가 정한다.** 요청한 층은 제안일 뿐이고 도달 층을 못 넘는다 — 넘기면
   1층 캐릭터로 10층 보상을 뽑는다 (T2 와 같은 자리).
2. **재시뮬이 확정한 승리만 층을 연다.** 클라이언트 보고로 열면 "10층을 깼다" 고 적어
   보내는 것이 곧 진행이 된다 (T9).
3. **되돌아가도 기록이 안 내려간다.** 편한 층을 다시 도는 것이 벌이 되면 안 된다.
4. **끝이 있다.** 마지막 층을 넘어 열리지 않아야 「깼다」가 성립한다.
"""

import os

import pytest

from game.app.progression.floors import read_boss_floor, read_floor_cap, resolve_floor
from game.app.store.connection import DATABASE_URL_ENV


def test_a_requested_floor_cannot_exceed_what_was_reached():
    """★ 요청한 층을 그대로 쓰면 1층 캐릭터가 10층 보상을 뽑는다."""
    assert resolve_floor(10, 3) == 3
    assert resolve_floor(2, 3) == 2


def test_a_floor_never_falls_below_the_first():
    """★ 0층·음수 층은 없다 — 스케일이 음수 배율이 되면 적이 회복하며 태어난다."""
    assert resolve_floor(0, 5) == 1
    assert resolve_floor(-3, 5) == 1


def test_a_fresh_account_starts_at_the_first_floor():
    """★ 기록이 없으면 1층이다."""
    assert resolve_floor(9, 0) == 1


def test_the_cap_comes_from_balance():
    """★ 끝을 밸런스가 정한다 — 코드에 박으면 조정하려면 배포해야 한다."""
    assert read_floor_cap({"floor_scale": {"max_floor": 10}}) == 10
    assert read_boss_floor({"floor_scale": {"max_floor": 10, "boss_floor": 10}}) == 10


def test_an_unknown_cap_stays_at_one():
    """★ 모르면 안 내려보낸다.

    큰 값으로 넘겨짚으면 방이 모자란 층으로 사람을 보내게 되고, 그 층은 후보가 없어
    같은 방만 되풀이된다.
    """
    assert read_floor_cap({}) == 1


def test_the_shipped_balance_declares_ten_floors():
    """★ 실제로 쓰는 밸런스가 10층을 말한다 — 수식만 있고 값이 없으면 층이 안 오른다."""
    import json
    from pathlib import Path

    balance = json.loads(Path("game/resources/balance/balance.json").read_text(encoding="utf-8"))
    assert read_floor_cap(balance) == 10
    assert read_boss_floor(balance) == 10


pytestmark_db = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def entity():
    """계정 하나와 그 개체. 앱을 세워 마이그레이션까지 끝난 상태를 받는다."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.deps import get_pool
    from game.api.main import create_app
    from game.app.store.accounts import find_player_entity

    with fastapi_testclient.TestClient(create_app()) as client:
        account_id = int(client.post("/api/account").json()["account_id"])
        yield get_pool(), find_player_entity(get_pool(), account_id)


@pytestmark_db
def test_a_new_entity_has_reached_the_first_floor(entity):
    """★ 새 계정이 깊은 층에서 시작하면 층 진행이 뜻을 잃는다."""
    from game.app.store.progress import read_reached_floor

    pool, entity_id = entity
    assert read_reached_floor(pool, entity_id) == 1


@pytestmark_db
def test_clearing_a_floor_opens_the_next(entity):
    """★ 층을 깨면 다음 층이 열린다 — 안 열리면 1층에 갇힌다."""
    from game.app.store.progress import apply_floor_progress, read_reached_floor

    pool, entity_id = entity
    assert apply_floor_progress(pool, entity_id, 1, 10) == 2
    assert read_reached_floor(pool, entity_id) == 2


@pytestmark_db
def test_replaying_a_lower_floor_never_lowers_the_record(entity):
    """★ 편한 층을 다시 도는 것이 벌이 되면 연습할 곳이 사라진다."""
    from game.app.store.progress import apply_floor_progress

    pool, entity_id = entity
    apply_floor_progress(pool, entity_id, 4, 10)
    assert apply_floor_progress(pool, entity_id, 1, 10) == 5


@pytestmark_db
def test_the_record_stops_at_the_last_floor(entity):
    """★ 끝을 넘어 열리면 「깼다」가 성립하지 않는다."""
    from game.app.store.progress import apply_floor_progress

    pool, entity_id = entity
    assert apply_floor_progress(pool, entity_id, 10, 10) == 10
    assert apply_floor_progress(pool, entity_id, 99, 10) == 10


@pytestmark_db
def test_the_ticket_floor_is_decided_by_the_server(entity):
    """★ 요청한 층을 그대로 발급하면 1층 캐릭터가 10층 티켓을 받는다 (T2)."""
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as client:
        token = client.post("/api/account").json()["token"]
        issued = client.post(
            "/api/ticket",
            json={"room_id": "open_field", "floor": 10},
            headers={"X-Game-Token": token},
        ).json()
    assert issued["floor"] == 1


@pytestmark_db
def test_only_a_verified_win_opens_the_next_floor(entity):
    """★ 반려된 제출이나 진 판이 층을 열면 제출만 하면 내려가는 길이 열린다 (T9)."""
    from dataclasses import dataclass

    from game.api.routes.run import apply_floor_outcome
    from game.app.store.accounts import find_player_entity
    from game.app.store.progress import read_reached_floor

    @dataclass
    class Probe:
        verdict: str
        outcome: str

    pool, entity_id = entity
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT owner_account_id FROM entity_record WHERE id = %s", (entity_id,)
        ).fetchone()
    account_id = int(row[0])
    assert find_player_entity(pool, account_id) == entity_id

    assert apply_floor_outcome(account_id, Probe("verified", "ENEMY_WIN"), 1) == ""
    assert apply_floor_outcome(account_id, Probe("rejected", "PLAYER_WIN"), 1) == ""
    assert read_reached_floor(pool, entity_id) == 1

    assert "2층" in apply_floor_outcome(account_id, Probe("verified", "PLAYER_WIN"), 1)
    assert read_reached_floor(pool, entity_id) == 2


@pytestmark_db
def test_clearing_a_floor_twice_says_nothing_the_second_time(entity):
    """★ 이미 지나온 층을 다시 이겼을 때도 「열렸다」가 뜨면 그 줄이 뜻을 잃는다."""
    from dataclasses import dataclass

    from game.api.routes.run import apply_floor_outcome

    @dataclass
    class Probe:
        verdict: str
        outcome: str

    pool, entity_id = entity
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT owner_account_id FROM entity_record WHERE id = %s", (entity_id,)
        ).fetchone()
    account_id = int(row[0])
    won = Probe("verified", "PLAYER_WIN")
    assert apply_floor_outcome(account_id, won, 1) != ""
    assert apply_floor_outcome(account_id, won, 1) == ""
