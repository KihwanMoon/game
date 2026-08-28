"""RuleVM — 규칙표를 읽어 매 틱 행동 하나를 고른다 (TDD §5).

평가 순서는 **셀렉터 → 조건 → 행동** 이다 (Phase 0 F-1 결정). 조건의 `대상 HP%` 는
그 규칙의 TARGET 이 가리키는 적을 뜻하며, 셀렉터가 아무도 못 고르면 그 규칙은
발동하지 않는다 — 없는 소환사를 공격하라는 규칙이 틱을 버리는 것을 막는다.

우선순위 오름차순으로 평가해 **최초로 참인 규칙 하나만** 실행한다. 전부 거짓이면
DEFAULT 인 '가장 가까운 적에게 접근' 이 나간다 (TDD §5.2).

조건 평가는 순수 함수다. 부작용이 없으므로 같은 스냅샷을 두 번 물으면 같은 답이 나오고,
무한 루프가 원천 차단된다. 플래그 기록 같은 상태 변경은 계획에만 담아 ACT 로 넘긴다.
"""

from dataclasses import dataclass

from game.app.grid.geometry import get_manhattan_distance
from game.app.rules.selectors import resolve_target
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.plan import PlannedAction
from game.app.simulation.state import Entity, WorldState
from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import OP_OR, Condition, Rule, RuleSet, Term

# 대상이 정해져야 값이 나오는 인지 변수. 스냅샷이 아니라 해석된 대상에서 읽는다.
TARGET_BLOCKS = frozenset({"target_hp_percent", "target_is_casting"})

DEFAULT_ACTION = "APPROACH"
DEFAULT_SELECTOR = "NEAREST"

