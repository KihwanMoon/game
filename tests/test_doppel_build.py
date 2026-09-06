"""그림자가 **실제로 그 빌드로 싸우는가** (설계/6_몬스터 §5).

`test_api_doppel.py` 는 그림자가 서는 조건과 무엇을 들고 서는가를 보고,
`test_doppel_roster.py` 는 자리를 누가 갖는가를 본다. 여기는 **얼려 둔 것이 전투에
도달하는가**다 — 저장은 되는데 안 읽히는 자리가 이 기제에 셋이나 있었다.

실측이 계기였다. 7층 그림자가 이랬다.

    전투에 쓰이는 값 : hp 204 · 공 24 · 방 7      ← 카탈로그(hp 100) + 등급 + 성장
    얼려 둔 봇의 값  : hp 357 · 공 70 · 방 42     ← 아무도 안 읽음

**그림자가 원본 봇보다 약했다.** 공격 1/3, 방어 1/6. 「그 빌드로 여기까지 왔다」가
이 개체의 뜻인데, 정작 그 빌드가 전투에 하나도 안 도달하고 있었다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

fastapi_testclient = pytest.importorskip("fastapi.testclient")

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)

# 봇이 쓰던 전투 입력. 카탈로그 기본값(hp 100 · 공 12 · 방 5 · 사거리 1)과 전부 다르게
# 골랐다 — 같은 값이 섞이면 「덮은 것」과 「원래 그랬던 것」이 구분되지 않는다.
BOT_LOADOUT = {
    "hp_max": 357,
    "attack": 70,
    "defense": 42,
    "attack_range": 4,
    "rule_slots": 9,
    "cpu_budget": 19,
    "skills": ["AIMED_SHOT", "GUARD_BRACE"],
    "consumables": {"POTION": 3},
}


@pytest.fixture
def client():
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


@pytest.fixture(autouse=True)
def clean_doppels(client):
    """검사 사이에 그림자를 지운다 — 상한이 있어 안 지우면 뒤가 건너뛰어진다."""
    from game.api.deps import get_pool

    def wipe():
        with get_pool().connection() as connection:
            connection.execute("DELETE FROM entity_record WHERE kind = 'MONSTER' AND is_doppel")

    wipe()
    yield
    wipe()


def build_shadow(client, floor=7):
    """봇의 빌드로 그림자 하나를 세우고 그 스냅샷을 낸다.

    Args:
        client: 테스트 클라이언트.
        floor: 세울 층.

    Returns:
        (스냅샷, 카탈로그 절).
    """
    from game.api.deps import get_context, get_pool
    from game.app.store.bots import create_bot
    from game.app.store.doppels import create_doppel
    from game.app.store.monster_snapshots import build_monster_snapshot
    from game.app.store.monsters import find_monster

    pool = get_pool()
    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    create_bot(pool, account_id, "그림자봇", "g0_kite", 720, 60)
    record_id = create_doppel(pool, account_id, floor, "build_slot", BOT_LOADOUT, {})
    assert record_id != 0
    record = find_monster(pool, record_id)
    assert record is not None
    base = next(k for k in get_context().balance["enemies"] if k["id"] == "doppelganger")
    return build_monster_snapshot(record, base), base


def test_the_frozen_build_reaches_the_snapshot(client):
    """★ 얼려 둔 스탯이 전투에 도달한다 — 안 읽히면 그림자가 원본보다 약하다."""
    snapshot, base = build_shadow(client)

    assert snapshot.hp_max == BOT_LOADOUT["hp_max"]
    assert snapshot.attack == BOT_LOADOUT["attack"]
    assert snapshot.defense == BOT_LOADOUT["defense"]
    # 카탈로그 값이 아니라는 것을 못 박는다 — 우연히 같아진 것이 아니어야 한다.
    assert snapshot.hp_max != base["hp_max"]


def test_the_frozen_build_replaces_and_never_stacks(client):
    """★ 덮는 것이지 얹는 것이 아니다.

    등급·성장을 곱하면 같은 개체가 볼 때마다 다른 값을 갖게 되어 「그 빌드로 여기까지
    왔다」가 뜻을 잃는다 — 전투 쪽이 층 스케일을 대체하는 것과 같은 규율이다.
    """
    shallow, _base = build_shadow(client, floor=2)
    assert shallow.hp_max == BOT_LOADOUT["hp_max"], "얕은 층에서 값이 달라졌다"


def test_the_kit_reaches_the_snapshot(client):
    """★ 사거리·스킬이 실린다 — 장궁 든 봇의 그림자가 근접으로 싸우면 안 된다.

    **물약만 빠진다** (2026-09-06). 목숨 셋에 회복까지 붙으면 한 판이 아니라 소모전이
    된다 — 잡을 수 있어야 「끝내 지웠다」가 성립한다.
    """
    snapshot, base = build_shadow(client)

    assert snapshot.attack_range == BOT_LOADOUT["attack_range"]
    assert snapshot.attack_range != base["attack_range"], "카탈로그 사거리 그대로다"
    # 정렬해서 담는다 — 순회 순서가 티켓에 새면 두 코어가 갈린다 (R5).
    assert snapshot.skills == ("AIMED_SHOT", "GUARD_BRACE")
    assert snapshot.potions == 0, "그림자가 물약을 들고 있다"


def test_the_kit_reaches_the_battle(client):
    """★ 스냅샷까지 왔다고 전투까지 오는 것은 아니다.

    스탯이 바로 그렇게 끊겨 있었다 — `stat_json` 에 저장은 되는데 `list_monsters` 가
    그 칸을 안 읽어서, 실려 있으나 아무도 안 보는 값이었다.
    """
    from game.api.deps import get_context
    from game.app.services.run_battle import build_engine
    from game.config import ROOM_TEMPLATES_PATH
    from game.schemas.room import load_room_templates

    snapshot, _base = build_shadow(client)
    context = get_context()
    template = next(iter(load_room_templates(ROOM_TEMPLATES_PATH)))
    # 스냅샷이 걸릴 자리 이름으로 맞춘다 — 안 맞으면 아무에게도 안 붙는다.
    slot = f"{template.enemy_spawns[0].kind}_0"
    engine = build_engine(
        template=template,
        balance=context.balance,
        seed=1,
        # **층을 맞춰야 스냅샷이 걸린다.** 얼려 둔 것은 사는 층으로 골라지므로, 층이
        # 다르면 그 개체는 아무에게도 안 붙고 템플릿의 고블린이 그대로 선다.
        floor=7,
        snapshots=(
            type(snapshot)(**{**vars(snapshot), "entity_id": slot, "kind_id": "doppelganger"}),
        ),
    )

    entity = engine.state.entities[slot]
    assert entity.kind_id == "doppelganger"
    assert entity.attack_range == BOT_LOADOUT["attack_range"], "사거리가 종의 값으로 떨어졌다"
    # **물약만 뺀다** (2026-09-06). 목숨 셋에 회복까지 붙으면 한 판이 아니라 소모전이
    # 되고, 잡을 수 있어야 「끝내 지웠다」가 성립한다. 나머지 키트는 그대로 온다.
    assert entity.count_item("POTION") == 0
    assert entity.skills == ("AIMED_SHOT", "GUARD_BRACE")
    assert entity.hp_max == BOT_LOADOUT["hp_max"]


def test_an_old_ticket_still_simulates_the_same(client):
    """★ 키트를 안 싣던 옛 티켓은 예전과 똑같이 돌아야 한다 (R5).

    안 실린 값을 0 이나 빈 것으로 읽어 그대로 쓰면, 이미 발급된 티켓의 재시뮬이 발급
    당시와 달라지고 정상 제출이 반려된다.
    """
    from game.schemas.monster_snapshot import parse_snapshot

    old = parse_snapshot(
        {
            "entity_id": "goblin_rusher_0",
            "record_id": 1,
            "kind_id": "goblin_rusher",
            "tier": "NORMAL",
            "level": 1,
            "hp_max": 10,
            "attack": 2,
            "defense": 1,
            "rule_slots": 0,
            "cpu_budget": 0,
        }
    )

    # 셋 다 「안 실렸다」여야 전투가 종의 값으로 떨어진다.
    assert old.attack_range == 0
    assert old.skills == ()
    assert old.potions == -1


# 이 그림자만의 규칙표. 종의 기본표(`ai_veteran`)와 **다른 행동**을 골라야 갈렸는지 보인다.
SHADOW_RULESET = {
    "ruleset_id": "shadow_only",
    "version": 1,
    "rules": [
        {
            "priority": 1,
            "conditions": {
                "op": "SINGLE",
                "terms": [{"cmp": ">=", "lhs": "self_hp_pct", "lhs_param": None, "rhs": 0}],
            },
            "action": "RETREAT",
            "target": "NEAREST",
            "cpu_cost": 1,
            "set_flag": None,
        }
    ],
}


def test_the_shadow_fights_with_its_own_ruleset(client):
    """★ 「그 규칙표가 나를 읽는다」가 이 개체의 전부다.

    종으로만 고르면 모든 그림자가 `ai_veteran` 하나로 싸운다 — 다섯을 만나도 다섯 번
    같은 싸움이다. 저장은 되고 있었고(`entity_record.ruleset_json`) 관리자 화면만 그것을
    읽었다.
    """
    from game.api.deps import get_context, get_pool
    from game.app.services.run_battle import assign_enemy_policies, build_engine
    from game.app.store.bots import create_bot
    from game.app.store.doppels import create_doppel
    from game.app.store.monster_snapshots import build_monster_snapshot
    from game.app.store.monsters import find_monster
    from game.config import ROOM_TEMPLATES_PATH
    from game.schemas.room import load_room_templates

    pool = get_pool()
    token = client.post("/api/account").json()["token"]
    account_id = client.get("/api/account", headers=build_headers(token)).json()["account_id"]
    create_bot(pool, account_id, "그림자봇", "g0_kite", 720, 60)
    record_id = create_doppel(pool, account_id, 7, "ruleset_slot", BOT_LOADOUT, SHADOW_RULESET)
    record = find_monster(pool, record_id)
    assert record is not None
    context = get_context()
    base = next(k for k in context.balance["enemies"] if k["id"] == "doppelganger")
    snapshot = build_monster_snapshot(record, base)
    assert snapshot.ruleset is not None, "스냅샷이 규칙표를 안 실었다"

    template = next(iter(load_room_templates(ROOM_TEMPLATES_PATH)))
    slot = f"{template.enemy_spawns[0].kind}_0"
    frozen = type(snapshot)(**{**vars(snapshot), "entity_id": slot, "kind_id": "doppelganger"})
    engine = build_engine(
        template=template, balance=context.balance, seed=1, floor=7, snapshots=(frozen,)
    )
    assign_enemy_policies(
        engine, context.balance, context.catalog, context.enemy_rulesets, (frozen,)
    )

    policy = engine.policies[slot]
    assert getattr(policy, "ruleset", None) is not None
    assert policy.ruleset.ruleset_id == "shadow_only", "종의 기본표로 싸운다"


def test_a_broken_ruleset_falls_back_quietly(client):
    """★ 못 읽는 절 하나가 판 전체를 깨뜨리면 안 된다.

    그 개체만 종의 표로 싸우면 된다 — 옛 티켓이나 어휘가 바뀐 절이 여기로 온다.
    """
    from game.app.services.run_battle import build_entity_rulesets
    from game.schemas.monster_snapshot import parse_snapshot

    broken = parse_snapshot(
        {
            "entity_id": "doppelganger_0",
            "record_id": 1,
            "kind_id": "doppelganger",
            "tier": "ELITE",
            "level": 1,
            "hp_max": 10,
            "attack": 2,
            "defense": 1,
            "rule_slots": 0,
            "cpu_budget": 0,
            "ruleset": {"이건": "규칙표가 아니다"},
        }
    )

    assert build_entity_rulesets((broken,)) == {}


def test_the_ordinary_monster_keeps_the_kind_ruleset(client):
    """★ 개체 표가 없으면 종의 표를 탄다 — 소환물·추격자가 그 길로 싸운다."""
    from game.app.services.run_battle import build_entity_rulesets
    from game.schemas.monster_snapshot import parse_snapshot

    plain = parse_snapshot(
        {
            "entity_id": "goblin_rusher_0",
            "record_id": 1,
            "kind_id": "goblin_rusher",
            "tier": "NORMAL",
            "level": 1,
            "hp_max": 10,
            "attack": 2,
            "defense": 1,
            "rule_slots": 0,
            "cpu_budget": 0,
        }
    )

    assert plain.ruleset is None
    assert build_entity_rulesets((plain,)) == {}
