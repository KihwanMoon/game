/**
 * 세로 모바일 시트의 상태 계산 — 탭, 켜고 끈 규칙, 그 규칙표로 도는 판.
 *
 * 세로 배치는 데스크톱 세 열을 **축소한 것이 아니라 재배치한 것**이다(design/README.md
 * 「반응형」). 도면은 12×9 전체를 유지한 채 화면 위쪽에 고정되고, 규칙표와 로그가
 * 아래쪽 시트 하나를 탭으로 나눠 쓴다. 도면이 고정돼 있으므로 규칙을 읽는 동안에도
 * 유닛 위치가 계속 보인다 — 이 배치의 존재 이유가 그것이다.
 *
 * **규칙을 끄면 판이 처음부터 다시 돈다.** 끄기는 "규칙 편집 화면까지 가지 않고 가설을
 * 시험하는" 수단이고(모바일 원본 D), 가설을 시험한다는 것은 곧 **입력이 바뀐 판을 새로
 * 돌린다**는 뜻이다. 도는 판의 규칙표를 중간에 갈아 끼우면 같은 시드가 같은 결과를 내지
 * 않는다 (R5, App.tsx 의 `run` 주석과 같은 이유).
 *
 * 꺼진 우선순위는 **정렬된 배열**로 든다. 집합을 순회해 규칙표를 만들면 순서가 보장되지
 * 않고, 그 순서가 곧 RuleVM 의 평가 순서다.
 */

import type { RuleSet } from '../core/schemas'

/** 시트가 보여 줄 수 있는 것. 규칙표와 로그 둘뿐이다. */
export type SheetTab = 'rules' | 'log'

/** 탭 순서. 배열 순서가 화면 순서다. */
export const SHEET_TABS: readonly SheetTab[] = ['rules', 'log']

/** 탭 라벨. 카운트는 따로 붙인다. */
export const SHEET_TAB_LABELS: ReadonlyMap<SheetTab, string> = new Map([
  ['rules', '규칙표'],
  ['log', '실행 로그'],
])

/**
 * 꺼진 규칙의 조건문 뒤에 붙는 꼬리말.
 *
 * 불투명도만으로 알리지 않는 이유는 늘 같다 — 명도는 채널 하나이고, 그것 하나로만
 * 적으면 흑백·저조도·색약 조건에서 사라진다. 앞의 공백 둘은 조건문과 붙어 읽히지 않게
 * 띄운 것이며 모바일 원본이 정한 표기다.
 */
export const RULE_OFF_SUFFIX = '  · 꺼짐'

/** 틱 표기의 자릿수. `027` 처럼 폭이 흔들리지 않아야 옆의 글자가 밀리지 않는다. */
export const TICK_PAD_WIDTH = 3

/** 로그 탭 카운트의 머리글자. `T027`. */
const TICK_PREFIX = 'T'

/**
 * 틱을 고정 폭 표기로 만든다.
 *
 * @param tick 현재 틱.
 * @returns `027` 꼴. 세 자리를 넘으면 그대로 늘어난다.
 */
export function formatTick(tick: number): string {
  return String(tick).padStart(TICK_PAD_WIDTH, '0')
}

/**
 * 로그 탭에 적을 카운트.
 *
 * @param tick 현재 틱.
 * @returns `T027`.
 */
export function formatLogTabCount(tick: number): string {
  return `${TICK_PREFIX}${formatTick(tick)}`
}

/**
 * 규칙표 탭에 적을 카운트.
 *
 * @param enabled 켜진 규칙 수.
 * @param total 규칙표 전체 줄 수.
 * @returns `4/5`.
 */
export function formatRulesTabCount(enabled: number, total: number): string {
  return `${String(enabled)}/${String(total)}`
}

/**
 * 그 규칙이 켜져 있는가.
 *
 * @param disabled 꺼진 우선순위들.
 * @param priority 볼 우선순위.
 * @returns 켜져 있으면 참.
 */
export function checkRuleEnabled(disabled: readonly number[], priority: number): boolean {
  return !disabled.includes(priority)
}

/**
 * 규칙 하나를 켜거나 끈다.
 *
 * @param disabled 지금 꺼진 우선순위들.
 * @param priority 누른 줄의 우선순위.
 * @returns 새 목록. 오름차순으로 정렬돼 나온다.
 */
export function toggleRulePriority(
  disabled: readonly number[],
  priority: number,
): readonly number[] {
  if (disabled.includes(priority)) {
    return disabled.filter((one) => one !== priority)
  }
  return [...disabled, priority].sort((left, right) => left - right)
}

/**
 * 조건문에 꺼짐 표시를 붙인다.
 *
 * @param condition 원래 조건문.
 * @param enabled 켜져 있는가.
 * @returns 켜져 있으면 원문 그대로, 꺼져 있으면 꼬리말이 붙은 문자열.
 */
export function formatRuleCondition(condition: string, enabled: boolean): string {
  return enabled ? condition : `${condition}${RULE_OFF_SUFFIX}`
}

/**
 * 꺼진 규칙을 뺀 규칙표 대응표를 만든다. 판은 이것으로 조립된다.
 *
 * 아무것도 끄지 않았으면 **받은 대응표를 그대로 돌려준다.** 새 Map 을 만들면 참조가
 * 매번 바뀌어 판이 재조립되고, 그러면 데스크톱에서 화면이 다시 그려질 때마다 전투가
 * 처음으로 돌아간다.
 *
 * @param rulesets 규칙표 id 대응표.
 * @param rulesetId 플레이어 규칙표 id.
 * @param disabled 꺼진 우선순위들.
 * @returns 판에 실을 대응표.
 */
export function buildRunRulesets(
  rulesets: ReadonlyMap<string, RuleSet>,
  rulesetId: string,
  disabled: readonly number[],
): ReadonlyMap<string, RuleSet> {
  const ruleset = rulesets.get(rulesetId)
  if (disabled.length === 0 || ruleset === undefined) {
    return rulesets
  }
  const next = new Map(rulesets)
  next.set(rulesetId, {
    ...ruleset,
    rules: ruleset.rules.filter((rule) => checkRuleEnabled(disabled, rule.priority)),
  })
  return next
}
