/**
 * 자산에서 도감 페이지를 만든다 (SEO — `codexPage` 의 내용 쪽).
 *
 * **여기 있는 것이 색인될 본문 전부다.** 자산의 `_note` 는 원래 다음 사람에게 설계
 * 의도를 남기려고 쓴 글인데, 그것이 곧 「이 몬스터가 무엇이고 어떻게 상대하는가」라
 * 읽을거리로도 성립한다. 새로 쓰지 않고 그것을 편다.
 *
 * **서로 잇는다.** 몬스터 ↔ 재주 ↔ 방을 고리로 묶어야 크롤러가 스물셋을 「낱장」이
 * 아니라 한 덩어리로 본다.
 */
import {
  type CodexPage,
  attachParticle,
  buildArtLinkList,
  buildLinkList,
  buildNote,
  buildStatTable,
  escapeHtml,
  renderPage,
} from './codexPage'

/** balance.json 의 적 한 줄 중 우리가 쓰는 것. */
export interface EnemyRow {
  readonly id: string
  readonly label_ko: string
  readonly type: string
  readonly tier: string
  readonly hp_max: number
  readonly attack: number
  readonly defense: number
  readonly attack_range: number
  readonly initiative: number
  readonly cpu_budget: number
  readonly rule_slots: number
  readonly ruleset_id: string
  readonly _note?: string
}

/** skills.json 의 한 줄 중 우리가 쓰는 것. */
export interface SkillRow {
  readonly id: string
  readonly label_ko?: string
  readonly family?: string
  readonly actor?: string
  readonly coef_pct?: number
  readonly cooldown?: number
  readonly range?: number
  readonly telegraph?: number
  readonly hits?: string
  readonly _note?: string
}

/** enemies.json 의 규칙표 한 벌 중 우리가 쓰는 것. */
export interface EnemyRuleSet {
  readonly ruleset_id: string
  readonly label_ko?: string
  readonly strategy_ko?: string
  readonly rules: readonly { readonly action: string; readonly action_param?: string | null }[]
}

/** items.json 의 한 줄 중 우리가 쓰는 것. */
export interface ItemRow {
  readonly id: string
  readonly label_ko: string
  readonly slot?: string | null
  readonly grants_skill?: string
}

/** 방 템플릿 한 벌 중 우리가 쓰는 것. */
export interface RoomRow {
  readonly id: string
  readonly label_ko: string
  readonly min_floor: number
  readonly enemy_spawns: readonly unknown[]
}

/** 도감을 굽는 데 필요한 자산 전부. */
export interface CodexInput {
  readonly enemies: readonly EnemyRow[]
  readonly skills: readonly SkillRow[]
  readonly rulesets: readonly EnemyRuleSet[]
  readonly rooms: readonly RoomRow[]
  readonly items: readonly ItemRow[]
  /** 종 id 에서 그 그림(SVG 원문)으로. 없는 종은 그림 없이 나간다. */
  readonly monsterArt: ReadonlyMap<string, string>
  /**
   * 재주 id 에서 그 그림으로. **몬스터 표와 갈라 둔다** — 한 표에 담으면 id 가 겹치는
   * 날 재주 장에 도깨비가 그려지고, 지금 안 겹치는 것은 우연이지 규칙이 아니다.
   * 화면 쪽도 같은 이유로 표가 둘이다 (`content/monsterArt.ts`·`content/skillArt.ts`).
   */
  readonly skillArt: ReadonlyMap<string, string>
}

/** 적 유형의 한글 이름. 자산에 없어 화면이 들고 있던 것을 여기서도 쓴다. */
const TYPE_LABELS: ReadonlyMap<string, string> = new Map([
  ['MELEE', '근접형'],
  ['RANGED', '사격형'],
  ['CASTER', '주술형'],
  ['SUMMONER', '소환형'],
  ['HEALER', '치유형'],
  ['BOMBER', '자폭형'],
])

/** 재주가 무엇을 맞히는가의 한글 이름. 영문 id 를 그대로 두면 그 줄만 다른 언어가 된다. */
const HITS_LABELS: ReadonlyMap<string, string> = new Map([
  ['TARGET', '대상 하나'],
  ['HOSTILE_AREA', '주변의 적 전부'],
  ['TILES', '예고한 칸'],
])

