/**
 * 규칙표가 없을 때 쓰는 기본 행동 결정기 — `game/app/rules/fallback_policy.py` 의 이식.
 *
 * RuleVM 이 DecisionPolicy 자리에 들어오면 이 모듈은 그 폴백이 된다.
 *
 * TDD §5.2 가 정의한 DEFAULT 는 "가장 가까운 적에게 접근" 하나뿐이다. 그것만으로는 인접한
 * 뒤 더 다가갈 곳이 없어 아무도 죽지 않으므로, 여기서는 사거리 안이면 공격하는 한 줄을 더
 * 둔다. RuleVM 의 DEFAULT 는 TDD 대로 접근만 한다 — 둘은 다른 것이다.
 */

import { getManhattanDistance } from '../grid/geometry'
import { findMinBy } from '../ordering'
import { type PerceptionSnapshot, readSnapshot } from '../sim/perception'
import {
  type DecisionPolicy,
  type PlannedAction,
  createPlannedAction,
} from '../sim/plan'
import type { Entity, WorldState } from '../sim/state'

/** 이 아래로 떨어지면 포션을 쓴다. */
export const LOW_HP_PERCENT = 30

/** 붙어서 때리고, HP 가 낮으면 포션을 쓴다. */
export class FallbackPolicy implements DecisionPolicy {
  /**
   * 이번 틱의 행동을 정한다. 부작용을 내지 않는다.
   *
   * @param entity 결정 대상.
   * @param snapshot PERCEPTION 이 고정한 값들.
   * @param state 세계 상태. 읽기만 한다.
   * @returns 실행할 계획.
   */
  planAction(entity: Entity, snapshot: PerceptionSnapshot, state: WorldState): PlannedAction {
    const hpPercent = readSnapshot(snapshot, 'self_hp_percent')
    if (entity.potions > 0 && typeof hpPercent === 'number' && hpPercent < LOW_HP_PERCENT) {
      return createPlannedAction({
        entityId: entity.entityId,
        actionId: 'USE_POTION',
        expr: `HP%(${hpPercent}) < ${LOW_HP_PERCENT}`,
      })
    }

    const hostiles = state.listHostiles(entity)
    if (hostiles.length === 0) {
      return createPlannedAction({ entityId: entity.entityId, actionId: 'HOLD', expr: '적 없음' })
    }

    const nearest = findMinBy(hostiles, (other) => [
      getManhattanDistance(entity.position, other.position),
      other.entityId,
    ]) as Entity
    const distance = getManhattanDistance(entity.position, nearest.position)
    const inRange = distance <= entity.attackRange
    const comparison = inRange ? '<=' : '>'
    return createPlannedAction({
      entityId: entity.entityId,
      actionId: inRange ? 'ATTACK' : 'APPROACH',
      targetId: nearest.entityId,
      expr: `적거리(${distance}) ${comparison} 사거리(${entity.attackRange})`,
    })
  }
}
