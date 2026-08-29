"""조건식과 RuleVM 의 기준값 (게이트 G3).

`export_rules_golden.py` 에서 갈라 나왔다. 핵심은 `적거리(2) <= 사거리(3)` 처럼 양변에
실측값이 붙는가다 (GDD §8.2). 참/거짓만 맞고 문자열이 갈리면 로그가 쓸모없어진다.
"""

from typing import Any

from game.app.rules.rule_vm import build_rule_vm, count_cpu_usage, evaluate_condition
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.state import WorldState
from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import Condition, parse_ruleset
from scripts.rules_golden_specs import (
    KIND_TYPES,
    build_rule_document,
    build_ruleset_document,
    build_single_rule_document,
    build_term_document,
    render_plan_document,
)
from scripts.rules_golden_validator_cases import resolve_case_ruleset


def build_condition_specs() -> list[dict[str, Any]]:
    """조건식 렌더링 기준의 입력만 적는다.

    Returns:
        결과를 아직 채우지 않은 입력 목록.
    """
    return [
        {
            "name": "AND 는 모든 항을 요구한다",
            "world_id": "wounded",
            "condition": {
                "op": "AND",
                "terms": [
                    build_term_document("self_hp_percent", "<", 50),
                    build_term_document("self_potion_count", ">", 0),
                ],
            },
        },
        {
            "name": "OR 는 한 항이면 된다",
            "world_id": "wounded",
            "condition": {
                "op": "OR",
                "terms": [
                    build_term_document("self_hp_percent", "<", 50),
                    build_term_document("self_potion_count", ">", 0),
                ],
            },
        },
        {
            "name": "스탯 우변은 양변에 실측값이 붙는다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [
                    build_term_document(
                        "target_distance", "<=", {"stat": "attack_range"}, "NEAREST"
                    )
                ],
            },
        },
        {
            "name": "모르는 스탯은 거짓이다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [
                    build_term_document(
                        "target_distance", "<=", {"stat": "no_such_stat"}, "NEAREST"
                    )
                ],
            },
        },
        {
            "name": "값이 없는 항은 거짓이다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("self_exposed_to_los", "==", True)],
            },
        },
        {
            "name": "대상이 없으면 대상 계열도 거짓이다",
            "world_id": "field_mixed",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("target_hp_percent", "<", 50)],
            },
        },
        {
            "name": "대상 HP% 는 셀렉터가 고른 적을 가리킨다",
            "world_id": "field_mixed",
            "target_id": "e_echo",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("target_hp_percent", "<", 90)],
            },
        },
        {
            "name": "대상 시전 여부는 예고판을 읽는다",
            "world_id": "field_mixed",
            "target_id": "e_delta",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("target_is_casting", "==", True)],
            },
        },
        {
            "name": "CPU 여유는 VM 이 답한다",
            "world_id": "field_mixed",
            "cpu_headroom": 7,
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("self_cpu_headroom", ">=", 7)],
            },
        },
        {
            "name": "불리언 리터럴은 참거짓으로 적힌다",
            "world_id": "spring",
            "condition": {
                "op": "SINGLE",
                "terms": [build_term_document("self_on_heal_tile", "==", True)],
            },
        },
    ]


def build_condition_cases(
    worlds: dict[str, WorldState], snapshots: dict[str, PerceptionSnapshot], catalog: BlockCatalog
) -> list[dict[str, Any]]:
    """조건식의 참거짓과 렌더링 문자열을 적는다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.
        snapshots: 세계 id 에서 플레이어 스냅샷으로의 대응표.
        catalog: 라벨을 얻을 블록 카탈로그.

    Returns:
        기준 항목 목록.
    """
    cases: list[dict[str, Any]] = []
    for spec in build_condition_specs():
        case = dict(spec)
        case.setdefault("target_id", None)
        case.setdefault("cpu_headroom", None)
        state = worlds[case["world_id"]]
        target_id = case["target_id"]
        fired, expr = evaluate_condition(
            Condition(
                op=case["condition"]["op"],
                terms=parse_ruleset(
                    build_ruleset_document(
                        [build_rule_document(1, case["condition"]["terms"], "HOLD")]
                    )
                )
                .rules[0]
                .conditions.terms,
            ),
            snapshots[case["world_id"]],
            None if target_id is None else state.entities[target_id],
            catalog,
            case["cpu_headroom"],
            actor=state.entities["player"],
            casting_ids=state.casting_ids,
        )
        case["fired"] = fired
        case["expr"] = expr
        cases.append(case)
    return cases


