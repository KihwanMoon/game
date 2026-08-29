/**
 * 조건 항의 **실측값** — 모바일 편집 화면의 「실측 줄」이 읽는 것 (명세 C 의 조건 카드).
 *
 * 편집 화면이 조건을 세 조각(좌변·비교·우변)으로만 보여 주면, 사람은 자기가 고른 항이
 * 실제로 무슨 값이었는지 모른 채 규칙을 고친다. 그것이 이 게임이 가장 피하려는 상태다 —
 * `적거리(2) <= 사거리(3)` 처럼 **양변의 실제 값을 병기**해야 죽고 나서 고칠 곳이
 * 특정된다 (GDD §8.2, P1).
 *
 * 값의 출처는 **직전 틱의 평가**다. 카드 헤더 오른쪽의 `평가값 = 이번 틱` 이 그 사실을
 * 적는다. 아직 한 틱도 돌지 않았으면 값이 없고, 그때는 `–` 를 둔다. **`없음` 을 쓰지
 * 않는다** — 그것은 "값을 만들 수 없었다" 는 뜻이고 여기는 "아직 보지 않았다" 는 뜻이라,
 * 두 사실을 같은 표기로 적으면 진단이 틀어진다 (`battle/ruleTrace.ts` 와 같은 구분).
 *
 * **판정과 표기를 여기서 다시 구현하지 않는다.** 값이 다 있는 항은 코어의 `renderTerm`
 * 이 만든 문자열을 그대로 쓰고, 참·거짓은 코어의 `COMPARATORS` 로 낸다. 두 벌을 두면
 * 편집 화면이 말하는 참과 엔진이 실행하는 참이 언젠가 갈리고, 그때 플레이어는 어느 쪽을
 * 믿어야 할지 알 수 없다.
 */
import { COMPARATORS, formatValue, renderTerm, type MeasuredValue } from '../core/rules/ruleVm'
import { OP_OR, isStatRef, type BlockCatalog, type Rule, type Term } from '../core/schemas'
import type { GlyphStateKind } from '../ds'

/** 아직 평가되지 않은 값 자리. `없음`(값을 만들 수 없었다)과 다른 뜻이다. */
export const UNMEASURED = '–'

/** 조건 카드 헤더 오른쪽에 적는 값의 출처. */
export const MEASURE_SOURCE = '평가값 = 이번 틱'

/** 자기 스탯 우변의 측정값을 담을 때 쓰는 키 접두어. 인지 변수 키와 섞이지 않게 한다. */
export const STAT_KEY_PREFIX = '$'

/**
 * 직전 틱의 측정값 대응표.
 *
 * 키는 인지 변수의 항 키(`buildTermKey`)이거나 자기 스탯 키(`buildStatKey`)다.
 * 아직 한 틱도 돌지 않은 화면은 빈 표를 넘긴다 — 그러면 모든 항이 `pending` 이다.
 */
export type TermReadings = ReadonlyMap<string, number | boolean>

/**
 * 항의 좌변을 가리키는 키를 만든다. 인자까지 포함해야 `쿨타임[SKILL_1]` 과
 * `쿨타임[SKILL_2]` 가 서로 다른 값을 가진다.
 *
 * @param term 조건 항.
 * @returns `blockId` 또는 `blockId[param]`.
 */
export function buildTermKey(term: Term): string {
  return term.lhsParam === null ? term.lhs : `${term.lhs}[${term.lhsParam}]`
}

/**
 * 자기 스탯 우변을 가리키는 키를 만든다.
 *
 * @param stat 스탯 id.
 * @returns `$stat` 형태의 키.
 */
export function buildStatKey(stat: string): string {
  return `${STAT_KEY_PREFIX}${stat}`
}

/**
 * 좌변의 측정값을 읽는다.
 *
 * @param term 조건 항.
 * @param readings 측정값 대응표.
 * @returns 측정값. 아직 평가되지 않았으면 undefined.
 */
