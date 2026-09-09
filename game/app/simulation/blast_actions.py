"""예고형 광역 — 즉발 대신 붉은 칸을 먼저 띄우는 행동.

`actions.py` 에서 갈라 나왔다. 400줄 상한이 계기였지만 가르는 선은 책임이다 (§4) —
저쪽은 **이번 틱에 끝나는 것**, 이쪽은 **다음 틱으로 넘기는 것**이다. 넘긴 뒤의 일은
`telegraph.py` 가 든다.

**두 갈래가 있고 스킬이 먼저다.** 개체 종류가 정하는 예고(자폭형)는 그 종류의 성질이고,
스킬이 정하는 예고는 그 **행동**의 성질이라 누가 쓰든 같아야 한다 — 플레이어가 예고를
거는 길이 그것이다 (설계/5_스킬 §10).
"""

from game.app.grid.geometry import get_manhattan_distance
from game.app.simulation import abilities
from game.app.simulation.plan import EngineConfig, PlannedAction
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.telegraph import MIN_LEAD_TICKS, TelegraphBoard
from game.app.skills.catalog import find_skill

# 퍼센트 기준. 100 이 1.0배다.
PERCENT_BASE = 100


class BlastActionMixin:
    """예고형 광역기. `ActionExecutor` 가 이것을 상속한다.

    아래 넷은 **구체 클래스가 채운다** — `SupportActionMixin` 과 같은 계약이다.
    """

    state: WorldState
    config: EngineConfig
    telegraphs: TelegraphBoard

    def _record(self, actor_id: str, plan: PlannedAction, outcome: str, delta: int | None) -> None:
        """구체 클래스가 채운다."""
        raise NotImplementedError

    def _apply_cooldown(self, entity: Entity, action_id: str) -> None:
        """구체 클래스가 채운다."""
        raise NotImplementedError

    def _apply_strike(self, entity: Entity, target: Entity, plan: PlannedAction) -> None:
        """구체 클래스가 채운다."""
        raise NotImplementedError

    def apply_cast(self, entity: Entity, plan: PlannedAction) -> bool:
        """스킬이 예고를 정하면 그것을 걸고 True 를 돌려준다.

        **디스패치를 데이터로 가르는 첫 자리다.** 실행기는 `action_id` 로 갈리므로 새
        스킬 id 는 어느 갈래에도 안 닿는다 — `apply_area_attack` 안에 예고를 넣어 두면
        `AREA_ATTACK` 이라는 이름을 쓴 스킬만 예고를 걸 수 있고, 그것은 「스킬을 데이터로
        더한다」의 반대다 (설계/5_스킬 §10.8).

        엔진이 id 갈래보다 **먼저** 이것을 묻는다. 예고는 그 행동의 성질이지 이름의
        성질이 아니므로, 이름을 아는 것보다 앞선다.

        Args:
            entity: 시전자.
            plan: 실행할 계획.

        Returns:
            예고를 걸었으면 True. 이 스킬이 예고를 안 쓰면 False — 그때는 엔진이
            평소의 갈래로 넘어간다.
        """
        cast = self._build_skill_telegraph(entity, plan)
        if cast is None:
            return False
        self._register_telegraph(entity, plan, cast)
        return True

    def apply_area_attack(self, entity: Entity, plan: PlannedAction) -> None:
        """반경 안의 적 전체를 친다.

        Args:
            entity: 공격자.
            plan: 실행할 계획.
        """
        # 스킬이 정하는 예고는 엔진이 앞에서 `apply_cast` 로 이미 걸렀다. 여기 남는
        # 것은 **개체 종류**가 정하는 예고(자폭형)뿐이다.
        telegraph = self.config.enemy_stats.get(entity.kind_id, {}).get("telegraph")
        if telegraph is not None:
            self._register_telegraph(entity, plan, telegraph)
            return
        # **반경의 정본은 데이터다** (설계/5_스킬 §9). 예전에는 여기 상수가 있었고
        # `skills.json` 의 `shape` 는 아무도 안 읽어 거짓이었다.
        radius = find_skill(self.config.skills, plan.action_id).shape.radius
        victims = [
            other
            for other in self.state.list_hostiles(entity)
            if get_manhattan_distance(entity.position, other.position) <= radius
        ]
        if not victims:
            self._record(entity.entity_id, plan, "반경 안에 적 없음 — 틱 낭비", None)
            return
        for victim in victims:
            self._apply_strike(entity, victim, plan)
        self._apply_cooldown(entity, plan.action_id)

    def _build_skill_telegraph(self, entity: Entity, plan: PlannedAction) -> dict | None:
        """스킬이 예고를 쓰면 등록할 절을 만든다 (설계/5_스킬 §10).

        **피해를 시전 시점에 얼린다.** 예고 피해는 방어력 감쇠를 안 거치는 고정값이라
        (`telegraph.py` 머리말: 「예고의 유일한 정답이 회피여야」), 발동 시점에 다시
        계산하면 그 사이의 버프·저주가 회피 판정에 섞인다. 시전자의 공격력에 계수를
        곱한 값을 그때 굳혀 두면 「누가 걸었는가」는 반영되고 「그 뒤에 무슨 일이
        있었는가」는 안 반영된다.

        **`cancel_on_death` 는 True 다.** 시전자를 먼저 죽이는 것이 예고에 대한 또 하나의
        답이고, 그 답을 막아야 하는 것은 보스의 확정 광역기뿐이다.

        Args:
            entity: 시전자.
            plan: 실행 중인 계획.

        Returns:
            등록할 절. 이 스킬이 예고를 안 쓰면 None.
        """
        skill = find_skill(self.config.skills, plan.action_id)
        if skill.telegraph <= 0:
            return None
        target = self.state.entities.get(plan.target_id or "")
        # **유물이 제약을 바꾼다** (설계/5_스킬 §10.7). 스킬을 열어 주지 않는 이유는
        # 그러면 그 스킬이 유물 드롭률(만분의 5) 뒤에 갇히기 때문이고, 더 센 것을 주지
        # 않는 이유는 그러면 규칙표가 안 바뀌기 때문이다 — 바뀌는 것은 **대가**다.
        lead = max(MIN_LEAD_TICKS, skill.telegraph - entity.cast_lead_cut)
        return {
            "skill": plan.action_id,
            "shape": skill.shape.kind,
            "radius": skill.shape.radius + entity.blast_radius,
            "length": skill.shape.length,
            # `LINE` 은 방향이 필요하다. 이 게임에 바라보는 방향이 없으므로 대상 쪽으로
            # 잡는다 — 대상이 없으면 방향도 없어 칸이 0 개가 되고, 그때는 예고가
            # 「빈 칸」으로 서서 아무도 안 맞는다. 그 사실은 로그에 남는다.
            "toward": target.position if target is not None else entity.position,
            "damage": entity.attack * skill.coef_pct // PERCENT_BASE,
            "lead_ticks": lead,
            # 전 구간을 붉힌다. 좁게 잡는 것은 예측 회로에 값을 주려는 예고이고,
            # 플레이어가 거는 것은 적이 확실히 볼 수 있어야 「비켜선다」가 성립한다.
            "visible_ticks": lead,
            "cancel_on_death": True,
            # 흔들림 없는 시전은 **행동 취소만** 끈다. 피격 취소는 그대로다 —
            # 둘 다 끄면 「안전한 자리에서 쏘는가」가 사라져 상위 호환이 된다.
            "cancel_on_act": skill.cancel_on_act and entity.steady_cast <= 0,
            "cancel_on_hit": skill.cancel_on_hit,
            # **얹을 것들.** 피해와 별개다 — 피해 0 인 장판이 상태만 거는 자리다.
            "effects": skill.effects,
        }

    def _register_telegraph(self, entity: Entity, plan: PlannedAction, telegraph: dict) -> None:
        """즉발 대신 예고를 건다 (GDD §4.2).

        Args:
            entity: 시전자.
            plan: 실행 중인 계획.
            telegraph: balance.json 의 그 종류 telegraph 절.
        """
        outcome = abilities.register_blast(self.state, self.telegraphs, entity, telegraph)
        self._apply_cooldown(entity, plan.action_id)
        self._record(entity.entity_id, plan, outcome, None)