COMPARATORS = {
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


def read_term_value(
    term: Term,
    snapshot: PerceptionSnapshot,
    target: Entity | None,
    cpu_headroom: int | None = None,
) -> int | bool | None:
    """조건 항의 좌변 값을 읽는다.

    대상 계열과 CPU 여유는 스냅샷에 없다. 전자는 규칙마다 셀렉터가 다르고, 후자는
    규칙표를 알아야 계산되기 때문이다 — 둘 다 VM 만 답할 수 있다.

    Args:
        term: 읽을 항.
        snapshot: PERCEPTION 이 고정한 값들.
        target: 이 규칙의 셀렉터가 고른 대상. 없으면 None.
        cpu_headroom: 남은 CPU 예산.

    Returns:
        측정된 값. 아직 구현되지 않은 블록이면 None.
    """
    if term.lhs == "target_hp_percent":
        return target.hp_percent if target is not None else None
    if term.lhs == "self_cpu_headroom":
        return cpu_headroom
    if term.lhs in TARGET_BLOCKS:
        return None
    return snapshot.read(term.lhs, term.lhs_param)


def render_term(term: Term, value: int | bool | None, catalog: BlockCatalog) -> str:
    """항을 실측값이 붙은 문자열로 편다.

    GDD §8.2 가 요구하는 것은 참/거짓이 아니라 **평가된 조건의 실제 값**이다.
    `적거리(2) <= 3` 처럼 괄호로 병기해야 죽고 나서 고칠 곳이 특정된다.

    Args:
        term: 대상 항.
        value: 측정된 좌변 값.
        catalog: 라벨을 얻을 블록 카탈로그.

    Returns:
        사람이 읽는 조건 문자열.
    """
    block = catalog.perceptions.get(term.lhs)
    label = block.label_ko if block is not None else term.lhs
    if term.lhs_param is not None:
        label = f"{label}[{term.lhs_param}]"
    shown = (
        "없음"
        if value is None
        else ("참" if value is True else "거짓" if value is False else value)
    )
    right = "참" if term.rhs is True else "거짓" if term.rhs is False else term.rhs
    return f"{label}({shown}) {term.comparison} {right}"


def evaluate_condition(
    condition: Condition,
    snapshot: PerceptionSnapshot,
    target: Entity | None,
    catalog: BlockCatalog,
    cpu_headroom: int | None = None,
) -> tuple[bool, str]:
    """조건식을 평가하고 사람이 읽는 문자열을 함께 만든다.

    값을 아직 만들 수 없는 블록(LOS 등)이 섞이면 그 항은 거짓으로 본다. 0 으로 채워
    참이 되게 하면 구현되지 않은 기능이 동작하는 것처럼 보인다.

    Args:
        condition: 평가할 조건식.
        snapshot: PERCEPTION 이 고정한 값들.
        target: 셀렉터가 고른 대상.
        catalog: 라벨을 얻을 블록 카탈로그.
        cpu_headroom: 남은 CPU 예산. self_cpu_headroom 항이 이것을 읽는다.

    Returns:
        (참/거짓, 렌더링된 조건 문자열).
    """
    results: list[bool] = []
    rendered: list[str] = []
    for term in condition.terms:
        value = read_term_value(term, snapshot, target, cpu_headroom)
        rendered.append(render_term(term, value, catalog))
        if value is None:
            results.append(False)
            continue
        results.append(bool(COMPARATORS[term.comparison](value, term.rhs)))

    joiner = " OR " if condition.op == OP_OR else " AND "
    outcome = any(results) if condition.op == OP_OR else all(results)
    return outcome, joiner.join(rendered)


@dataclass(frozen=True)
class RuleVm:
    """컴파일된 규칙표. 방 진입 시 한 번 만들고 틱마다 재사용한다 (TDD §5.1)."""

    ruleset: RuleSet
    catalog: BlockCatalog
    kind_types: dict[str, str]

    def _resolve_rule_target(
        self, rule: Rule, entity: Entity, state: WorldState
    ) -> tuple[Entity | None, bool]:
        """규칙의 대상을 먼저 정한다 (F-1 결정).

        Args:
            rule: 평가 중인 규칙.
            entity: 결정 주체.
            state: 세계 상태.

        Returns:
            (고른 대상, 이 규칙을 계속 볼 수 있는가).
        """
        if rule.target is None:
            return None, True
        target = resolve_target(rule.target, entity, state, self.kind_types)
        return target, target is not None

    def plan_action(
        self, entity: Entity, snapshot: PerceptionSnapshot, state: WorldState
    ) -> PlannedAction:
        """규칙표를 위에서부터 평가해 이번 틱의 행동을 고른다.

        Args:
            entity: 결정 주체.
            snapshot: PERCEPTION 이 고정한 값들.
            state: 세계 상태. 읽기만 한다.

        Returns:
            최초로 참이 된 규칙의 계획. 전부 거짓이면 DEFAULT 계획.
        """
        for rule in self.ruleset.rules:
            target, usable = self._resolve_rule_target(rule, entity, state)
            if not usable:
                continue
            fired, expr = evaluate_condition(
                rule.conditions, snapshot, target, self.catalog, self._get_headroom(entity)
            )
            if not fired:
                continue
            return PlannedAction(
                entity_id=entity.entity_id,
                action_id=rule.action,
                target_id=target.entity_id if target is not None else None,
                rule_index=rule.priority,
                expr=expr,
                set_flag=rule.set_flag,
            )
        return self._build_default_action(entity, state)

    def _get_headroom(self, entity: Entity) -> int:
        """남은 CPU 예산 (GDD §3.6).

        Args:
            entity: 규칙표를 쓰는 엔티티.

        Returns:
            예산에서 규칙표가 쓰는 양을 뺀 값. 음수면 초과 상태다.
        """
        return entity.cpu_budget - count_cpu_usage(self.ruleset)

    def _build_default_action(self, entity: Entity, state: WorldState) -> PlannedAction:
        """전부 거짓일 때의 기본 행동 (TDD §5.2).

        Args:
            entity: 결정 주체.
            state: 세계 상태.

        Returns:
            가장 가까운 적에게 접근하는 계획. 적이 없으면 대기.
        """
        target = resolve_target(DEFAULT_SELECTOR, entity, state, self.kind_types)
        if target is None:
            return PlannedAction(entity_id=entity.entity_id, action_id="HOLD", expr="적 없음")
        distance = get_manhattan_distance(entity.position, target.position)
        return PlannedAction(
            entity_id=entity.entity_id,
            action_id=DEFAULT_ACTION,
            target_id=target.entity_id,
            expr=f"모든 규칙 거짓 → DEFAULT (적거리 {distance})",
        )


def build_rule_vm(ruleset: RuleSet, catalog: BlockCatalog, kind_types: dict[str, str]) -> RuleVm:
    """규칙표를 실행 가능한 형태로 만든다.

    Args:
        ruleset: 검증을 통과한 규칙표.
        catalog: 동결된 블록 카탈로그.
        kind_types: 엔티티 종류에서 적 유형으로의 대응표.

    Returns:
        DecisionPolicy 로 쓸 수 있는 VM.
    """
    return RuleVm(ruleset=ruleset, catalog=catalog, kind_types=kind_types)


def count_cpu_usage(ruleset: RuleSet) -> int:
    """규칙표가 쓰는 CPU 총량을 센다 (GDD §3.6).

    Args:
        ruleset: 대상 규칙표.

    Returns:
        cpu_cost 의 합.
    """
    return sum(rule.cpu_cost for rule in ruleset.rules)
