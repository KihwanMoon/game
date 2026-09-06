/**
 * 몬스터 스냅샷 — 지속 몬스터를 런 등식 **안에** 넣는 장치.
 *
 * `game/schemas/monster_snapshot.py` 의 이식이다.
 *
 * 이 게임의 전부는 `런 결과 = f(시드, 규칙표, 코어 버전)` 이고, 리플레이·데일리·헤드리스
 * 밸런싱·서버 재검증이 전부 여기 얹혀 있다. 여러 플레이어가 공유하는 살아 있는 몬스터는
 * 시드에서 나오지 않는 **세계 상태**라 그 등식 밖이다.
 *
 * 그래서 런이 시작될 때 그 상태를 티켓에 얼려 넣는다 — 등식이
 * `f(시드, 규칙표, 코어 버전, 스냅샷)` 이 될 뿐 성질은 그대로다. 서버는 같은 스냅샷으로
 * 재시뮬해 검증할 수 있고, 오프라인 플레이도 살아남는다.
 *
 * **클라이언트는 스냅샷을 되보내지 않는다.** 서버가 티켓 id 로 자기가 발급한 것을
 * 조회한다 — 받으면 약한 스냅샷으로 바꿔 제출할 수 있다 (T8).
 */

import type { RawRuleSet } from './ruleset'

/** 엔티티 id 를 만드는 구분자. 방 배치와 같아야 스냅샷이 그 자리에 걸린다. */
export const ENTITY_ID_SEPARATOR = '_'

/** 지속 몬스터 하나의 얼어붙은 상태. */
export interface MonsterSnapshot {
  readonly entityId: string
  readonly recordId: number
  readonly kindId: string
  readonly tier: string
  readonly level: number
  readonly hpMax: number
  readonly attack: number
  readonly defense: number
  readonly ruleSlots: number
  readonly cpuBudget: number
  /**
   * 이 개체가 사는 층. **자리 이름이 층을 구분하지 않는다** — `goblin_rusher_0` 이
   * 1층부터 9층까지 따로 살고, 하강 티켓은 그 전부를 싣는다. 층이 없으면 방에 얹을 때
   * 이름만 보고 겹쳐 **1층 방에 9층 개체가 선다**.
   *
   * 0 은 「모른다」다. 층을 싣기 전에 발급된 티켓이 그 값이며, 그 티켓은 예전처럼 층을
   * 안 보고 얹는다 — 발급 당시와 다르게 재시뮬하면 정상 제출이 반려된다 (R5).
   */
  readonly zoneFloor: number
  /**
   * 이 개체가 실제로 닿는 거리. **0 은 「안 실렸다」**이고 그때는 종의 값을 쓴다.
   *
   * 도플갱어 때문에 생겼다. 스탯만 실으니 **장궁 든 봇의 그림자가 사거리 1 근접**으로
   * 싸웠다 — 빌드에서 가장 그 빌드다운 것이 빠진 채 숫자만 큰 몹이 됐다.
   */
  readonly attackRange: number
  /**
   * 이 개체가 쓸 수 있는 스킬. **빈 배열은 「안 실렸다」**이고 그때는 종의 규칙을 쓴다.
   *
   * `Entity.skills` 는 undefined 가 「전부 허용」이고 빈 것이 「아무것도 없음」이라 뜻이
   * 반대다 — 여기서 빈 것은 **모른다**이므로 undefined 로 옮긴다. 그래야 스킬을 안 싣던
   * 옛 티켓이 예전과 똑같이 재시뮬된다 (R5).
   */
  readonly skills: readonly string[]
  /** 들고 들어가는 물약 수. **-1 이 「안 실렸다」**다 — 0 은 「없다」라는 진짜 값이다. */
  readonly potions: number
  /**
   * 이 개체 **하나만의** 규칙표. null 이면 종의 표를 쓴다.
   *
   * 도플갱어의 뜻이 여기 걸린다 — 「그 규칙표가 나를 읽는다」가 이 개체의 전부인데,
   * 나르는 칸이 없어서 모든 그림자가 종의 기본표 하나로 싸웠다.
   */
  readonly ruleset: RawRuleSet | null
}

