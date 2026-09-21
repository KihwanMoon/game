/**
 * 도면 네 귀퉁이에 겹치는 HUD (2026-09-21 요청).
 *
 * **상태를 보려고 탭을 옮기면 그동안 판이 계속 돈다.** 체력·상태이상·소모품·쿨타임은
 * 「지금 무엇을 할 수 있나」를 정하는 값이라 늘 보여야 하는데, 지금은 시트의 첫 탭에
 * 있어서 로그나 규칙표를 보는 동안 사라진다.
 *
 * **전용 줄을 안 두고 겹친다.** 고정 줄 하나가 곧 시트를 그만큼 밀어내고, 2026-09-08 에
 * 상태 줄 44px 을 뺀 것이 바로 그 회계다(`--bars-h`). 겹치면 높이 비용이 0 이다.
 *
 * **요약이지 대체가 아니다.** 상태 탭은 그대로 둔다 — 여기 올릴 수 있는 것은 귀퉁이에
 * 들어가는 만큼이고, 스탯 넷·깃발·CPU 는 줄이 길어 못 올린다.
 *
 * `vitalRows` 와 갈라 둔 이유는 **모양이 다르기 때문**이다. 저쪽은 이름·값 문자열 줄을
 * 내고(표에 그대로 들어간다) 여기는 게이지와 칸을 그릴 **수치**를 낸다 — 문자열에서
 * 수치를 되파내면 그 파싱이 곧 두 번째 정본이 된다.
 */
import { USE_TAG_CODES, USE_TAG_LABELS } from '../content/consumableTags'
import { readCooldownLabel, STATUS_LABELS, type VitalInput } from './vitalRows'

/** 체력이 이 퍼센트 밑이면 경고다. 상태 탭과 같은 값이어야 한다. */
const LOW_HP_PERCENT = 30
const PERCENT_BASE = 100

/** 좌상단에 서는 상태이상 하나. */
export interface HudStatus {
  readonly label: string
  /** 남은 틱. 0 이면 안 세운다 — 안 걸린 것을 세우면 칸만 먹는다. */
  readonly ticks: number
}

/** 좌하단에 서는 소모품 칸 하나. */
export interface HudItem {
  /** 두 글자 도식 코드. 「어느 칸에 들어가는가」를 말한다 (`USE_TAG_CODES`). */
  readonly code: string
  readonly label: string
  /** 지금 남은 수. */
  readonly held: number
  /** 들고 들어온 수. 0 이면 이 칸 자체를 안 세운다. */
  readonly carried: number
}

/** 우하단에 서는 재주 칸 하나. */
export interface HudSkill {
  readonly label: string
  /** 남은 쿨타임 틱. 0 이면 준비됨이다. */
  readonly left: number
  /** 전체 쿨타임. 0 이면 쿨이 없는 재주다. */
  readonly total: number
}

/** 도면 위에 겹치는 값 전부. */
export interface PlanHud {
  readonly hp: number
  readonly hpMax: number
  /** 체력이 낮은가. 상태 탭의 경고와 같은 기준이다. */
  readonly isLow: boolean
  readonly statuses: readonly HudStatus[]
  readonly items: readonly HudItem[]
  readonly skills: readonly HudSkill[]
}

/**
 * 걸려 있는 상태이상만 고른다.
 *
 * **안 걸린 것은 안 세운다.** 상태 탭은 「없음」이라고 적어 정보가 있다는 것을 보이지만,
 * 도면 귀퉁이는 자리가 좁아 빈 칸이 곧 가린 칸이다.
 *
 * @param input 상태 값들.
 * @returns 걸린 것들. `STATUS_LABELS` 순서를 따른다.
 */
export function listHudStatuses(input: VitalInput): readonly HudStatus[] {
  return [...STATUS_LABELS]
    .map(([id, label]) => ({ label, ticks: input.statuses?.get(id) ?? 0 }))
    .filter((one) => one.ticks > 0)
}

/**
 * 들고 들어온 소모품 칸들.
 *
 * **들고 온 것만 세운다.** 안 들고 온 태그까지 세우면 다섯 칸이 늘 서서 도면을 가린다 —
 * 「부적 0 / 0」이 뜨던 자리와 같은 문제다 (2026-09-11).
 *
 * @param input 상태 값들.
 * @returns 칸들. `USE_TAG_LABELS` 순서를 따른다.
 */
export function listHudItems(input: VitalInput): readonly HudItem[] {
  return [...USE_TAG_LABELS]
    .map(([tag, label]) => ({
      code: USE_TAG_CODES.get(tag) ?? tag.slice(0, 2),
      label,
      held: input.held?.get(tag) ?? 0,
      carried: input.carried?.get(tag) ?? 0,
    }))
    .filter((one) => one.carried > 0)
}

/**
 * 이 규칙표가 쓰는 재주 칸들.
 *
 * **늘 보인다.** 도는 쿨만 적으면 아직 안 쓴 틱에 칸이 사라져 「정보가 없어졌다」로
 * 읽힌다 — 상태 탭의 쿨타임 줄이 같은 이유로 늘 선다.
 *
 * @param input 상태 값들.
 * @returns 칸들. 규칙표가 쓰는 순서 그대로.
 */
export function listHudSkills(input: VitalInput): readonly HudSkill[] {
  return (input.skills ?? []).map((skill) => ({
    label: readCooldownLabel(skill),
    left: input.cooldowns?.get(skill) ?? 0,
    total: input.totals?.get(skill) ?? 0,
  }))
}

/**
 * 도면 위에 겹칠 값을 모은다.
 *
 * @param input 상태 값들. `buildVitalRows` 와 같은 것을 받는다 — 두 자리가 다른 입력을
 *     보면 같은 화면에서 체력이 둘로 갈린다.
 * @returns 겹칠 값 전부.
 */
export function buildPlanHud(input: VitalInput): PlanHud {
  return {
    hp: input.hp,
    hpMax: input.hpMax,
    isLow: input.hpMax > 0 && (input.hp * PERCENT_BASE) / input.hpMax < LOW_HP_PERCENT,
    statuses: listHudStatuses(input),
    items: listHudItems(input),
    skills: listHudSkills(input),
  }
}
