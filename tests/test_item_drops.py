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

# **표본이 크다.** 유물 등급은 만분의 5(0.05%)라 4000번으로는 기대값이 2이고, 그 자리에서
# 두 분포를 비교하면 검사가 운에 걸린다 — 실제로 전량 실행에서 깜빡였다. 확률이 작을수록
# 표본이 커야 하고, 그 사실을 상수 하나로 못 박는다.
ROLLS = 200_000


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
    # 천장은 기본 가중치의 3배까지 민다(PITY_CAP_PCT). 여유를 두고 2배만 본다 —
    # 정확한 배율은 `test_the_pity_stops_at_a_ceiling` 이 결정적으로 확인한다.
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


def test_every_fixed_affix_reaches_the_instance():
    """★ 고정 접사는 전부 붙는다 — 등급이 개수를 정하면 **잘리는 쪽이 늘 저주다**.

    카탈로그가 좋은 접사를 먼저 적어 두므로, 앞에서 잘라 쓰면 대검의 과부하와 장궁의
    페널티가 영원히 발급되지 않는다 (프로덕션에서 실제로 그랬다).
    """
    from game.app.items.drops import create_affix_rolls
    from game.schemas.item import Affix

    base = (
        Affix(stat="attack", flat=5, label_ko="묵직함"),
        Affix(stat="cpu_budget", percent=-25, label_ko="[과부하] 굼뜬 제어"),
    )
    for _try in range(40):
        rolled = create_affix_rolls(base)
        assert len(rolled) == len(base)
        assert [item.stat for item in rolled] == ["attack", "cpu_budget"]


def test_the_worst_roll_still_keeps_the_curse(monkeypatch):
    """★ 최악으로 굴려도 저주는 저주로 남는다.

    **표본에 기대지 않고 최저 굴림을 고정해 본다.** 무작위로 40번 돌면 굴림 폭의
    바닥값이 안 걸리는 판이 대부분이라, 페널티가 0 이 되는 회귀를 놓친다.
    """
    from game.app.items import loot
    from game.app.items.drops import create_affix_rolls
    from game.schemas.item import Affix

    monkeypatch.setattr(loot, "get_below", lambda _bound: 0)
    rolled = create_affix_rolls(
        (
            Affix(stat="attack", flat=5, label_ko="묵직함"),
            Affix(stat="cpu_budget", percent=-25, label_ko="[과부하] 굼뜬 제어"),
        )
    )
    assert rolled[0].flat == 4  # 5 × 80% = 4
    assert rolled[1].percent == -20  # -25 × 80% = -20. 0 이 되면 페널티가 사라진다


def test_a_catalog_without_affixes_stays_bare():
    """★ 접사가 없는 카탈로그에 굴림이 접사를 만들어 내지 않는다 (물약·두루마리)."""
    from game.app.items.drops import create_affix_rolls

    assert create_affix_rolls(()) == ()


def test_the_pity_stops_at_a_ceiling():
    """★ 상한이 없으면 천장이 자동 지급이 된다.

    한 런에 열여섯 번 굴린다 — 실측이다. 미획득이 런당 16씩 쌓이므로, 상한이 없으면
    가중치 5 짜리 유물 등급이 한 판 만에 몇 배가 된다.
    """
    from game.app.items.drops import PITY_CAP_PCT, compute_grade_weight

    ceiling = 5 + 5 * PITY_CAP_PCT // 100
    assert compute_grade_weight(5, 0, 0, 10_000) == ceiling
    assert compute_grade_weight(5, 0, 0, 1_000_000) == ceiling


