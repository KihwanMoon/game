/**
 * 세계 상태 — `game/app/simulation/state.py` 의 이식. 엔티티와 방의 현재 모습.
 *
 * 순회 순서를 이니셔티브 내림차순, 동률이면 entityId 사전순으로 고정한다. 삽입 순서에
 * 기대면 스폰 순서가 바뀔 때 결과가 흔들려 리플레이가 깨진다 (R5).
 *
 * 엔티티 목록은 객체가 아니라 `Map` 이다. 객체의 키 순회 순서는 명세가 정수 키를 앞으로
 * 끌어올리므로 `"3"` 같은 id 가 섞이는 순간 순서가 달라진다 — `Map` 은 삽입 순서를
 * 그대로 지킨다. 그래도 게임 상태를 만들 때는 반드시 `listActors()` 를 거친다.
 */

import { type Position, checkSamePosition, formatPositionKey } from '../grid/geometry'
import type { DeterministicRng } from '../rng'
import { type RoomTemplate, getRoomTile } from '../schemas'
import type { TileReader } from '../grid/vision'
import { sortByKey } from '../ordering'

export const FACTION_PLAYER = 'player'
export const FACTION_ENEMY = 'enemy'

/** 전투에 참여하는 개체 하나 (TDD §3.1). 필드는 전투 중 바뀐다. */
export interface Entity {
  readonly entityId: string
  readonly kindId: string
  readonly faction: string
  position: Position
  hp: number
  hpMax: number
  attack: number
  defense: number
  attackRange: number
  initiative: number
  regenBase: number
  cpuBudget: number
  potions: number
  /** 누가 불러냈는가. 소환 상한을 소환사별로 세기 위해 필요하다. */
  summonerId: string | null
  readonly cooldowns: Map<string, number>
  readonly flags: Map<string, boolean>
  readonly statuses: Map<string, number>
}

/** `createEntity` 가 받는 값들. 생략한 항목은 파이썬 dataclass 의 기본값과 같다. */
export interface EntityInput {
  readonly entityId: string
  readonly kindId: string
  readonly faction: string
  readonly position: Position
  readonly hp: number
  readonly hpMax: number
  readonly attack: number
  readonly defense: number
  readonly attackRange: number
  readonly initiative: number
  readonly regenBase?: number
  readonly cpuBudget?: number
  readonly potions?: number
  readonly summonerId?: string | null
  readonly cooldowns?: ReadonlyMap<string, number>
  readonly flags?: ReadonlyMap<string, boolean>
  readonly statuses?: ReadonlyMap<string, number>
}

/**
 * 기본값을 채워 엔티티를 만든다.
 *
 * @param input 채워 넣을 값들.
 * @returns 만들어진 엔티티.
 */
export function createEntity(input: EntityInput): Entity {
  return {
    entityId: input.entityId,
    kindId: input.kindId,
    faction: input.faction,
    position: input.position,
    hp: input.hp,
    hpMax: input.hpMax,
    attack: input.attack,
    defense: input.defense,
    attackRange: input.attackRange,
    initiative: input.initiative,
    regenBase: input.regenBase ?? 0,
    cpuBudget: input.cpuBudget ?? 0,
    potions: input.potions ?? 0,
    summonerId: input.summonerId ?? null,
    cooldowns: new Map(input.cooldowns ?? []),
    flags: new Map(input.flags ?? []),
    statuses: new Map(input.statuses ?? []),
  }
}

/**
 * HP 가 남아 있는가.
 *
 * @param entity 볼 엔티티.
 * @returns 살아 있으면 true.
 */
export function isAlive(entity: Entity): boolean {
  return entity.hp > 0
}

/**
 * 현재 HP 비율. 정수 퍼센트다 — 부동소수를 쓰지 않는다 (R5).
 *
 * @param entity 볼 엔티티.
 * @returns 0 이상 100 이하의 정수.
 */
export function getHpPercent(entity: Entity): number {
  const PERCENT_BASE = 100
  return Math.floor((entity.hp * PERCENT_BASE) / entity.hpMax)
}

/** 한 방의 전체 상태. 시야 함수들이 받는 TileReader 이기도 하다. */
export class WorldState implements TileReader {
  /** 등장한 엔티티들. 죽은 것도 남는다 — 로그가 이름으로 되짚기 때문이다. */
  readonly entities = new Map<string, Entity>()

  tick = 0

  /**
   * 소환된 개체에 붙일 일련번호. 시간이나 난수가 아니라 단조 증가여야 같은 시드가
   * 같은 id 를 만든다 (R5).
   */
  spawnCounter = 0

  /** 파괴된 벽·마른 샘 등 지형 변경분. 좌표 열쇠에서 타일 ID 로. */
  readonly tileOverrides = new Map<string, number>()

  /** 생명의 샘의 잔여 회복량. 좌표 열쇠에서 잔여량으로. */
  readonly springPools = new Map<string, number>()

  /**
   * 이번 틱에 예고를 걸어 둔 시전자들. TELEGRAPH 페이즈가 정렬해 채운다.
   * 셀렉터 CASTING 과 인지 변수 `대상이 시전 중인가` 가 이 값을 읽는다 — 예고판을
   * 엔진이 들고 있어 selectors 가 닿지 못하므로 세계 상태로 내린다.
   */
  castingIds: readonly string[] = []

  /**
   * 세계 상태를 만든다.
   *
   * @param room 이 방의 템플릿.
   * @param rng 이 방이 쓸 난수원. 소비 순서가 곧 리플레이의 정본이다.
   */
  constructor(
    readonly room: RoomTemplate,
    readonly rng: DeterministicRng,
  ) {}

  /**
   * 좌표의 현재 타일 ID. 파괴된 벽 등 변경분을 반영한다.
   *
   * @param x 가로 좌표.
   * @param y 세로 좌표.
   * @returns 타일 ID.
   */
  getTile(x: number, y: number): number {
    const override = this.tileOverrides.get(formatPositionKey({ x, y }))
    return override ?? getRoomTile(this.room, x, y)
  }

  /**
   * 살아 있는 엔티티를 행동 순서대로 돌려준다.
   *
   * 이동 충돌은 이니셔티브로 가른다(TDD §4.2). 동률이면 entityId 사전순이며, 그래도
   * 같은 경우는 없다 — id 가 유일하기 때문이다.
   *
   * @returns 이니셔티브 내림차순으로 정렬된 엔티티들.
   */
  listActors(): readonly Entity[] {
    const alive = [...this.entities.values()].filter(isAlive)
    return sortByKey(alive, (entity) => [-entity.initiative, entity.entityId])
  }

  /**
   * 그 칸에 서 있는 살아 있는 엔티티를 찾는다.
   *
   * @param position 찾을 좌표.
   * @returns 찾은 엔티티. 없으면 undefined.
   */
  findEntityAt(position: Position): Entity | undefined {
    return this.listActors().find((entity) => checkSamePosition(entity.position, position))
  }

  /**
   * 상대 진영의 살아 있는 엔티티들.
   *
   * @param viewer 기준 엔티티.
   * @returns 진영이 다른 엔티티들. 순서는 listActors 와 같다.
   */
  listHostiles(viewer: Entity): readonly Entity[] {
    return this.listActors().filter((entity) => entity.faction !== viewer.faction)
  }
}
