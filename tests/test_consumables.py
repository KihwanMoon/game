"""소모품 다종화 — `USE_ITEM[kind]` (블록 v6, #54).

**보호 주문서가 카탈로그에 있는데 그것을 쓸 수 있는 행동이 없었다.** 얻어도 영영 쓰지
못했고, 그것은 부품만 있고 배선이 없는 상태였다.

여기서 지키는 것은 넷이다.

1. 파라미터는 **태그**다. 물약을 여러 등급으로 늘려도 규칙표가 안 깨진다.
2. 소모품이 없으면 **「불가」**다 — 거짓과 다르다. 조건은 참인데 수단이 없다.
3. `USE_POTION` 은 별칭으로 남는다. 지우면 저장된 규칙표와 골든이 깨진다.
4. 종류마다 실제로 다른 일이 일어난다. 안 그러면 다종화가 이름뿐이다.
"""

import pytest

from game.app.rules.rule_vm import build_rule_vm
from game.app.services.run_battle import assign_enemy_policies, build_engine, load_balance
from game.app.simulation.plan import STATUS_GUARD
from game.config import BALANCE_PATH, BLOCKS_PATH, ENEMY_RULESETS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets, parse_ruleset

ROOM = "open_field"


@pytest.fixture(scope="module")
def parts():
    rooms = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    return {
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "room": rooms[ROOM],
        "enemies": load_rulesets(ENEMY_RULESETS_PATH),
    }


def build_use_item(kind):
    """그 소모품을 무조건 쓰는 규칙표 하나."""
    return {
        "ruleset_id": "probe",
        "version": 1,
        "rules": [
            {
                "priority": 1,
                "cpu_cost": 1,
                "action": "USE_ITEM",
                "action_param": kind,
                "target": None,
                "set_flag": None,
                "conditions": {
                    "op": "SINGLE",
                    "terms": [{"lhs": "self_hp_percent", "cmp": "<=", "rhs": 100}],
                },
            }
        ],
    }


def run_one_tick(parts, payload, consumables):
    """한 틱만 돌리고 플레이어와 로그를 돌려준다."""
    engine = build_engine(parts["room"], parts["balance"], seed=7)
    player = engine.state.entities["player"]
    player.consumables = dict(consumables)
    player.hp = player.hp_max // 2
    engine.policies["player"] = build_rule_vm(
        parse_ruleset(payload), parts["catalog"], engine.config.kind_types
    )
    assign_enemy_policies(engine, parts["balance"], parts["catalog"], parts["enemies"])
    engine.run_tick()
    return player, engine.log.format_lines()


# ── 블록 ─────────────────────────────────────────────────────────────────


def test_use_item_is_one_action_with_a_tag_parameter(parts):
    """★ 소모품마다 액션을 더하면 블록 버전이 계속 올라 랭킹 시즌이 갈린다."""
    action = parts["catalog"].actions["USE_ITEM"]
    assert action.param is not None
    assert action.param.name == "item"
    assert set(action.param.values) >= {"POTION", "SCROLL"}


def test_use_potion_still_parses(parts):
    """★ 별칭을 지우면 저장된 규칙표와 골든 리플레이가 전부 깨진다."""
    assert "USE_POTION" in parts["catalog"].actions


# ── 실행 ─────────────────────────────────────────────────────────────────


def test_a_potion_heals(parts):
    player, _ = run_one_tick(parts, build_use_item("POTION"), {"POTION": 1})
    assert player.hp > player.hp_max // 2
    assert player.count_item("POTION") == 0


def test_a_scroll_raises_a_guard(parts):
    """★ **여기가 다종화의 전부다.**

    종류마다 실제로 다른 일이 일어나지 않으면 이름만 늘어난 것이다.
    """
    player, _ = run_one_tick(parts, build_use_item("SCROLL"), {"SCROLL": 1})
    assert player.statuses.get(STATUS_GUARD, 0) > 0
    assert player.count_item("SCROLL") == 0
    # 주문서는 회복이 아니다 — 둘이 같은 일을 하면 가를 이유가 없다.
    assert player.hp == player.hp_max // 2


def test_the_two_kinds_are_counted_separately(parts):
    """★ 하나를 써도 다른 하나가 줄면 안 된다."""
    player, _ = run_one_tick(parts, build_use_item("SCROLL"), {"POTION": 2, "SCROLL": 1})
    assert player.count_item("POTION") == 2
    assert player.count_item("SCROLL") == 0


# ── 불가 ─────────────────────────────────────────────────────────────────


def test_a_missing_consumable_is_blocked_not_false(parts):
    """★ 조건은 참인데 수단이 없다 — 「거짓」과 다르다 (결정 #04).

    조용히 넘어가면 플레이어는 왜 안 떴는지 알 수 없다 (P1).
    """
    _, lines = run_one_tick(parts, build_use_item("SCROLL"), {})
    joined = "\n".join(line for line in lines if "player" in line)
    assert "SCROLL 없음" in joined, joined


def test_holding_the_wrong_kind_is_still_blocked(parts):
    """★ 물약을 들고 주문서 규칙을 쓰면 막힌다 — 종류를 안 보면 다종화가 없다."""
    _, lines = run_one_tick(parts, build_use_item("SCROLL"), {"POTION": 9})
    assert "SCROLL 없음" in "\n".join(line for line in lines if "player" in line)
