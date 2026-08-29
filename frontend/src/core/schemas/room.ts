/**
 * 룸 템플릿 — 손으로 그린 12x9 그리드 (GDD §4.4, TDD §7.2). `game/schemas/room.py` 의 이식이다.
 *
 * 템플릿 JSON 은 사람이 그리는 자리라 ASCII 로 적혀 있다. 런타임 형식은 TDD §3.4 가 정한
 * 숫자 배열이며 이 모듈이 legend 로 변환한다.
 *
 * 생성 직후 flood fill 로 `시작점 -> 모든 문` 도달 가능성을 확인한다. 벽 하나 잘못 찍으면
 * 클리어 불가능한 방이 되고, 그것은 규칙 설계 실패와 구분되지 않는다.
 */

export const TILE_FLOOR = 0
export const TILE_WALL = 1
export const TILE_BREAKABLE_WALL = 2
export const TILE_THORNS = 3
export const TILE_DOOR = 4
export const TILE_SPRING = 5
export const TILE_STAIRS = 6
export const TILE_LAVA = 7
export const TILE_TRAP = 8
export const TILE_COVER = 9

/**
 * 진입 시점에 지나갈 수 있는 타일. 파괴 가능 벽(2)은 부수기 전에는 막혀 있으므로 도달성
 * 검사에서 통로로 세지 않는다 — 통로로 세면 부술 수단이 없는 규칙표가 갇힌다.
 */
export const WALKABLE_TILES: ReadonlySet<number> = new Set([
  TILE_FLOOR,
  TILE_THORNS,
  TILE_DOOR,
  TILE_SPRING,
  TILE_STAIRS,
  TILE_LAVA,
  TILE_TRAP,
])

/**
 * 상하좌우만 센다. 대각 이동이 허용되더라도 4방향으로 닿으면 8방향으로도 닿으므로 이쪽이
 * 더 엄격한 검사다.
 */
export const STEP_OFFSETS: readonly (readonly [number, number])[] = [
  [0, -1],
  [0, 1],
  [-1, 0],
  [1, 0],
]

/** 격자 좌표. 파이썬의 튜플 좌표에 대응한다. */
export interface GridPosition {
  readonly x: number
  readonly y: number
}

/** 어떤 적이 어디서 나오는가 (TDD §3.4). */
export interface EnemySpawn {
  readonly kind: string
  readonly position: GridPosition
}

/** 룸 템플릿 하나. tiles 는 [y][x] 순서다. */
export interface RoomTemplate {
  readonly templateId: string
  readonly purpose: string
  readonly tiles: readonly (readonly number[])[]
  readonly width: number
  readonly height: number
  readonly playerSpawn: GridPosition
  readonly enemySpawns: readonly EnemySpawn[]
}

/** templates.json 의 원시 형태. */
export interface RawEnemySpawn {
  readonly kind: string
  readonly pos: readonly number[]
}

export interface RawRoomTemplate {
  readonly id: string
  readonly purpose: string
  readonly rows: readonly string[]
  readonly player_spawn: readonly number[]
  readonly enemy_spawns: readonly RawEnemySpawn[]
}

export interface RawRoomFile {
  readonly size: readonly number[]
  readonly legend: Readonly<Record<string, number>>
  readonly templates: readonly RawRoomTemplate[]
}

const POSITION_LENGTH = 2

/**
 * 좌표의 타일 ID 를 돌려준다.
 *
 * @param template 볼 템플릿.
 * @param x 가로 좌표.
 * @param y 세로 좌표.
 * @returns 타일 ID. 격자 밖이면 벽으로 취급해 TILE_WALL.
 */
export function getRoomTile(template: RoomTemplate, x: number, y: number): number {
  if (x < 0 || x >= template.width || y < 0 || y >= template.height) {
    return TILE_WALL
  }
  const row = template.tiles[y]
  const tile = row?.[x]
  return tile ?? TILE_WALL
}

/**
 * ASCII 행들을 타일 ID 격자로 바꾼다.
 *
 * @param rows 한 글자가 한 칸인 문자열 목록.
 * @param legend 글자에서 타일 ID 로의 대응표.
 * @returns [y][x] 순서의 타일 격자.
 * @throws legend 에 없는 글자가 있는 경우.
 */
export function convertRowsToTiles(
  rows: readonly string[],
  legend: Readonly<Record<string, number>>,
): number[][] {
  return rows.map((row) =>
    [...row].map((char) => {
      const tile = legend[char]
      if (tile === undefined) {
        throw new Error(`legend 에 없는 글자다: ${char}`)
      }
      return tile
    }),
  )
}

