/**
 * 카탈로그 관리 화면.
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **삭제 버튼이 없다.** 지우면 과거 기록을 못 읽는다.
 * 2. **폐기된 것도 보인다.** 폐기는 「없다」가 아니라 「새로 안 나온다」다.
 * 3. **세대가 눈에 있다.** 고치면 순위표 시즌이 갈린다 — 누르기 전에 알아야 한다.
 * 4. **못 고치는 것을 못 고친다고 적는다.** 서버만 막으면 「왜 안 되지」가 된다.
 * 5. **긴 목록에 찾기와 한 장이 있다.** 쉰 종이 한 번에 깔리면 폰에서는 스크롤이 곧
 *    찾기가 된다 — 배치는 검사가 못 보므로 **구조**를 잰다: 틀이 섰는가, 찾기 칸이
 *    있는가, 줄이 그려지는가, 한 장에서 끊기는가.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import {
  CatalogAdminPanel,
  CatalogDetail,
  CatalogForm,
  buildAffixPayload,
  buildAffixRows,
  buildRowFromSpec,
  listAffixStats,
} from './CatalogAdminPanel'
import { GRID_PAGE } from './SlotBoard'
import type { CatalogAdminView } from '../storage'

const VIEW: CatalogAdminView = {
  generation: 7,
  grades: ['COMMON', 'FINE', 'RELIC'],
  stats: ['hp_max', 'attack', 'defense', 'attack_range', 'initiative', 'cpu_budget'],
  items: [
    {
      catalogId: 'helm_iron',
      kind: 'EQUIPMENT',
      labelKo: '철 투구',
      slot: 'HEAD',
      hands: '',
      grade: 'COMMON',
      minFloor: 1,
      isRetired: false,
      affixes: ['튼튼함 +8'],
      affixRows: [{ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함' }],
      requirements: [],
      grantsSkill: '',
      attackRange: 0,
      useTag: '',
      dropWeight: 1,
    },
    {
      catalogId: 'old_blade',
      kind: 'EQUIPMENT',
      labelKo: '옛 검',
      slot: 'WEAPON_MAIN',
      hands: 'ONE',
      grade: 'FINE',
      minFloor: 3,
      isRetired: true,
      affixes: [],
      affixRows: [],
      requirements: [],
      grantsSkill: '',
      attackRange: 0,
      useTag: '',
      dropWeight: 0,
    },
    {
      catalogId: 'potion_heal',
      kind: 'CONSUMABLE',
      labelKo: '회복 물약',
      slot: '',
      hands: '',
      grade: 'COMMON',
      minFloor: 1,
      isRetired: false,
      affixes: [],
      affixRows: [],
      requirements: [],
      grantsSkill: '',
      attackRange: 0,
      useTag: 'POTION',
      dropWeight: 1,
    },
    {
      catalogId: 'bow_long',
      kind: 'EQUIPMENT',
      labelKo: '장궁',
      slot: 'WEAPON_MAIN',
      hands: 'TWO',
      grade: 'COMMON',
      minFloor: 1,
      isRetired: false,
      affixes: ['날카로움 +3'],
      affixRows: [{ stat: 'attack', flat: 3, percent: 0, labelKo: '날카로움' }],
      requirements: [],
      grantsSkill: '',
      attackRange: 4,
      useTag: '',
      dropWeight: 1,
    },
  ],
}

/**
 * 픽스처에서 한 줄을 찾는다.
 *
 * **자리 번호로 안 찾는다.** 줄을 하나 끼우면 뒤엣것이 다 밀려서, 「사거리 검사」가 물약을
 * 보게 된다 — 실제로 그렇게 빨개졌다.
 *
 * @param catalogId 찾을 id.
 * @returns 그 줄.
 */
function findRow(catalogId: string) {
  const found = VIEW.items.find((item) => item.catalogId === catalogId)
  if (found === undefined) {
    throw new Error(`픽스처에 없다: ${catalogId}`)
  }
  return found
}

/**
 * 그려진 줄들의 이름.
 *
 * **마크업을 통째로 박지 않는다.** 예전에는 격자가 그리던 `span` 한 줄을 그대로 박아
 * 두어, 같은 목록을 공용 틀로 옮기는 것만으로 검사가 빨개졌다 — 지키려던 것은 「그 줄이
 * 목록에 그려진다」이지 그 태그가 아니다.
 *
 * @param html 그려진 마크업.
 * @returns 줄 이름들. 페이지가 자른 것은 안 들어온다.
 */
