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
import { USE_TAG_LABELS } from '../content/consumableTags'
import type {
  ActionBlock,
  BlockCatalog,
  Comparison,
  PerceptionBlock,
  Rule,
  SelectorBlock,
  StatBlock,
} from '../core/schemas'
import { resolveWantedFaction } from '../core/rules/validator'
import { ENEMY_ONLY_SKILL_IDS, SKILL_NAMES } from '../core/resources'
import { readActivePack } from '../content/pack'

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
  // **별칭은 목록에서 숨긴다.** `USE_POTION` 은 `USE_ITEM[물약]` 과 같은 일이라 둘 다
  // 보이면 「소모품 사용이 둘인데 뭐가 다르지」가 된다 — 저장된 규칙표와 골든이 쓰므로
  // 코어에서는 안 지우고, 고르는 자리에서만 뺀다.
  const visible = [...catalog.actions.values()].filter((block) => block.blockId !== 'USE_POTION')
  return buildGroups(visible, (block) => block.category, ACTION_CATEGORY_LABELS)
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
 * 그 행동이 고를 수 있는 셀렉터만 낸다 (블록 목록 v4).
 *
 * 행동은 요구하는 진영을 선언하고 셀렉터는 고르는 진영을 선언한다. 어긋난 조합은 검증기가
 * 거부하므로, 목록에 그대로 두면 고를 수는 있는데 늘 빨간 줄이 뜨는 칸이 생긴다.
 *
 * @param catalog 블록 카탈로그.
 * @param action 고른 행동. 아직 없거나 대상을 받지 않으면 전체를 낸다.
 * @returns 카탈로그 순서를 유지한 셀렉터 목록.
 */