/** 등급의 한글 이름. */
const TIER_LABELS: ReadonlyMap<string, string> = new Map([
  ['NORMAL', '보통'],
  ['ELITE', '정예'],
  ['BOSS', '보스'],
])

/**
 * 그 종의 페이지 주소.
 *
 * @param id 종 id.
 * @returns 경로.
 */
export function buildMonsterPath(id: string): string {
  return `/codex/monsters/${id}.html`
}

/**
 * 그 재주의 페이지 주소.
 *
 * @param id 재주 id.
 * @returns 경로.
 */
export function buildSkillPath(id: string): string {
  return `/codex/skills/${id}.html`
}

/**
 * 그 규칙표가 쓰는 재주 id 들.
 *
 * 맨 행동(`SKILL_1`)과 인자꼴(`USE_SKILL[HEX_FIRE]`) 둘 다 재주를 가리킨다 — 둘을
 * 한 축으로 모은 것이 2026-09-19 의 일이고, 여기서도 같은 축으로 읽는다.
 *
 * @param ruleset 적 규칙표.
 * @returns 재주 id 들. 순서는 규칙 순서다.
 */
export function listRulesetSkills(ruleset: EnemyRuleSet): readonly string[] {
  const found: string[] = []
  for (const rule of ruleset.rules) {
    const id = rule.action_param ?? rule.action
    if (!found.includes(id)) {
      found.push(id)
    }
  }
  return found
}

/**
 * 그 종이 나오는 방들.
 *
 * @param rooms 방 템플릿들.
 * @param kindId 종 id.
 * @returns 방들. 층 낮은 순이다.
 */
export function listRoomsOf(rooms: readonly RoomRow[], kindId: string): readonly RoomRow[] {
  return rooms
    .filter((room) => JSON.stringify(room.enemy_spawns).includes(`"${kindId}"`))
    .slice()
    .sort((left, right) => left.min_floor - right.min_floor)
}

/**
 * 몬스터 한 마리의 페이지.
 *
 * @param enemy 적 한 줄.
 * @param input 자산 전부.
 * @returns 구운 페이지.
 */
export function buildMonsterPage(enemy: EnemyRow, input: CodexInput): CodexPage {
  const type = TYPE_LABELS.get(enemy.type) ?? enemy.type
  const tier = TIER_LABELS.get(enemy.tier) ?? enemy.tier
  const art = input.monsterArt.get(enemy.id)
  const ruleset = input.rulesets.find((one) => one.ruleset_id === enemy.ruleset_id)
  const skillNames = new Map(input.skills.map((one) => [one.id, one.label_ko ?? one.id]))
  const usedSkills = ruleset === undefined ? [] : listRulesetSkills(ruleset)
  const skillLinks = usedSkills
    .filter((id) => skillNames.has(id))
    .map((id) => [buildSkillPath(id), skillNames.get(id) ?? id] as const)
  const rooms = listRoomsOf(input.rooms, enemy.id)
  const description = `${enemy.label_ko} — ${type} ${tier}. 체력 ${String(enemy.hp_max)} · 공격 ${String(enemy.attack)} · 사거리 ${String(enemy.attack_range)}.`

  const body = [
    `<article class="cx">`,
    art === undefined ? '' : `<div class="cx__art">${art}</div>`,
    `<h1>${escapeHtml(enemy.label_ko)}</h1>`,
    `<p class="cx__kind">${escapeHtml(type)} · ${escapeHtml(tier)}</p>`,
    buildStatTable([
      ['체력', String(enemy.hp_max)],
      ['공격력', String(enemy.attack)],
      ['방어력', String(enemy.defense)],
      ['사거리', String(enemy.attack_range)],
      ['선공', String(enemy.initiative)],
      ['CPU 예산', String(enemy.cpu_budget)],
      ['규칙 슬롯', String(enemy.rule_slots)],
    ]),
    enemy._note === undefined ? '' : `<section class="cx__note">${buildNote(enemy._note)}</section>`,
    ruleset?.strategy_ko === undefined
      ? ''
      : `<section class="cx__note"><h2>어떻게 싸우는가</h2>${buildNote(ruleset.strategy_ko)}</section>`,
    skillLinks.length === 0 ? '' : `<section><h2>쓰는 재주</h2>${buildLinkList(skillLinks)}</section>`,
    rooms.length === 0
      ? ''
      : `<section><h2>나오는 방</h2><p>${rooms
          .map((room) => `${escapeHtml(room.label_ko)}(${String(room.min_floor)}장)`)
          .join(' · ')}</p></section>`,
    `</article>`,
  ]
    .filter((part) => part !== '')
    .join('\n      ')

  return {
    path: buildMonsterPath(enemy.id),
    html: renderPage({ title: enemy.label_ko, description, path: buildMonsterPath(enemy.id), body }),
  }
}