function listRowNames(html: string): readonly string[] {
  return [...html.matchAll(/class="ds-cell__name">([^<]*)</g)].map((hit) => hit[1] ?? '')
}

/**
 * 그려진 줄 수.
 *
 * @param html 그려진 마크업.
 * @returns 줄 수. `ds-cell__hit` 은 안 센다 — 칸 하나에 버튼이 하나다.
 */
function countRows(html: string): number {
  return [...html.matchAll(/class="ds-cell"/g)].length
}

const noop = () => undefined
const MARKUP = renderToStaticMarkup(
  <CatalogAdminPanel catalog={VIEW} detail="" onRetire={noop} onEdit={noop}
        onCreate={noop} />,
)

describe('카탈로그 관리', () => {
  it('★ 삭제 버튼이 없다 — 지우면 원장이 가리키는 id 가 사라진다', () => {
    expect(MARKUP).not.toContain('삭제')
  })

  it('★ 폐기된 것도 목록에 남는다 — 되살릴 수 있어야 한다', () => {
    expect(listRowNames(MARKUP)).toContain('옛 검')
    expect(MARKUP).toContain('폐기')
  })

  it('★ 세대가 머리에 있다 — 고치면 순위표 시즌이 갈린다', () => {
    expect(MARKUP).toContain('세대 7')
    expect(MARKUP).toContain('순위표 시즌이 갈린다')
  })

  it('★ 못 고치는 것을 못 고친다고 적는다 — 서버만 막으면 「왜 안 되지」가 된다', () => {
    // **고르기 전에 있어야 한다.** 상세 안에 두면 규칙을 아는 시점이 늦고, 그때는 이미
    // 거절을 한 번 겪은 뒤다.
    expect(MARKUP).toContain('새 id 로 등록하고 옛 id 를 폐기한다')
  })

  it('★ 서버가 없으면 그렇게 말한다 — 빈 카탈로그와 못 불러온 카탈로그는 다르다', () => {
    const html = renderToStaticMarkup(
      <CatalogAdminPanel catalog={undefined} detail="" onRetire={noop} onEdit={noop}
        onCreate={noop} />,
    )
    expect(html).toContain('서버에 닿지 못했다')
  })

  it('★ 거절 사유를 그대로 적는다 — 서버가 답을 알고 있다', () => {
    const html = renderToStaticMarkup(
      <CatalogAdminPanel
        catalog={VIEW}
        detail="이미 나온 아이템이 소급해 바뀐다 — 새 id 로 등록한다"
        onRetire={noop}
        onEdit={noop}
        onCreate={noop}
      />,
    )
    expect(html).toContain('새 id 로 등록한다')
  })
})

describe('신규 등록 폼', () => {
  it('★ 등록 길이 화면에 있다 — 수정이 막혀 있으니 등록이 유일한 변경 경로다', () => {
    expect(MARKUP).toContain('새 종류 등록')
    expect(MARKUP).toContain('등록')
  })

  it('★ 서버가 아는 슬롯 이름을 그대로 쓴다 — 화면이 새 이름을 지으면 서버가 못 읽는다', () => {
    for (const slot of ['WEAPON_MAIN', 'HEAD', 'BODY', 'FEET', 'HANDS']) {
      expect(MARKUP).toContain(slot)
    }
  })

  it('★ 등급을 서버가 준 목록에서 고른다 — 화면이 목록을 들고 있으면 갈린다', () => {
    for (const grade of VIEW.grades) {
      expect(MARKUP).toContain(grade)
    }
  })

  it('★ id 가 없으면 잠긴다 — 이름 없는 아이템은 원장만 더럽힌다', () => {
    const html = renderToStaticMarkup(
      <CatalogForm grades={VIEW.grades} stats={VIEW.stats} onCreate={() => undefined} />,
    )
    expect(html).toContain('disabled')
  })

  it('★ 등록도 새 id 로 하라는 안내가 붙는다 — 수정이 막힌 이유가 여기서 이어진다', () => {
    expect(MARKUP).toContain('새로 등록하고 옛 id 를 폐기한다')
  })
})

