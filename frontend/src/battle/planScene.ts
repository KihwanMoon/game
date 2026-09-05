/**
 * 장면 — 엔진의 현재 상태를 도면이 그릴 값 묶음으로 접는다.
 *
 * 렌더러가 `TickEngine` 을 직접 받지 않는 이유는 두 가지다. 첫째, 그리기 도중에 세계를
 * 만질 길이 없어야 한다 — 캔버스가 `state.entities` 를 들고 있으면 언젠가 거기서 값을
 * 고치는 코드가 생기고, 그 순간 화면이 리플레이를 바꾼다 (R5). 둘째, 장면이 순수 값이면
 * 테스트가 캔버스 없이 "무엇을 그리기로 했는가" 를 확인할 수 있다.
 *
 * 순서는 전부 결정적이다. 말은 `listActors()` 순서(이니셔티브 내림차순)를 그대로 쓰고,
 * 예고 칸은 행 우선 (y, x) 로 정렬한다. 객체 키 순회는 쓰지 않는다.
 */

import { formatPositionKey } from '../core/grid/geometry'
import { sortByKey } from '../core/ordering'
import type { PlanActorKind } from '../ds'
import type { TickEngine } from '../core/sim/engine'
import { PLAYER_ENTITY_ID } from '../core/services/runBattle'
import { checkTelegraphVisible, getForesightTicks } from '../core/sim/telegraph'
import { FACTION_PLAYER, type Entity, getHpPercent } from '../core/sim/state'
import type { LogEntry } from '../core/eventLog'
import { PHASE_ACT } from '../core/sim/phases'

import { GUARD_STATUS } from '../core/sim/abilities'
import { checkDoppel, resolveActorKind, resolveActorLabel } from './actorKind'

/** 도면에 그릴 말 하나. */
export interface PlanActorView {
  readonly entityId: string
  readonly kindId: string
  readonly x: number
  readonly y: number
  readonly kind: PlanActorKind
  /** 일반·엘리트·보스. 도면이 색과 테두리로 가른다. */
  readonly tier: string
  /**
   * 도플갱어인가. **등급과 따로 싣는다** — ELITE 로 서지만 다른 정예와 같은 것이 아니다.
   *
   * 렌더러가 `kindId` 를 보고 직접 판정하지 않는 이유는, 그러면 그리는 쪽이 종 id 하나를
   * 알아야 하고 그 앎이 캔버스·DOM 두 곳으로 갈리기 때문이다.
   */
  readonly isDoppel: boolean
  /**
   * 지금 방어 태세인가 (`GUARD_BRACE`).
   *
   * **모델에 있는데 화면에 없던 것이다.** 받는 피해를 50% 깎고 2틱 가는데 도면에도
   * 로그에도 안 나왔다 — 보는 사람에게는 「왜 갑자기 덜 아프지」가 설명 없이 일어났다.
   * 설명 없는 것은 버그와 구별되지 않는다 (P1).
   */
  readonly isGuarding: boolean
  /** 글리프 아래 두 글자 표기. 글리프가 겹치는 자리를 이것이 가른다. */
  readonly label: string
  /** 남은 체력 백분율. 말 아래 명도 막대가 이 값을 쓴다. */
  readonly hpPercent: number
  /** 플레이어인가. 황동은 이 말 하나에만 쓴다. */
  readonly isSelf: boolean
}

/** 예고가 걸린 칸 하나 (GDD §4.2). */
export interface PlanHazardView {
  readonly x: number
  readonly y: number
  /** 발동까지 남은 틱. 0 이면 이번 틱에 터진다. */
  readonly ticks: number
  /**
   * 플레이어의 인지 폭 안에 들어왔는가.
   *
   * 관전자는 예고를 전부 보지만 규칙표는 인지 변수가 참이 된 것만 읽는다. 둘을 같은
   * 모양으로 그리면 "붉은데 왜 회피 규칙이 안 도는가" 를 설명할 길이 없다 — 아직 못
   * 읽는 예고는 점선으로 그려 센서 모듈(GDD §6.2)이 사는 값을 눈에 보이게 한다.
   */
  readonly isSensed: boolean
}

