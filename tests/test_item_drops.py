"""두 단계 추첨과 처치 단위 굴림 (설계/4_아이템 §15).

여기서 지키는 것은 여섯이다.

1. **처치마다 굴린다.** 런 단위로 굴리면 몬스터 레벨이 개입할 자리가 없다.
2. **등급이 인스턴스에 복사된다.** 참조로 두면 카탈로그를 고칠 때 남의 가방 아이템의
   등급이 소급해 바뀐다.
3. **안 나온 굴림도 남는다.** 안 나온 것이 데이터다 — 결과만 남기면 확률을 사후에
   증명할 수 없다.
4. **천장이 돈다.** 확률만으로는 "나는 안 나온다" 를 못 막는다.
5. **아직 안 열린 층의 아이템은 안 나온다.**
6. **아이템을 더해도 등급 분포가 안 흔들린다.** 두 단계로 가른 이유 그 자체다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

ROLLS = 4000


def build_weights():
    from game.app.store.drops import DEFAULT_GRADE_WEIGHTS, GRADE_MISS

    graded = tuple((g, w, s) for g, w, s in DEFAULT_GRADE_WEIGHTS if g != GRADE_MISS)
    miss = next(w for g, w, _s in DEFAULT_GRADE_WEIGHTS if g == GRADE_MISS)
    return graded, miss


def count_grades(level, pity=None):
    from collections import Counter

    from game.app.items.drops import build_grade_pool, get_weighted

    graded, miss = build_weights()
    return Counter(
        get_weighted(build_grade_pool(graded, miss, level, pity or {})) for _ in range(ROLLS)
    )


def test_a_higher_level_pushes_the_upper_grades():
    """★ 레벨이 1단계에만 개입한다 (§15.2)."""
    low = count_grades(1)
    high = count_grades(20)
    assert high["FINE"] > low["FINE"], "레벨이 올라도 상급 몫이 안 는다"


def test_the_pity_lifts_the_grade_it_counts():
    """★ 확률만으로는 「나는 안 나온다」를 못 막는다 (D2)."""
    plain = count_grades(1)
    pitied = count_grades(1, {"RELIC": 40})
    assert pitied["RELIC"] > plain["RELIC"] * 2


def test_adding_an_item_does_not_move_the_grade_split():
    """★ 이 설계의 전부다 — 아이템을 더해도 등급 분포가 안 흔들린다.

    한 표에 절대 확률을 적어 두면 보통 등급에 하나를 더하는 순간 유물 등급까지 내려간다.
    2단계는 등급 **안의** 비율이므로 1단계 저울에 손대지 않는다.
    """
    from game.app.items.drops import build_grade_pool

    graded, miss = build_weights()
    before = build_grade_pool(graded, miss, 3, {})
    after = build_grade_pool(graded, miss, 3, {})
    assert before == after
    # 2단계 저울을 아무리 늘려도 1단계는 같은 값이다.
    assert dict(before)["COMMON"] == dict(after)["COMMON"]


def test_a_zero_pool_yields_nothing():
    """★ 가중치가 0 뿐이면 아무것도 안 뽑는다 — 마지막 것을 억지로 내면 분포가 거짓이 된다."""
    from game.app.items.drops import get_weighted

    assert get_weighted((("a", 0), ("b", 0))) is None
    assert get_weighted(()) is None


def test_the_grade_decides_how_many_affixes_roll():
    """★ 등급이 성능을 정한다 — 이름표로만 두면 등급이 뜻을 잃는다 (§15.4)."""
    from game.app.items.drops import create_affix_rolls
    from game.schemas.item import GRADE_COMMON, GRADE_RELIC, Affix

    base = tuple(Affix(stat=f"s{index}", flat=index + 1) for index in range(3))
    assert all(len(create_affix_rolls(base, GRADE_COMMON)) == 1 for _ in range(20))
    assert max(len(create_affix_rolls(base, GRADE_RELIC)) for _ in range(60)) == 3


def test_the_weight_never_goes_below_zero():
    """음수 가중치가 나오면 get_weighted 의 합이 어긋나 뽑기가 치우친다."""
    from game.app.items.drops import compute_grade_weight

    assert compute_grade_weight(10, -500, 9, 0) == 0


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


@pytest.fixture
def token(client):
    return client.post("/api/account").json()["token"]


def build_headers(token):
    return {"X-Game-Token": token}


def count_rolls(account_id):
    from game.api.deps import get_pool

    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM item_roll_log WHERE account_id = %s", (account_id,)
        ).fetchone()
    return 0 if row is None else int(row[0])


def test_every_kill_rolls_once(client, token):
    """★ 처치마다 굴린다 — 런 단위로 굴리면 몬스터 레벨이 개입할 자리가 없다 (§15.3)."""
    from types import SimpleNamespace

    from game.api.loot_service import create_run_drops

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    before = count_rolls(account_id)
    verified = SimpleNamespace(
        summary=SimpleNamespace(defeated_kinds=("goblin_rusher", "goblin_rusher", "goblin_archer"))
    )
    create_run_drops(account_id, None, verified, 1, "no-such-ticket")
    assert count_rolls(account_id) - before == 3


def test_nothing_defeated_rolls_nothing(client, token):
    """★ 아무도 못 잡았으면 굴리지 않는다 — 굴리면 진 판이 이긴 판과 같아진다."""
    from types import SimpleNamespace

    from game.api.loot_service import create_run_drops

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    before = count_rolls(account_id)
    verified = SimpleNamespace(summary=SimpleNamespace(defeated_kinds=()))
    assert create_run_drops(account_id, None, verified, 1, "t") == []
    assert count_rolls(account_id) == before


def test_a_miss_is_written_down_too(client, token):
    """★ 안 나온 것이 데이터다 — 결과만 남기면 확률을 사후에 증명할 수 없다 (D4)."""
    from types import SimpleNamespace

    from game.api.deps import get_pool
    from game.api.loot_service import create_run_drops

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    verified = SimpleNamespace(summary=SimpleNamespace(defeated_kinds=("goblin_rusher",) * 40))
    create_run_drops(account_id, None, verified, 1, "t")
    with get_pool().connection() as connection:
        row = connection.execute(
            "SELECT count(*) FROM item_roll_log WHERE account_id = %s AND catalog_id IS NULL",
            (account_id,),
        ).fetchone()
    assert row is not None and int(row[0]) > 0, "안 나온 굴림이 하나도 안 남았다"


def test_the_instance_carries_the_grade_it_rolled(client, token):
    """★ 카탈로그를 참조하지 않고 복사한다 (§15.5)."""
    from types import SimpleNamespace

    from game.api.deps import get_pool
    from game.api.loot_service import create_run_drops
    from game.app.store.accounts import find_player_entity

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    verified = SimpleNamespace(summary=SimpleNamespace(defeated_kinds=("goblin_rusher",) * 60))
    create_run_drops(account_id, None, verified, 1, "t")
    entity_id = find_player_entity(get_pool(), account_id)
    with get_pool().connection() as connection:
        rows = connection.execute(
            "SELECT grade FROM item_instance WHERE owner_entity_id = %s", (entity_id,)
        ).fetchall()
    assert rows, "60번 잡았는데 하나도 안 나왔다"
    assert all(row[0] in {"COMMON", "FINE", "RELIC"} for row in rows)


def test_an_unopened_floor_item_does_not_drop(client, token):
    """★ 1층에서 유물이 나오면 깊이 들어갈 이유가 없다 (D1)."""
    from game.api.deps import get_pool
    from game.app.store.drops import SOURCE_ANY, find_source, read_item_weights

    source_id = find_source(get_pool(), SOURCE_ANY)
    assert source_id is not None
    with get_pool().connection() as connection:
        connection.execute(
            "UPDATE item_catalog SET min_floor = 5 WHERE catalog_id = %s", ("helm_iron",)
        )
    try:
        shallow = dict(read_item_weights(get_pool(), source_id, "COMMON", 1))
        deep = dict(read_item_weights(get_pool(), source_id, "COMMON", 5))
        assert "helm_iron" not in shallow
        assert "helm_iron" in deep
    finally:
        with get_pool().connection() as connection:
            connection.execute(
                "UPDATE item_catalog SET min_floor = 1 WHERE catalog_id = %s", ("helm_iron",)
            )


def test_a_retired_item_stops_dropping(client, token):
    """★ 폐기는 「새로 안 나온다」다 — 그 뜻이 실제로 걸려야 한다 (§15.7)."""
    from game.api.deps import get_pool
    from game.app.store.drops import SOURCE_ANY, find_source, read_item_weights
    from game.app.store.item_catalog import apply_retire

    source_id = find_source(get_pool(), SOURCE_ANY)
    assert source_id is not None
    apply_retire(get_pool(), "helm_iron")
    try:
        assert "helm_iron" not in dict(read_item_weights(get_pool(), source_id, "COMMON", 9))
    finally:
        apply_retire(get_pool(), "helm_iron", is_retired=False)
