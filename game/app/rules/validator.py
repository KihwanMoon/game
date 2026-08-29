"""규칙표 검증 — 컴파일 전에 막을 수 있는 것을 전부 막는다 (TDD §5.1).

검증 없이 컴파일하면 규칙이 조용히 무시되고, 플레이어는 자기 논리가 틀렸다고
오해한다. 무엇이 왜 거부됐는지 문자열로 돌려주는 이유가 그것이다 (P1).
"""

from game.schemas.blocks import ActionBlock, BlockCatalog, PerceptionBlock
from game.schemas.ruleset import (
    COMPARISONS,
    CONDITION_OPS,
    MAX_TERMS,
    Rule,
    RuleSet,
    StatRef,
    Term,
)

CPU_COST_BY_TERM_COUNT = {1: 1, 2: 2, 3: 4}

# 진영 id 를 사람이 읽는 말로. 메시지에 "ally" 라고 적으면 화면에서만 영어가 튄다.
FACTION_LABELS = {"enemy": "적대", "ally": "아군"}

# 스탯 우변은 수치 비교다. bool 인지 변수와 견주면 `내 상태이상 == 사거리` 같은 항이
# 되어 뜻이 없다 — 값이 나오는데도 영영 거짓인 규칙이 만들어진다.
NUMERIC_RETURN = "int"


def _check_term_rhs(term: Term, block: PerceptionBlock, catalog: BlockCatalog, label: str) -> str:
    """조건 항의 우변이 성립하는지 본다 (F-2).

    Args:
        term: 검사할 항.
        block: 좌변 인지 변수.
        catalog: 블록 카탈로그. 허용 스탯의 정본이다.
        label: 메시지에 붙일 규칙 표시.

    Returns:
        위반 메시지. 성립하면 빈 문자열.
    """
    if not isinstance(term.rhs, StatRef):
        return ""
    if term.rhs.stat not in catalog.rhs_stats:
        return f"{label} 목록에 없는 스탯 {term.rhs.stat}"
    if block.returns != NUMERIC_RETURN:
        return f"{label} {term.lhs} 는 {block.returns} 라서 스탯과 비교할 수 없다"
    return ""


def _check_term(
    term: Term, catalog: BlockCatalog, unlocked: frozenset[str], label: str
) -> list[str]:
    """조건 항 하나가 목록 안에 있고 인자·우변이 맞는지 본다.

    Args:
        term: 검사할 항.
        catalog: 동결된 블록 카탈로그.
        unlocked: 해금된 블록 id 집합.
        label: 메시지에 붙일 규칙 표시.

    Returns:
        위반 메시지 목록.
    """
    problems: list[str] = []
    if term.comparison not in COMPARISONS:
        problems.append(f"{label} 알 수 없는 비교 연산자 {term.comparison}")
    block = catalog.perceptions.get(term.lhs)
    if block is None:
        problems.append(f"{label} 목록에 없는 인지 변수 {term.lhs}")
        return problems
    if term.lhs not in unlocked:
        problems.append(f"{label} 아직 해금되지 않은 인지 변수 {term.lhs}")
    if block.param is None and term.lhs_param is not None:
        problems.append(f"{label} {term.lhs} 는 인자를 받지 않는다")
    elif block.param is not None and term.lhs_param not in block.param.values:
        problems.append(f"{label} {term.lhs} 의 인자 {term.lhs_param} 는 허용되지 않는다")
    rhs_problem = _check_term_rhs(term, block, catalog, label)
    if rhs_problem:
        problems.append(rhs_problem)
    return problems


def _check_terms(rule: Rule, catalog: BlockCatalog, unlocked: frozenset[str]) -> list[str]:
    """조건식 전체가 동결 목록 안에 있는지 본다.

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
        problems.extend(_check_term(term, catalog, unlocked, label))
    return problems


def _check_target_faction(
    rule: Rule, action: ActionBlock, catalog: BlockCatalog, label: str
) -> list[str]:
    """행동이 요구하는 진영과 셀렉터가 고르는 진영이 맞는지 본다 (블록 목록 v4).

    `HEAL @NEAREST` 는 적을 회복하고 `ATTACK @ALLY_WOUNDED` 는 아군을 때린다. 둘 다
    문법으로는 만들 수 있으므로 여기서 막지 않으면 규칙표가 조용히 반대로 돈다.

    Args:
        rule: 검사할 규칙.
        action: 그 규칙의 행동 블록.
        catalog: 동결된 블록 카탈로그.
        label: 메시지에 붙일 규칙 표시.

    Returns:
        위반 메시지 목록.
    """
    selector = catalog.selectors.get(rule.target or "")
    if selector is None or action.target_faction is None:
        return []
    if selector.faction == action.target_faction:
        return []
    want = FACTION_LABELS.get(action.target_faction, action.target_faction)
    got = FACTION_LABELS.get(selector.faction, selector.faction)
    return [f"{label} {rule.action} 는 {want} 셀렉터가 필요하다 — {rule.target} 는 {got} 셀렉터다"]


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
    problems.extend(_check_target_faction(rule, action, catalog, label))
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