describe('접사 입력 (JSON 을 손으로 치지 않는다)', () => {
  it('★ 능력치를 목록에서 고른다 — 오타 난 능력치는 아무 효과가 없다', () => {
    const html = renderToStaticMarkup(
      <CatalogForm grades={VIEW.grades} stats={VIEW.stats} onCreate={() => undefined} />,
    )
    expect(html).toContain('<select')
    expect(html).toContain('attack_range')
  })

  it('★ 빈 줄은 안 보낸다 — 아무 효과 없는 접사가 붙고 이름만 뜬다', () => {
    const rows = [
      { stat: 'attack', flat: '3', percent: '', labelKo: '예리함' },
      { stat: 'defense', flat: '', percent: '', labelKo: '' },
    ]
    const payload = buildAffixPayload(rows)
    expect(payload).toHaveLength(1)
    expect(payload[0]).toEqual({ stat: 'attack', flat: 3, percent: 0, label_ko: '예리함' })
  })

  it('★ 이름을 안 적으면 비워 둔 채로 보낸다 — 능력치 키를 박으면 게임에서 영어로 뜬다', () => {
    // 예전에는 여기서 `hp_max` 를 이름으로 박았고, 그 아이템이 가방에서 「hp_max +8」 로
    // 보였다. 이름이 없으면 서버가 능력치의 한글 이름(「최대체력」)으로 적는다.
    const payload = buildAffixPayload([{ stat: 'hp_max', flat: '8', percent: '', labelKo: '' }])
    expect(payload[0]?.label_ko).toBe('')
  })

  it('줄 하나만 고친다 — 나머지 칸이 같이 지워지면 못 쓴다', () => {
    const rows = [
      { stat: 'attack', flat: '1', percent: '', labelKo: 'a' },
      { stat: 'defense', flat: '2', percent: '', labelKo: 'b' },
    ]
    const next = buildAffixRows(rows, 1, { flat: '9' })
    expect(next[0]).toBe(rows[0])
    expect(next[1]?.flat).toBe('9')
    expect(next[1]?.labelKo).toBe('b')
  })
})

describe('이름·최소 장 고치기', () => {
  const first = VIEW.items[0]
  if (first === undefined) {
    throw new Error('픽스처가 비었다')
  }
  const picked = renderToStaticMarkup(
    <CatalogDetail
      row={first}
      grades={VIEW.grades}
      stats={VIEW.stats}
      onRetire={noop}
      onEdit={noop}
    />,
  )

  it('★ 이름 칸이 있다 — 없어서 이름은 고칠 방법이 아예 없었다', () => {
    expect(picked).toContain('aria-label="아이템 이름"')
  })

  it('★ 최소 장 칸이 있다 — 「+1」 버튼만으로는 되돌릴 수도 없었다', () => {
    // **입력 칸을 직접 본다.** 그냥 "최소 장" 을 찾으면 버튼의 title 이 그 말을 담고 있어
    // 칸을 지워도 검사가 통과한다 — 실제로 그렇게 통과했다.
    expect(picked).toContain('aria-label="최소 장"')
  })

  it('★ 고치기 버튼이 있다', () => {
    expect(picked).toContain('고치기')
  })
})


describe('수치·특성 편집 (설계/4_아이템 §15.11)', () => {
  const first = VIEW.items[0]
  if (first === undefined) {
    throw new Error('픽스처가 비었다')
  }
  const html = renderToStaticMarkup(
    <CatalogDetail
      row={first}
      grades={VIEW.grades}
      stats={VIEW.stats}
      onRetire={noop}
      onEdit={noop}
    />,
  )

  it('★ 등급을 고를 수 있다 — 인스턴스가 자기 등급을 갖게 된 뒤로 열렸다', () => {
    for (const grade of VIEW.grades) {
      expect(html).toContain(grade)
    }
  })

  it('★ 접사를 고치는 길이 있다 — 없으면 "수치를 못 바꾼다" 가 그대로다', () => {
    expect(html).toContain('접사 고치기')
  })

  it('★ 편집 칸이 **능력치 축을 그대로** 받는다 — 적힌 문자열에서 되돌리면 축이 사라진다', () => {
    // 「튼튼함 +8」 에는 hp_max 가 안 담겨 있다. 그것만 보고 칸을 채우면 축이 목록의 첫
    // 항목으로 떨어지고, 이름만 고치려던 편집이 hp_max 접사를 attack 으로 바꿔 저장한다.
    const row = buildRowFromSpec({ stat: 'hp_max', flat: 8, percent: 0, labelKo: '튼튼함' })
    expect(row.stat).toBe('hp_max')
    expect(row.labelKo).toBe('튼튼함')
    expect(row.flat).toBe('8')
    expect(row.percent).toBe('')
  })

  it('퍼센트 접사는 퍼센트 칸으로 간다 — 둘 다 채우면 값이 두 번 붙는다', () => {
    const row = buildRowFromSpec({ stat: 'cpu_budget', flat: 0, percent: -25, labelKo: '굼뜬 제어' })
    expect(row.percent).toBe('-25')
    expect(row.flat).toBe('')
    expect(row.stat).toBe('cpu_budget')
  })
})

