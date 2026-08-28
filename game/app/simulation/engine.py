"""틱 엔진 — 7페이즈를 고정 순서로 돈다 (TDD §4.1).

UPKEEP → TELEGRAPH → PERCEPTION → DECIDE → ACT → RESOLVE → CLEANUP.

PERCEPTION 과 DECIDE 를 나누는 이유는 동시성 공정성이다. 모든 엔티티가 같은 시점의
세계를 보고 판단해야 하며, 순차 갱신하면 처리 순서가 유리/불리를 만든다. 그래서
DECIDE 는 부작용을 내지 않고 계획만 돌려주며, 실제 변경은 ACT 부터다.

행동을 실제로 옮기는 일은 actions.ActionExecutor 가 맡는다. 이 모듈은 순서만 책임진다.
"""

from dataclasses import dataclass, field

from game.app.core.event_log import EventLog, LogEntry
from game.app.simulation.actions import ATTACK_ACTIONS, MOVE_ACTIONS, ActionExecutor
from game.app.simulation.perception import PerceptionSnapshot, build_snapshot
from game.app.simulation.plan import (
    OUTCOME_ONGOING,
    OUTCOME_PLAYER_LOSS,
    OUTCOME_PLAYER_WIN,
    OUTCOME_TIMEOUT,
    PHASE_DECIDE,
    PHASE_UPKEEP,
    DecisionPolicy,
    EngineConfig,
    PlannedAction,
)
from game.app.simulation.state import FACTION_PLAYER, Entity, WorldState
from game.schemas.room import TILE_LAVA, TILE_SPRING

LAVA_DAMAGE = 3
SPRING_REGEN_PER_TICK = 2


