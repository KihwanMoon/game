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
import { resolveActorKind, resolveActorLabel } from './actorKind'

/** 도면에 그릴 말 하나. */
export interface PlanActorView {
  readonly entityId: string
  readonly kindId: string
  readonly x: number
  readonly y: number
  readonly kind: PlanActorKind
  /** 일반·엘리트·보스. 도면이 색과 테두리로 가른다. */
  readonly tier: string
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

/** 도면 한 장. 순수 값이며 엔진을 참조하지 않는다. */
export interface PlanScene {
  readonly tick: number
  readonly cols: number
  readonly rows: number
  /** 현재 타일 ID. `[y][x]` 순서이며 파괴된 벽 등 변경분이 반영돼 있다. */
  readonly tiles: readonly (readonly number[])[]
  readonly actors: readonly PlanActorView[]
  readonly hazards: readonly PlanHazardView[]
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
  }
}