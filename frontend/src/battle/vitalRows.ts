/**
 * 상태 탭의 줄들 — **정보 하나에 한 줄** (실제 요청).
 *
 * 체력·소모품·쿨타임·예산은 셋도 넷도 아니고 하나의 질문에 답한다: **지금 내가 무엇을
 * 얼마나 남겼는가.** 그런데 화면 세 곳에 흩어져 있다가, 한 줄로 모으니 이번에는 그 한
 * 줄이 `◍ 2/2 · ▤ 1/1 · 쿨 — 스킬 1 0/6틱 · 스킬 2 3/8틱` 처럼 길어져 잘렸다 — 가로로
 * 이으면 무엇이 들어 있는지 훑을 수 없다 (정산 탭이 같은 이유로 세로로 쌓는다).
 *
 * 그래서 탭 하나를 준다. 한 줄에 하나씩 쌓으면 잘리지 않고, 스킬이 늘어도 줄이 늘 뿐이다.
 *
 * 순수 함수다. 화면 상태를 안 건드리므로 테스트가 값만 보고 판정할 수 있다.
 */

/** 상태 한 줄. 이름과 값, 그리고 눈에 띄어야 하는지. */
export interface VitalRow {
  /** 왼쪽 이름. */
  readonly label: string
  /** 오른쪽 값. `38 / 100` 처럼 단위를 포함한다. */
  readonly value: string
  /**
   * 위험한 값인가 (체력이 바닥이거나 예산을 넘겼거나).
   *
   * **색이 유일한 채널이 아니다.** 값 자체가 이미 `10 / 8` 처럼 말하고 있고, 색은
   * 그것을 빨리 찾게 도울 뿐이다.
   */
  readonly isWarning?: boolean
}

/** 쿨타임 이름표. 코어의 행동 id 를 사람이 읽는 말로. */
export const COOLDOWN_LABELS: ReadonlyMap<string, string> = new Map([
  ['ATTACK', '공격'],
  ['SKILL_1', '스킬 1'],
  ['SKILL_2', '스킬 2'],
  ['AREA_ATTACK', '광역'],
  ['HEAL', '치유'],
  ['SUMMON', '소환'],
  ['GUARD_BRACE', '방어'],
])

/** 체력이 이 비율 아래면 눈에 띄게 한다. 규칙표의 흔한 문턱(25~30%)과 같은 자리다. */
const LOW_HP_PERCENT = 30

/** 백분율 기준. 부동소수를 안 쓰므로 정수 비교로 판정한다 (R5 와 같은 규율). */
const PERCENT_BASE = 100

/** `buildVitalRows` 가 받는 값들. */
export interface VitalInput {
  readonly hp: number
  readonly hpMax: number
  readonly potions: number
  readonly potionsMax: number
  readonly scrolls: number
  readonly scrollsMax: number
  /** 켜진 규칙들의 누적 CPU 와 예산. 초과는 오류가 아니라 수치다. */
  readonly cpuUsed: number
  readonly cpuBudget: number
  /** 남은 쿨타임. 코어의 `entity.cooldowns` 를 그대로 받는다. */
  readonly cooldowns?: ReadonlyMap<string, number> | undefined
  /** 이 규칙표가 쓰는 스킬들. 안 쓰는 스킬의 쿨을 적으면 줄만 늘어난다. */
  readonly skills?: readonly string[]
  /** 스킬별 전체 쿨타임. `0/6` 의 뒷자리다. */
  readonly totals?: ReadonlyMap<string, number> | undefined
}

/**
 * 쿨타임을 이름·값 쌍으로 편다.
 *
 * **늘 보인다.** 도는 쿨만 적으면 스킬을 아직 안 쓴 틱에 줄이 사라져 「정보가
 * 없어졌다」로 읽힌다(실제 신고). 남은틱/전체틱으로 적는다 — `0/6` 이 곧 「준비됨」이다.
 *
 * @param input 상태 값들.
 * @returns 스킬 순서 그대로의 줄들. 쓰는 스킬이 없으면 빈 배열.
 */
export function listCooldownRows(input: VitalInput): readonly VitalRow[] {
  return (input.skills ?? []).map((skill) => ({
    label: COOLDOWN_LABELS.get(skill) ?? skill,
    value: `${String(input.cooldowns?.get(skill) ?? 0)} / ${String(input.totals?.get(skill) ?? 0)}틱`,
  }))
}

/**
 * 상태 탭에 세울 줄 전부.
 *
 * 순서가 곧 급한 순서다 — 체력, 들고 있는 것, 쓸 수 있는 것, 예산.
 *
 * @param input 상태 값들.
 * @returns 한 줄에 하나씩 쌓을 줄들.
 */
export function buildVitalRows(input: VitalInput): readonly VitalRow[] {
  const isLow =
    input.hpMax > 0 && (input.hp * PERCENT_BASE) / input.hpMax < LOW_HP_PERCENT
  return [
    { label: '체력', value: `${String(input.hp)} / ${String(input.hpMax)}`, isWarning: isLow },
    { label: '물약', value: `${String(input.potions)} / ${String(input.potionsMax)}` },
    { label: '주문서', value: `${String(input.scrolls)} / ${String(input.scrollsMax)}` },
    ...listCooldownRows(input),
    {
      label: 'cpu',
      value: `${String(input.cpuUsed)} / ${String(input.cpuBudget)}`,
      // 예산 초과는 오류가 아니라 수치다. 색만 넘어가고 판은 그대로 돈다 (GDD §3.6).
      isWarning: input.cpuUsed > input.cpuBudget,
    },
  ]
}