/**
 * 수치를 문장으로 편다.
 *
 * **설명문이 없는 재주가 있다.** 기본 공격·일격 같은 것들인데, 표만 있는 장은 사람에게도
 * 크롤러에게도 얇다. 표에 적힌 것을 한 문장으로 다시 말하면 읽을 것이 생기고, 그 문장은
 * 자산에서 바로 나오므로 손으로 적은 설명과 갈릴 일이 없다.
 *
 * @param name 재주 이름.
 * @param skill 재주 한 줄.
 * @param hits 판정의 한글 이름.
 * @returns 한 문장.
 */
export function buildSkillSentence(name: string, skill: SkillRow, hits: string): string {
  const coef = skill.coef_pct ?? 0
  const telegraph = skill.telegraph ?? 0
  const cooldown = skill.cooldown ?? 0
  const hit =
    coef === 0
      ? `${hits}에 걸린다`
      : `${attachParticle(hits, '을', '를')} 공격력의 ${String(coef)}% 로 친다`
  const wait = telegraph === 0 ? '쓰는 그 틱에 나간다' : `${String(telegraph)}틱 동안 자리를 예고한 뒤 터진다`
  const rest = cooldown === 0 ? '쿨타임이 없다' : `다시 쓰려면 ${String(cooldown)}틱을 기다린다`
  return `${attachParticle(name, '은', '는')} ${hit}. ${wait}. ${rest}.`
}

/**
 * 재주 하나의 페이지.
 *
 * @param skill 재주 한 줄.
 * @param input 자산 전부.
 * @returns 구운 페이지.
 */
