/**
 * 재주 한 줄이 가진 칸들 — 규격 한 벌 (2026-09-19).
 *
 * **머리줄과 값줄이 어긋나지 않게 한 곳에서 선언한다.** `SkillTable` 이 원래 적어 둔
 * 걱정이 그것이다: 고칠 칸을 하나 늘리면 값줄에는 입력칸이 서는데 머리줄을 따로 적어
 * 두면 거기만 안 따라오고, 그 뒤로 모든 값이 한 칸씩 밀린 채 읽힌다.
 *
 * **고르는 칸의 항목은 「구현된 것」만 담는다.** 예전에는 `family`·`shape`·
 * `target_faction` 을 통째로 잠갔고 사유가 「실행기가 읽는 구조라 바꾸면 조용히 아무 일도
 * 안 한다」였다. 자유 입력이면 그 말이 맞다 — 그러나 **고르개는 없는 값을 못 고른다.**
 * 잠그는 대신 고를 수 있는 것을 줄이는 쪽이, 같은 사고를 막으면서 화면을 쓸 수 있게 한다.
 *
 * 그 사유를 칸마다 `why` 에 적어 둔다. 화면이 **표 위에 한 번** 보여 주므로,
 * 항목 이름은 짧은 말만 든다 — 항목마다 설명을 달면 칸이 넓어져 표가 가로로 길어진다.
 */

/** 칸이 받는 값의 종류. 화면이 무엇을 그릴지 이것으로 가른다. */
const DECIMAL_RADIX = 10

export type SkillFieldKind = 'number' | 'text' | 'select' | 'toggle' | 'tags'

/** 고르는 칸 하나의 항목. */
export interface SkillFieldOption {
  readonly value: string
  readonly label: string
}

/** 재주 칸 하나의 규격. */
export interface SkillField {
  /** 절 안의 자리. 점으로 중첩을 적는다 (`shape.kind`). */
  readonly path: string
  /** 머리줄에 적을 말. */
  readonly label: string
  readonly kind: SkillFieldKind
  readonly options?: readonly SkillFieldOption[]
  /** 비워 둘 수 있는가. `range` 가 그렇다 — 비면 무기 사거리를 쓴다. */
  readonly nullable?: boolean
  /** 왜 이 항목뿐인가. 화면이 그대로 보여 준다. */
  readonly why?: string
}

/**
 * 형태. **예고형에서 실제로 갈리는 것은 셋뿐이다** —
 * `telegraph_cast.build_cast_tiles` 가 `CHAIN`·`LINE` 만 따로 보고 나머지는 전부
 * 반경으로 읽는다. 즉발은 실행기가 `SINGLE`·`AREA`·`SELF` 로 갈린다.
 */
const SHAPE_OPTIONS: readonly SkillFieldOption[] = [
  { value: 'SINGLE', label: '단일' },
  { value: 'AREA', label: '범위' },
  { value: 'LINE', label: '직선' },
  { value: 'CHAIN', label: '연쇄' },
  { value: 'SELF', label: '자신' },
]

/**
 * 누가 맞는가 (`sim/targeting`). **셋 다 실행기가 있다** — 예전에는 같은 `AREA` 인데
 * 즉발은 적만, 예고형은 진영 없이 맞혀서 데이터로는 구별이 안 됐다.
 */
const HITS_OPTIONS: readonly SkillFieldOption[] = [
  { value: 'TARGET', label: '대상' },
  { value: 'HOSTILE_AREA', label: '반경 적' },
  { value: 'TILES', label: '칸 전부' },
]

/**
 * 거는 상태. **`STUN` 은 없다** — 인지 변수 목록과 팔레트에는 있는데 엔진이 아무
 * 데서도 안 읽는다(`simulation/plan` 의 상태 셋만 구현돼 있다). 고를 수 있게 두면
 * 「걸었는데 아무 일도 안 나는」 재주를 만들게 된다.
 */
