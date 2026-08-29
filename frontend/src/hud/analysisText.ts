/**
 * 사후 분석의 **표현** — 집계가 낸 수를 사람이 읽는 문구로 바꾼다.
 *
 * `analysis.ts` 와 나눠 둔 이유는 파이썬과 같다. 집계는 대조 대상이고(`__golden__`),
 * 문구는 화면마다 달라져도 되는 것이다. 한 파일에 섞으면 문구를 다듬을 때마다 게이트가
 * 깨지고, 그러면 아무도 문구를 다듬지 않게 된다.
 *
 * 진단 문구의 분기와 순서는 파이썬 `format_rule_stats` 와 같다. 터미널과 웹이 같은 판을
 * 다르게 진단하면 둘 중 어느 쪽을 믿어야 할지 알 수 없다.
 */

import { formatOutcome, formatOutcomeNotice } from '../battle'
import { divideFloor } from '../core/combat/damage'

import { SUSPICIOUS_WASTE_PCT, getWastePercent } from './analysis'
import type { RuleStat } from './analysis'

/**
 * 판정 문구는 **전투 화면과 같은 표**를 쓴다. 사후 분석이 전투 화면을 덮으며 뜨므로
 * 라벨표가 두 벌이면 한 화면에 `패배` 와 `사망` 이 함께 보인다 — 실제로 그랬다.
 * 정본은 `battle/outcomeText.ts` 이고 여기서는 다시 내보내기만 한다.
 */
export { formatOutcome, formatOutcomeNotice }

/** 틱 번호를 0 으로 채울 자릿수. 코어 `formatLines` 의 `{tick:03d}` 와 같다. */
const TICK_PAD_WIDTH = 3

/** 피해가 없는 칸의 표기. 색을 못 봐도 빈 칸이 읽힌다. */
export const HEAT_EMPTY_GLYPH = '·'

/** 히트맵 강도 단계 수. 0(피해 없음)을 빼고 넷이다. */
export const HEAT_LEVELS = 4

/**
 * 틱 번호 표기.
 *
 * @param tick 틱 번호.
 * @returns `T027` 형태. 자릿수를 채워 컬럼이 어긋나지 않게 한다.
 */
export function formatTickLabel(tick: number): string {
  return `T${String(tick).padStart(TICK_PAD_WIDTH, '0')}`
}

/**
 * 규칙 하나의 진단 문구 (파이썬 `format_rule_stats` 의 note 열).
 *
 * @param stat 볼 성적.
 * @returns 진단 한 줄. 짚을 것이 없으면 빈 문자열.
 */
export function describeRuleStat(stat: RuleStat): string {
  const wastePct = getWastePercent(stat)
  if (stat.fired > 0 && stat.acted === 0 && stat.wasted === 0) {
    return '발동했지만 실행 단계에 도달하지 않음'
  }
  if (wastePct >= SUSPICIOUS_WASTE_PCT) {
    return `시도의 ${String(wastePct)}% 가 헛돎 — 조건을 의심할 것`
  }
  if (stat.fired === 0) {
    return '한 번도 발동하지 않음 — 조건이 너무 좁다'
  }
  return ''
}

/**
 * 히트맵 한 칸의 강도 단계.
 *
 * 색은 정보의 유일한 채널이 될 수 없으므로 칸에는 숫자가 함께 적힌다. 단계는 배경 명도를
 * 나누는 용도뿐이다.
 *
 * @param value 그 칸의 피해 합계.
 * @param peak 격자의 최댓값.
 * @returns 0 이상 HEAT_LEVELS 이하의 정수. 피해가 있으면 최소 1 이다.
 */
export function getHeatLevel(value: number, peak: number): number {
  if (value <= 0 || peak <= 0) {
    return 0
  }
  // 정수 나눗셈으로 올림한다. 화면 값이라도 부동소수를 들이지 않는 편이 낫다 (R5).
  const level = divideFloor(value * HEAT_LEVELS + peak - 1, peak)
  return Math.min(HEAT_LEVELS, Math.max(1, level))
}

/**
 * 히트맵 한 칸의 표기.
 *
 * @param value 그 칸의 피해 합계.
 * @returns 피해가 있으면 수치, 없으면 점 하나.
 */
export function formatHeatValue(value: number): string {
  return value <= 0 ? HEAT_EMPTY_GLYPH : String(value)
}