export function buildSkillPage(skill: SkillRow, input: CodexInput): CodexPage {
  const name = skill.label_ko ?? skill.id
  const art = input.skillArt.get(skill.id)
  const telegraph = skill.telegraph ?? 0
  const reach = skill.range ?? undefined
  const hits = skill.hits ?? 'TARGET'
  const users = input.enemies.filter((enemy) => {
    const ruleset = input.rulesets.find((one) => one.ruleset_id === enemy.ruleset_id)
    return ruleset !== undefined && listRulesetSkills(ruleset).includes(skill.id)
  })
  // **이 재주를 여는 장비.** 설명문이 없는 기본 재주는 이것 말고 적을 것이 없고,
  // 「무엇을 껴야 쓰나」는 읽는 사람이 실제로 찾는 것이다.
  const openers = input.items.filter((item) => item.grants_skill === skill.id)
  const description = `${name} — ${skill.actor === 'enemy' ? '적 전용' : '플레이어'} 재주. 계수 ${String(skill.coef_pct ?? 0)}% · 쿨타임 ${String(skill.cooldown ?? 0)}틱${telegraph > 0 ? ` · 예고 ${String(telegraph)}틱` : ''}.`

  const body = [
    `<article class="cx">`,
    art === undefined ? '' : `<div class="cx__art">${art}</div>`,
    `<h1>${escapeHtml(name)}</h1>`,
    `<p class="cx__kind">${escapeHtml(skill.actor === 'enemy' ? '적 전용' : '플레이어')}</p>`,
    `<p>${escapeHtml(buildSkillSentence(name, skill, HITS_LABELS.get(hits) ?? hits))}</p>`,
    buildStatTable([
      ['계수', `${String(skill.coef_pct ?? 0)}%`],
      ['쿨타임', `${String(skill.cooldown ?? 0)}틱`],
      // **`?? ` 로 받는다.** 자산이 「없음」을 `null` 로 적는데 `undefined` 만 보면
      // 화면에 글자 `null` 이 찍힌다 — 실제로 찍혔다.
      ['사거리', reach === undefined ? '무기 사거리' : String(reach)],
      ['예고', telegraph === 0 ? '즉발' : `${String(telegraph)}틱`],
      ['맞는 곳', HITS_LABELS.get(hits) ?? hits],
    ]),
    skill._note === undefined || skill._note === ''
      ? ''
      : `<section class="cx__note">${buildNote(skill._note)}</section>`,
    users.length === 0
      ? ''
      : `<section><h2>쓰는 몬스터</h2>${buildLinkList(
          users.map((one) => [buildMonsterPath(one.id), one.label_ko] as const),
        )}</section>`,
    openers.length === 0
      ? ''
      : `<section><h2>이 재주를 여는 장비</h2><p>${openers
          .map((item) => escapeHtml(item.label_ko))
          .join(' · ')}</p></section>`,
    skill.actor === 'enemy'
      ? '<section><h2>고를 수 있는가</h2><p>적만 쓰는 재주다. 규칙 편집기의 재주 목록에는 뜨지 않고, 이문록이 적의 규칙표를 펴서 보여 줄 때만 이름이 나온다.</p></section>'
      : '',
    `</article>`,
  ]
    .filter((part) => part !== '')
    .join('\n      ')

  return {
    path: buildSkillPath(skill.id),
    html: renderPage({ title: name, description, path: buildSkillPath(skill.id), body }),
  }
}

/**
 * 도감 첫 장. **모든 낱장이 여기서 한 번은 이어진다.**
 *
 * @param input 자산 전부.
 * @returns 구운 페이지.
 */
export function buildCodexIndex(input: CodexInput): CodexPage {
  // **첫 장은 고리 마흔 개가 서는 자리다.** 글자만 있으면 훑어지지 않으므로 낱장이
  // 이미 들고 있는 그림을 여기에도 세운다 — 새 자산이 아니라 같은 도트다.
  const monsters = buildArtLinkList(
    input.enemies.map((one) => ({
      path: buildMonsterPath(one.id),
      name: one.label_ko,
      art: input.monsterArt.get(one.id),
    })),
  )
  const skills = buildArtLinkList(
    input.skills.map((one) => ({
      path: buildSkillPath(one.id),
      name: one.label_ko ?? one.id,
      art: input.skillArt.get(one.id),
    })),
  )
  const body = [
    `<article class="cx">`,
    `<h1>도감</h1>`,
    `<p>비각에 나오는 몬스터 ${String(input.enemies.length)}종과 재주 ${String(input.skills.length)}가지를 적어 둔다. 수치는 1장 기준이며, 한 장 내려갈 때마다 적의 체력과 공격이 함께 오른다.</p>`,
    `<section><h2>몬스터 ${String(input.enemies.length)}종</h2>${monsters}</section>`,
    `<section><h2>재주 ${String(input.skills.length)}가지</h2>${skills}</section>`,
    `</article>`,
  ].join('\n      ')
  return {
    path: '/codex/',
    html: renderPage({
      title: '도감',
      description: `비각의 몬스터 ${String(input.enemies.length)}종과 재주 ${String(input.skills.length)}가지 — 수치와 상대법.`,
      path: '/codex/',
      body,
    }),
  }
}

/**
 * 도감 전부를 굽는다.
 *
 * @param input 자산 전부.
 * @returns 페이지들. 첫 장이 맨 앞이다.
 */
export function buildCodexPages(input: CodexInput): readonly CodexPage[] {
  return [
    buildCodexIndex(input),
    ...input.enemies.map((one) => buildMonsterPage(one, input)),
    ...input.skills.map((one) => buildSkillPage(one, input)),
  ]
}
