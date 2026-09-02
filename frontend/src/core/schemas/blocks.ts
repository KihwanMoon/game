/**
 * 블록 카탈로그 — 인지 변수·행동·셀렉터 목록 (GDD §3.2·§3.3·§3.4).
 * `game/schemas/blocks.py` 의 TypeScript 이식이다.
 *
 * 개수는 인지 18 / 행동 14 / 셀렉터 9 이며 로드 시점에 그것을 검사한다. 숫자가 어긋난 채로
 * 조용히 로드되면 규칙표가 참조하는 블록이 사라져도 알 수 없다.
 *
 * v4 가 치유형을 열었다 (docs/04 H-1~H-3). 대상을 받는 행동은 요구하는 진영을
 * (`targetFaction`) 선언하고 셀렉터는 고르는 진영을(`faction`) 선언한다 — 검증기가
 * `HEAL @NEAREST` 처럼 어긋난 조합을 거부한다.
 *
 * `rhsStats` 는 조건 우변에 둘 수 있는 자기 스탯의 닫힌 목록이다 (F-2). 열어 두면 오타 난
 * 스탯 이름이 조용히 거짓이 되어 규칙이 영영 발동하지 않는다.
 *
 * 목록을 `Record` 가 아니라 `Map` 으로 담는 이유는 순회 순서다. 객체 키 순회는 숫자처럼
 * 보이는 키를 앞으로 끌어올리는 등 삽입 순서를 보장하지 않는다 — 게임 상태를 그 순서로
 * 만들면 결정론이 깨진다(R5). `Map` 은 삽입 순서, 즉 JSON 에 적힌 순서를 유지한다.
 */

/** 동결된 개수. 로드 때마다 실제 개수와 대조한다. */
// v7 에서 self_scroll_count 가 들어왔다 (§5 소모품 칸).
export const PERCEPTION_COUNT = 21
export const ACTION_COUNT = 16 // v6 에서 USE_ITEM 이 들어왔다 (#54)
export const SELECTOR_COUNT = 9
// v7 에서 scrolls 가 들어왔다 — potions 와 짝.
export const RHS_STAT_COUNT = 7

/** 셀렉터가 고르는 진영. 행동의 targetFaction 도 이 둘 중 하나다. */
export const FACTION_ENEMY = 'enemy'
export const FACTION_ALLY = 'ally'

/** 블록이 내는 값의 종류. */
export type BlockReturns = 'int' | 'bool'

/** 블록이 받는 인자. 예: 쿨타임[스킬], 플래그[A~D]. */
export interface BlockParam {
  readonly name: string
  readonly values: readonly string[]
}

/** 인지 변수 하나. 규칙 조건의 좌변이 될 수 있는 것. */
export interface PerceptionBlock {
  readonly blockId: string
  readonly category: string
  readonly returns: BlockReturns
  readonly labelKo: string
  readonly param: BlockParam | null
  readonly valueRange: readonly [number, number] | null
}

/** 행동 하나. 규칙이 실행하는 것. */
export interface ActionBlock {
  readonly blockId: string
  readonly category: string
  readonly targeted: boolean
  readonly labelKo: string
  /** 이 행동이 요구하는 대상 진영. 대상을 받지 않는 행동은 null 이다. */
  readonly targetFaction: string | null
  /**
   * 이 행동이 받는 인자 (v5). `USE_SKILL[skill]` 이 이것을 쓴다.
   *
   * 스킬마다 액션을 더하면 `block_list_version` 이 계속 올라 랭킹 시즌이 갈린다
   * (docs/설계/5_스킬 §4).
   */
  readonly param: BlockParam | null
}

/** 타겟 셀렉터 하나. targeted 행동이 대상을 고르는 방식. */
export interface SelectorBlock {
  readonly blockId: string
  readonly labelKo: string
  /** 이 셀렉터가 고르는 진영. v3 까지는 전부 적대였다. */
  readonly faction: string
}

/** 조건 우변에 둘 수 있는 자기 스탯 하나 (F-2). */
export interface StatBlock {
  readonly blockId: string
  readonly labelKo: string
}

/** 블록 목록 전체. */
export interface BlockCatalog {
  readonly version: number
  readonly perceptions: ReadonlyMap<string, PerceptionBlock>
  readonly actions: ReadonlyMap<string, ActionBlock>
  readonly selectors: ReadonlyMap<string, SelectorBlock>
  readonly rhsStats: ReadonlyMap<string, StatBlock>
}

/** blocks.json 의 원시 형태. */
export interface RawBlockParam {
  readonly name: string
  readonly values: readonly string[]
}

export interface RawPerception {
  readonly id: string
  readonly category: string
  readonly returns: string
  readonly label_ko: string
  readonly param?: RawBlockParam
  readonly range?: readonly number[]
}

export interface RawAction {
  readonly id: string
  readonly category: string
  readonly targeted: boolean
  readonly label_ko: string
  readonly target_faction?: string
  readonly param?: RawBlockParam
}

export interface RawNamedBlock {
  readonly id: string
  readonly label_ko: string
}

/** blocks.json 의 selectors 절 한 항목. faction 은 v4 에서 붙었다. */
export interface RawSelector extends RawNamedBlock {
  readonly faction?: string
}

export interface RawBlockCatalog {
  readonly block_list_version: number
  readonly perceptions: readonly RawPerception[]
  readonly actions: readonly RawAction[]
  readonly selectors: readonly RawSelector[]
  readonly rhs_stats: readonly RawNamedBlock[]
}

