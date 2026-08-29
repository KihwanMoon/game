/**
 * 블록 팔레트가 보여 줄 목록을 카탈로그에서 만든다.
 *
 * 목록의 정본은 `game/resources/balance/blocks.json` 하나이며, 여기서 하는 일은 그것을
 * 카테고리로 묶고 사람이 읽는 이름을 붙이는 것뿐이다. 블록을 여기 하드코딩하면 JSON 을
 * 늘렸을 때 팔레트에만 안 보이는 블록이 생긴다 — 규칙표는 그 블록을 참조할 수 있는데
 * 에디터로는 만들 수 없는 상태가 되고, 그것이 가장 찾기 어려운 종류의 어긋남이다.
 *
 * 목록은 전부 `ReadonlyMap` 순회 순서, 곧 JSON 에 적힌 순서를 유지한다. 팔레트의 순서가
 * 실행마다 달라지면 손이 위치를 외울 수 없어 편집 속도가 그대로 무너진다.
 */
import type {
  ActionBlock,
  BlockCatalog,
  Comparison,
  PerceptionBlock,
  SelectorBlock,
  StatBlock,
} from '../core/schemas'

/** 카테고리 하나로 묶인 블록들. 팔레트가 이 단위로 접히고 펼쳐진다. */
export interface BlockGroup<BlockT> {
  readonly category: string
  readonly labelKo: string
  readonly blocks: readonly BlockT[]
}

/** 인지 변수 카테고리 이름 (GDD §3.2 의 4개 분류). */
const PERCEPTION_CATEGORY_LABELS: ReadonlyMap<string, string> = new Map([
  ['self', '자기 상태'],
  ['enemy', '적 정보'],
  ['terrain', '지형/공간'],
  ['resource', '시간/자원'],
])

/** 행동 카테고리 이름 (GDD §3.4). */
const ACTION_CATEGORY_LABELS: ReadonlyMap<string, string> = new Map([
  ['attack', '공격'],
  ['move', '이동'],
  ['control', '제어'],
])

/** 불리언 인지 변수에 뜻이 있는 비교 연산자. `내 상태이상 < 3` 같은 항을 만들지 못하게 한다. */
export const BOOL_COMPARISONS: readonly Comparison[] = ['==', '!=']

/** 플래그 값을 읽는 인지 변수. SET 절의 플래그 목록도 이 블록의 인자에서 나온다. */
const FLAG_BLOCK_ID = 'flag_state'

/**
 * 카테고리별로 블록을 묶는다.
 *
 * @param blocks 카탈로그 순서를 유지한 블록 목록.
 * @param getCategory 블록에서 카테고리를 꺼내는 함수.
 * @param labels 카테고리 이름표. 없는 카테고리는 id 를 그대로 쓴다.
 * @returns 처음 등장한 카테고리 순서대로 묶인 그룹 목록.
 */
function buildGroups<BlockT>(
  blocks: readonly BlockT[],
  getCategory: (block: BlockT) => string,
  labels: ReadonlyMap<string, string>,
): readonly BlockGroup<BlockT>[] {
  const collected = new Map<string, BlockT[]>()
  for (const block of blocks) {
    const category = getCategory(block)
    const bucket = collected.get(category)
    if (bucket === undefined) {
      collected.set(category, [block])
    } else {
      bucket.push(block)
    }
  }
  return [...collected].map(([category, items]) => ({
    category,
    labelKo: labels.get(category) ?? category,
    blocks: items,
  }))
}

/**
 * 인지 변수를 카테고리별로 묶어 낸다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 카테고리 그룹 목록.
 */
export function listPerceptionGroups(catalog: BlockCatalog): readonly BlockGroup<PerceptionBlock>[] {
  return buildGroups(
    [...catalog.perceptions.values()],
    (block) => block.category,
    PERCEPTION_CATEGORY_LABELS,
  )
}

/**
 * 행동을 카테고리별로 묶어 낸다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 카테고리 그룹 목록.
 */
export function listActionGroups(catalog: BlockCatalog): readonly BlockGroup<ActionBlock>[] {
  return buildGroups([...catalog.actions.values()], (block) => block.category, ACTION_CATEGORY_LABELS)
}

/**
 * 셀렉터 목록을 낸다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 카탈로그 순서를 유지한 셀렉터 목록.
 */
export function listSelectors(catalog: BlockCatalog): readonly SelectorBlock[] {
  return [...catalog.selectors.values()]
}

/**
 * 조건 우변에 둘 수 있는 자기 스탯 목록을 낸다 (F-2).
 *
 * @param catalog 블록 카탈로그.
 * @returns 카탈로그 순서를 유지한 스탯 목록.
 */
export function listRhsStats(catalog: BlockCatalog): readonly StatBlock[] {
  return [...catalog.rhsStats.values()]
}

/**
 * SET 절에 쓸 플래그 이름 목록을 낸다.
 *
 * 목록을 여기 적지 않고 `flag_state` 블록의 인자에서 꺼낸다. 서브루틴 모듈이 플래그를
 * 늘리면(GDD §6.2) 읽는 쪽과 쓰는 쪽이 같은 목록을 보게 하려는 것이다.
 *
 * @param catalog 블록 카탈로그.
 * @returns 플래그 이름 목록. 블록이 없으면 빈 목록.
 */
export function listFlagNames(catalog: BlockCatalog): readonly string[] {
  return catalog.perceptions.get(FLAG_BLOCK_ID)?.param?.values ?? []
}

/**
 * 인지 변수가 쓸 수 있는 비교 연산자를 고른다.
 *
 * @param block 좌변 인지 변수. 아직 고르지 않았으면 undefined.
 * @param all 전체 비교 연산자 목록.
 * @returns bool 블록이면 등호 둘, 그 밖에는 전부.
 */
export function listComparisons(
  block: PerceptionBlock | undefined,
  all: readonly Comparison[],
): readonly Comparison[] {
  return block !== undefined && block.returns === 'bool' ? BOOL_COMPARISONS : all
}
