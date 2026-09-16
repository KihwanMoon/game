/**
 * 도감 화면 검사 (E단계).
 *
 * **"내 아이템을 들고 있다" 가 화면에 없으면 사본을 만드는 뜻이 사라진다.** 되찾으러
 * 가는 동기가 도달하지 않으면 World Loop 이 서지 않는다 (docs/설계/6_몬스터 §8).
 *
 * 격자는 가방과 같은 것을 쓴다 (2026-09-16). 칸은 상태만 그리고 규칙표는 고른 칸 아래
 * 한 곳에 편다 — 그래서 **칸에서 볼 것**과 **상세에서 볼 것**을 갈라 본다.
 */

import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { BestiaryDetail, BestiaryPanel, listRuleLines } from './BestiaryPanel'
import { buildBestiaryCells, HOLDS_MINE_MARK } from './bestiaryCells'
import { readBestiary } from '../storage'
import type { BestiaryEntry } from '../storage'

const ENTRIES: readonly BestiaryEntry[] = [
  {
    recordId: 1,
    catalogId: 'goblin_rusher',
    labelKo: '사나운 고블린 돌격병',
    tier: 'ELITE',
    level: 3,
    levelCap: 5,
    zoneFloor: 1,
    entitySlot: 'goblin_rusher_0',
    hpMax: 74,
    attack: 14,
    defense: 3,
    ruleset: {
      rulesetId: 'ai_rusher',
      version: 1,
      rules: [
        {
          priority: 1,
          cpuCost: 1,
          action: 'ATTACK',
          target: 'NEAREST',
          setFlag: null,
          actionParam: null,
          conditions: {
            op: 'SINGLE',
            terms: [
              { lhs: 'target_distance', lhsParam: 'NEAREST', comparison: '<=', rhs: 1 },
            ],
          },
        },
      ],
    },
    affixes: ['사나운'],
    trophies: ['helm_iron'],
    holdsMine: true,
  },
]

const ENTRY = ENTRIES[0] as BestiaryEntry

describe('도감 격자', () => {
  const markup = renderToStaticMarkup(<BestiaryPanel entries={ENTRIES} link="online" />)

  it('★ 내 장비를 들고 있는 개체는 칸에서 보인다 — 되찾기 동기', () => {
    // 표적을 고르는 일이 스크롤이 되면 안 된다. 어느 칸을 눌러야 하는지가 격자에서
    // 보여야 하고, 그 한 글자가 이것이다.
    expect(markup).toContain(HOLDS_MINE_MARK)
    expect(buildBestiaryCells(ENTRIES).map((cell) => cell.marks)).toEqual([[HOLDS_MINE_MARK]])
  })

  it('★ 등급을 색으로 칠하지 않는다 — 글자로 적는다', () => {
    expect(markup).toContain('ELITE')
    expect(markup).not.toContain('brass')
  })

  it('칸 구석은 어느 층인가를 말한다 — 되찾으러 갈 수 있는지가 거기서 갈린다', () => {
    expect(buildBestiaryCells(ENTRIES).map((cell) => [cell.code, cell.countText])).toEqual([
      ['1장', 'lv3'],
    ])
  })

  it('몬스터 그림은 아직 0장이라 칸이 글자로 떨어진다', () => {
    // 아이템 그림표에 몬스터 id 를 넣지 않는다 — 접두사가 겹치는 날 도깨비 칸에 칼이
    // 그려진다 (이문록 재주 칸과 같은 이유).
    expect(buildBestiaryCells(ENTRIES).map((cell) => cell.art)).toEqual([undefined])
  })

  it('★ 아무것도 안 골랐으면 규칙표가 어디서 나오는지 말한다', () => {
    expect(markup).toContain('칸을 고르면 규칙표가 그대로 뜬다')
  })
})