const RANGE_LENGTH = 2

/**
 * 원시 절에서 블록 인자를 만든다.
 *
 * @param raw JSON 의 param 절. 인자가 없는 블록이면 undefined.
 * @returns 만들어진 인자, 또는 null.
 */
function buildBlockParam(raw: RawBlockParam | undefined): BlockParam | null {
  if (raw === undefined) {
    return null
  }
  return { name: raw.name, values: [...raw.values] }
}

/**
 * 원시 절에서 값 범위를 만든다.
 *
 * @param raw JSON 의 range 절.
 * @param blockId 오류 메시지에 쓸 블록 id.
 * @returns 하한·상한 쌍, 또는 null.
 * @throws 길이가 2 가 아닌 경우.
 */
function buildValueRange(
  raw: readonly number[] | undefined,
  blockId: string,
): readonly [number, number] | null {
  if (raw === undefined) {
    return null
  }
  const [low, high] = raw
  if (raw.length !== RANGE_LENGTH || low === undefined || high === undefined) {
    throw new Error(`${blockId}: range 는 [하한, 상한] 두 값이어야 한다`)
  }
  return [low, high]
}

/**
 * id 를 키로 하는 Map 을 만들고 중복 id 를 잡는다.
 *
 * @param items 원소 목록.
 * @param getKey 원소에서 키를 꺼내는 함수.
 * @param section 오류 메시지에 쓸 절 이름.
 * @returns 삽입 순서를 유지하는 Map.
 * @throws id 가 중복된 경우.
 */
function buildBlockMap<ValueT>(
  items: readonly ValueT[],
  getKey: (item: ValueT) => string,
  section: string,
): ReadonlyMap<string, ValueT> {
  const collected = new Map<string, ValueT>()
  for (const item of items) {
    const key = getKey(item)
    if (collected.has(key)) {
      throw new Error(`블록 id 가 중복됐다: ${section}.${key}`)
    }
    collected.set(key, item)
  }
  return collected
}

/**
 * 동결된 개수와 실제 개수를 대조한다.
 *
 * @param catalog 검사할 카탈로그.
 * @returns 불일치 메시지 목록. 전부 맞으면 빈 배열.
 */
export function checkCatalogCounts(catalog: BlockCatalog): string[] {
  const expected: readonly [string, number, number][] = [
    ['perceptions', catalog.perceptions.size, PERCEPTION_COUNT],
    ['actions', catalog.actions.size, ACTION_COUNT],
    ['selectors', catalog.selectors.size, SELECTOR_COUNT],
    ['rhsStats', catalog.rhsStats.size, RHS_STAT_COUNT],
  ]
  return expected
    .filter(([, got, want]) => got !== want)
    .map(([name, got, want]) => `${name} 개수가 동결값과 다르다: ${got} != ${want}`)
}

/**
 * 인지 변수가 내는 값의 종류를 읽는다.
 *
 * @param raw JSON 의 returns 값.
 * @param blockId 오류 메시지에 쓸 블록 id.
 * @returns int 또는 bool.
 * @throws 그 밖의 값인 경우.
 */
function parseBlockReturns(raw: string, blockId: string): BlockReturns {
  if (raw !== 'int' && raw !== 'bool') {
    throw new Error(`${blockId}: returns 는 int 나 bool 이어야 한다: ${raw}`)
  }
  return raw
}

/**
 * 블록 목록 JSON 을 읽어 카탈로그를 만든다.
 *
 * @param raw blocks.json 의 내용.
 * @returns 동결 개수 검사를 통과한 카탈로그.
 * @throws 개수가 동결값과 다르거나 id 가 중복된 경우.
 */
export function loadBlockCatalog(raw: RawBlockCatalog): BlockCatalog {
  const perceptions = buildBlockMap(
    raw.perceptions.map(
      (item): PerceptionBlock => ({
        blockId: item.id,
        category: item.category,
        returns: parseBlockReturns(item.returns, item.id),
        labelKo: item.label_ko,
        param: buildBlockParam(item.param),
        valueRange: buildValueRange(item.range, item.id),
      }),
    ),
    (item) => item.blockId,
    'perceptions',
  )
  const actions = buildBlockMap(
    raw.actions.map(
      (item): ActionBlock => ({
        blockId: item.id,
        category: item.category,
        targeted: item.targeted,
        labelKo: item.label_ko,
        targetFaction: item.target_faction ?? null,
        param: buildBlockParam(item.param),
      }),
    ),
    (item) => item.blockId,
    'actions',
  )
  const selectors = buildBlockMap(
    raw.selectors.map(
      (item): SelectorBlock => ({
        blockId: item.id,
        labelKo: item.label_ko,
        faction: item.faction ?? FACTION_ENEMY,
      }),
    ),
    (item) => item.blockId,
    'selectors',
  )
  const rhsStats = buildBlockMap(
    raw.rhs_stats.map((item): StatBlock => ({ blockId: item.id, labelKo: item.label_ko })),
    (item) => item.blockId,
    'rhs_stats',
  )

  const catalog: BlockCatalog = {
    version: raw.block_list_version,
    perceptions,
    actions,
    selectors,
    rhsStats,
  }
  const problems = checkCatalogCounts(catalog)
  if (problems.length > 0) {
    throw new Error(problems.join('; '))
  }
  return catalog
}
