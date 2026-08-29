/**
 * 텔레그래프(예고 공격) — `game/app/simulation/telegraph.py` 의 이식 (GDD §4.2, TDD §4.1).
 *
 * 보스·정예는 피격 예정 타일을 N틱 전에 표시하고, 그 사이에 비켜서면 피해가 없다. 예고가
 * 없으면 `위험 예고 타일 위에 있는가` 인지 변수는 영원히 거짓이고, 회피 규칙은 플레이어가
 * 아무리 잘 짜도 발동하지 않는 죽은 코드가 된다.
 *
 * **등록됐다고 곧바로 보이지는 않는다.** 남은 틱이 그 예고의 인지 폭 안에 들어와야 인지
 * 변수가 참이 된다. 폭을 넓히는 것이 GDD §6.2 의 예측 회로이고, 조회 함수가 받는
 * foresightTicks 가 그 자리다.
 *
 * 피해는 방어력 감쇠를 거치지 않는 고정값이다. 예고의 유일한 정답이 회피여야 그 조건이
 * 전술이 된다 — 맞고 버티는 선택지가 성립하면 텔레그래프는 연출로 전락한다.
 */

import { EventLog, createLogEntry } from '../eventLog'
import {
  type Position,
  formatPositionKey,
  getManhattanDistance,
  sortUniquePositions,
} from '../grid/geometry'
import { PHASE_TELEGRAPH } from './phases'
import { type Entity, type WorldState, isAlive } from './state'

/** GDD §5 자폭형 — 접근 후 2틱 예고 뒤 폭발. */
export const DEFAULT_LEAD_TICKS = 2

/** 등록과 동시에 터지는 예고는 회피할 틈이 없어 예고가 아니다. */
export const MIN_LEAD_TICKS = 1

/** 기본 인지 폭. 남은 틱이 이 값 이하일 때만 인지 변수가 참이 된다. */
export const VISIBLE_TICKS = 1

/** GDD §6.2 예측 회로가 주는 보너스. 인지 폭을 이만큼 넓힌다. */
export const PREDICTOR_BONUS_TICKS = 1

/** 예측 회로 보유 여부를 담는 플래그 이름. 규칙표가 쓰는 A~D 와 겹치지 않는다. */
export const FORESIGHT_FLAG = 'FORESIGHT'

/** 이 이하로 남으면 경고를 danger 로 올린다 (design/README.md ThreatNotice). */
export const IMMINENT_TICKS = 1

export const TONE_DANGER = 'danger'
export const TONE_NEUTRAL = 'neutral'

/**
 * 색은 정보의 유일한 채널이 될 수 없다 — 글리프를 함께 낸다 (design/README.md).
 * 이모지를 쓰지 않는 것도 같은 문서의 규칙이다.
 */
export const GLYPH_IMMINENT = '▲'
export const GLYPH_PENDING = '△'

/**
 * UI 의 ThreatNotice 가 그대로 받는 값 (design/README.md 컴포넌트 계약).
 *
 * LogEntry 가 LogRow 에 대응하듯 이것은 경고 배너에 대응한다. 코어가 남은 틱을 내지
 * 않으면 UI 는 `3틱 후 피격` 을 그릴 수 없다.
 */
export interface ThreatNotice {
  readonly text: string
  readonly ticks: number
  readonly glyph: string
  readonly tone: string
}

/** 예고 한 건. 남은 틱이 0 이 되는 틱에 발동한다. */
export interface Telegraph {
  readonly telegraphId: string
  readonly casterId: string
  readonly skillId: string
  /** 정렬된 좌표다. 집합으로 들고 있으면 발동 로그의 순서가 흔들린다 (R5). */
  readonly tiles: readonly Position[]
  remainingTicks: number
  readonly damage: number
  /**
   * 남은 틱이 이 값 이하일 때부터 인지 변수에 잡힌다. leadTicks 와 같게 두면 등록
   * 순간부터 전 구간이 보인다 (GDD §4.2 의 "N틱 전에 표시").
   */
  readonly visibleTicks: number
  /**
   * 시전자를 먼저 죽이는 것이 예고에 대한 또 하나의 답이다. 보스의 확정 광역기처럼
   * 그 답을 막아야 하는 예고만 false 로 등록한다.
   */
  readonly cancelOnDeath: boolean
}