describe('고른 개체의 상세', () => {
  const detail = renderToStaticMarkup(<BestiaryDetail entry={ENTRY} />)

  it('★ 내 장비를 들고 있다고 말한다 — 되찾기 동기', () => {
    expect(detail).toContain('내 장비 보유')
    expect(detail).toContain('helm_iron')
  })

  it('레벨과 상한을 함께 적는다 — 얼마나 더 클 수 있는지가 표적 판단에 든다', () => {
    expect(detail).toContain('lv 3/5')
  })

  it('★ 규칙표를 그대로 낸다 — 줄 수로 접으면 카운터를 설계할 수 없다', () => {
    // 서버는 처음부터 규칙표를 보내고 있었는데 화면이 `rules.length` 로 접어 버렸다.
    // 도감이 표적 목록인 이유가 바로 그 규칙표다 (`설계/6_몬스터` §8).
    // 이제는 접는 버튼조차 없다 — 펴는 자리가 하나면 접을 이유가 없다.
    expect(detail).toContain('규칙표 1줄')
    expect(detail).toContain('ATTACK')
    expect(listRuleLines(ENTRY).join('\n')).toContain('ATTACK')
  })

  it('★ 얼마나 센지도 적는다 — 규칙표만으로는 이길 수 있는지 알 수 없다', () => {
    expect(detail).toContain('hp 74')
    expect(detail).toContain('공 14')
  })

  it('규칙표가 없으면 펼칠 것도 없다 — 카탈로그 기본표가 빈 경우다', () => {
    const bare = { ...ENTRY, ruleset: undefined }
    expect(listRuleLines(bare)).toEqual([])
    expect(renderToStaticMarkup(<BestiaryDetail entry={bare} />)).not.toContain('규칙표')
  })

  it('접사가 붙은 이름으로 개체를 지목한다', () => {
    expect(detail).toContain('사나운 고블린 돌격병')
  })
})

describe('도감 패널 — 빈 경우', () => {
  it('서버 없음과 빈 세계를 구분해서 말한다', () => {
    const offline = renderToStaticMarkup(<BestiaryPanel entries={undefined} link="offline" />)
    const empty = renderToStaticMarkup(<BestiaryPanel entries={[]} link="online" />)
    expect(offline).toContain('서버에 닿지 못했다')
    expect(empty).toContain('아직 비각에 지속 몬스터가 없다')
  })
})

/*
 * 생 hex·자체 `@media` 검사는 여기 없다 — **`editor.css` 전량을 보는 자리가 따로 있다**
 * (`editorRender.test.tsx` 의 hex·px·그림자, `mobileEditor.test.tsx` 의 `@media`).
 *
 * 예전에는 여기서 `css.slice(css.indexOf('/* ── 도감'))` 로 제 구역만 잘라 봤는데, **표지 주석이
 * 바뀌면 `indexOf` 가 -1 이라 마지막 글자 한 개를 검사하고 통과했다.** 못 잡는 검사는
 * 없느니만 못하다 — 초록색으로 「봤다」고 말하기 때문이다. 전량 검사가 이 구역을
 * 포함하므로 지우는 쪽이 맞다.
 */

describe('도감을 읽을 때 종류 id 를 잃지 않는다', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /**
   * 서버가 이런 도감 한 줄을 보냈다고 둔다.
   *
   * @param entry 줄에 덮어쓸 값.
   * @returns fetch 가 낼 응답.
   */
  function stubBestiary(entry: Record<string, unknown>): void {
    const body = {
      entries: [
        {
          record_id: 35,
          catalog_id: 'goblin_rusher',
          label_ko: '몽둥이 도깨비',
          tier: 'NORMAL',
          level: 2,
          level_cap: 5,
          zone_floor: 1,
          entity_slot: 'goblin_rusher_0',
          ruleset: null,
          affixes: [],
          trophies: [],
          holds_mine: false,
          ...entry,
        },
      ],
    }
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) }),
    )
  }

  it('★ catalog_id 를 옮긴다 — 그림을 붙일 열쇠는 이름이 아니라 이것이다', async () => {
    // 이름에는 접사가 앞에 붙어 개체마다 달라진다. 종류를 지목할 수 있는 것은
    // catalog_id 뿐인데, 서버가 내는 것을 매핑이 버리고 있었다.
    stubBestiary({})
    expect((await readBestiary('token'))?.[0]?.catalogId).toBe('goblin_rusher')
  })

  it('구버전 서버가 안 보내면 빈 문자열이다 — 그림만 없고 줄은 읽힌다', async () => {
    stubBestiary({ catalog_id: undefined })
    expect((await readBestiary('token'))?.[0]?.catalogId).toBe('')
  })
})
