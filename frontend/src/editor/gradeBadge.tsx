/**
 * 등급 표기 — 색·글리프·이름 세 채널 (design/README.md §성격).
 *
 * `InventoryPanel` 에서 갈라 나왔다. 가방·소모품 칸·상세 셋이 같은 표기를 쓰는데 한
 * 패널 안에 있으면 나머지 둘이 패널을 통째로 들여와야 한다.
 *
 * **색만으로 가르지 않는다.** 색을 못 가르는 사람에게 채워진 마름모와 빈 마름모는
 * 노랑과 주황보다 확실하다 — 참·거짓을 색·글리프·명도 셋으로 적는 규율과 같다.
 */

/** 등급의 한글 이름. */
export const GRADE_LABELS: ReadonlyMap<string, string> = new Map([
  ['COMMON', '보통'],
  ['FINE', '상급'],
  ['RELIC', '유물'],
])

/** 등급의 글리프. 괘선 굵기로 안 가르는 이유는 `--bw-accent` 가 활성 규칙 전용이라서다. */
export const GRADE_GLYPHS: ReadonlyMap<string, string> = new Map([
  ['COMMON', '·'],
  ['FINE', '◇'],
  ['RELIC', '◆'],
])

/**
 * 등급에 붙는 class 를 정한다.
 *
 * @param grade 등급 코드.
 * @returns class 이름. 모르는 등급이면 빈 문자열 — 색을 안 입힌다.
 */
export function formatGradeClass(grade: string): string {
  return GRADE_LABELS.has(grade) ? ` inv__name--${grade.toLowerCase()}` : ''
}

/**
 * 등급 이름표를 그린다.
 *
 * @param grade 등급 코드.
 * @returns 이름표. 모르는 등급이면 아무것도 안 그린다.
 */
export function renderGrade(grade: string): React.JSX.Element | null {
  const label = GRADE_LABELS.get(grade)
  if (label === undefined) {
    return null
  }
  return (
    <span className={`inv__grade inv__grade--${grade.toLowerCase()}`}>
      {`${GRADE_GLYPHS.get(grade) ?? ''} ${label}`}
    </span>
  )
}
