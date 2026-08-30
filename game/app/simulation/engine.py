"""틱 엔진 — 7페이즈를 고정 순서로 돈다 (TDD §4.1).

UPKEEP → TELEGRAPH → PERCEPTION → DECIDE → ACT → RESOLVE → CLEANUP.

PERCEPTION 과 DECIDE 를 나누는 이유는 동시성 공정성이다. 모든 엔티티가 같은 시점의
세계를 보고 판단해야 하며, 순차 갱신하면 처리 순서가 유리/불리를 만든다. 그래서
DECIDE 는 부작용을 내지 않고 계획만 돌려주며, 실제 변경은 ACT 부터다.

행동을 실제로 옮기는 일은 actions.ActionExecutor 가 맡는다. 이 모듈은 순서만 책임진다.

방 하나가 살아 있는 동안 유지되는 것 셋을 함께 든다 — 가시성 캐시(vision), 예고판
(telegraphs), 압력 추적기(pressure). 앞의 둘은 방 단위이고 압력 추적기만 층 단위라
바깥에서 받는다. 방마다 새로 만들면 GDD §7 의 '층 지연' 압력이 매 방 0 으로 돌아간다.
"""

from dataclasses import dataclass, field

from game.app.core.event_log import EventLog, LogEntry
from game.app.grid.vision import VisionCache, VisionGrid
from game.app.simulation.actions import (
    ATTACK_ACTIONS,
    GUARD_SKILL_ID,
    MOVE_ACTIONS,
    ActionExecutor,
)
from game.app.simulation.perception import PerceptionSnapshot, build_snapshot
from game.app.simulation.plan import (
    OUTCOME_BLOCKED,
    OUTCOME_ONGOING,
    OUTCOME_PLAYER_LOSS,
    OUTCOME_PLAYER_WIN,
    OUTCOME_TIMEOUT,
    PHASE_DECIDE,
    PHASE_TELEGRAPH,
    PHASE_UPKEEP,
    DecisionPolicy,
    EngineConfig,
    PlannedAction,
    PolicyFactory,
    resolve_skill_plan,
)
from game.app.simulation.pressure import PressureTracker
from game.app.simulation.springs import apply_spring_drain, remove_drained_springs
from game.app.simulation.state import FACTION_PLAYER, Entity, WorldState
from game.app.simulation.telegraph import Telegraph, TelegraphBoard
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
    # 진행 중인 예고. 방 단위다 — 방을 나가면 남은 예고도 함께 사라진다.
    telegraphs: TelegraphBoard = field(default_factory=TelegraphBoard)
    # 어뷰징 차단 (GDD §7). **층 단위 객체라 바깥에서 받는다.**
    pressure: PressureTracker = field(default_factory=PressureTracker)
    # 전투 도중 등장한 엔티티(소환물·추격자)에 규칙표를 붙이는 공장.
    policy_factory: PolicyFactory | None = None
    vision: VisionCache = field(init=False)
    actions: ActionExecutor = field(init=False)

    def __post_init__(self) -> None:
        """방 진입 시 한 번 하는 준비 — 가시성 맵 사전 계산 (TDD §5.4)."""
        grid = VisionGrid(self.state, self.state.room.width, self.state.room.height)
        self.vision = VisionCache(grid=grid)
        self.actions = ActionExecutor(
            state=self.state, log=self.log, config=self.config, telegraphs=self.telegraphs
        )
        self.register_newcomers()

    def register_newcomers(self) -> None:
        """아직 준비되지 않은 엔티티에 가시성 맵과 규칙표를 붙인다.

        소환물과 추격자는 방을 세운 뒤에 생기므로 조립 시점의 일괄 배정이 닿지 않는다.
        붙이지 않으면 그들만 폴백 정책으로 싸워 아무 압력도 되지 못한다.
        """
        for actor in self.state.list_actors():
            if self.vision.read(actor.entity_id) is None:
                self.vision.register(actor.entity_id, actor.position)
            if actor.entity_id in self.policies or self.policy_factory is None:
                continue
            policy = self.policy_factory.build_policy(actor)
            if policy is not None:
                self.policies[actor.entity_id] = policy

    def get_policy(self, entity_id: str) -> DecisionPolicy:
        """그 엔티티의 결정기를 돌려준다.

        Args:
            entity_id: 대상 엔티티 id.

        Returns:
            지정된 결정기, 없으면 기본 결정기.
        """
        return self.policies.get(entity_id, self.policy)

    def run_upkeep(self) -> None:
        """압력·쿨타임·상태이상·회복·타일 피해를 처리한다 (페이즈 1).

        압력을 엔티티 순회보다 **먼저** 건다. 그래야 그 틱에 등장한 추격자가
        전투 중 판정(회복 감쇠)에 들어가고, 자신도 같은 틱의 층 보너스를 받는다.
        """
        self.pressure.run_upkeep(self.state, self.log)
        self.register_newcomers()
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
        """예고를 1틱 진행하고 만기된 것을 터뜨린다 (페이즈 2).

        PERCEPTION 보다 앞이어야 한다. 카운트다운이 끝난 남은 틱을 그 틱의 인지
        변수가 읽고 규칙표가 회피를 결정한다 — 뒤집으면 항상 1틱 늦게 인지한다.
        """
        for telegraph in self.telegraphs.run_countdown(self.state, self.log):
            self._apply_self_destruct(telegraph)
        # 셀렉터 CASTING 과 `대상이 시전 중인가` 가 읽는다. 정렬해 내려야
        # 같은 시드가 같은 대상을 고른다 (R5).
        self.state.casting_ids = tuple(
            sorted({pending.caster_id for pending in self.telegraphs.list_active()})
        )

    def _apply_self_destruct(self, telegraph: Telegraph) -> None:
        """자폭형 예고가 터졌으면 시전자도 함께 죽인다 (GDD §5).

        예고판은 (WorldState, EventLog) 만 계약으로 갖고 종류 데이터를 모른다.
        그래서 '누가 자폭형인가' 는 여기서 본다.

        Args:
            telegraph: 이번 틱에 발동한 예고.
        """
        caster = self.state.entities.get(telegraph.caster_id)
        if caster is None or not caster.is_alive:
            return
        setting = self.config.enemy_stats.get(caster.kind_id, {}).get("telegraph") or {}
        if not setting.get("self_destruct"):
            return
        self.actions.apply_damage(
            caster, caster.hp, PHASE_TELEGRAPH, f"{telegraph.skill_id} 자폭", caster.entity_id
        )

    def build_perceptions(self) -> dict[str, PerceptionSnapshot]:
        """전 엔티티의 인지 변수를 이 시점에 고정한다 (페이즈 3).

        가시성 맵을 먼저 갱신한다. refresh 는 좌표가 그대로면 이전 맵을 그대로
        돌려주므로 실제 재계산은 이번 틱에 움직인 엔티티분만 일어난다 (TDD §5.4).

        Returns:
            entity_id 에서 스냅샷으로의 대응표.
        """
        self.register_newcomers()
        for actor in self.state.list_actors():
            self.vision.refresh(actor.entity_id, actor.position)
        return {
            entity.entity_id: build_snapshot(
                self.state,
                entity,
                self.config.kind_types,
                grid=self.vision.grid,
                board=self.telegraphs,
            )
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
            # 조건은 참인데 수단이 없어 건너뛴 규칙을 **먼저** 남긴다. 발동한 규칙보다
            # 위에 있던 것들이라 순서가 그렇고, 순서가 뒤집히면 "무엇이 무엇을 막았는가"
            # 를 로그에서 읽을 수 없다.
            for skipped in plan.blocked:
                self.log.record(
                    LogEntry(
                        tick=self.state.tick,
                        entity_id=plan.entity_id,
                        phase=PHASE_DECIDE,
                        expr=skipped.expr,
                        outcome=f"{OUTCOME_BLOCKED} — {skipped.reason}",
                        rule=skipped.rule_index,
                        fired=False,
                    )
                )
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
            self._apply_settled(executor, entity, plan)
            executor.apply_flag(entity, plan)

    def _apply_settled(self, executor: ActionExecutor, entity: Entity, plan: PlannedAction) -> None:
        """이동이 끝난 뒤 하는 행동을 실행기에 넘긴다.

        `USE_SKILL` 은 **한 겹의 지시**다 — 어느 스킬인지는 plan.skill_id 에 있다.
        여기서 그 스킬로 풀어 주면 실행기는 v5 를 몰라도 된다. 실행기마다 USE_SKILL 을
        알게 하면 스킬을 더할 때마다 실행기가 늘어나고, 그것이 블록을 파라미터화한 이유와
        정면으로 어긋난다 (docs/설계/5_스킬 §4).

        Args:
            executor: 행동 실행기.
            entity: 행위자.
            plan: 실행할 계획.
        """
        plan = resolve_skill_plan(plan)
        if plan.action_id in ATTACK_ACTIONS:
            executor.apply_attack(entity, plan)
        elif plan.action_id == "AREA_ATTACK":
            executor.apply_area_attack(entity, plan)
        elif plan.action_id == "USE_POTION":
            executor.apply_potion(entity, plan)
        elif plan.action_id == "HEAL":
            executor.apply_heal(entity, plan)
        elif plan.action_id == GUARD_SKILL_ID:
            executor.apply_guard(entity, plan)
        elif plan.action_id in {"HOLD", "SET_FLAG"}:
            executor.apply_hold(entity, plan)
        elif plan.action_id == "SUMMON":
            # 이동 루프보다 뒤여야 소환 위치가 이번 틱의 이동 결과를 반영한다.
            executor.apply_summon(entity, plan)

    def resolve_effects(self) -> None:
        """사망 정리와 타일 상태 갱신 (페이즈 6).

        여기서 바뀌는 타일은 샘 → 바닥뿐이고 둘 다 시야를 막지 않으므로 가시성 맵을
        다시 만들지 않는다. **파괴 가능 벽을 부수는 기능이 붙으면 그렇지 않다** —
        refresh 는 좌표만 보므로, 그 틱에는 전원 register 를 다시 불러야 한다.
        """
        remove_drained_springs(self.state, self.log)
        alive = {actor.entity_id for actor in self.state.list_actors()}
        # 죽은 관측자의 낡은 맵이 남으면 노출 판정에 섞여 원인 추적이 어려워진다.
        for entity_id in sorted(set(self.vision.maps) - alive):
            self.vision.drop(entity_id)

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
            # 잔여량 항목이 없는 좌표에 0 을 써 넣지 않는다 — 써 넣으면 그 샘이
            # 초기화되기도 전에 RESOLVE 의 소멸 대상이 된다.
            tile_regen = apply_spring_drain(self.state, position, SPRING_REGEN_PER_TICK)
        # 전투 중 감쇠는 GDD §7 의 어뷰징 차단이다. 정수 연산이라 regen_base 1 은
        # 전투 중 0 이 된다 — 문서의 0.5 를 내림한 값이며 의도된 결과다.
        regen_pct = self.config.combat_regen_pct if in_combat else 100
        base = entity.regen_base * regen_pct // 100
        healed = min(entity.hp_max - entity.hp, base + tile_regen)
        if healed > 0:
            entity.hp += healed