/**
 * 이번 틱에 누가 누구에게 무엇을 했는가 (한 줄).
 *
 * **말만 봐서는 누가 누구를 때렸는지 알 수 없다.** 격자에 다섯이 서 있고 HP 가 줄면,
 * 그것이 어느 말의 짓인지 화면 어디에도 안 적혀 있었다 — 로그를 눈으로 따라가야 했다.
 * 조건문에 실측값을 병기하는 것과 같은 이유로, 대상이 있는 행동은 선으로 잇는다 (P1).
 *
 * 색은 **방향**이다. 내가 하는 것과 나에게 오는 것은 읽는 사람에게 전혀 다른 사건이다.
 */
export interface PlanLinkView {
  readonly fromX: number
  readonly fromY: number
  readonly toX: number
  readonly toY: number
  /** 플레이어가 건 것인가. 황동과 녹슨 붉은색을 가르는 유일한 기준이다. */
  readonly isFromSelf: boolean
}

/**
 * 이번 틱에 수치가 움직인 자리 (간단한 이펙트).
 *
 * 로그의 `delta` 에서 나온다 — 피해는 붉게, 회복·방어는 초록으로 그 말을 고리로 감싼다.
 * 화려한 연출이 아니라 **무슨 일이 일어났는지의 표시**다 (P1).
 */
export interface PlanPulseView {
  readonly x: number
  readonly y: number
  /** 좋은 일(회복·방어)이면 참. 색이 갈린다 — verdigris 대 rust. */
  readonly isGain: boolean
  /**
   * 움직인 수치. **고리만으로는 얼마나였는지 모른다** — 조건문에 실측값을 병기하는
   * 규율(P1) 그대로, 맞은 자리에 -7, 회복에 +12 를 적는다. 수치 없는 스킬은 null.
   */
  readonly delta: number | null
  /** 무슨 스킬이었는지 두세 글자. 방어·소환처럼 수치가 없는 스킬은 이것만 남는다. */
  readonly label: string
}

/** 도면 한 장. 순수 값이며 엔진을 참조하지 않는다. */
export interface PlanScene {
  readonly tick: number
  readonly cols: number
  readonly rows: number
  /** 현재 타일 ID. `[y][x]` 순서이며 파괴된 벽 등 변경분이 반영돼 있다. */
  readonly tiles: readonly (readonly number[])[]
  readonly actors: readonly PlanActorView[]
  readonly hazards: readonly PlanHazardView[]
  /** 이번 틱의 대상 있는 행동들. 없으면 빈 배열이다. */
  readonly links: readonly PlanLinkView[]
  /** 이번 틱에 수치가 움직인 자리들. */
  readonly pulses: readonly PlanPulseView[]
}

/**
 * 엔티티 하나를 도면 말로 접는다.
 *
 * @param entity 그릴 엔티티.
 * @param kindTypes 종류에서 유형으로의 대응표.
 * @returns 도면 말.
 */
function convertEntityToActor(
  entity: Entity,
  kindTypes: ReadonlyMap<string, string>,
): PlanActorView {
  const isSelf = entity.faction === FACTION_PLAYER
  return {
    entityId: entity.entityId,
    kindId: entity.kindId,
    x: entity.position.x,
    y: entity.position.y,
    kind: isSelf ? 'self' : resolveActorKind(entity.kindId, kindTypes),
    label: isSelf ? '자신' : resolveActorLabel(entity.kindId),
    tier: entity.tier,
    isDoppel: !isSelf && checkDoppel(entity.kindId),
    isGuarding: (entity.statuses.get(GUARD_STATUS) ?? 0) > 0,
    hpPercent: getHpPercent(entity),
    isSelf,
  }
}

