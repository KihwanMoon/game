/**
 * 플레이어 로드아웃 — 장비·레벨이 확정한 전투 입력.
 *
 * `game/schemas/loadout.py` 의 이식이다.
 *
 * **장비는 전투 전에 캐릭터로 녹는다** (결정 #13). 규칙표는 캐릭터만 읽으므로 장비 전용
 * DSL 블록이 없고, 사거리가 바뀌면 같은 규칙표가 저절로 다르게 돈다.
 *
 * 문제는 장비를 **서버가 알고** 전투를 **브라우저가 돈다**는 것이다. 몬스터 스냅샷과
 * 같은 상황이라 같은 방법으로 푼다 — 티켓에 얼려 넣는다. 넣지 않으면 화면은 맨몸으로
 * 싸우고 서버는 장비를 낀 채로 재시뮬한다.
 */

/** 아무것도 안 껴도 쓸 수 있는 스킬. 파이썬 `BASE_SKILLS` 와 같아야 한다. */
export const BASE_SKILLS: readonly string[] = ['ATTACK', 'SKILL_1', 'SKILL_2']

/** 런 하나의 플레이어 전투 입력. 티켓이 얼려 둔 값이다. */
/** 스킬위력의 기준값. 100 이 "계수 그대로" 다. */
export const BASE_SKILL_POWER_PCT = 100

export interface PlayerLoadout {
  readonly hpMax: number
  readonly attack: number
  readonly defense: number
  readonly attackRange: number
  readonly initiative: number
  readonly cpuBudget: number
  readonly ruleSlots: number
  /**
   * 이 캐릭터가 내는 스킬의 위력. 정수 퍼센트로 100 이 "계수 그대로" 다 (결정 #51).
   * 지능이 여기를 올린다.
   */
  readonly skillPowerPct: number
  readonly skills: readonly string[]
  /**
   * 이 런에 들고 들어가는 소모품. 태그에서 개수로 (#54).
   *
   * **장비와 같은 이유로 티켓이 싣는다.** 인벤토리는 서버가 알고 전투는 브라우저가
   * 도므로, 얼려 두지 않으면 화면은 빈손으로 싸우고 서버는 주머니를 채운 채 재시뮬한다.
   */
  readonly consumables: readonly (readonly [string, number])[]
}

/** 서버가 주는 절. 파이썬 `build_loadout_payload` 와 같은 열쇠다. */
export interface RawPlayerLoadout {
  readonly hp_max: number
  readonly attack: number
  readonly defense: number
  readonly attack_range: number
  readonly initiative: number
  readonly cpu_budget: number
  readonly rule_slots: number
  readonly skill_power_pct?: number
  readonly skills: readonly string[]
  readonly consumables?: Record<string, number>
}

/**
 * 로드아웃 절을 읽는다.
 *
 * @param raw 서버가 준 절.
 * @returns 만들어진 로드아웃.
 */
export function parseLoadout(raw: RawPlayerLoadout): PlayerLoadout {
  return {
    hpMax: raw.hp_max,
    attack: raw.attack,
    defense: raw.defense,
    attackRange: raw.attack_range,
    initiative: raw.initiative,
    cpuBudget: raw.cpu_budget,
    ruleSlots: raw.rule_slots,
    // 없으면 기준값이다. 구버전 티켓이 "위력 0" 으로 읽히면 그 티켓으로 돌린 판이
    // 전부 최소피해로 끝난다.
    skillPowerPct: raw.skill_power_pct ?? BASE_SKILL_POWER_PCT,
    // 정렬해서 담는다. 순서가 실행마다 다르면 같은 티켓이 다른 글자로 저장된다 (R5).
    skills: [...raw.skills].sort(),
    // 정렬해서 담는다 (R5). 없으면 빈손이다 — 구버전 티켓이 그 경우다.
    consumables: Object.entries(raw.consumables ?? {})
      .map(([kind, count]) => [kind, Number(count)] as const)
      .sort((left, right) => (left[0] < right[0] ? -1 : 1)),
  }
}
