/**
 * SET 절 하나를 읽고 쓴다 — `A=true` 와 (플래그 이름, 값) 사이의 변환.
 *
 * 데스크톱 규칙 행과 모바일 편집 카드가 **같은 판정**을 써야 한다. 코어는 `=` 뒤가
 * `false` 가 아니면 전부 참으로 읽으므로(`core/sim/actions.ts`), 화면이 참이라고 적은
 * 것을 엔진이 거짓으로 읽는 일이 없게 여기 한 곳에 둔다.
 */

/** SET 절이 없음을 고르는 값. 빈 문자열은 select 의 기본값과 섞이므로 따로 둔다. */
export const FLAG_NONE = 'NONE'
export const FLAG_TRUE = 'true'
export const FLAG_FALSE = 'false'

/** 이름과 값을 가르는 글자. */
const FLAG_SEPARATOR = '='

/**
 * SET 절 문자열에서 플래그 이름을 읽는다.
 *
 * @param setFlag `A=true` 형태의 SET 절. 없으면 null.
 * @returns 플래그 이름, 또는 없음 표시.
 */
export function getFlagName(setFlag: string | null): string {
  if (setFlag === null) {
    return FLAG_NONE
  }
  const separator = setFlag.indexOf(FLAG_SEPARATOR)
  return separator < 0 ? setFlag : setFlag.slice(0, separator)
}

/**
 * SET 절 문자열에서 넣을 값을 읽는다.
 *
 * @param setFlag `A=true` 형태의 SET 절. 없으면 null.
 * @returns 'true' 또는 'false'.
 */
export function getFlagValue(setFlag: string | null): string {
  if (setFlag === null) {
    return FLAG_TRUE
  }
  const separator = setFlag.indexOf(FLAG_SEPARATOR)
  const raw = separator < 0 ? '' : setFlag.slice(separator + 1)
  return raw.trim().toLowerCase() === FLAG_FALSE ? FLAG_FALSE : FLAG_TRUE
}

/**
 * 고른 이름과 값을 SET 절 문자열로 되돌린다.
 *
 * @param name 플래그 이름. 없음이면 절을 지운다.
 * @param value 넣을 값.
 * @returns SET 절 문자열. 없음이면 null.
 */
export function buildSetFlag(name: string, value: string): string | null {
  return name === FLAG_NONE ? null : `${name}${FLAG_SEPARATOR}${value}`
}