export function readLhsMeasure(term: Term, readings: TermReadings): MeasuredValue {
  return readings.get(buildTermKey(term))
}

/**
 * 우변의 측정값을 읽는다. 리터럴 우변은 값이 곧 측정값이다.
 *
 * @param term 조건 항.
 * @param readings 측정값 대응표.
 * @returns 측정값. 스탯 우변인데 아직 읽지 못했으면 undefined.
 */
export function readRhsMeasure(term: Term, readings: TermReadings): MeasuredValue {
  return isStatRef(term.rhs) ? readings.get(buildStatKey(term.rhs.stat)) : term.rhs
}

/**
 * 측정값 하나를 적는다.
 *
 * @param value 측정값.
 * @returns 값 표기. 아직 평가되지 않았으면 `–`.
 */
function formatMeasure(value: MeasuredValue): string {
  return value === undefined ? UNMEASURED : formatValue(value)
}

/**
 * 조건 항을 실측값이 병기된 한 줄로 적는다.
 *
 * 값이 다 있으면 코어의 `renderTerm` 이 만든 문자열 **그대로** 다 — 로그·규칙표와 같은
 * 문장을 편집 화면에서도 읽게 하려는 것이다.
 *
 * @param term 조건 항.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @param readings 측정값 대응표.
 * @returns `적거리(2) <= 사거리(3)` 형태의 한 줄.
 */
export function formatMeasuredTerm(
  term: Term,
  catalog: BlockCatalog,
  readings: TermReadings,
): string {
  const lhsValue = readLhsMeasure(term, readings)
  const rhsValue = readRhsMeasure(term, readings)
  if (lhsValue !== undefined && rhsValue !== undefined) {
    return renderTerm(term, lhsValue, catalog, rhsValue)
  }
  const base = catalog.perceptions.get(term.lhs)?.labelKo ?? term.lhs
  const label = term.lhsParam === null ? base : `${base}[${term.lhsParam}]`
  const right = isStatRef(term.rhs)
    ? `${catalog.rhsStats.get(term.rhs.stat)?.labelKo ?? term.rhs.stat}(${formatMeasure(rhsValue)})`
    : formatValue(term.rhs)
  return `${label}(${formatMeasure(lhsValue)}) ${term.comparison} ${right}`
}

/**
 * 항의 판정을 낸다. 참·거짓은 **색만으로 적지 않는다** — GlyphState 가 글리프와 명도를
 * 함께 낸다 (design/README.md).
 *
 * @param term 조건 항.
 * @param readings 측정값 대응표.
 * @returns 참·거짓, 또는 아직 평가되지 않았으면 pending.
 */
export function resolveMeasureState(term: Term, readings: TermReadings): GlyphStateKind {
  const lhsValue = readLhsMeasure(term, readings)
  const rhsValue = readRhsMeasure(term, readings)
  const compare = COMPARATORS.get(term.comparison)
  if (lhsValue === undefined || rhsValue === undefined || compare === undefined) {
    return 'pending'
  }
  return compare(Number(lhsValue), Number(rhsValue)) ? 'true' : 'false'
}

/** 조건절을 잇는 표기. 코어의 `evaluateCondition` 이 쓰는 것과 같은 문자열이다. */
const JOIN_AND = ' AND '
const JOIN_OR = ' OR '

/**
 * 규칙의 조건절 전체를 실측값이 병기된 한 줄로 적는다. 규칙 목록의 한 줄이 이것을 쓴다.
 *
 * @param rule 규칙 한 줄.
 * @param catalog 라벨을 얻을 블록 카탈로그.
 * @param readings 측정값 대응표.
 * @returns 항을 연산자로 이은 한 줄.
 */
export function formatMeasuredCondition(
  rule: Rule,
  catalog: BlockCatalog,
  readings: TermReadings,
): string {
  const joiner = rule.conditions.op === OP_OR ? JOIN_OR : JOIN_AND
  return rule.conditions.terms
    .map((term) => formatMeasuredTerm(term, catalog, readings))
    .join(joiner)
}