def build_rule_vm_specs() -> list[dict[str, Any]]:
    """RuleVM 실행 규약 기준의 입력만 적는다.

    Returns:
        계획을 아직 채우지 않은 입력 목록.
    """
    hold = "HOLD"
    hp_true = ("self_hp_percent", "<=", 100)
    return [
        {
            "name": "최초로 참인 규칙 하나만 실행한다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, "self_potion_count", ">", 0, "USE_POTION"),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "전부 거짓이면 DEFAULT 가 나간다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 0, hold)]
            ),
        },
        {
            "name": "셀렉터가 빈손이면 그 규칙은 건너뛴다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, *hp_true, "ATTACK", target="BOSS"),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "조건 문자열에 실측값이 붙는다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document([build_single_rule_document(1, *hp_true, hold)]),
        },
        {
            "name": "플래그 기록은 계획에 담긴다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, *hp_true, hold, set_flag="A=true")]
            ),
        },
        {
            "name": "스탯 우변은 주인의 값을 따른다",
            "world_id": "throne",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1,
                        "target_distance",
                        "<=",
                        {"stat": "attack_range"},
                        "ATTACK",
                        target="NEAREST",
                        lhs_param="NEAREST",
                    ),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "모르는 스탯은 거짓이라 다음 규칙으로 넘어간다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(
                        1,
                        "target_distance",
                        "<=",
                        {"stat": "no_such_stat"},
                        "ATTACK",
                        target="NEAREST",
                        lhs_param="NEAREST",
                    ),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "적이 없으면 DEFAULT 도 대기가 된다",
            "world_id": "solitude",
            "ruleset": build_ruleset_document(
                [build_single_rule_document(1, "self_hp_percent", "<", 0, hold)]
            ),
        },
        {
            "name": "CPU 여유는 규칙표 크기를 반영한다",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, "self_cpu_headroom", ">=", 7, hold),
                    build_single_rule_document(2, *hp_true, "APPROACH", target="NEAREST"),
                ]
            ),
        },
        {
            "name": "시전 중인 적을 고르는 규칙",
            "world_id": "field_mixed",
            "ruleset": build_ruleset_document(
                [
                    build_single_rule_document(1, *hp_true, "ATTACK", target="CASTING"),
                    build_single_rule_document(2, *hp_true, hold),
                ]
            ),
        },
        {
            "name": "g0 압박형 규칙표",
            "world_id": "field_mixed",
            "ruleset_ref": ["g0", "g0_pressure"],
        },
        {"name": "g0 카이팅 규칙표", "world_id": "spring", "ruleset_ref": ["g0", "g0_kite"]},
        {"name": "g0 엄폐형 규칙표", "world_id": "throne", "ruleset_ref": ["g0", "g0_cover"]},
    ]


def build_rule_vm_cases(
    worlds: dict[str, WorldState], snapshots: dict[str, PerceptionSnapshot], catalog: BlockCatalog
) -> list[dict[str, Any]]:
    """RuleVM 이 고른 행동을 적는다.

    Args:
        worlds: 세계 id 에서 세계 상태로의 대응표.
        snapshots: 세계 id 에서 플레이어 스냅샷으로의 대응표.
        catalog: 동결된 블록 카탈로그.

    Returns:
        기준 항목 목록.
    """
    cases: list[dict[str, Any]] = []
    for spec in build_rule_vm_specs():
        case = dict(spec)
        state = worlds[case["world_id"]]
        ruleset = resolve_case_ruleset(case)
        vm = build_rule_vm(ruleset, catalog, KIND_TYPES)
        plan = vm.plan_action(state.entities["player"], snapshots[case["world_id"]], state)
        case["cpu_usage"] = count_cpu_usage(ruleset)
        case["plan"] = render_plan_document(plan)
        cases.append(case)
    return cases