describe('능력치 목록의 정본 (설계/4_아이템 §9)', () => {
  it('★ 서버가 준 목록을 쓴다 — 화면이 정본을 들고 있으면 서버가 늘려도 안 보인다', () => {
    expect(listAffixStats(['attack', 'defense'])).toEqual(['attack', 'defense'])
  })

  it('서버가 아직 안 줬으면 바닥값으로 그린다 — 빈 칸이 뜨면 아무것도 못 고른다', () => {
    expect(listAffixStats([]).length).toBeGreaterThan(0)
  })

  it('★ 서버가 준 이름이 실제로 칸에 뜬다 — 목록만 만들고 안 쓰면 그대로다', () => {
    const html = renderToStaticMarkup(
      <CatalogForm grades={VIEW.grades} stats={['probe_stat']} onCreate={() => undefined} />,
    )
    expect(html).toContain('probe_stat')
  })
})


describe('무기 사거리 (설계/4_아이템 §2.2)', () => {
  const helm = findRow('helm_iron')
  const bow = findRow('bow_long')

  it('★ 무기에 사거리 칸이 있다 — 접사로 흉내내면 굴림에서 잘려 활이 근접무기가 된다', () => {
    const html = renderToStaticMarkup(
      <CatalogDetail
        row={bow}
        grades={VIEW.grades}
        stats={VIEW.stats}
        onRetire={noop}
        onEdit={noop}
      />,
    )
    expect(html).toContain('aria-label="사거리"')
  })

  it('★ 무기가 아니면 사거리 칸이 없다 — 투구의 사거리는 아무 뜻도 없다', () => {
    const html = renderToStaticMarkup(
      <CatalogDetail
        row={helm}
        grades={VIEW.grades}
        stats={VIEW.stats}
        onRetire={noop}
        onEdit={noop}
      />,
    )
    expect(html).not.toContain('aria-label="사거리"')
  })

  it('★ 빈 칸은 지금 값을 보여 준다 — 0 으로 보이면 못 때리는 무기로 읽힌다', () => {
    const html = renderToStaticMarkup(
      <CatalogDetail
        row={bow}
        grades={VIEW.grades}
        stats={VIEW.stats}
        onRetire={noop}
        onEdit={noop}
      />,
    )
    expect(html).toContain('placeholder="4"')
  })

  it('★ 목록 요약이 사거리를 적는다 — 무기를 고를 때 첫 번째로 궁금한 값이다', () => {
    const html = renderToStaticMarkup(
      <CatalogDetail
        row={bow}
        grades={VIEW.grades}
        stats={VIEW.stats}
        onRetire={noop}
        onEdit={noop}
      />,
    )
    expect(html).toContain('사거리 4')
  })
})


describe('소모품의 쓰임새 (설계/4_아이템 §4)', () => {
  const potion = findRow('potion_heal')
  const bow = findRow('bow_long')

  const draw = (row: (typeof VIEW.items)[number]) =>
    renderToStaticMarkup(
      <CatalogDetail
        row={row}
        grades={VIEW.grades}
        stats={VIEW.stats}
        onRetire={noop}
        onEdit={noop}
      />,
    )

  it('★ 소모품에 쓰임새 칸이 있다 — 이것이 `USE_ITEM[kind]` 가 가리키는 값이다', () => {
    expect(draw(potion)).toContain('aria-label="쓰임새"')
  })

  it('★ 무기에는 쓰임새 칸이 없다 — 장검의 쓰임새는 아무 뜻도 없다', () => {
    expect(draw(bow)).not.toContain('aria-label="쓰임새"')
  })

  it('★ 쓰임새가 없으면 그 사실을 말한다 — 조용히 비면 왜 못 쓰는지 알 길이 없다', () => {
    const bare = { ...potion, useTag: '' }
    expect(draw(bare)).toContain('어느 내력도 못 쓴다')
  })
})