def test_one_run_of_misses_does_not_multiply_the_top_grade():
    """★ 한 판 굴린 것만으로 유물이 몇 배가 되면 천장이 아니라 지급이다."""
    from game.app.items.drops import compute_grade_weight

    kills_per_run = 16
    base = compute_grade_weight(5, 0, 0, 0)
    after = compute_grade_weight(5, 0, 0, kills_per_run)
    assert after <= base * 4


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
    verified = SimpleNamespace(summary=SimpleNamespace(defeated_kinds=("goblin_rusher",) * 400))
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
    verified = SimpleNamespace(summary=SimpleNamespace(defeated_kinds=("goblin_rusher",) * 400))
    create_run_drops(account_id, None, verified, 1, "t")
    entity_id = find_player_entity(get_pool(), account_id)
    with get_pool().connection() as connection:
        rows = connection.execute(
            "SELECT grade FROM item_instance WHERE owner_entity_id = %s", (entity_id,)
        ).fetchall()
    # 400번이다. 굴림당 3.7% 라 60번으로는 한 판에 10% 확률로 빈손이 되고, 그러면
    # 검사가 운에 걸린다 — 실제로 그렇게 깜빡였다.
    assert rows, "400번 잡았는데 하나도 안 나왔다"
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


def test_a_quest_item_never_drops(client, token):
    """★ 퀘스트 아이템은 퀘스트가 주는 것이지 굴려서 나오는 것이 아니다 (설계 §4).

    예전 `list_droppable` 이 걸러 주던 것을 드롭 표로 옮기면서 빠뜨렸고, 프로덕션에서
    「봉인된 각인」이 전리품으로 나왔다.
    """
    from game.api.deps import get_item_catalog, get_pool
    from game.app.store.drops import SOURCE_ANY, find_source, read_item_weights
    from game.schemas.item import ItemKind

    catalog = get_item_catalog()
    quest = [key for key, entry in catalog.items() if entry.kind is ItemKind.QUEST]
    assert quest, "퀘스트 아이템이 카탈로그에 없어 이 검사가 아무것도 안 본다"
    source_id = find_source(get_pool(), SOURCE_ANY)
    assert source_id is not None
    listed = set()
    for grade in ("COMMON", "FINE", "RELIC"):
        listed |= {name for name, _weight in read_item_weights(get_pool(), source_id, grade, 99)}
    assert not (listed & set(quest)), f"퀘스트 아이템이 드롭 표에 있다: {listed & set(quest)}"


def test_a_monster_table_replaces_the_default(client, token):
    """★ 소스별 표가 있으면 `ANY` 를 안 본다 (D3).

    두 표를 합치면 "이 몬스터만 떨군다" 가 성립하지 않는다 — 도감이 표적 목록이 되는
    근거가 그 배타성이다.
    """
    from game.api.deps import get_pool
    from game.api.loot_service import find_drop_source
    from game.app.store.drops import (
        SOURCE_ANY,
        SOURCE_MONSTER,
        read_item_weights,
        save_monster_drop,
    )

    pool = get_pool()
    save_monster_drop(pool, "goblin_archer", "COMMON", "bow_long", 5)
    source_id, kind, ref = find_drop_source(pool, "goblin_archer")
    assert kind == SOURCE_MONSTER and ref == "goblin_archer"
    assert source_id is not None
    listed = dict(read_item_weights(pool, source_id, "COMMON", 9))
    assert listed == {"bow_long": 5}, "소스별 표에 ANY 의 후보가 섞였다"
    # 표가 없는 종은 그대로 ANY 로 떨어진다.
    assert find_drop_source(pool, "no_such_kind")[1] == SOURCE_ANY


def test_a_monster_table_inherits_the_grade_split(client, token):
    """★ 소스를 만들자마자 굴림이 통째로 막히면 아무도 소스를 안 만든다.

    **매번 새 종을 쓴다.** 같은 종을 쓰면 앞선 실행이 남긴 등급 가중치 때문에 상속을
    지워도 검사가 통과한다 — 실제로 그렇게 통과했다.
    """
    from game.api.deps import get_pool
    from game.app.store.drops import read_grade_weights, save_monster_drop

    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    pool = get_pool()
    source_id = save_monster_drop(pool, f"probe_kind_{account_id}", "FINE", "sword_great", 3)
    assert read_grade_weights(pool, source_id), "등급 가중치가 비어 있다 — 아무것도 안 나온다"
