/**
 * 스킬 세팅의 격자 칸 — 순수 값 (도면 그리드).
 *
 * **가방·소모품·경매와 같은 겉면을 쓴다.** 스킬 화면은 오래 칸을 손으로 그리고 있었고,
 * 그래서 다른 셋에는 있는 것이 여기만 없었다 — 고른 칸의 `aria-pressed`, 등급 색, 자리
 * 코드. 같은 격자로 보이는데 뒤에서는 다른 마크업이면, 셋을 고칠 때 이 하나가 남는다.
 *
 * 렌더는 `GridCellView` 가, 배치는 `SlotGrid` 가 한다. 여기 있는 것은 값뿐이다.
 */
import type { SkillPrefView } from '../storage'

import type { CellFace } from './gridCell'

/** 끈 스킬에 붙는 표시. 이름은 남는다 — 무엇을 다시 켤지 골라야 한다. */
const OFF_MARK = '끔'

/** 못 끄는 스킬에 붙는 표시. 폴백이 이것에 기대므로 빼면 판이 멈춘다. */
const LOCKED_CODE = '기본'

/**
 * 스킬 한 줄을 격자 칸으로 접는다.
 *
 * @param row 스킬 세팅 한 줄.
 * @param label 사람이 읽는 이름.
 * @returns 격자 칸 하나.
 */
function buildSkillCell(
  row: { readonly skillId: string; readonly isOn: boolean; readonly isLocked: boolean },
  label: string,
): CellFace {
  return {
    // **key 가 곧 스킬 id 다.** 고름은 `usePickedKey` 가 key 로 들므로, 접두사를 붙이면
    // 고른 칸에서 스킬을 되찾는 데 문자열을 다시 잘라야 한다.
    key: row.skillId,
    code: row.isLocked ? LOCKED_CODE : '',
    label,
    grade: '',
    marks: row.isOn ? [] : [OFF_MARK],
    countText: '',
    fact: '',
    // **막힌 것이 아니라 끈 것이다.** 막힌 자리는 이름 대신 `▨` 가 서는데, 스킬은
    // 이름이 남아야 다시 켤 것을 고를 수 있다.
    isSealedSlot: false,
    isOff: !row.isOn,
  }
}

/**
 * 스킬 세팅을 격자 칸들로 접는다.
 *
 * @param view 스킬 세팅. 없으면 빈 배열이다.
 * @param formatLabel 스킬 id 를 사람이 읽는 이름으로 바꾸는 함수.
 * @returns 격자 칸들. 줄 순서를 그대로 지킨다 — 순서가 바뀌면 눈이 자리를 다시 잡는다.
 */
export function buildSkillCells(
  view: SkillPrefView | undefined,
  formatLabel: (skillId: string) => string,
): readonly CellFace[] {
  if (view === undefined) {
    return []
  }
  return view.rows.map((row) => buildSkillCell(row, formatLabel(row.skillId)))
}
