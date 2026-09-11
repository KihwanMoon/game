"""RuleVM — 규칙표를 읽어 매 틱 행동 하나를 고른다 (TDD §5).

평가 순서는 **셀렉터 → 조건 → 행동** 이다 (Phase 0 F-1 결정). 조건의 `대상 HP%` 는
그 규칙의 TARGET 이 가리키는 적을 뜻하며, 셀렉터가 아무도 못 고르면 그 규칙은
발동하지 않는다 — 없는 소환사를 공격하라는 규칙이 틱을 버리는 것을 막는다.

우선순위 오름차순으로 평가해 **최초로 참인 규칙 하나만** 실행한다. 전부 거짓이면
DEFAULT 인 '가장 가까운 적에게 접근' 이 나간다 (TDD §5.2).

조건 평가는 순수 함수다. 부작용이 없으므로 같은 스냅샷을 두 번 물으면 같은 답이 나오고,
무한 루프가 원천 차단된다. 플래그 기록 같은 상태 변경은 계획에만 담아 ACT 로 넘긴다.
"""

from dataclasses import dataclass, replace

from game.app.grid.geometry import get_manhattan_distance
from game.app.rules.condition import (
    DEFAULT_ACTION,
    DEFAULT_SELECTOR,
    evaluate_condition,
)
from game.app.rules.sight import check_sight_blocked
from game.app.simulation.abilities import ITEM_POTION
from game.app.simulation.perception import PerceptionSnapshot
from game.app.simulation.plan import (
    FREE_ITEMS,
    FREE_SKILLS,
    USE_ITEM_ACTION,
    USE_SKILL_ACTION,
    BlockedRule,
    PlannedAction,
)
from game.app.simulation.scrolls import check_already_held
from game.app.simulation.selectors import resolve_target
from game.app.simulation.state import Entity, WorldState
from game.schemas.blocks import BlockCatalog
from game.schemas.ruleset import Rule, RuleSet


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
        blocked: list[BlockedRule] = []
        free: list[str] = []
        free_items: list[str] = []
        for rule in self.ruleset.rules:
            target, usable = self._resolve_rule_target(rule, entity, state)
            if not usable:
                continue
            fired, expr = evaluate_condition(
                rule.conditions,
                snapshot,
                target,
                self.catalog,
                self._get_headroom(entity),
                actor=entity,
                casting_ids=state.casting_ids,
            )
            if not fired:
                continue
            # 조건이 참이어도 수단이 없으면 넘어간다. 그리고 **그 사실을 들고 나온다** —
            # 조용히 다음 규칙으로 가면 플레이어는 왜 안 떴는지 알 수 없다 (P1).
            if rule.action == USE_SKILL_ACTION and not entity.check_has_skill(
                rule.action_param or ""
            ):
                blocked.append(
                    BlockedRule(
                        rule_index=rule.priority,
                        expr=expr,
                        reason=f"{rule.action_param} 미장착",
                    )
                )
                continue
            # 소모품도 같다 — 조건은 참인데 수단이 없다. 이것이 「거짓」과 다르다는 것이
            # 이 게임의 규칙 상태 4종 중 하나다 (결정 #04).
            # **인자가 없으면 물약이다.** `USE_POTION` 별칭과 같은 규약이고, 실행부
            # (`apply_item`)도 그렇게 떨어진다 — 예전에는 문지기만 빈 문자열의 개수를
            # 세서(늘 0) **인자 없는 소모품 규칙이 영원히 「불가」였다.** 인자 고르개가
            # 생기기 전에 지은 규칙 전부가 그 상태였다 (e2).
            item_kind = rule.action_param or ITEM_POTION
            if rule.action == USE_ITEM_ACTION and entity.count_item(item_kind) <= 0:
                blocked.append(
                    BlockedRule(
                        rule_index=rule.priority,
                        expr=expr,
                        reason=f"{item_kind} 없음",
                    )
                )
                continue
            # **겹쳐 쓰면 충전만 탄다** (2026-09-11, 실제 요청). 이미 걸려 있는데 또
            # 쓰면 남은 틱이 덮일 뿐이고, 그 사실은 로그에도 안 남는다. 「불가」로
            # 잡으면 다음 규칙이 기회를 얻는다 — 소모품이 없을 때와 같은 자리다.
            if rule.action == USE_ITEM_ACTION and check_already_held(entity, item_kind):
                blocked.append(
                    BlockedRule(
                        rule_index=rule.priority,
                        expr=expr,
                        reason=f"{item_kind} 이미 걸림",
                    )
                )
                continue
            # **시야가 막힌 원거리 공격도 「불가」다** — 조건은 참인데 수단이 없다.
            #
            # 예전에는 그대로 발동시켜 틱만 버렸다. 사거리 안에 있는 한 조건은 매 틱 참이라
            # **같은 규칙이 영원히 다시 뽑히고**, 캐릭터가 엄폐물 뒤의 적을 향해 가만히 선
            # 채로 판이 끝났다. 여기서 막으면 다음 규칙이 기회를 얻는다 — 소모품이 없을
            # 때와 같은 자리다 (결정 #04 의 규칙 상태 4종).
            if check_sight_blocked(rule.action, entity, target, state):
                blocked.append(BlockedRule(rule_index=rule.priority, expr=expr, reason="시야 없음"))
                continue
            # **켜 두고 다음 규칙으로 간다** (`plan.FREE_SKILLS`). 여기서 return 하면
            # 그 틱의 행동이 「켜기」로 끝나고, 그 한 틱이 방벽이 값을 못 하던 이유였다.
            # 미장착·시야 검사 뒤에 둔다 — 앞에 두면 「불가」가 안 잡힌다 (결정 #04).
            if rule.action == USE_SKILL_ACTION and rule.action_param in FREE_SKILLS:
                free.append(rule.action_param or "")
                continue
            # 보호 주문서도 같다 — **같은 상태를 같은 값으로 거는데 한쪽만 틱을 내면
            # 세계에 규칙이 둘이 된다.** 없음·겹침 검사 뒤에 둔다: 앞에 두면 빈 칸으로도
            # 「켰다」가 되고, 그러면 주문서가 없다는 사실이 화면 어디에도 안 보인다.
            if rule.action == USE_ITEM_ACTION and item_kind in FREE_ITEMS:
                free_items.append(item_kind or "")
                continue
            return PlannedAction(
                entity_id=entity.entity_id,
                action_id=rule.action,
                target_id=target.entity_id if target is not None else None,
                rule_index=rule.priority,
                expr=expr,
                set_flag=rule.set_flag,
                skill_id=rule.action_param if rule.action == USE_SKILL_ACTION else None,
                item_kind=(rule.action_param or ITEM_POTION)
                if rule.action == USE_ITEM_ACTION
                else None,
                blocked=tuple(blocked),
                free_skills=tuple(free),
                free_items=tuple(free_items),
            )
        return replace(
            self._build_default_action(entity, state),
            blocked=tuple(blocked),
            free_skills=tuple(free),
            free_items=tuple(free_items),
        )

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
