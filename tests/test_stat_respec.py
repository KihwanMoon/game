"""능력치 무르기 — 언제 공짜이고 언제 값을 내는가 (2026-09-17).

**예전에는 조건 없이 공짜였다.** 라우트 독스트링이 「되돌릴 수 없다」고 적어 두었는데
`check_allocation` 은 「쓴 점 ≤ 가진 점」만 봤고 저장은 배분표를 통째로 덮어썼다 — 화면이
더하기만 시켜서 안 드러났을 뿐, API 로는 언제든 갈아치울 수 있었다. 문서와 코드가 반대인
채로 있던 자리다.

규칙은 셋이다.

* **늘리기는 값을 안 받는다.** 안 쓴 포인트를 쓰는 데 돈을 받으면 레벨업이 벌이 된다.
* **1장을 깨기 전에는 무르기도 공짜다.** 처음 오는 사람은 **지능이 CPU 를 연다**는 것을
  모른 채 찍고, 힘에 몰아넣으면 규칙을 몇 줄 못 돌리는 몸이 된다 (P3).
* **그 뒤로는 푼을 내고, 값은 레벨마다 가팔라진다.**
"""

import os

import pytest

from game.app.progression.levels import (
    RESPEC_FREE_BEFORE_FLOOR,
    check_is_respec,
    check_respec_is_free,
    compute_respec_cost,
)
from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

# **규칙 검사는 DB 없이도 돈다.** 아래쪽 라우트 검사만 DB 가 필요하므로, 건너뛰기를
# 파일 전체에 걸지 않고 그 함수들에만 건다 — 전체에 걸면 순수 규칙까지 함께 잠긴다.
needs_db = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


def test_raising_a_stat_is_not_a_respec() -> None:
    """안 쓴 포인트를 쓰는 것은 무르기가 아니다."""
    assert not check_is_respec({"str": 5, "dex": 0, "int": 0}, {"str": 3, "dex": 0, "int": 0})
    assert not check_is_respec({"str": 3, "dex": 2, "int": 0}, {"str": 3, "dex": 0, "int": 0})


def test_lowering_any_stat_is_a_respec() -> None:
    """한 축이라도 줄면 무르기다 — 합이 같아도 그렇다."""
    assert check_is_respec({"str": 0, "dex": 0, "int": 3}, {"str": 3, "dex": 0, "int": 0})
    # 합은 그대로인데 축만 옮긴 경우. **이것이 전형적인 무르기다.**
    assert check_is_respec({"str": 2, "dex": 1, "int": 0}, {"str": 3, "dex": 0, "int": 0})


def test_an_untouched_table_is_not_a_respec() -> None:
    """같은 표를 다시 보내는 것에 값을 받으면 새로고침이 벌이 된다."""
    assert not check_is_respec({"str": 3, "dex": 0, "int": 0}, {"str": 3, "dex": 0, "int": 0})


def test_a_missing_key_counts_as_zero_and_lowers() -> None:
    """빠뜨린 축은 0 이다 — 안 그러면 키를 빼는 것으로 값을 피할 수 있다."""
    assert check_is_respec({"dex": 0, "int": 0}, {"str": 3, "dex": 0, "int": 0})


def test_the_first_floor_is_free() -> None:
    """1장을 깨기 전에는 공짜다. 깨면 그때부터 값을 낸다."""
    assert check_respec_is_free(1)
    assert not check_respec_is_free(RESPEC_FREE_BEFORE_FLOOR)
    assert not check_respec_is_free(9)


def test_the_cost_accelerates_with_level() -> None:
    """**선형이면 깊이 간 사람에게 부담이 안 된다.** 레벨마다 가팔라져야 한다."""
    costs = [compute_respec_cost(level) for level in range(1, 12)]
    assert costs == sorted(costs)
    # 가속: 뒤쪽 한 칸의 증가폭이 앞쪽보다 커야 한다.
    assert costs[10] - costs[9] > costs[1] - costs[0]
    # 깊이 간 사람에게는 실제로 무겁다 — 지갑 중앙값이 155 푼이다 (2026-09-17 실측).
    assert compute_respec_cost(10) > 5000


def test_the_cost_never_vanishes() -> None:
    """레벨 1 에서도 0 이 아니다 — 0 이면 규칙이 없는 것과 같다."""
    assert compute_respec_cost(1) > 0
    assert compute_respec_cost(0) == compute_respec_cost(1)


