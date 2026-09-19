"""행동의 인자가 성립하는가 — 두 코어가 같은 말을 하는가.

2026-09-19 의 사고다. 조건 항의 인자(``쿨타임[X]``)는 처음부터 검증했는데 행동의
인자(``재주 사용[X]``)는 **아무도 안 봤다**. 그래서 ``build_rule_payload`` 가
``action_param`` 을 버리던 시절(2026-09-17 수정)의 피해가 조용히 남았고, 운영 슬롯에
재주 없는 ``USE_SKILL`` 이 9줄 있었다.

메시지 글자까지 TS 와 맞춘다 — 같은 규칙표를 열어도 서버와 브라우저가 다른 말을 하면
어느 쪽을 믿어야 하는지 알 수 없다.
"""

import pytest

from game.app.rules.validator import validate_ruleset
from game.config import BLOCKS_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.ruleset import parse_ruleset

BUDGET = 99


@pytest.fixture(name="catalog")
def fixture_catalog():
    """블록 카탈로그.

    Returns:
        동결된 카탈로그.
    """
    return load_block_catalog(BLOCKS_PATH)


def build_ruleset(action: str, action_param: str | None, target: str | None):
    """규칙 한 줄짜리 규칙표를 만든다.

    Args:
        action: 행동 id.
        action_param: 행동 인자. 없으면 None.
        target: 셀렉터 id. 없으면 None.

    Returns:
        파서를 거친 규칙표.
    """
    rule: dict = {
        "priority": 1,
        "cpu_cost": 1,
        "action": action,
        "target": target,
        "set_flag": None,
        "conditions": {
            "op": "SINGLE",
            "terms": [{"lhs": "self_hp_percent", "cmp": "<", "rhs": 50}],
        },
    }
    if action_param is not None:
        rule["action_param"] = action_param
    return parse_ruleset({"ruleset_id": "probe", "version": 1, "rules": [rule]})


def test_missing_skill_is_rejected(catalog):
    """재주를 안 고른 USE_SKILL 을 반려한다."""
    ruleset = build_ruleset("USE_SKILL", None, "NEAREST")
    problems = validate_ruleset(ruleset, catalog, BUDGET, BUDGET)
    assert "[1] USE_SKILL 의 재주 를 안 골랐다" in problems


def test_unknown_skill_is_rejected(catalog):
    """목록에 없는 재주를 반려한다. 예전에는 무엇을 적든 통과했다."""
    problems = validate_ruleset(
        build_ruleset("USE_SKILL", "있지도 않은 재주", "NEAREST"), catalog, BUDGET, BUDGET
    )
    assert "[1] USE_SKILL 의 인자 있지도 않은 재주 는 허용되지 않는다" in problems


def test_chosen_skill_passes(catalog):
    """제대로 고른 것은 통과한다."""
    ruleset = build_ruleset("USE_SKILL", "METEOR", "NEAREST")
    assert validate_ruleset(ruleset, catalog, BUDGET, BUDGET) == []


def test_param_on_paramless_action_is_rejected(catalog):
    """인자를 안 받는 행동에 인자가 붙어 있으면 반려한다."""
    problems = validate_ruleset(build_ruleset("HOLD", "METEOR", None), catalog, BUDGET, BUDGET)
    assert "[1] HOLD 는 인자를 받지 않는다" in problems


def test_paramless_action_passes(catalog):
    """인자를 안 받는 행동에 인자가 없는 것은 통과한다."""
    assert validate_ruleset(build_ruleset("HOLD", None, None), catalog, BUDGET, BUDGET) == []


def test_alias_is_read_from_json(catalog):
    """별칭 선언을 카탈로그가 읽는다 — 2026-09-19 까지 아무도 안 읽는 주석이었다."""
    assert catalog.actions["USE_POTION"].alias_of == "USE_ITEM[POTION]"
    assert catalog.actions["HOLD"].alias_of is None
