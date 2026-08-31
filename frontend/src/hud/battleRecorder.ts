/**
 * 관전 기록 — 판을 한 번 끝까지 돌리며 **틱마다의 화면 상태**를 받아 적는다.
 *
 * 왜 미리 다 돌려 두는가. 되감기 때문이다(GDD §8.3). 엔진은 앞으로만 가므로 슬라이더를
 * 뒤로 밀 방법이 없고, 그때마다 처음부터 다시 돌리면 화면이 멈춘다. 결정론 덕에 미리
 * 돌려 둔 프레임과 다시 돌린 판이 같다는 것이 보장되므로(R5) 한 번만 돌리고 그 배열
 * 위를 걷는다.
 *
 * 피격 좌표를 여기서 함께 적는 이유는 파이썬 `replay_battle.BattleRecorder` 와 같다.
 * 로그는 "누가 얼마를 맞았는가" 까지만 남기고 "어디에서" 는 그 틱의 세계 상태에만 있다.
 * 틱 전후의 좌표표를 그때 같이 읽어 두지 않으면 나중에 복원할 수 없다.
 *
 * **판 조립과 도면 장면은 `src/battle` 것을 그대로 쓴다.** 같은 것을 두 벌 두면 화면
 * 둘이 같은 시드로 다른 판을 그리게 되고, 그러면 어느 쪽 화면을 믿어야 할지 알 수 없다.
 * 여기가 더하는 것은 "지나간 틱을 다시 볼 수 있게 남긴다" 하나뿐이다.
 */

import { buildBattleSession, buildPlanScene, checkOngoing } from '../battle'
import type { BattleSetup, PlanScene } from '../battle'
import type { LogEntry } from '../core/eventLog'
import type { Position } from '../core/grid/geometry'
import type { RoomTemplate, RuleSet } from '../core/schemas'
import { countItem } from '../core/sim/state'
import { PLAYER_ENTITY_ID } from '../core/services/runBattle'
import { runTickBatch } from '../core/services/runSteppedBattle'
import { countEnemyKinds } from '../core/services/runSummary'
import type { EnemyTally } from '../core/services/runSummary'
import type { TickEngine } from '../core/sim/engine'
import { OUTCOME_ONGOING } from '../core/sim/phases'
import type { WorldState } from '../core/sim/state'
import { buildThreatNotice, getForesightTicks } from '../core/sim/telegraph'
import type { ThreatNotice } from '../core/sim/telegraph'

import { extractDamageHits } from './analysis'
import type { DamageHit, PositionTable } from './analysis'

/** 한 번에 한 틱씩 돈다. 틱 안에서 멈추면 DECIDE 와 ACT 가 보는 세계가 갈린다 (TDD §4.1). */
const ONE_TICK = 1

/** 한 틱이 끝난 시점의 화면 상태. 되감기가 이 배열 위를 오간다. */
export interface RecordedFrame {
  readonly tick: number
  /** 이 틱의 로그가 시작되는 첨자 (`entries` 기준). */
  readonly logStart: number
  /** 이 틱의 로그가 끝나는 첨자. 반열린 구간이다. */
  readonly logEnd: number
  /** 그릴 도면 한 장. 순수 값이라 나중에 다시 그려도 같은 그림이 나온다. */
  readonly scene: PlanScene
  readonly playerHp: number
  readonly playerHpMax: number
  readonly potions: number
  /** 플레이어가 선 칸에 걸린 예고. 없으면 undefined 다 — 0 으로 접지 마라. */
  readonly threat: ThreatNotice | undefined
  /** 이 틱이 끝난 시점의 승패. 진행 중이면 OUTCOME_ONGOING. */
  readonly outcome: string
}