@dataclass
class TickEngine:
    """한 방의 전투를 틱 단위로 진행한다."""

    state: WorldState
    policy: DecisionPolicy
    config: EngineConfig
    log: EventLog = field(default_factory=EventLog)
    # 엔티티별 결정기. GDD §5 — 몬스터도 플레이어와 완전히 동일한 DSL 로 기술한다.
    # 하나의 정책을 전 엔티티에 공유하면 적이 플레이어의 규칙표로 싸우게 되고,
    # 그 상태로 잰 승률은 아무 의미가 없다.
    policies: dict[str, DecisionPolicy] = field(default_factory=dict)

    @property
    def actions(self) -> ActionExecutor:
        """행동 실행기."""
        return ActionExecutor(state=self.state, log=self.log, config=self.config)

    def get_policy(self, entity_id: str) -> DecisionPolicy:
        """그 엔티티의 결정기를 돌려준다.

        Args:
            entity_id: 대상 엔티티 id.

        Returns:
            지정된 결정기, 없으면 기본 결정기.
        """
        return self.policies.get(entity_id, self.policy)

    def run_upkeep(self) -> None:
        """쿨타임·상태이상 감소, 회복, 타일 피해를 처리한다 (페이즈 1)."""
        executor = self.actions
        in_combat = any(e.faction != FACTION_PLAYER for e in self.state.list_actors())
        for entity in self.state.list_actors():
            for skill, remaining in entity.cooldowns.items():
                entity.cooldowns[skill] = max(0, remaining - 1)
            for status, remaining in entity.statuses.items():
                entity.statuses[status] = max(0, remaining - 1)
            if self.state.get_tile(*entity.position) == TILE_LAVA:
                executor.apply_damage(
                    entity, LAVA_DAMAGE, PHASE_UPKEEP, "용암 위", actor_id=entity.entity_id
                )
            self._apply_regen(entity, in_combat=in_combat)

    def run_telegraph(self) -> None:
        """예고 공격을 진행한다 (페이즈 2).

        Phase 2 W6 산출물이다. 지금은 아무것도 하지 않지만 페이즈 자리는 비워 둔다 —
        나중에 끼워 넣으면 그 앞뒤 페이즈의 순서 전제가 바뀐다.
        """

    def build_perceptions(self) -> dict[str, PerceptionSnapshot]:
        """전 엔티티의 인지 변수를 이 시점에 고정한다 (페이즈 3).

        Returns:
            entity_id 에서 스냅샷으로의 대응표.
        """
        return {
            entity.entity_id: build_snapshot(self.state, entity, self.config.kind_types)
            for entity in self.state.list_actors()
        }

    def plan_actions(self, snapshots: dict[str, PerceptionSnapshot]) -> tuple[PlannedAction, ...]:
        """각 엔티티의 행동을 결정한다 (페이즈 4). 세계를 바꾸지 않는다.

        Args:
            snapshots: PERCEPTION 이 고정한 스냅샷들.

        Returns:
            엔티티별 계획.
        """
        plans = tuple(
            self.get_policy(entity.entity_id).plan_action(
                entity, snapshots[entity.entity_id], self.state
            )
            for entity in self.state.list_actors()
        )
        # 결정을 매 틱 남긴다. 피해가 난 틱만 기록하면 "왜 그 규칙이 안 떴는지"를
        # 되짚을 수 없고, 그것이 P1(실패는 정보다)의 실현을 막는다.
        for plan in plans:
            target = f" @{plan.target_id}" if plan.target_id else ""
            self.log.record(
                LogEntry(
                    tick=self.state.tick,
                    entity_id=plan.entity_id,
                    phase=PHASE_DECIDE,
                    expr=plan.expr,
                    outcome=f"{plan.action_id}{target}",
                    rule=plan.rule_index,
                    fired=True,
                )
            )
        return plans

    def apply_actions(self, plans: tuple[PlannedAction, ...]) -> None:
        """계획을 실행한다 (페이즈 5). 이동을 먼저, 공격을 나중에 한다.

        Args:
            plans: DECIDE 가 내놓은 계획들.
        """
        executor = self.actions
        order = self._sort_by_initiative(plans)
        for plan in order:
            entity = self._get_live_entity(plan)
            if entity is not None and plan.action_id in MOVE_ACTIONS:
                executor.apply_move(entity, plan)
        for plan in order:
            entity = self._get_live_entity(plan)
            if entity is None:
                continue
            if plan.action_id in ATTACK_ACTIONS:
                executor.apply_attack(entity, plan)
            elif plan.action_id == "AREA_ATTACK":
                executor.apply_area_attack(entity, plan)
            elif plan.action_id == "USE_POTION":
                executor.apply_potion(entity, plan)
            elif plan.action_id in {"HOLD", "SET_FLAG"}:
                executor.apply_hold(entity, plan)
            executor.apply_flag(entity, plan)

    def resolve_effects(self) -> None:
        """사망 처리와 타일 상태 갱신 (페이즈 6)."""
        for position, pool in list(self.state.spring_pools.items()):
            if pool <= 0:
                self.state.tile_overrides[position] = 0

    def run_cleanup(self) -> str:
        """승패를 판정한다 (페이즈 7).

        Returns:
            OUTCOME_* 중 하나.
        """
        actors = self.state.list_actors()
        if not [e for e in actors if e.faction == FACTION_PLAYER]:
            return OUTCOME_PLAYER_LOSS
        if not [e for e in actors if e.faction != FACTION_PLAYER]:
            return OUTCOME_PLAYER_WIN
        if self.state.tick >= self.config.max_ticks:
            return OUTCOME_TIMEOUT
        return OUTCOME_ONGOING

    def run_tick(self) -> str:
        """7페이즈를 한 바퀴 돈다.

        Returns:
            이번 틱 종료 시점의 승패 판정.
        """
        self.state.tick += 1
        self.run_upkeep()
        self.run_telegraph()
        snapshots = self.build_perceptions()
        plans = self.plan_actions(snapshots)
        self.apply_actions(plans)
        self.resolve_effects()
        return self.run_cleanup()

    # ── 내부 ────────────────────────────────────────────────────────────────

    def _get_live_entity(self, plan: PlannedAction) -> Entity | None:
        """계획의 주체가 아직 살아 있으면 돌려준다.

        Args:
            plan: 확인할 계획.

        Returns:
            살아 있는 엔티티, 아니면 None.
        """
        entity = self.state.entities.get(plan.entity_id)
        return entity if entity is not None and entity.is_alive else None

    def _sort_by_initiative(self, plans: tuple[PlannedAction, ...]) -> tuple[PlannedAction, ...]:
        """이동 충돌을 가를 순서를 정한다 (TDD §4.2).

        entity_id 사전순으로 가르면 이름이 앞선 엔티티가 영구히 유리해진다. 그래서
        이니셔티브를 먼저 보고, 동률은 시드 PRNG 로 가른다 — 시드가 같으면 같은 순서다.

        Args:
            plans: 정렬할 계획들.

        Returns:
            실행 순서대로 정렬된 계획들.
        """
        keyed = [
            (-self.state.entities[plan.entity_id].initiative, self.state.rng.get_uint64(), plan)
            for plan in plans
        ]
        keyed.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2] for item in keyed)

    def _apply_regen(self, entity: Entity, *, in_combat: bool) -> None:
        """회복을 적용한다. 전투 중에는 감쇠하고 샘은 잔여량을 깎는다 (GDD §7).

        Args:
            entity: 대상.
            in_combat: 전투 중인가.
        """
        tile_regen = 0
        position = entity.position
        if self.state.get_tile(*position) == TILE_SPRING:
            pool = self.state.spring_pools.get(position, 0)
            tile_regen = min(SPRING_REGEN_PER_TICK, pool)
            self.state.spring_pools[position] = pool - tile_regen
        # 전투 중 감쇠는 GDD §7 의 어뷰징 차단이다. 정수 연산이라 regen_base 1 은
        # 전투 중 0 이 된다 — 문서의 0.5 를 내림한 값이며 의도된 결과다.
        regen_pct = self.config.combat_regen_pct if in_combat else 100
        base = entity.regen_base * regen_pct // 100
        healed = min(entity.hp_max - entity.hp, base + tile_regen)
        if healed > 0:
            entity.hp += healed
