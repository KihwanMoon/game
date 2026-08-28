"""규칙표 검증 — 컴파일 전에 막을 수 있는 것을 전부 막는다 (TDD §5.1).

검증 없이 컴파일하면 규칙이 조용히 무시되고, 플레이어는 자기 논리가 틀렸다고
오해한다. 무엇이 왜 거부됐는지 문자열로 돌려주는 이유가 그것이다 (P1).
"""

from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import (
    COMPARISONS,
    CONDITION_OPS,
    MAX_TERMS,
    Rule,
    RuleSet,
)

CPU_COST_BY_TERM_COUNT = {1: 1, 2: 2, 3: 4}


def _check_terms(rule: Rule, catalog: BlockCatalog, unlocked: frozenset[str]) -> list[str]:
    """조건 항들이 동결 목록 안에 있고 인자가 맞는지 본다.

    Args:
        rule: 검사할 규칙.
        catalog: 동결된 블록 카탈로그.
        unlocked: 해금된 블록 id 집합.

    Returns:
        위반 메시지 목록.
    """
    problems: list[str] = []
    label = f"[{rule.priority}]"
    if rule.conditions.op not in CONDITION_OPS:
        problems.append(f"{label} 알 수 없는 조건 연산자 {rule.conditions.op}")
    if not 1 <= len(rule.conditions.terms) <= MAX_TERMS:
        problems.append(f"{label} 조건 항이 1~{MAX_TERMS}개를 벗어났다")

    for term in rule.conditions.terms:
        if term.comparison not in COMPARISONS:
            problems.append(f"{label} 알 수 없는 비교 연산자 {term.comparison}")
        block = catalog.perceptions.get(term.lhs)
        if block is None:
            problems.append(f"{label} 목록에 없는 인지 변수 {term.lhs}")
            continue
        if term.lhs not in unlocked:
            problems.append(f"{label} 아직 해금되지 않은 인지 변수 {term.lhs}")
        if block.param is None and term.lhs_param is not None:
            problems.append(f"{label} {term.lhs} 는 인자를 받지 않는다")
        elif block.param is not None and term.lhs_param not in block.param.values:
            problems.append(f"{label} {term.lhs} 의 인자 {term.lhs_param} 는 허용되지 않는다")
    return problems


def _check_action(rule: Rule, catalog: BlockCatalog, unlocked: frozenset[str]) -> list[str]:
    """행동과 셀렉터의 조합이 성립하는지 본다.

    Args:
        rule: 검사할 규칙.
        catalog: 동결된 블록 카탈로그.
        unlocked: 해금된 블록 id 집합.

    Returns:
        위반 메시지 목록.
    """
    problems: list[str] = []
    label = f"[{rule.priority}]"
    action = catalog.actions.get(rule.action)
    if action is None:
        return [f"{label} 목록에 없는 행동 {rule.action}"]
    if rule.action not in unlocked:
        problems.append(f"{label} 아직 해금되지 않은 행동 {rule.action}")
    if action.targeted and rule.target is None:
        problems.append(f"{label} {rule.action} 는 TARGET 셀렉터가 필요하다")
    if not action.targeted and rule.target is not None:
        problems.append(f"{label} {rule.action} 는 TARGET 을 받지 않는다")
    if rule.target is not None and rule.target not in catalog.selectors:
        problems.append(f"{label} 목록에 없는 셀렉터 {rule.target}")
    return problems


def validate_ruleset(
    ruleset: RuleSet,
    catalog: BlockCatalog,
    cpu_budget: int,
    rule_slots: int,
    unlocked: frozenset[str] | None = None,
) -> list[str]:
    """규칙표가 실행 가능한지 검사한다.

    Args:
        ruleset: 검사할 규칙표.
        catalog: 동결된 블록 카탈로그.
        cpu_budget: 이 엔티티의 CPU 예산.
        rule_slots: 이 엔티티의 규칙 슬롯 수.
        unlocked: 해금된 블록 id 집합. None 이면 전부 해금된 것으로 본다.

    Returns:
        위반 메시지 목록. 비어 있으면 실행 가능하다.
    """
    if unlocked is None:
        unlocked = frozenset(catalog.perceptions) | frozenset(catalog.actions)

    problems: list[str] = []
    if len(ruleset.rules) > rule_slots:
        problems.append(f"규칙 {len(ruleset.rules)}개가 슬롯 {rule_slots}개를 넘는다")

    priorities = [rule.priority for rule in ruleset.rules]
    if len(priorities) != len(set(priorities)):
        problems.append("우선순위가 중복된다 — 평가 순서가 정해지지 않는다")

    total_cpu = 0
    for rule in ruleset.rules:
        expected = CPU_COST_BY_TERM_COUNT.get(len(rule.conditions.terms))
        if expected is not None and rule.cpu_cost != expected:
            problems.append(
                f"[{rule.priority}] CPU 비용 {rule.cpu_cost} 가 항 수 기준 {expected} 와 다르다"
            )
        total_cpu += rule.cpu_cost
        problems.extend(_check_terms(rule, catalog, unlocked))
        problems.extend(_check_action(rule, catalog, unlocked))

    if total_cpu > cpu_budget:
        problems.append(f"CPU {total_cpu} 가 예산 {cpu_budget} 을 넘는다")
    return problems