/** 서버가 주는 절. 파이썬 `build_snapshot_payload` 와 같은 열쇠다. */
export interface RawMonsterSnapshot {
  readonly entity_id: string
  readonly record_id: number
  readonly kind_id: string
  readonly tier: string
  readonly level: number
  readonly hp_max: number
  readonly attack: number
  readonly defense: number
  readonly rule_slots: number
  readonly cpu_budget: number
  /** 구버전 서버는 안 보낸다. 그때는 0 — 층을 모른다는 뜻이다. */
  readonly zone_floor?: number
  /** 키트를 싣기 전 서버는 안 보낸다. 그때는 종의 값을 쓴다. */
  readonly attack_range?: number
  readonly skills?: readonly string[]
  readonly potions?: number
  readonly ruleset?: RawRuleSet | null
}

/**
 * 방 배치와 같은 규칙으로 엔티티 id 를 만든다.
 *
 * @param kindId 적 종류 id.
 * @param index 배치 순번.
 * @returns `goblin_rusher_0` 형태의 id.
 */
export function buildEntityId(kindId: string, index: number): string {
  return `${kindId}${ENTITY_ID_SEPARATOR}${String(index)}`
}

/**
 * 스냅샷 한 줄을 읽는다.
 *
 * @param raw 서버가 준 절.
 * @returns 만들어진 스냅샷.
 */
export function parseSnapshot(raw: RawMonsterSnapshot): MonsterSnapshot {
  return {
    entityId: raw.entity_id,
    recordId: raw.record_id,
    kindId: raw.kind_id,
    tier: raw.tier,
    level: raw.level,
    hpMax: raw.hp_max,
    attack: raw.attack,
    defense: raw.defense,
    ruleSlots: raw.rule_slots,
    cpuBudget: raw.cpu_budget,
    zoneFloor: raw.zone_floor ?? 0,
    attackRange: raw.attack_range ?? 0,
    // 정렬해서 담는다 — 순회 순서가 게임 상태로 새면 두 코어가 갈린다 (R5).
    skills: [...(raw.skills ?? [])].map(String).sort(),
    potions: raw.potions ?? -1,
    ruleset: raw.ruleset ?? null,
  }
}

/**
 * 스냅샷을 순서대로 세운다.
 *
 * 순서가 실행마다 다르면 같은 티켓이 다른 글자로 저장되고, 그 위에서 만든 검증이
 * 흔들린다 (R5).
 *
 * **entityId 만으로는 순서가 정해지지 않는다.** 같은 이름이 층마다 있어서 동률이 생기고,
 * 동률에서는 들어온 순서가 남는다 — 그것은 DB 조회 순서이지 계약이 아니다. 층과 레코드
 * id 까지 넣어 전순서로 만든다.
 *
 * @param snapshots 정렬할 스냅샷들.
 * @returns (entityId, 층, recordId) 순으로 정렬된 스냅샷들.
 */
export function sortSnapshots(
  snapshots: readonly MonsterSnapshot[],
): readonly MonsterSnapshot[] {
  return [...snapshots].sort((left, right) => {
    if (left.entityId !== right.entityId) {
      return left.entityId < right.entityId ? -1 : 1
    }
    if (left.zoneFloor !== right.zoneFloor) {
      return left.zoneFloor - right.zoneFloor
    }
    return left.recordId - right.recordId
  })
}

/**
 * 도플갱어의 자리 이름 머리 (G3 — 파이썬 `schemas/monster_snapshot.py` 와 같은 값).
 *
 * 코어는 이 머리로 「방 배치에 없어도 더해야 하는 개체」를 가른다.
 */
export const DOPPEL_SLOT_PREFIX = 'doppel_'

/**
 * 방 배치에 없어도 방에 **더해야** 하는 자리인가.
 *
 * **아무것이나 더하면 안 된다.** 그 층의 지속 몬스터는 자기 자리를 덮어쓰는 개체라,
 * 자리가 없는 방에 더하면 그 방의 적이 늘어난다 — 실제로 세계 몬스터가 모든 방에
 * 더해져 방당 둘이 다섯이 됐다.
 *
 * @param slot 자리 이름.
 * @returns 더해야 하면 true.
 */
export function checkIsExtraSlot(slot: string): boolean {
  return slot.startsWith(DOPPEL_SLOT_PREFIX)
}
