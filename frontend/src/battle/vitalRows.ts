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

/** 상태이상 이름표. 코어의 상태 id 를 사람이 읽는 말로. */
export const STATUS_LABELS: ReadonlyMap<string, string> = new Map([
  ['POISON', '중독'],
  ['SLOW', '둔화'],
  ['STUN', '기절'],
])

/** 깃발 이름들. 규칙표가 세우고 읽는 넷이다 (`flag_state[A]`). */
export const FLAG_NAMES: readonly string[] = ['A', 'B', 'C', 'D']

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
  /**
   * 싸우는 값 넷. **규칙표가 직접 읽는 축이라 화면에도 있어야 한다** — `적거리 <=
   * 사거리` 가 참인지 틀린지를 사람이 눈으로 확인할 수 있어야 P1 이 성립한다.
   *
   * **없으면 줄을 안 만든다.** 재생·사후 분석은 프레임에 이 값을 안 들고 있는데,
   * 없는 것을 0 으로 적으면 「공격 0」이 사실처럼 보인다 — 모르는 것과 0 인 것은
   * 다른 말이고, 이 저장소는 그 구분으로 여러 번 다쳤다.
   */
  readonly attack?: number
  readonly defense?: number
  readonly attackRange?: number
  readonly initiative?: number
  /** 남은 쿨타임. 코어의 `entity.cooldowns` 를 그대로 받는다. */
  readonly cooldowns?: ReadonlyMap<string, number> | undefined
  /** 걸린 상태이상. 코어의 `entity.statuses` 를 그대로 받는다. */
  readonly statuses?: ReadonlyMap<string, number> | undefined
  /** 세워 둔 깃발. 코어의 `entity.flags` 를 그대로 받는다. */
  readonly flags?: ReadonlyMap<string, boolean> | undefined
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
 * 싸우는 값 넷을 줄로 편다.
 *
 * **규칙표가 `적거리 <= 사거리` 로 직접 읽는 축인데 전투 화면 어디에도 없었다** —
 * 무기를 바꿔 사거리가 달라진 것을 확인할 자리가 없었다 (결정 #13 이 파는 것이 바로
 * 그 변화다).
 *
 * @param input 상태 값들.
 * @returns 네 줄. 값을 안 받았으면 빈 배열이다 — 재생 프레임이 그 경우다.
 */
export function listCombatRows(input: VitalInput): readonly VitalRow[] {
  if (input.attack === undefined) {
    return []
  }
  return [
    { label: '공격', value: String(input.attack) },
    { label: '방어', value: String(input.defense ?? 0) },
    { label: '사거리', value: String(input.attackRange ?? 0) },
    { label: '선공', value: String(input.initiative ?? 0) },
  ]
}

/**
 * 걸린 상태이상을 한 줄로 적는다.
 *
 * **한 줄에 몰아 적는다.** 셋을 각각 줄로 두면 안 걸린 동안 「중독 0틱」 같은 줄이 셋
 * 늘 서 있고, 걸릴 때만 그리면 줄 수가 흔들린다 — 둘 다 나쁘다. 한 줄이면 자리는
 * 고정이고 값만 바뀐다.
 *
 * @param input 상태 값들.
 * @returns 상태이상 한 줄.
 */
export function formatStatusRow(input: VitalInput): VitalRow {
  const parts = [...STATUS_LABELS]
    .map(([id, label]) => [label, input.statuses?.get(id) ?? 0] as const)
    .filter(([, left]) => left > 0)
    .map(([label, left]) => `${label} ${String(left)}틱`)
  return { label: '상태이상', value: parts.length === 0 ? '없음' : parts.join(' · ') }
}

/**
 * 세워 둔 깃발을 한 줄로 적는다.
 *
 * **규칙표가 세우고 읽는 값인데 화면 어디에도 없었다.** `SET_FLAG` 로 세우고
 * `flag_state[A]` 로 읽는 넷이 보이지 않으면, 깃발을 쓰는 규칙표는 왜 안 도는지를
 * 로그에서 거꾸로 짚어야 한다 — 값을 보여 주는 것이 P1 이 요구하는 것이다.
 *
 * @param input 상태 값들.
 * @returns 깃발 한 줄.
 */
export function formatFlagRow(input: VitalInput): VitalRow {
  const on = FLAG_NAMES.filter((name) => input.flags?.get(name) === true)
  return { label: '깃발', value: on.length === 0 ? '없음' : on.join(' · ') }
}

/**
 * 상태 탭에 세울 줄 전부.
 *
 * 순서가 곧 급한 순서다 — 체력, 들고 있는 것, **싸우는 값**, 쓸 수 있는 것,
 * 걸린 것, 세워 둔 것, 예산.
 *
 * **빈 자리를 값으로 채운 것이다** (2026-09-09, 실제 신고: 「탭 안쪽 정보 출력부도
 * 봐 달라」). 다섯 줄만 서 있어서 시트의 185px 이 비어 있었는데, 그 사이 규칙표가
 * 읽는 축 여섯(공격·방어·사거리·선공·상태이상·깃발)은 화면 어디에도 없었다.
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
    ...listCombatRows(input),
    ...listCooldownRows(input),
    formatStatusRow(input),
    formatFlagRow(input),
    {
      label: 'cpu',
      value: `${String(input.cpuUsed)} / ${String(input.cpuBudget)}`,
      // 예산 초과는 오류가 아니라 수치다. 색만 넘어가고 판은 그대로 돈다 (GDD §3.6).
      isWarning: input.cpuUsed > input.cpuBudget,
    },
  ]
}
