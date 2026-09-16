/**
 * 콘텐츠 카탈로그 격자의 셀 모델 (관리자, 읽기 전용).
 *
 * **가방과 같은 형식이다.** 카탈로그가 답하는 것은 「무엇이 들어 있는가」이고, 그 답은
 * 가방 격자와 같은 모양이어야 한다 — 같은 아이템이 관리 화면에서만 다른 모양으로
 * 그려지면, 「봇에게 뭐가 있지」를 답하려던 화면이 답을 틀리게 한다 (`InventoryGrid` 머리말).
 *
 * **등급은 여기 없다.** 카탈로그 줄은 종류이고 등급은 개체에 붙는다 — 없는 것을 칸에
 * 칠하지 않는다.
 *
 * 순수 값이다. 렌더 검사가 훅 없이 셀 배치를 볼 수 있어야 한다.
 */
import { findItemArt } from '../content/itemArt'
import type { CatalogEnemyRow, CatalogItemRow } from '../storage'

import type { CellFace } from './gridCell'
import { clipCellLabel, EQUIP_CELL_CODES } from './inventoryCells'

/** 슬롯이 없는 아이템의 두 글자 코드. 소모품이 여기 온다. */
export const KIND_CELL_CODES: ReadonlyMap<string, string> = new Map([
  ['EQUIPMENT', 'EQ'],
  ['CONSUMABLE', 'CS'],
])

/**
 * 적 유형의 두 글자 코드.
 *
 * 다섯이 정본이다(`core/sim/perception` 의 `ENEMY_TYPES`). 모르는 유형은 `EN` 으로
 * 떨어진다 — 새 유형이 생겼을 때 칸이 비는 것보다 낫다.
 */
export const ENEMY_CELL_CODES: ReadonlyMap<string, string> = new Map([
  ['MELEE', 'ME'],
  ['RANGED', 'RA'],
  ['SUMMONER', 'SU'],
  ['BOMBER', 'BO'],
  ['HEALER', 'HE'],
])

/** 카탈로그 격자 칸 하나 — 아이템. */
export interface CatalogItemCell extends CellFace {
  readonly row: CatalogItemRow
}

/** 카탈로그 격자 칸 하나 — 적. */
export interface CatalogEnemyCell extends CellFace {
  readonly row: CatalogEnemyRow
}

/**
 * 근접 사거리. 1 은 거의 모든 무기가 같으므로 칸에 안 적는다 — 모든 칸에 같은 글자가
 * 붙으면 그 자리가 아무 말도 안 하게 된다. 0 은 「무기가 안 정한다」다.
 */
const MELEE_RANGE = 1

/**
 * 칸에 적을 사거리.
 *
 * @param attackRange 사거리.
 * @returns `사4` 꼴. 적을 것이 없으면 빈 문자열.
 */
export function formatRangeText(attackRange: number): string {
  return attackRange > MELEE_RANGE ? `사${String(attackRange)}` : ''
}

/**
 * 아이템 칸의 「무엇을 해 주는가」 한 줄.
 *
 * **여는 재주가 먼저다.** 장비가 스킬을 여는 것은 스탯 몇 점과 다른 급의 사실이고
 * (결정 #13), 장비 교체가 규칙 재설계로 이어지는 지점이 거기다.
 *
 * @param row 카탈로그 줄.
 * @returns 한 줄. 적을 것이 없으면 빈 문자열.
 */
export function pickItemFact(row: CatalogItemRow): string {
  if (row.grantsSkill !== '') {
    return `재주 ${row.grantsSkill}`
  }
  return row.affixes[0] ?? ''
}

/**
 * 아이템 줄들을 격자 칸으로 만든다.
 *
 * @param rows 카탈로그 아이템 줄들.
 * @returns 서버가 준 순서 그대로의 칸들.
 */
export function buildCatalogItemCells(
  rows: readonly CatalogItemRow[],
): readonly CatalogItemCell[] {
  return rows.map((row) => ({
    key: `cat:item:${row.catalogId}`,
    code: EQUIP_CELL_CODES.get(row.slot) ?? KIND_CELL_CODES.get(row.kind) ?? 'IT',
    label: clipCellLabel(row.labelKo),
    // **손 수까지 넘긴다** — 같은 `sword_` 넷 중 양손 하나는 협도이고, 안 넘기면
    // 카탈로그가 그것을 직검으로 그린다. 「무엇이 들어 있는가」를 보는 화면이라
    // 여기서 그림이 거짓말하면 안 된다.
    //
    // **`use_tag` 는 이 응답에 없다.** `catalog_view.build_item_rows` 가 싣지 않아서
    // 축지·눈밝이·불의 부적 셋이 보통 부적으로 뜬다 — 서버 필드라 다음 단계다.
    art: findItemArt(row.catalogId, row.hands),
    grade: '',
    marks: [],
    countText: formatRangeText(row.attackRange),
    fact: pickItemFact(row),
    isSealedSlot: false,
    row,
  }))
}

/**
 * 적 줄들을 격자 칸으로 만든다.
 *
 * **그림이 없다.** 그려 둔 것은 아이템 형태뿐이라 적 칸은 유형 코드로 떨어진다.
 *
 * @param rows 카탈로그 적 줄들.
 * @returns 서버가 준 순서 그대로의 칸들.
 */
export function buildCatalogEnemyCells(
  rows: readonly CatalogEnemyRow[],
): readonly CatalogEnemyCell[] {
  return rows.map((row) => {
    const range = formatRangeText(row.attackRange)
    return {
      key: `cat:enemy:${row.kindId}`,
      code: ENEMY_CELL_CODES.get(row.type) ?? 'EN',
      label: clipCellLabel(row.labelKo),
      grade: '',
      marks: [],
      countText: `hp${String(row.hpMax)}`,
      // 얼마나 아픈가와 어디까지 닿는가. 정체(규칙표)는 상세가 낸다 — 내력 id 는 칸에
      // 안 들어가고, 잘린 채 두면 아무 말도 안 하느니만 못하다.
      fact: `공${String(row.attack)}${range === '' ? '' : ` ${range}`}`,
      isSealedSlot: false,
      row,
    }
  })
}
