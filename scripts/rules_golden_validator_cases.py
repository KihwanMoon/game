"""검증기 기준값 — 위반 메시지와 그 순서 (게이트 G3).

`export_rules_golden.py` 에서 갈라 나왔다. 메시지 문자열과 순서까지 기준인 이유는
규칙 에디터가 이것을 그대로 띄우기 때문이다 (P1). 문구가 갈리면 플레이어가 보는
화면이 갈린다.
"""

import json
from typing import Any

from game.app.rules.validator import validate_ruleset
from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import RuleSet, parse_ruleset
from scripts.rules_golden_specs import (
    RULESET_FILES,
    build_rule_document,
    build_ruleset_document,
    build_single_rule_document,
    build_term_document,
)


def build_validator_specs() -> list[dict[str, Any]]:
    """검증기 기준 항목의 입력만 적는다.

    파이썬 테스트 `tests/test_rule_vm.py` 의 검증기 절을 그대로 옮기고, 거기서 다루지
    않은 경계(목록에 없는 행동·셀렉터, 항 수 초과)를 더했다.

    Returns:
        위반 메시지를 아직 채우지 않은 입력 목록.
    """
    hold = "HOLD"
    overflow = [
        build_single_rule_document(i, "self_hp_percent", "<", 50, hold) for i in range(1, 7)
    ]
    stat_ref = {"stat": "no_such_stat"}
    return [
        {"name": "슬롯 초과", "ruleset": build_ruleset_document(overflow), "rule_slots": 5},
        {"name": "CPU 초과", "ruleset": build_ruleset_document(overflow[:4]), "cpu_budget": 2},
        {
            "name": "목록에 없는 인지 변수",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "does_not_exist", "<", 1, hold)]
            ),
        },
        {
            "name": "허용되지 않는 인자",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "flag_state", "==", True, hold, lhs_param="Z")]
            ),
        },
        {
            "name": "인자를 빠뜨린 인지 변수",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "flag_state", "==", True, hold)]
            ),
        },
        {
            "name": "인자를 받지 않는 인지 변수에 인자를 줬다",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold, lhs_param="A")]
            ),
        },
        {
            "name": "TARGET 이 필요한 행동",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, "ATTACK")]
            ),
        },
        {
            "name": "TARGET 을 받지 않는 행동",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold, target="NEAREST")]
            ),
        },
        {
            "name": "우선순위 중복",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, "self_hp_percent", "<", 50, hold),
                    build_single_rule_document(1, "self_potion_count", ">", 0, hold),
                ]
            ),
        },
        {
            "name": "CPU 비용 불일치",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold, cpu_cost=4)]
            ),
        },
        {
            "name": "해금되지 않은 블록",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, hold)]
            ),
            "unlocked": [hold],
        },
        {
            "name": "목록에 없는 스탯",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "target_distance", "<=", stat_ref, hold, lhs_param="NEAREST"
                    )
                ]
            ),
        },
        {
            "name": "불리언 블록과 스탯 비교",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_on_heal_tile", "==", {"stat": "attack_range"}, hold
                    )
                ]
            ),
        },
        {
            "name": "목록에 없는 행동",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 50, "NO_SUCH_ACTION")]
            ),
        },
        {
            "name": "목록에 없는 셀렉터",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_hp_percent", "<", 50, "ATTACK", target="NO_SUCH_SELECTOR"
                    )
                ]
            ),
        },
        {
            "name": "항 수 초과",
            "ruleset": build_ruleset_document(
                [
                    build_rule_document(
                        1,
                        [
                            build_term_document("self_hp_percent", "<", 50),
                            build_term_document("self_potion_count", ">", 0),
                            build_term_document("visible_enemy_count", ">", 0),
                            build_term_document("room_elapsed_ticks", ">", 0),
                        ],
                        hold,
                        op="AND",
                        cpu_cost=4,
                    )
                ]
            ),
        },
        {
            "name": "세 항 AND 는 통과한다",
            "ruleset": build_ruleset_document(
                [
                    build_rule_document(
                        1,
                        [
                            build_term_document("self_hp_percent", "<", 50),
                            build_term_document("self_potion_count", ">", 0),
                            build_term_document("visible_enemy_count", ">", 0),
                        ],
                        hold,
                        op="AND",
                    )
                ]
            ),
        },
        {
            "name": "회복에 적대 셀렉터를 줬다",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_hp_percent", "<", 50, "HEAL", target="NEAREST"
                    )
                ]
            ),
        },
        {
            "name": "공격에 아군 셀렉터를 줬다",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_hp_percent", "<", 50, "ATTACK", target="ALLY_WOUNDED"
                    )
                ]
            ),
        },
        {
            "name": "진영이 맞으면 통과한다",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1, "self_hp_percent", "<", 50, "HEAL", target="ALLY_WOUNDED"
                    )
                ]
            ),
        },
        {"name": "적 치유형 규칙표는 통과한다", "ruleset_ref": ["enemies", "ai_mender"]},
        {"name": "g0 압박형은 통과한다", "ruleset_ref": ["g0", "g0_pressure"]},
        {"name": "g0 카이팅은 통과한다", "ruleset_ref": ["g0", "g0_kite"]},
        {"name": "g0 엄폐형은 통과한다", "ruleset_ref": ["g0", "g0_cover"]},
        {"name": "적 소환사 규칙표는 통과한다", "ruleset_ref": ["enemies", "ai_summoner"]},
        {"name": "벤치마크 규칙표는 통과한다", "ruleset_ref": ["benchmark", "focus_summoner"]},
    ]


def resolve_case_ruleset(case: dict[str, Any]) -> RuleSet:
    """검증기 항목이 가리키는 규칙표를 얻는다.

    Args:
        case: 인라인 `ruleset` 또는 `ruleset_ref` 를 가진 항목.

    Returns:
        읽어들인 규칙표.
    """
    if "ruleset" in case:
        return parse_ruleset(case["ruleset"])
    alias, ruleset_id = case["ruleset_ref"]
    raw = json.loads(RULESET_FILES[alias].read_text(encoding="utf-8"))
    found = next(item for item in raw["rulesets"] if item["ruleset_id"] == ruleset_id)
    return parse_ruleset(found)


def build_validator_cases(catalog: BlockCatalog) -> list[dict[str, Any]]:
    """검증기가 내는 위반 메시지를 순서까지 그대로 적는다.

    Args:
        catalog: 동결된 블록 카탈로그.

    Returns:
        기준 항목 목록.
    """
    default_budget = 99
    default_slots = 5
    cases: list[dict[str, Any]] = []
    for spec in build_validator_specs():
        case = dict(spec)
        case.setdefault("cpu_budget", default_budget)
        case.setdefault("rule_slots", default_slots)
        case.setdefault("unlocked", None)
        unlocked = case["unlocked"]
        case["problems"] = validate_ruleset(
            resolve_case_ruleset(case),
            catalog,
            case["cpu_budget"],
            case["rule_slots"],
            None if unlocked is None else frozenset(unlocked),
        )
        cases.append(case)
    return cases