const STATUS_OPTIONS: readonly SkillFieldOption[] = [
  { value: '', label: '없음' },
  { value: 'POISON', label: '중독' },
  { value: 'SLOW', label: '둔화' },
  { value: 'ROOT', label: '이동불가' },
]

/** 시전 중 다른 행동을 어떻게 할 것인가 (`cast_policy`). */
const CAST_OPTIONS: readonly SkillFieldOption[] = [
  { value: 'LOCK', label: '잠금' },
  { value: 'HOLD', label: '버팀' },
  { value: 'CANCEL', label: '취소' },
  { value: 'FREE', label: '자유' },
]

/** 대상 진영. 셀렉터 검증이 이것을 본다 (`rules/validator`). */
const FACTION_OPTIONS: readonly SkillFieldOption[] = [
  { value: 'enemy', label: '적' },
  { value: 'ally', label: '아군' },
  { value: 'self', label: '자신' },
]

/** 누가 쓰는가. 빈 값이면 양쪽이고, `enemy` 면 규칙 팔레트에서 빠진다. */
const ACTOR_OPTIONS: readonly SkillFieldOption[] = [
  { value: '', label: '양쪽' },
  { value: 'enemy', label: '적 전용' },
]

/**
 * 계열. **아무 데서도 안 읽힌다** — 실행기는 `family` 를 안 보고 행동 id 와 `shape` 로
 * 갈린다. 그래서 고쳐도 게임이 안 바뀐다: 사람이 표를 읽는 이름표다.
 */
const FAMILY_OPTIONS: readonly SkillFieldOption[] = [
  { value: 'ATTACK', label: 'ATTACK' },
  { value: 'STATUS', label: 'STATUS' },
  { value: 'UTILITY', label: 'UTILITY' },
  { value: 'GUARD', label: 'GUARD' },
]

/**
 * 분류 이름표. **`SCROLL` 은 없다** — 그쪽은 소모품 태그이고 여기는 재주다.
 * 복수로 고른다.
 */
export const TAG_OPTIONS: readonly SkillFieldOption[] = [
  { value: 'MAGIC', label: 'MAGIC' },
  { value: 'CAST', label: 'CAST' },
  { value: 'AOE', label: 'AOE' },
  { value: 'CONTROL', label: 'CONTROL' },
  { value: 'MELEE', label: 'MELEE' },
  { value: 'RANGED', label: 'RANGED' },
  { value: 'BASIC', label: 'BASIC' },
  { value: 'SUPPORT', label: 'SUPPORT' },
  { value: 'SHIELD', label: 'SHIELD' },
]

/**
 * 표가 그리는 칸들. **순서가 곧 화면의 순서다.**
 *
 * 이름 → 성질(누가·계열·형태·진영) → 수치 → 시전 → 분류 순으로 둔다. 고치는 사람이
 * 「무엇인가」를 먼저 정하고 「얼마나」를 나중에 정하기 때문이다.
 */