describe('목록 틀 (긴 목록의 바깥은 DataList 가 진다)', () => {
  // 쉰 종이 실제 크기다. 한 장(24)보다 길어야 「한 장에서 끊기는가」를 잴 수 있다.
  const HELM = findRow('helm_iron')
  const LONG: CatalogAdminView = {
    ...VIEW,
    items: Array.from({ length: GRID_PAGE + 6 }, (_, at) => ({
      ...HELM,
      catalogId: `helm_${String(at)}`,
      labelKo: `철 투구 ${String(at)}`,
    })),
  }
  const longHtml = renderToStaticMarkup(
    <CatalogAdminPanel catalog={LONG} detail="" onRetire={noop} onEdit={noop} onCreate={noop} />,
  )

  it('★ 찾기 칸이 있다 — 쉰 종을 스크롤로 훑고 있었다', () => {
    expect(MARKUP).toContain('class="dlist__find"')
    expect(MARKUP).toContain('aria-label="이름·분류로 찾기"')
  })

  it('★ 줄이 그려진다 — 틀만 서고 칸이 안 그려지면 빈 목록과 같다', () => {
    expect(listRowNames(MARKUP)).toEqual(VIEW.items.map((item) => item.labelKo))
  })

  it('★ 격자로 깐다 — 틀은 `display` 를 안 정하므로 안 주면 한 줄씩 쌓인다', () => {
    expect(MARKUP).toContain('ds-cells')
    expect(countRows(MARKUP)).toBe(VIEW.items.length)
  })

  it('★ 고름이 보조 기술에도 간다 — 색·명도만으로 알리지 않는다', () => {
    expect(MARKUP).toContain('aria-pressed="false"')
  })

  it('★ 그림이 그대로 뜬다 — 틀로 옮기면서 떨어뜨리면 자리 코드만 남는다', () => {
    // 「여기 그림 없잖아」(2026-09-17)를 잡던 것은 소스를 훑는 검사였는데, 그것은
    // `<Thumb` 이 이 파일에 있을 때만 돈다. 틀로 옮긴 뒤에는 이 자리가 그것을 진다.
    expect(MARKUP).toContain('ds-thumb__art')
    // 칸 그림이라 `md` 다. 줄 앞 그림(`sm`)으로 떨어지면 옮기는 김에 그림이 작아진다.
    expect(MARKUP).toContain('ds-thumb--md')
  })

  it('★ 한 장씩 깐다 — 전부 깔면 고른 칸의 상세와 등록 폼이 화면 밖이다', () => {
    expect(countRows(longHtml)).toBe(GRID_PAGE)
    expect(longHtml).toContain('더 보기')
    expect(longHtml).toContain(`남은 ${String(LONG.items.length - GRID_PAGE)}종`)
  })

  it('★ 거른 뒤에도 전체가 몇인지 함께 적는다 — 질의가 가린 것을 「없다」로 읽는다', () => {
    expect(MARKUP).toContain(`${String(VIEW.items.length)}종`)
  })

  it('★ 짧고 길이가 고정인 목록에는 「더 보기」가 없다 — 뒤에 더 있다는 거짓말이 된다', () => {
    // 분류 셋 · 자리 여섯 · 등급 셋 · 접사 줄. 접사는 자르면 더 나쁘다 — 보이는 줄을
    // 페이지가 줄이면 누른 줄과 갈리는 줄이 어긋나 **옆 줄을 갈아 버린다**.
    const form = renderToStaticMarkup(
      <CatalogForm grades={VIEW.grades} stats={VIEW.stats} onCreate={noop} />,
    )
    expect(form).not.toContain('더 보기')
    expect(form).not.toContain('class="dlist__find"')
    // 한 장보다 짧은 카탈로그에도 안 선다.
    expect(MARKUP).not.toContain('더 보기')
  })
})