/** `TelegraphBoard.register` 가 받는 값들. */
export interface TelegraphInput {
  readonly casterId: string
  readonly skillId: string
  /** 피격 예정 좌표들. 중복은 합치고 정렬해 보관한다. */
  readonly tiles: readonly Position[]
  /** 발동 시 피해량. 방어력 감쇠를 받지 않는다. */
  readonly damage: number
  /** 발동까지 남은 틱. MIN_LEAD_TICKS 아래로는 내려가지 않는다. */
  readonly leadTicks?: number
  /** 인지 폭. leadTicks 를 넘기면 전 구간이 보인다. */
  readonly visibleTicks?: number
  /** 시전자가 죽으면 취소할 것인가. */
  readonly cancelOnDeath?: boolean
}

/**
 * 그 좌표가 피격 예정 타일인가.
 *
 * @param telegraph 볼 예고.
 * @param position 확인할 좌표.
 * @returns 피격 예정이면 true.
 */
export function checkTelegraphTile(telegraph: Telegraph, position: Position): boolean {
  const key = formatPositionKey(position)
  return telegraph.tiles.some((tile) => formatPositionKey(tile) === key)
}

/**
 * 지금 인지 가능한가.
 *
 * @param telegraph 볼 예고.
 * @param foresightTicks 예측 회로가 넓혀 주는 인지 폭.
 * @returns 남은 틱이 인지 폭 안이면 true.
 */
export function checkTelegraphVisible(telegraph: Telegraph, foresightTicks: number): boolean {
  return telegraph.remainingTicks <= telegraph.visibleTicks + foresightTicks
}

/**
 * 그 엔티티의 예고 인지 보너스 틱 (GDD §6.2 예측 회로).
 *
 * 아이템 모듈 접사는 아직 없다. 지금은 플래그 하나로 켜고 끄되 조회 지점을 여기 하나로
 * 모아 둔다 — 흩어 놓으면 모듈 시스템이 붙을 때 전부 찾아야 한다.
 *
 * @param entity 기준 엔티티.
 * @returns 인지 폭에 더할 틱 수. 예측 회로가 없으면 0.
 */
export function getForesightTicks(entity: Entity): number {
  return entity.flags.get(FORESIGHT_FLAG) === true ? PREDICTOR_BONUS_TICKS : 0
}

/**
 * 중심에서 맨해튼 반경 안의 좌표를 모은다.
 *
 * 거리는 이동과 같은 맨해튼이다 (F-5 결정). 체비셰프로 재면 대각으로 한 칸 물러난 자리가
 * 안전해 보이는데 실제로는 두 칸이라 회피 판단이 어긋난다.
 *
 * @param center 중심 좌표.
 * @param radius 맨해튼 반경. 0 이면 중심 한 칸이다.
 * @returns 정렬된 좌표들. 벽·방 밖은 거르지 않는다 — 무엇을 표시할지는 호출자가 정한다.
 */
export function buildBlastTiles(center: Position, radius: number): readonly Position[] {
  const found: Position[] = []
  for (let y = center.y - radius; y <= center.y + radius; y += 1) {
    for (let x = center.x - radius; x <= center.x + radius; x += 1) {
      const cell: Position = { x, y }
      if (getManhattanDistance(center, cell) <= radius) {
        found.push(cell)
      }
    }
  }
  return sortUniquePositions(found)
}

/**
 * 진행 중인 예고들. 등록 순서를 유지한다.
 *
 * 집합·대응표에 담으면 같은 틱에 여러 예고가 터질 때 피해 순서가 흔들려 같은 시드가
 * 다른 결과를 낸다 (R5). 그래서 배열이다.
 */
export class TelegraphBoard {
  pending: Telegraph[] = []

  /**
   * 예고 id 의 일련번호. 시간이나 난수가 아니라 단조 증가여야 같은 시드가 같은 id 를
   * 만든다 (R5). WorldState.spawnCounter 와 같은 이유다.
   */
  issuedCount = 0

