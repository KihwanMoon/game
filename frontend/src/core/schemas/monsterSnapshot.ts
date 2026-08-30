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
  }
}

/**
 * 스냅샷을 entityId 순으로 정렬한다.
 *
 * 순서가 실행마다 다르면 같은 티켓이 다른 글자로 저장되고, 그 위에서 만든 검증이
 * 흔들린다 (R5).
 *
 * @param snapshots 정렬할 스냅샷들.
 * @returns 정렬된 스냅샷들.
 */
export function sortSnapshots(
  snapshots: readonly MonsterSnapshot[],
): readonly MonsterSnapshot[] {
  return [...snapshots].sort((left, right) => (left.entityId < right.entityId ? -1 : 1))
}