/**
 * 좌표 배열을 좌표로 바꾼다.
 *
 * @param raw `[x, y]` 두 값.
 * @param label 오류 메시지에 쓸 이름.
 * @returns 만들어진 좌표.
 * @throws 값이 두 개가 아닌 경우.
 */
function parseGridPosition(raw: readonly number[], label: string): GridPosition {
  const [x, y] = raw
  if (raw.length !== POSITION_LENGTH || x === undefined || y === undefined) {
    throw new Error(`${label}: 좌표는 [x, y] 두 값이어야 한다`)
  }
  return { x, y }
}

/**
 * 좌표를 집합에 넣을 키로 만든다. 객체를 그대로 넣으면 동등성 비교가 참조로 되기 때문이다.
 *
 * @param position 바꿀 좌표.
 * @returns `x,y` 형태의 문자열.
 */
function formatPositionKey(position: GridPosition): string {
  return `${position.x},${position.y}`
}

/**
 * 시작점에서 모든 문·계단과 적 스폰에 닿는지 확인한다 (TDD §7.2).
 *
 * @param template 검사할 템플릿.
 * @returns 문제 설명 목록. 이상이 없으면 빈 배열.
 */
export function checkRoomReachability(template: RoomTemplate): string[] {
  const problems: string[] = []
  const start = template.playerSpawn
  if (!WALKABLE_TILES.has(getRoomTile(template, start.x, start.y))) {
    return [
      `${template.templateId}: 플레이어 시작점 (${start.x}, ${start.y}) 이 통행 불가 타일이다`,
    ]
  }

  const reached = new Set<string>([formatPositionKey(start)])
  const frontier: GridPosition[] = [start]
  for (;;) {
    const current = frontier.pop()
    if (current === undefined) {
      break
    }
    for (const [dx, dy] of STEP_OFFSETS) {
      const step: GridPosition = { x: current.x + dx, y: current.y + dy }
      const key = formatPositionKey(step)
      if (reached.has(key) || !WALKABLE_TILES.has(getRoomTile(template, step.x, step.y))) {
        continue
      }
      reached.add(key)
      frontier.push(step)
    }
  }

  const exits: GridPosition[] = []
  for (let y = 0; y < template.height; y += 1) {
    for (let x = 0; x < template.width; x += 1) {
      const tile = getRoomTile(template, x, y)
      if (tile === TILE_DOOR || tile === TILE_STAIRS) {
        exits.push({ x, y })
      }
    }
  }
  if (exits.length === 0) {
    problems.push(`${template.templateId}: 문도 계단도 없다`)
  }
  for (const exit of exits) {
    if (!reached.has(formatPositionKey(exit))) {
      problems.push(`${template.templateId}: 출구 (${exit.x}, ${exit.y}) 에 시작점에서 닿을 수 없다`)
    }
  }
  for (const spawn of template.enemySpawns) {
    if (!reached.has(formatPositionKey(spawn.position))) {
      const at = `(${spawn.position.x}, ${spawn.position.y})`
      problems.push(`${template.templateId}: 적 스폰 ${at} 에 시작점에서 닿을 수 없다`)
    }
  }
  return problems
}

/**
 * 룸 템플릿 JSON 을 읽어 변환한다.
 *
 * @param raw templates.json 의 내용.
 * @returns 선언된 크기와 일치하는 템플릿들.
 * @throws 선언 크기가 [폭, 높이] 가 아니거나 템플릿 크기가 그와 다른 경우.
 */
export function loadRoomTemplates(raw: RawRoomFile): readonly RoomTemplate[] {
  const declared = parseGridPosition(raw.size, 'size')
  const width = declared.x
  const height = declared.y

  return raw.templates.map((item) => {
    const tiles = convertRowsToTiles(item.rows, raw.legend)
    if (tiles.length !== height || tiles.some((row) => row.length !== width)) {
      throw new Error(`${item.id}: 크기가 선언(${width}x${height})과 다르다`)
    }
    return {
      templateId: item.id,
      purpose: item.purpose,
      tiles,
      width,
      height,
      playerSpawn: parseGridPosition(item.player_spawn, `${item.id}.player_spawn`),
      enemySpawns: item.enemy_spawns.map((spawn) => ({
        kind: spawn.kind,
        position: parseGridPosition(spawn.pos, `${item.id}.enemy_spawns`),
      })),
    }
  })
}