export const SKILL_FIELDS: readonly SkillField[] = [
  { path: 'label_ko', label: '한글 이름', kind: 'text' },
  {
    path: 'actor',
    label: '주인',
    kind: 'select',
    options: ACTOR_OPTIONS,
    why: '적 전용은 규칙 팔레트에서 빠진다 (ENEMY_ONLY_SKILL_IDS).',
  },
  {
    path: 'family',
    label: '계열',
    kind: 'select',
    options: FAMILY_OPTIONS,
    why: '아무 데서도 안 읽힌다 — 사람이 표를 읽는 이름표다.',
  },
  {
    path: 'shape.kind',
    label: '형태',
    kind: 'select',
    options: SHAPE_OPTIONS,
    why: '예고형은 연쇄·직선만 따로 보고 나머지는 반경으로 읽는다.',
  },
  {
    path: 'target_faction',
    label: '진영',
    kind: 'select',
    options: FACTION_OPTIONS,
    why: '셀렉터 검증이 이것을 본다 — 어긋나면 그 규칙이 거절된다.',
  },
  {
    path: 'hits',
    label: '맞는 것',
    kind: 'select',
    options: HITS_OPTIONS,
    why: '「칸 전부」는 진영을 안 가린다 — 아군도 시전자도 맞는다 (예고가 좌표에 떨어지기 때문이다).',
  },
  { path: 'coef_pct', label: '계수%', kind: 'number' },
  { path: 'shape.radius', label: '반경', kind: 'number' },
  { path: 'cooldown', label: '쿨', kind: 'number' },
  { path: 'range', label: '사거리', kind: 'number', nullable: true, why: '비우면 무기 사거리를 쓴다.' },
  {
    path: 'telegraph',
    label: '선·예고',
    kind: 'number',
    why: '터지기 전 굳는 틱. 0 이면 즉발이고 1 이상이면 붉은 칸이 먼저 선다.',
  },
  {
    path: 'recover',
    label: '후·경직',
    kind: 'number',
    why: '터진 뒤 굳는 틱. 쿨타임과 다르다 — 쿨은 그 재주를 다시 쓰기까지이고 이것은 아무것도 못 하는 시간이다.',
  },
  {
    path: 'cast_act',
    label: '시전 규율',
    kind: 'select',
    options: CAST_OPTIONS,
    why: '예고가 0 이면 아무 뜻이 없다.',
  },
  {
    path: 'cancel_on_hit',
    label: '피격 취소',
    kind: 'toggle',
    why: '시전 규율과 별개 축이다 — 잠겨 있어도 맞으면 끊긴다.',
  },
  {
    path: 'effects.0.status',
    label: '거는 상태',
    kind: 'select',
    options: STATUS_OPTIONS,
    why: '즉발도 예고형도 같은 핵이 얹는다 (2026-09-19 이전에는 예고형에만 걸렸다).',
  },
  { path: 'effects.0.duration', label: '상태 틱', kind: 'number', nullable: true },
  {
    path: 'heal_pct',
    label: '회복%',
    kind: 'number',
    nullable: true,
    why: '대상 최대 체력의 정수 퍼센트. 고정값이 아닌 이유는 회복이 덩치에 비례해야 해서다.',
  },
  { path: 'guard_pct', label: '감쇠%', kind: 'number', nullable: true },
  { path: 'guard_ticks', label: '감쇠 틱', kind: 'number', nullable: true },
  { path: 'tags', label: '분류', kind: 'tags', options: TAG_OPTIONS },
]

/** 머리줄이 쓸 이름들. id 칸을 앞에 세운다. */
export const SKILL_COLUMNS: readonly string[] = ['id', ...SKILL_FIELDS.map((one) => one.label)]

/**
 * 절에서 그 칸의 값을 읽는다. 점으로 중첩을 따라간다.
 *
 * @param row 재주 한 줄.
 * @param path 칸의 자리 (`shape.kind`).
 * @returns 값. 없으면 undefined.
 */
export function readFieldValue(row: Record<string, unknown>, path: string): unknown {
  let at: unknown = row
  for (const step of path.split('.')) {
    if (at === null || typeof at !== 'object') {
      return undefined
    }
    at = (at as Record<string, unknown>)[step]
  }
  return at
}

/**
 * 화면이 그릴 글자. **타입마다 빈 값의 뜻이 다르다** — 수치의 빈칸은 「안 정함」이고
 * 글의 빈칸은 「이름이 없다」다.
 *
 * @param row 재주 한 줄.
 * @param field 칸 규격.
 * @returns 입력칸에 넣을 글자.
 */
export function readFieldText(row: Record<string, unknown>, field: SkillField): string {
  const value = readFieldValue(row, field.path)
  if (value === null || value === undefined) {
    return ''
  }
  if (Array.isArray(value)) {
    return value.map(String).join(',')
  }
  return String(value)
}

/**
 * 고친 값을 절에 다시 넣는다. 중첩 경로를 따라가며 **지나는 객체를 복사한다.**
 *
 * @param row 재주 한 줄.
 * @param path 칸의 자리.
 * @param value 넣을 값.
 * @returns 새 절.
 */