# ── 여기서부터는 라우트가 실제로 값을 받는가. DB 가 있어야 돈다.


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_probe(client, reached_floor, level_xp, coins):
    """무르기를 시험할 계정 하나를 세운다.

    Args:
        client: 테스트 클라이언트.
        reached_floor: 서버가 아는 도달 층.
        level_xp: 넣어 줄 누적 경험치.
        coins: 넣어 줄 푼.

    Returns:
        (토큰, 계정 id).
    """
    from game.api.deps import get_pool
    from game.app.store.accounts import find_account, find_player_entity
    from game.app.store.equipment import add_currency

    token = client.post("/api/account").json()["token"]
    pool = get_pool()
    account = find_account(pool, token)
    entity_id = find_player_entity(pool, account.account_id)
    with pool.connection() as connection:
        connection.execute(
            "UPDATE entity_record SET total_xp = %s, reached_floor = %s WHERE id = %s",
            (level_xp, reached_floor, entity_id),
        )
    add_currency(pool, account.account_id, coins)
    return token, account.account_id


def read_coins(account_id):
    """지갑 잔액.

    Args:
        account_id: 계정 id.

    Returns:
        푼.
    """
    from game.api.deps import get_pool
    from game.app.store.equipment import read_balance

    return read_balance(get_pool(), account_id)


@needs_db
def test_a_respec_before_the_first_floor_costs_nothing(client):
    """★ 1장을 깨기 전에는 무르기가 공짜다 — 처음 오는 사람이 잠기면 안 된다."""
    token, account_id = build_probe(client, reached_floor=1, level_xp=5000, coins=10_000)
    headers = {"X-Game-Token": token}
    client.put("/api/progress/stats", json={"stats": {"str": 3}}, headers=headers)
    before = read_coins(account_id)
    answer = client.put("/api/progress/stats", json={"stats": {"int": 3}}, headers=headers)
    assert answer.status_code == 200, answer.text
    assert answer.json()["stats"]["int"] == 3
    assert read_coins(account_id) == before, "공짜여야 하는데 값을 받았다"


@needs_db
def test_a_respec_after_the_first_floor_costs_coins(client):
    """★ 1장을 깬 뒤에는 푼을 낸다."""
    from game.app.progression.levels import compute_respec_cost

    token, account_id = build_probe(client, reached_floor=2, level_xp=5000, coins=1_000_000)
    headers = {"X-Game-Token": token}
    client.put("/api/progress/stats", json={"stats": {"str": 3}}, headers=headers)
    before = read_coins(account_id)
    answer = client.put("/api/progress/stats", json={"stats": {"int": 3}}, headers=headers)
    assert answer.status_code == 200, answer.text
    level = answer.json()["level"]
    assert before - read_coins(account_id) == compute_respec_cost(level)


@needs_db
def test_raising_a_stat_after_the_first_floor_is_still_free(client):
    """★ 늘리기에 값을 받으면 레벨업이 벌이 된다."""
    token, account_id = build_probe(client, reached_floor=5, level_xp=5000, coins=1_000_000)
    headers = {"X-Game-Token": token}
    client.put("/api/progress/stats", json={"stats": {"str": 3}}, headers=headers)
    before = read_coins(account_id)
    answer = client.put("/api/progress/stats", json={"stats": {"str": 6}}, headers=headers)
    assert answer.status_code == 200, answer.text
    assert read_coins(account_id) == before


@needs_db
def test_a_respec_without_the_coins_is_refused(client):
    """★ 못 내면 거절한다 — **배분은 그대로 남아야 한다.**

    돈이 모자란데 배분만 바뀌면 공짜 무르기가 된다.
    """
    token, account_id = build_probe(client, reached_floor=2, level_xp=5000, coins=0)
    headers = {"X-Game-Token": token}
    client.put("/api/progress/stats", json={"stats": {"str": 3}}, headers=headers)
    answer = client.put("/api/progress/stats", json={"stats": {"int": 3}}, headers=headers)
    assert answer.status_code == 400
    assert "푼" in answer.json()["detail"]
    live = client.get("/api/progress", headers=headers).json()
    assert live["stats"].get("str") == 3, "값을 못 냈는데 배분이 바뀌었다"
    assert read_coins(account_id) == 0