/** 판 하나를 처음부터 끝까지 적어 둔 것. */
export interface BattleRecording {
  readonly setup: BattleSetup
  readonly template: RoomTemplate
  readonly ruleset: RuleSet
  readonly playerId: string
  readonly cpuBudget: number
  readonly potionsMax: number
  readonly outcome: string
  readonly ticks: number
  readonly playerHp: number
  readonly entries: readonly LogEntry[]
  /** 첫 원소는 첫 틱을 돌리기 전(tick 0)이다. 그래서 길이가 틱 수보다 하나 많다. */
  readonly frames: readonly RecordedFrame[]
  readonly hits: readonly DamageHit[]
  /** 이 판에서 만난 적과 잡은 적. 결산(GDD §2.3)이 도감에 누적하는 입력이다. */
  readonly tally: EnemyTally
}

/**
 * 모든 엔티티의 현재 좌표를 읽는다.
 *
 * 죽은 개체도 담는다. 죽인 그 한 방이 어느 칸에서 났는지가 히트맵에서 가장 중요한 한
 * 칸이며, 살아 있는 것만 담으면 그 칸이 빠진다.
 *
 * @param state 세계 상태.
 * @returns entityId 에서 좌표로의 대응표. 조회용이며 순회 대상이 아니다.
 */
export function readPositions(state: WorldState): PositionTable {
  const table = new Map<string, Position>()
  for (const [entityId, entity] of state.entities) {
    table.set(entityId, entity.position)
  }
  return table
}

/**
 * 지금 시점의 프레임을 만든다.
 *
 * @param engine 도는 중인 엔진.
 * @param logStart 이 틱의 로그가 시작되는 첨자.
 * @param outcome 이 틱이 끝난 시점의 승패.
 * @returns 화면이 그대로 그릴 수 있는 한 틱의 상태.
 * @throws 플레이어 엔티티가 없는 경우. 조립이 잘못된 것이다.
 */
export function recordFrame(
  engine: TickEngine,
  logStart: number,
  outcome: string,
): RecordedFrame {
  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error(`플레이어 엔티티가 없다: ${PLAYER_ENTITY_ID}`)
  }
  return {
    tick: engine.state.tick,
    logStart,
    logEnd: engine.log.count(),
    scene: buildPlanScene(engine),
    playerHp: player.hp,
    playerHpMax: player.hpMax,
    potions: countItem(player, 'POTION'),
    threat: buildThreatNotice(engine.telegraphs, player.position, getForesightTicks(player)),
    outcome,
  }
}

/**
 * 판을 끝까지 돌리며 프레임과 피격 좌표를 받아 적는다.
 *
 * @param setup 방·규칙표·시드와 덧붙일 적.
 * @param rulesets 플레이어 규칙표 대응표.
 * @returns 관전과 사후 분석에 필요한 것이 다 든 기록.
 * @throws 없는 방이거나 없는 규칙표이거나, 플레이어 엔티티가 없는 경우.
 */
export function recordBattle(
  setup: BattleSetup,
  rulesets: ReadonlyMap<string, RuleSet>,
): BattleRecording {
  const session = buildBattleSession(setup, rulesets)
  const { engine } = session

  const frames: RecordedFrame[] = [recordFrame(engine, 0, OUTCOME_ONGOING)]
  const hits: DamageHit[] = []
  let outcome = OUTCOME_ONGOING
  while (checkOngoing(outcome)) {
    const logStart = engine.log.count()
    const startPositions = readPositions(engine.state)
    const batch = runTickBatch(engine, ONE_TICK)
    outcome = batch.outcome
    hits.push(...extractDamageHits(batch.entries, startPositions, readPositions(engine.state)))
    frames.push(recordFrame(engine, logStart, outcome))
  }

  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  if (player === undefined) {
    throw new Error(`플레이어 엔티티가 없다: ${PLAYER_ENTITY_ID}`)
  }
  return {
    setup,
    template: session.template,
    ruleset: session.ruleset,
    playerId: PLAYER_ENTITY_ID,
    cpuBudget: player.cpuBudget,
    potionsMax: session.balance.player.potions,
    outcome,
    ticks: engine.state.tick,
    playerHp: player.hp,
    entries: engine.log.entries,
    frames,
    hits,
    tally: countEnemyKinds(engine.state),
  }
}