function applyFieldValue(node: unknown, path: string, value: unknown): unknown {
  const [head, ...rest] = path.split('.')
  if (head === undefined) {
    return node
  }
  // **배열은 배열로 돌려준다.** 객체처럼 펴면 `effects` 가 `{0: {...}}` 가 되고, 그
  // 절은 코어의 로더가 못 읽는다 — 초안 검증에서야 걸리므로 그 전까지 조용하다.
  if (Array.isArray(node)) {
    const at = Number.parseInt(head, DECIMAL_RADIX)
    if (Number.isNaN(at)) {
      return node
    }
    const copy = [...node]
    // 없는 칸을 가리키면 빈 절을 세운다 — 「상태가 아직 없는 재주」에 처음 다는 자리다.
    copy[at] = rest.length === 0 ? value : applyFieldValue(copy[at] ?? {}, rest.join('.'), value)
    return copy
  }
  const record = (node ?? {}) as Record<string, unknown>
  if (rest.length === 0) {
    return { ...record, [head]: value }
  }
  // 다음 조각이 숫자면 배열 자리다. 없으면 배열로 연다.
  const nextIsIndex = !Number.isNaN(Number.parseInt(rest[0] ?? '', DECIMAL_RADIX))
  const nested = record[head] ?? (nextIsIndex ? [] : {})
  return { ...record, [head]: applyFieldValue(nested, rest.join('.'), value) }
}

/**
 * 들어온 글자를 그 칸의 타입으로 바꾼다.
 *
 * **못 바꾸면 undefined 를 낸다** — 부르는 쪽이 옛 값을 그대로 둔다. 숫자 칸에 글자를
 * 넣었다고 절이 깨지면 안 된다: 화면이 거절하는 것과 데이터가 망가지는 것은 다르다.
 *
 * @param field 칸 규격.
 * @param text 사람이 넣은 글자.
 * @returns 넣을 값. 타입이 안 맞으면 undefined.
 */
export function parseFieldInput(field: SkillField, text: string): unknown {
  const trimmed = text.trim()
  if (field.kind === 'number') {
    if (trimmed === '') {
      // 비울 수 있는 칸만 null 이 된다. 아니면 옛 값을 지킨다.
      return field.nullable === true ? null : undefined
    }
    const parsed = Number.parseInt(trimmed, DECIMAL_RADIX)
    return Number.isNaN(parsed) ? undefined : parsed
  }
  if (field.kind === 'toggle') {
    return trimmed === 'true'
  }
  if (field.kind === 'tags') {
    return trimmed === '' ? [] : trimmed.split(',').map((one) => one.trim()).filter(Boolean)
  }
  if (field.kind === 'select') {
    const known = (field.options ?? []).some((one) => one.value === trimmed)
    return known ? trimmed : undefined
  }
  return text
}

/**
 * 파일 안의 재주 하나를 고친다.
 *
 * **그 재주만 바꾸고 나머지는 원본 객체 그대로 둔다.** 통째로 다시 쓰면 `_note` 처럼
 * 아무도 안 읽지만 사람이 적어 둔 것이 사라진다.
 *
 * @param file 스킬 파일 절.
 * @param skillId 고칠 재주.
 * @param field 고칠 칸.
 * @param text 사람이 넣은 글자.
 * @returns 새 파일 절. 타입이 안 맞으면 받은 것을 그대로 돌려준다.
 */
export function buildSkillFile(
  file: Record<string, unknown>,
  skillId: string,
  field: SkillField,
  text: string,
): Record<string, unknown> {
  const value = parseFieldInput(field, text)
  if (value === undefined) {
    return file
  }
  const rows = (file.skills ?? []) as Record<string, unknown>[]
  return {
    ...file,
    skills: rows.map((row) =>
      String(row.id) === skillId
        ? (applyFieldValue(row, field.path, value) as Record<string, unknown>)
        : row,
    ),
  }
}
