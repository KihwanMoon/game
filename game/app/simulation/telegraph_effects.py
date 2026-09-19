"""예고가 터질 때 대상에게 얹는 것 (설계/5_스킬 §1).

`telegraph.py` 에서 갈라 나왔다. 저쪽은 **언제 터지는가**이고 이쪽은 **터졌을 때 피해
말고 무엇이 남는가**다. 400줄 상한이 계기였지만 가르는 선은 책임이다 (§4).

**평면 필드를 대신하지 않는다.** `coef_pct`·`heal_pct`·`guard_pct` 의 뜻은 그대로이고
여기 있는 것은 덧붙이기다 — 거기서 파생시키려던 설계가 반증에서 세 번 깨졌다:
`coef_pct: 0` 의 뜻이 단계마다 바뀌고, `find_skill` 의 폴백 계약이 뒤집히고, 전제
검사가 early return 이라 `[GUARD, DAMAGE]` 가 적 없을 때 보호막까지 안 걸렸다.

**붙는 시점이 발동이라는 것이 그 셋을 한꺼번에 없앤다.** 그때는 누가 그 칸에 섰는지
이미 정해져 있어 「대상이 없어서 못 걸었다」가 생기지 않는다.
"""

from typing import Protocol

from game.app.core.event_log import EventLog
from game.app.simulation.phases import PHASE_TELEGRAPH
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.telegraph_record import Telegraph
from game.app.skills.catalog import EFFECT_STATUS, SkillEffect


class BlastRecorder(Protocol):
    """로그를 남기는 쪽. 예고판이 이것을 만족한다.

    **판이 쓰는 기록기를 그대로 쓴다.** 사본을 두면 같은 발동이 두 모양으로 적힌다.
    """

    def record_blast(
        self,
        state: WorldState,
        log: EventLog,
        telegraph: Telegraph,
        expr: str,
        outcome: str,
        delta: int | None,
        target_id: str | None = None,
    ) -> None:
        """한 줄 남긴다."""
        ...


def apply_status_effects(victim: Entity, effects: tuple[SkillEffect, ...]) -> list[tuple[str, int]]:
    """맞은 대상에게 상태를 얹는다 — **예고를 모르는 핵** (2026-09-19).

    **예고 레코드에 묶여 있었다.** 그래서 `effects` 가 예고형에만 걸렸고, 즉발 재주에
    상태를 달면 파싱도 되고 저장도 되고 관리 화면에도 뜨는데 **아무 일도 안 났다** —
    이 저장소가 `SLOW`·`POISON`·`cast_cooldown_add` 에서 이미 세 번 잡은 「조용히 무효」와
    같은 자리다. 핵을 떼어 두면 즉발도 예고형도 같은 것을 쓴다.

    **로그는 부르는 쪽이 남긴다.** 예고는 예고판의 형식으로, 즉발은 실행기의 형식으로
    적어야 해서 여기서 적으면 한쪽이 남의 모양으로 찍힌다.

    Args:
        victim: 맞은 대상.
        effects: 얹을 것들.

    Returns:
        실제로 얹은 (상태, 틱) 들. 순서는 `effects` 가 정한다 (R5).
    """
    applied: list[tuple[str, int]] = []
    for effect in effects:
        if effect.kind != EFFECT_STATUS or not effect.status:
            continue
        # 더 긴 쪽을 남긴다. 겹칠 때 짧은 것으로 덮으면 뒤에 온 약한 장판이 앞의
        # 강한 것을 지운다.
        before = victim.statuses.get(effect.status, 0)
        victim.statuses[effect.status] = max(before, effect.duration)
        applied.append((effect.status, effect.duration))
    return applied


def apply_blast_effects(
    board: BlastRecorder,
    state: WorldState,
    log: EventLog,
    telegraph: Telegraph,
    victim: Entity,
) -> None:
    """맞은 대상에게 스킬의 효과를 얹는다.

    **피해와 별개다.** 피해 0 인 장판이 상태만 거는 것이 이 자리이고, 그것이 평면
    필드로는 못 적는 것이었다 — 「피해를 주면서 둔화도 건다」도 여기서 성립한다.

    **진영을 안 가린다.** 피해와 같은 규칙이다 — 예고는 좌표에 떨어지므로 시전자의
    아군도 맞고, 그래야 통로로 유인하는 전술이 성립한다 (GDD §4.3).

    Args:
        board: 로그를 남길 예고판.
        state: 세계 상태.
        log: 이벤트 로그.
        telegraph: 발동한 예고.
        victim: 맞은 대상.
    """
    for status, duration in apply_status_effects(victim, telegraph.effects):
        board.record_blast(
            state,
            log,
            telegraph,
            f"{telegraph.skill_id} {status}",
            f"{victim.entity_id} {status} {duration}틱",
            None,
            victim.entity_id,
        )


class DamageDealer(Protocol):
    """피해를 입히는 쪽. `ActionExecutor` 가 이것을 만족한다.

    **실행기를 통째로 들이지 않는다.** `actions.py` 가 이 모듈을 거슬러 부르므로
    순환이 난다 — `BlastRecorder` 를 프로토콜로 둔 것과 같은 자리다.
    """

    def apply_damage(
        self,
        target: Entity,
        amount: int,
        phase: str,
        expr: str,
        actor_id: str,
        rule: int | None = None,
    ) -> None:
        """피해를 입힌다."""
        ...


def apply_self_destruct(
    state: WorldState,
    executor: DamageDealer,
    enemy_stats: dict[str, dict],
    telegraph: Telegraph,
) -> None:
    """자폭형 예고가 터졌으면 시전자도 함께 죽인다 (GDD §5).

    **여기가 제자리다.** 이 모듈이 「터졌을 때 무엇이 남는가」를 맡고, 자폭은 그중
    시전자에게 남는 것이다. 예고판은 (WorldState, EventLog) 만 계약으로 갖고 종류
    데이터를 모르므로 「누가 자폭형인가」는 판 바깥에서 본다.

    Args:
        state: 세계 상태.
        executor: 피해를 입히는 실행기.
        enemy_stats: 종류에서 스탯 절로의 대응표.
        telegraph: 이번 틱에 발동한 예고.
    """
    caster = state.entities.get(telegraph.caster_id)
    if caster is None or not caster.is_alive:
        return
    setting = enemy_stats.get(caster.kind_id, {}).get("telegraph") or {}
    if not setting.get("self_destruct"):
        return
    executor.apply_damage(
        caster, caster.hp, PHASE_TELEGRAPH, f"{telegraph.skill_id} 자폭", caster.entity_id
    )
