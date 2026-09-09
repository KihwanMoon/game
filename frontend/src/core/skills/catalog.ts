/**
 * 스킬 한 줄을 레코드로 읽는다 — 파이썬 `game/app/skills/catalog.py` 의 이식이다.
 *
 * **평행한 맵을 하나로 모은다.** 예전에는 `EngineConfig` 가 스킬 속성마다 맵을 따로
 * 들었다 — 계수·사거리·쿨타임·회복률·감쇠율·감쇠틱 여섯이다. 속성을 하나 더하면 맵이
 * 하나 늘고, 무엇보다 **맵끼리 어긋날 수 있었다**: 계수 맵에는 있고 쿨타임 맵에 없는
 * 스킬은 「쿨타임 0」으로 조용히 돈다.
 *
 * `shape` 와 `telegraph` 가 이 모듈을 만든 직접적인 이유다. 파이썬은 그것을 읽어
 * 예고를 걸고 반경을 정하는데 TS 에는 담을 자리가 없어 **두 코어가 갈릴 수밖에
 * 없었다** — 방어 태세가 정확히 그렇게 조용히 갈려 있었다 (게이트 G3).
 */

/** 형태의 갈래 (설계/5_스킬 §2). `CONE` 은 쓰는 스킬이 생길 때 더한다. */
export const SHAPE_SINGLE = 'SINGLE'
export const SHAPE_AREA = 'AREA'
export const SHAPE_LINE = 'LINE'
export const SHAPE_SELF = 'SELF'

/** 형태를 안 적은 스킬의 기본. 한 명을 때리는 것이 가장 덜 놀라운 해석이다. */
export const DEFAULT_SHAPE_KIND = SHAPE_SINGLE

/** 계수를 안 적은 스킬의 기본. 100 이 「계수 그대로」다. */
export const DEFAULT_COEF_PCT = 100

/** 효과의 갈래. 지금은 상태 부여 하나다 — 피해·회복은 평면 필드가 이미 든다. */
export const EFFECT_STATUS = 'STATUS'

/** 스킬이 맞은 대상에게 얹는 것 하나. **평면 필드를 대신하지 않는다.** */
export interface SkillEffect {
  readonly kind: string
  readonly status: string
  readonly duration: number
}

/** 이 스킬이 무엇을 덮는가. */
export interface SkillShape {
  readonly kind: string
  /** 맨해튼 반경. `AREA` 만 쓴다. */
  readonly radius: number
  /** 직선 길이. `LINE` 만 쓴다. */
  readonly length: number
}

/** 스킬 하나. `skills.json` 의 한 줄이 이것이 된다. */
export interface SkillDef {
  readonly skillId: string
  readonly family: string
  readonly shape: SkillShape
  readonly targetFaction: string
  readonly coefPct: number
  readonly cooldown: number
  /** 자체 사거리. null 이면 엔티티의 `attackRange` 를 쓴다. */
  readonly reach: number | null
  /** 0 이면 즉시. >0 이면 그 틱만큼 예고를 띄운다 (설계/5_스킬 §10). */
  readonly telegraph: number
  /** 시전 중 다른 행동을 하면 취소되는가 (§10.3). */
  readonly cancelOnAct: boolean
  /** 시전 중 맞으면 취소되는가. */
  readonly cancelOnHit: boolean
  readonly healPct: number
  readonly guardPct: number
  readonly guardTicks: number
  readonly tags: readonly string[]
  /** 맞은 대상에게 얹는 것들. 붙는 시점은 **예고 발동**이다. */
  readonly effects: readonly SkillEffect[]
}

/** `skills.json` 의 한 줄. 없는 필드는 기본값으로 읽는다. */
export interface RawSkill {
  readonly id: string
  readonly family?: string
  readonly shape?: { readonly kind?: string; readonly radius?: number; readonly length?: number }
  readonly target_faction?: string
  readonly coef_pct?: number
  readonly cooldown?: number
  readonly range?: number | null
  readonly telegraph?: number
  readonly cancel_on_act?: boolean
  readonly cancel_on_hit?: boolean
  readonly heal_pct?: number
  readonly guard_pct?: number
  readonly guard_ticks?: number
  readonly tags?: readonly string[]
  readonly effects?: readonly { kind?: string; status?: string; duration?: number }[]
}

/**
 * `shape` 절을 읽는다.
 *
 * @param raw 절. 없으면 기본 형태다.
 * @returns 읽어 낸 형태.
 */
export function buildShape(raw: RawSkill['shape']): SkillShape {
  return {
    kind: raw?.kind ?? DEFAULT_SHAPE_KIND,
    radius: raw?.radius ?? 0,
    length: raw?.length ?? 0,
  }
}

/**
 * 스킬 절 하나를 레코드로 바꾼다.
 *
 * **없는 값은 기본값으로 둔다.** 필수로 막으면 스킬 절에 필드를 하나 더할 때마다 옛
 * 콘텐츠 팩이 통째로 안 읽힌다 — 발행된 팩은 되돌릴 수 없다.
 *
 * @param raw 한 줄.
 * @returns 읽어 낸 스킬.
 */
export function buildSkillDef(raw: RawSkill): SkillDef {
  return {
    skillId: raw.id,
    family: raw.family ?? '',
    shape: buildShape(raw.shape),
    targetFaction: raw.target_faction ?? '',
    coefPct: raw.coef_pct ?? DEFAULT_COEF_PCT,
    cooldown: raw.cooldown ?? 0,
    reach: raw.range ?? null,
    telegraph: raw.telegraph ?? 0,
    cancelOnAct: raw.cancel_on_act ?? false,
    cancelOnHit: raw.cancel_on_hit ?? false,
    healPct: raw.heal_pct ?? 0,
    guardPct: raw.guard_pct ?? 0,
    guardTicks: raw.guard_ticks ?? 0,
    tags: raw.tags ?? [],
    effects: (raw.effects ?? []).map((one) => ({
      kind: one.kind ?? '',
      status: one.status ?? '',
      duration: one.duration ?? 0,
    })),
  }
}

/**
 * 스킬 절 전부를 id 로 찾을 수 있게 담는다.
 *
 * @param rows `skills.json` 의 `skills` 배열.
 * @returns id 에서 스킬로의 대응표.
 */
export function loadSkillDefs(rows: readonly RawSkill[]): Map<string, SkillDef> {
  return new Map(rows.map((row) => [row.id, buildSkillDef(row)]))
}

/**
 * 스킬 하나를 찾는다.
 *
 * **모르는 id 도 레코드를 돌려준다.** null 을 돌려주면 부르는 쪽마다 없음 처리가 생기고,
 * 그중 하나가 빠지면 거기서 터진다 — 기본값 레코드는 「아무 특성도 없는 스킬」이라
 * 뜻이 분명하다. 파이썬 `find_skill` 과 같은 계약이다.
 *
 * @param defs 스킬 표.
 * @param skillId 찾을 id.
 * @returns 찾은 스킬. 없으면 기본값만 담긴 레코드.
 */
export function findSkill(defs: ReadonlyMap<string, SkillDef>, skillId: string): SkillDef {
  return defs.get(skillId) ?? buildSkillDef({ id: skillId })
}