export function listSelectorsForAction(
  catalog: BlockCatalog,
  action: ActionBlock | undefined,
  actionParam: string | null = null,
): readonly SelectorBlock[] {
  // **진영은 스킬이 정한다.** USE_SKILL 을 행동의 진영(enemy)으로 거르면 치유를
  // 자신·아군에게 거는 규칙을 지을 방법이 없다 — 검증기와 같은 셈이다.
  const wanted =
    action === undefined
      ? undefined
      : resolveWantedFaction({ action: action.blockId, actionParam }, {
          targetFaction: action.targetFaction,
        })
  if (wanted === undefined || wanted === null) {
    return listSelectors(catalog)
  }
  return listSelectors(catalog).filter((item) => item.faction === wanted)
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

/**
 * 규칙의 행동절을 사람이 읽는 한 줄로 적는다 — `사격 → 가장 가까운 적`.
 *
 * 도는 판에서는 `battle/ruleTrace.formatActionText` 가 같은 문자열을 만든다. 두 벌인
 * 이유는 계층이다 — 에디터가 전투 화면을 import 하면 화면 둘이 서로를 알게 되고, 규칙표를
 * 고치는 화면이 엔진·도면·캔버스를 함께 끌고 온다. 대신 **문자열 모양은 같아야 한다**:
 * 규칙표를 편집할 때와 관전할 때 같은 규칙이 다른 말로 적히면 둘이 같은 줄인지 알 수 없다.
 *
 * @param rule 규칙 한 줄.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @returns 행동절 한 줄.
 */
export function formatActionLabel(rule: Rule, catalog: BlockCatalog): string {
  const action = catalog.actions.get(rule.action)?.labelKo ?? rule.action
  if (rule.target === null) {
    return action
  }
  const selector = catalog.selectors.get(rule.target)?.labelKo ?? rule.target
  return `${action} → ${selector}`
}


/**
 * 행동 인자 값의 한글 이름.
 *
 * **id 를 그대로 적으면 `SCROLL` 이 화면에 뜬다.** 블록 목록은 전부 한글로 적히는데
 * 인자만 영문 id 로 남으면 그 한 칸만 다른 언어가 된다.
 *
 * 여기 없는 값은 id 를 그대로 쓴다 — 데이터가 앞서 나갔을 때 빈칸이 되는 것보다 낫다.
 *
 * **이름이 정본에 있으면 여기 안 적는다.** 재주는 `skills.json`, 고르개는 `blocks.json`,
 * 소모품 태그는 `content/consumableTags` 가 정본이고, 사본을 두면 같은 id 가 화면마다
 * 다른 이름으로 불린다. 여기 남는 것은 **정본이 없는 값들**뿐이다 — 상태이상·적 유형·
 * 지형, 그리고 정본에 `label_ko` 가 없는 재주 셋.
 */
const PARAM_LABELS: ReadonlyMap<string, string> = new Map([
  // 소모품 태그는 `content/consumableTags` 가 정본이다. 사본을 두면 새 주문서가 규칙
  // 편집기에서만 영문 id 로 뜬다 — 화면마다 다른 이름으로 불리는 것이 더 나쁘다.
  ...USE_TAG_LABELS,
  // 재주 이름의 정본은 `skills.json` 이다 — 소모품 태그와 같은 규율이다. 손으로 적으면
  // **이 화면만 옛 이름으로 말한다**: `GUARD_BRACE` 가 여기서는 「방어 태세」였는데
  // 전투 화면의 쿨타임 줄(`battle/vitalRows`)은 정본을 읽어 「방벽」이라고 적었고,
  // `HEAL` 은 화면 셋에서 세 이름이었다 (2026-09-18).
  //
  // **적만 쓰는 다섯도 여기 딸려 온다** (2026-09-17). 팔레트에서는 빠지지만
  // (`listParamOptions`) 이름은 있어야 한다 — 이문록이 적의 규칙표를 그대로 펴서 보여
  // 주고, 거기 영문 id 가 뜨면 카운터를 읽으라고 내놓은 표가 그 줄에서 끊긴다.
  ...SKILL_NAMES,
  // **정본에 이름이 없는 셋.** `ATTACK`·`AREA_ATTACK` 은 `skills.json` 에 `label_ko` 가
  // 없고 `SUMMON` 은 행 자체가 없다 — 그때 `SKILL_NAMES` 는 id 를 그대로 들고 있으므로
  // 여기서 덮지 않으면 그 칸만 영문이 된다. `battle/vitalRows` 의 `COOLDOWN_EXTRA` 와
  // 같은 자리이며, 정본에 `label_ko` 가 생기면 이 셋을 지운다.
  ['ATTACK', '공격'],
  ['AREA_ATTACK', '광역 공격'],
  ['SUMMON', '소환'],
  // `self_has_status` 가 묻는 상태들. GUARD·FOCUS 는 **스스로 거는 것**이라 규칙표가
  // 겹쳐 쓰기를 피하는 데 쓴다 — 이름이 없으면 「내 상태이상[GUARD]」로 적힌다.
  ['POISON', '중독'],
  ['SLOW', '둔화'],
  ['STUN', '기절'],
  // **둔화와 다른 축이다** — 둔화는 느려지는 것이고 이것은 발이 묶이는 것이다.
  // 때리는 것은 그대로 되므로 「묶였으면 물러서지 말고 때린다」가 규칙표로 지어진다.
  ['ROOT', '이동불가'],
  ['GUARD', '방어 태세'],
  // **고르개 이름은 여기 안 적는다.** 정본은 `blocks.json` 의 `selectors[].label_ko`
  // 이고 `readSelectorLabel` 이 읽는다 — 사본을 두었더니 규칙 한 줄을 편집하는 동안
  // 조건 칸에는 「사격형」, 행동 칸에는 「원거리 유형」이 동시에 떠 있었다 (2026-09-18).
  // `CASTING`·`ALLY_WOUNDED`·`BOSS` 도 고르개 값이라 함께 나갔다.
  //
  // 적 유형. `enemy_type_present` 가 묻는 값들이며 고르개 id 와는 다른 축이다 —
  // `RANGED` 는 유형이고 `TYPE_RANGED` 는 그 유형을 고르는 고르개다.
  ['MELEE', '근접형'],
  ['RANGED', '사격형'],
  ['SUMMONER', '소환형'],
  ['BOMBER', '자폭형'],
  ['HEALER', '치유형'],
  ['CASTER', '주술형'],
  // 지형. `nearest_tile_distance` 가 묻는다.
  ['DOOR', '문'],
  ['STAIRS', '계단'],
  ['SPRING', '샘'],
])

/**
 * 고르개 id 의 한글 이름. **정본은 `blocks.json` 하나다.**
 *
 * 같은 id 를 두 표로 그리면 한 화면에 두 이름이 뜬다 — 조건 칸의 인자 고르개는 이
 * 파일의 표로, 행동 칸의 대상 고르개와 규칙 줄의 행동절(`formatActionLabel`)은
 * 카탈로그로 그려서 「사격형」과 「원거리 유형」이 같은 줄에 나란히 서 있었다.
 *
 * **번들이 아니라 도는 팩을 읽는다.** 서버가 콘텐츠 팩을 보내면 카탈로그가 갈아 끼워
 * 지므로(`content/pack`), 빌드에 박힌 것을 읽으면 이 칸만 옛 이름으로 남는다.
 *
 * @param value 인자 값 id.
 * @returns 고르개면 그 이름, 아니면 undefined.
 */
function readSelectorLabel(value: string): string | undefined {
  return readActivePack().catalog.selectors.get(value)?.labelKo
}

/** 대괄호 안의 인자 하나. `대상 거리[NEAREST]` 의 `NEAREST` 를 집는다. */
const BRACKETED = /\[([A-Z][A-Z0-9_]*)\]/g

/**
 * 행동 인자 값을 사람이 읽는 말로 바꾼다.
 *
 * @param value 인자 값 id.
 * @returns 한글 이름. 모르는 값이면 id 그대로.
 */
export function formatParamLabel(value: string): string {
  return readSelectorLabel(value) ?? PARAM_LABELS.get(value) ?? value
}

/**
 * 이미 만들어진 문구 안의 인자들을 한글로 바꾼다.
 *
 * **코어를 안 고치는 이유가 있다.** 항 문구는 `core/rules/ruleVm` 의 `renderTerm` 이
 * 만들고, 그 문자열은 파이썬 코어가 내는 것과 **비트 단위로 같아야 한다**(게이트 G3).
 * 거기서 한글로 바꾸면 두 코어가 갈리고 골든 리플레이가 전부 무효가 된다 — 그래서
 * 표시 계층에서 덧칠한다. `battle/logNames` 의 `translateActions` 와 같은 규율이다.
 *
 * @param text 인자가 대괄호로 든 문구.
 * @returns 인자만 한글로 바뀐 문구. 모르는 값은 그대로 둔다.
 */
export function formatParamText(text: string): string {
  return text.replace(BRACKETED, (whole, value: string) => {
    const label = readSelectorLabel(value) ?? PARAM_LABELS.get(value)
    return label === undefined ? whole : `[${label}]`
  })
}

/**
 * 그 행동의 인자 고르개에 세울 것들.
 *
 * **적만 쓰는 재주를 뺀다** (2026-09-17). 카탈로그에는 들어 있어야 한다 — 적 규칙표가
 * 「쿨타임 완료[불 굿]」을 물어야 하고, 인지 목록과 카탈로그가 갈리면 그 값이 키째로
 * 안 만들어진다. 그러니 거르는 자리는 목록이 아니라 **화면**이다.
 *
 * 안 거르면 플레이어에게 열릴 길이 없는 칸이 다섯 개 생긴다 — 골라 놓고 「불가」만 뜨는
 * 줄이고, 「이건 언제 쓰나」에 답이 없다.
 *
 * @param action 고른 행동. 인자가 없으면 빈 목록이다.
 * @returns 값과 한글 이름 쌍들. 카탈로그 순서를 지킨다.
 */
export function listParamOptions(
  action: ActionBlock | undefined,
): readonly { readonly value: string; readonly label: string }[] {
  return (action?.param?.values ?? [])
    .filter((value) => !ENEMY_ONLY_SKILL_IDS.has(value))
    .map((value) => ({ value, label: formatParamLabel(value) }))
}