  /**
   * 예고를 등록한다. 이 틱에는 터지지 않는다.
   *
   * @param input 시전자·스킬·타일·피해와 선행 틱 수.
   * @returns 등록된 예고.
   */
  register(input: TelegraphInput): Telegraph {
    this.issuedCount += 1
    const telegraph: Telegraph = {
      telegraphId: `${input.casterId}#${input.skillId}#${this.issuedCount}`,
      casterId: input.casterId,
      skillId: input.skillId,
      tiles: sortUniquePositions(input.tiles),
      remainingTicks: Math.max(MIN_LEAD_TICKS, input.leadTicks ?? DEFAULT_LEAD_TICKS),
      damage: input.damage,
      visibleTicks: input.visibleTicks ?? VISIBLE_TICKS,
      cancelOnDeath: input.cancelOnDeath ?? true,
    }
    this.pending.push(telegraph)
    return telegraph
  }

  /**
   * 모든 예고를 1틱 진행하고 만기된 것을 터뜨린다 (페이즈 2).
   *
   * 이 페이즈는 PERCEPTION 보다 앞이다. 그래서 카운트다운이 끝난 값을 그 틱의 인지
   * 변수가 읽고, 규칙표는 남은 틱을 보고 회피를 결정할 수 있다.
   *
   * @param state 세계 상태.
   * @param log 이벤트 로그.
   * @returns 이번 틱에 발동한 예고들. 등록 순서를 유지한다.
   */
  runCountdown(state: WorldState, log: EventLog): readonly Telegraph[] {
    const survivors: Telegraph[] = []
    const fired: Telegraph[] = []
    for (const telegraph of this.pending) {
      if (telegraph.cancelOnDeath && !this.checkCasterAlive(state, telegraph)) {
        const expr = `${telegraph.skillId} 예고 취소`
        this.recordEvent(state, log, telegraph, expr, '시전자 사망', null)
        continue
      }
      telegraph.remainingTicks -= 1
      if (telegraph.remainingTicks > 0) {
        survivors.push(telegraph)
        continue
      }
      this.applyBlast(state, log, telegraph)
      fired.push(telegraph)
    }
    this.pending = survivors
    return fired
  }

  /**
   * 진행 중인 예고들.
   *
   * @returns 등록 순서대로의 예고들.
   */
  listActive(): readonly Telegraph[] {
    return [...this.pending]
  }

  /**
   * 지금 붉게 표시되는 타일 전부 (GDD §4.2).
   *
   * @param foresightTicks 예측 회로가 넓혀 주는 인지 폭.
   * @returns 정렬된 좌표들. 겹친 예고는 한 번만 센다.
   */
  listMarked(foresightTicks = 0): readonly Position[] {
    const marked: Position[] = []
    for (const telegraph of this.pending) {
      if (checkTelegraphVisible(telegraph, foresightTicks)) {
        marked.push(...telegraph.tiles)
      }
    }
    return sortUniquePositions(marked)
  }

  /**
   * 그 칸에 걸린 예고 중 가장 급한 것의 남은 틱 (ThreatNotice.ticks).
   *
   * @param position 확인할 좌표.
   * @param foresightTicks 예측 회로가 넓혀 주는 인지 폭.
   * @returns 남은 틱. 인지 가능한 예고가 없으면 undefined — 0 으로 채우면 "위험 없음" 과
   *   "이번 틱에 터짐" 이 구분되지 않는다.
   */
  getRemaining(position: Position, foresightTicks = 0): number | undefined {
    let soonest: number | undefined
    for (const telegraph of this.pending) {
      if (
        checkTelegraphTile(telegraph, position) &&
        checkTelegraphVisible(telegraph, foresightTicks)
      ) {
        soonest =
          soonest === undefined ? telegraph.remainingTicks : Math.min(soonest, telegraph.remainingTicks)
      }
    }
    return soonest
  }

  /**
   * 그 칸이 인지 가능한 예고 아래에 있는가 (self_on_hazard_telegraph).
   *
   * @param position 확인할 좌표.
   * @param foresightTicks 예측 회로가 넓혀 주는 인지 폭.
   * @returns 예고 타일 위면 true.
   */
  isMarked(position: Position, foresightTicks = 0): boolean {
    return this.getRemaining(position, foresightTicks) !== undefined
  }

  /**
   * 그 엔티티가 예고를 걸어 둔 상태인가 (target_is_casting).
   *
   * 인지 폭을 보지 않는다. 시전 동작은 예고 타일이 붉어지기 전부터 보이며, 그 차이가
   * 센서 모듈(GDD §6.2)이 파는 가치다.
   *
   * @param entityId 확인할 엔티티 id.
   * @returns 진행 중인 예고가 하나라도 있으면 true.
   */
  isCasting(entityId: string): boolean {
    return this.pending.some((telegraph) => telegraph.casterId === entityId)
  }