/**
 * 진행 중인 예고를 칸 단위로 편다.
 *
 * 겹친 예고는 **가장 급한 것**만 남긴다. 같은 칸에 남은 틱이 둘이면 화면이 둘을 다 적을
 * 자리가 없고, 늦은 쪽을 적으면 플레이어가 안전하다고 읽는다.
 *
 * @param engine 돌고 있는 엔진.
 * @param foresightTicks 플레이어의 인지 폭.
 * @returns 행 우선 (y, x) 로 정렬된 예고 칸들.
 */
function collectHazards(engine: TickEngine, foresightTicks: number): readonly PlanHazardView[] {
  const byCell = new Map<string, PlanHazardView>()
  for (const telegraph of engine.telegraphs.listActive()) {
    const isSensed = checkTelegraphVisible(telegraph, foresightTicks)
    for (const tile of telegraph.tiles) {
      const key = formatPositionKey(tile)
      const seen = byCell.get(key)
      if (seen !== undefined && seen.ticks <= telegraph.remainingTicks) {
        continue
      }
      byCell.set(key, {
        x: tile.x,
        y: tile.y,
        ticks: telegraph.remainingTicks,
        isSensed,
      })
    }
  }
  return sortByKey([...byCell.values()], (hazard) => [hazard.y, hazard.x])
}

/**
 * 지금 이 순간의 도면을 만든다.
 *
 * @param engine 돌고 있는 엔진. 읽기만 한다.
 * @returns 그릴 값 묶음.
 */
/** 행동 id 에서 이펙트 이름표로. 여기 없는 행동은 수치만 적는다. */
const PULSE_LABELS: ReadonlyMap<string, string> = new Map([
  ['ATTACK', ''],
  ['SKILL_1', '스킬1'],
  ['SKILL_2', '스킬2'],
  ['AREA_ATTACK', '광역'],
  ['HEAL', '치유'],
  ['GUARD_BRACE', '방어'],
  ['SUMMON', '소환'],
  ['USE_ITEM', '소모품'],
  ['USE_POTION', '물약'],
])

/** 수치가 없어도 이펙트를 남기는 행동들 — 방어 태세·소환은 delta 가 없다. */
const SILENT_PULSE_ACTIONS: ReadonlySet<string> = new Set(['GUARD_BRACE', 'SUMMON'])

/** 이펙트가 화면에 머무는 틱 수. 한 틱은 배속에서 안 보인다 — 두 틱이면 눈이 따라온다. */
const EFFECT_LINGER_TICKS = 2

/**
 * 이펙트가 살아 있는 최근 틱들의 로그 줄.
 *
 * **두 틱을 본다** (실제 요청 — 가시성). 이번 틱만 그리면 ×2 배속에서 타격·회복 고리가
 * 한 프레임 번쩍이고 사라져 무슨 일이 있었는지 못 읽는다. 렌더 전용이라 코어·리플레이는
 * 안 흔들린다.
 *
 * @param engine 돌고 있는 엔진.
 * @returns 최근 두 틱의 로그 줄들.
 */
function listRecentEntries(engine: TickEngine): readonly LogEntry[] {
  const log = engine.log
  if (log === undefined) {
    return []
  }
  const entries: LogEntry[] = []
  for (let back = EFFECT_LINGER_TICKS - 1; back >= 0; back -= 1) {
    entries.push(...log.filterByTick(engine.state.tick - back))
  }
  return entries
}

/**
 * 이번 틱의 로그에서 「누가 누구에게」를 뽑는다.
 *
 * **로그가 이미 알고 있다.** `target_id` 는 공격·스킬 기록에 처음부터 채워져 있었고
 * 골든에도 들어 있다 — 코어를 건드릴 이유가 없는 자리다.
 *
 * 죽어서 사라진 말은 뺀다. 없는 자리로 선을 그으면 격자 밖으로 나간다.
 *
 * @param engine 돌고 있는 엔진.
 * @param actors 이번 장면의 말들.
 * @returns 그릴 선들. 로그가 없으면 빈 배열.
 */