  // ── 내부 ──────────────────────────────────────────────────────────────────

  /**
   * 시전자가 아직 살아 있는가.
   *
   * @param state 세계 상태.
   * @param telegraph 확인할 예고.
   * @returns 살아 있으면 true.
   */
  private checkCasterAlive(state: WorldState, telegraph: Telegraph): boolean {
    const caster = state.entities.get(telegraph.casterId)
    return caster !== undefined && isAlive(caster)
  }

  /**
   * 예고 타일 위의 엔티티에게 피해를 넣는다.
   *
   * 진영을 가리지 않는다. 예고는 좌표에 떨어지는 것이므로 시전자의 아군도 맞으며,
   * 그래야 통로로 유인하는 전술이 성립한다 (GDD §4.3).
   *
   * @param state 세계 상태.
   * @param log 이벤트 로그.
   * @param telegraph 발동한 예고.
   */
  private applyBlast(state: WorldState, log: EventLog, telegraph: Telegraph): void {
    // 포함 검사에만 쓴다. 이것을 순회해 상태를 만들면 순서가 흔들린다 (R5).
    const marked = new Set(telegraph.tiles.map(formatPositionKey))
    const victims = state
      .listActors()
      .filter((entity) => marked.has(formatPositionKey(entity.position)))
    const expr = `${telegraph.skillId} 예고 발동 (${telegraph.tiles.length}칸)`
    if (victims.length === 0) {
      // 회피 성공도 남긴다. 아무 일이 없었다는 사실이 규칙표를 고칠 때 가장 필요한
      // 정보다 (P1 실패는 정보다).
      this.recordEvent(state, log, telegraph, expr, '예고 타일 비어 있음 — 회피 성공', null)
      return
    }
    for (const victim of victims) {
      victim.hp = Math.max(0, victim.hp - telegraph.damage)
      const suffix = isAlive(victim) ? '' : ' 사망'
      const outcome = `${victim.entityId} HP ${victim.hp}/${victim.hpMax}${suffix}`
      this.recordEvent(state, log, telegraph, expr, outcome, -telegraph.damage, victim.entityId)
    }
  }

  /**
   * 예고 관련 이벤트 한 줄을 남긴다.
   *
   * @param state 세계 상태. 틱 번호를 읽는다.
   * @param log 이벤트 로그.
   * @param telegraph 대상 예고.
   * @param expr 조건 자리에 남길 문자열.
   * @param outcome 결과 설명.
   * @param delta 수치 변화. 없으면 null.
   * @param targetId 피해를 받은 쪽. 피해가 아닌 이벤트면 null.
   */
  private recordEvent(
    state: WorldState,
    log: EventLog,
    telegraph: Telegraph,
    expr: string,
    outcome: string,
    delta: number | null,
    targetId: string | null = null,
  ): void {
    log.record(
      createLogEntry({
        tick: state.tick,
        entityId: telegraph.casterId,
        phase: PHASE_TELEGRAPH,
        expr,
        outcome,
        delta,
        fired: true,
        targetId,
      }),
    )
  }
}

/**
 * 그 칸에 대한 경고 배너를 만든다 (design/README.md ThreatNotice).
 *
 * @param board 예고 보드.
 * @param position 기준 좌표. 보통 플레이어가 선 자리다.
 * @param foresightTicks 예측 회로가 넓혀 주는 인지 폭.
 * @returns 표시할 경고. 인지 가능한 위험이 없으면 undefined.
 */
export function buildThreatNotice(
  board: TelegraphBoard,
  position: Position,
  foresightTicks = 0,
): ThreatNotice | undefined {
  const ticks = board.getRemaining(position, foresightTicks)
  if (ticks === undefined) {
    return undefined
  }
  const isImminent = ticks <= IMMINENT_TICKS
  return {
    text: `위험 예고 — ${ticks}틱 후 피격`,
    ticks,
    glyph: isImminent ? GLYPH_IMMINENT : GLYPH_PENDING,
    tone: isImminent ? TONE_DANGER : TONE_NEUTRAL,
  }
}