export function buildLinksFromLog(
  engine: TickEngine,
  actors: readonly PlanActorView[],
): readonly PlanLinkView[] {
  const spots = new Map(actors.map((actor) => [actor.entityId, actor]))
  const links: PlanLinkView[] = []
  for (const entry of listRecentEntries(engine)) {
    if (entry.phase !== PHASE_ACT || entry.targetId === null) {
      continue
    }
    const from = spots.get(entry.entityId)
    const to = spots.get(entry.targetId)
    // 자기 자신에게 거는 것(회복 등)은 선이 점이 된다 — 그릴 것이 없다.
    if (from === undefined || to === undefined || from === to) {
      continue
    }
    links.push({
      fromX: from.x,
      fromY: from.y,
      toX: to.x,
      toY: to.y,
      isFromSelf: from.isSelf,
    })
  }
  return links
}

/**
 * 이번 틱의 로그에서 수치가 움직인 자리를 뽑는다.
 *
 * @param engine 돌고 있는 엔진.
 * @param actors 이번 장면의 말들.
 * @returns 고리를 그릴 자리들.
 */
export function buildPulsesFromLog(
  engine: TickEngine,
  actors: readonly PlanActorView[],
): readonly PlanPulseView[] {
  // **죽은 말의 자리도 안다.** `listActors()` 는 죽은 것을 빼므로, 한 방에 죽인 적은
  // 이펙트가 붙을 자리를 잃어 마지막 타격이 화면에 안 보였다(실제 신고). 엔진의
  // 엔티티 표는 죽은 것도 들고 있으므로 그 좌표를 받침으로 쓴다.
  const spots = new Map<string, { x: number; y: number }>()
  for (const [entityId, entity] of engine.state.entities ?? []) {
    spots.set(entityId, { x: entity.position.x, y: entity.position.y })
  }
  for (const actor of actors) {
    spots.set(actor.entityId, { x: actor.x, y: actor.y })
  }
  const pulses: PlanPulseView[] = []
  for (const entry of listRecentEntries(engine)) {
    if (entry.phase !== PHASE_ACT || !entry.fired) {
      continue
    }
    const action = entry.expr.split(' @')[0] ?? ''
    const label = PULSE_LABELS.get(action) ?? ''
    if (entry.delta !== null && entry.delta !== 0) {
      // 피해는 대상에게, 회복·방어는 행위자 자신에게 적힌다.
      const spot = spots.get(entry.targetId ?? entry.entityId)
      if (spot !== undefined) {
        pulses.push({ x: spot.x, y: spot.y, isGain: entry.delta > 0, delta: entry.delta, label })
      }
    } else if (SILENT_PULSE_ACTIONS.has(action)) {
      // 방어 태세·소환은 수치가 없다 — 이름표라도 남겨야 「뭔가 했다」가 보인다.
      const spot = spots.get(entry.entityId)
      if (spot !== undefined) {
        pulses.push({ x: spot.x, y: spot.y, isGain: true, delta: null, label })
      }
    }
  }
  return pulses
}

export function buildPlanScene(engine: TickEngine): PlanScene {
  const { room } = engine.state
  const tiles: number[][] = []
  for (let y = 0; y < room.height; y += 1) {
    const row: number[] = []
    for (let x = 0; x < room.width; x += 1) {
      row.push(engine.state.getTile(x, y))
    }
    tiles.push(row)
  }

  const kindTypes = engine.config.kindTypes
  const actors = engine.state
    .listActors()
    .map((entity) => convertEntityToActor(entity, kindTypes))

  const player = engine.state.entities.get(PLAYER_ENTITY_ID)
  const foresight = player === undefined ? 0 : getForesightTicks(player)

  return {
    tick: engine.state.tick,
    cols: room.width,
    rows: room.height,
    tiles,
    actors,
    hazards: collectHazards(engine, foresight),
    links: buildLinksFromLog(engine, actors),
    pulses: buildPulsesFromLog(engine, actors),
  }
}