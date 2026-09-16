/**
 * 목록 틀 검사 — **보이는 글자와 줄 수만 본다.**
 *
 * 클래스 이름을 검사에 적으면, 화면을 이 틀로 옮길 때 이름이 하나 바뀌는 것만으로
 * 빨개진다 — 그러면 다음 사람은 검사를 고치고 지나가고, 검사는 계약이 아니라 통행세가
 * 된다. 그래서 여기서 확인하는 것은 **사람이 읽는 글자**와 **줄이 몇 개 그려졌는가** 다.
 * (마크업 구조를 보는 자리는 둘뿐이다 — `<li>` 를 세는 것과 `ul`/`ol` 을 가르는 것.
 * 둘 다 이름이 아니라 HTML 요소라 옮겨도 안 바뀐다.)
 *
 * 여섯을 덮는다.
 *
 * 1. **빈 목록** — 정말 없을 때의 문구. 「불러오는 중」은 여기 오지 않는다(틀 밖의 일).
 * 2. **거르기 0건** — 빈 목록과 **다른 문구**여야 한다. 같은 문구로 적으면 가진 것을
 *    질의가 가리고 있다는 사실이 사라지고, 사람은 목록이 빈 줄 알고 떠난다.
 * 3. **더 보기** — `pageSize` 를 준 목록에만 선다. 고정 길이 목록에 서면 「뒤에 더
 *    있다」는 거짓말이 된다.
 * 4. **개수 표기** — 세는 것은 보이는 줄이 아니라 걸린 줄이다.
 * 5. **줄 앞 그림** — 주면 서고 안 주면 안 선다.
 * 6. **ol 번호** — 번호가 뜻인 목록이 있다. 틀이 글머리를 지우면 그 뜻이 사라진다.
 *
 * 부정 검사(`not.toContain`)는 혼자 두지 않는다. 같은 글자가 실제로 나오는 렌더를 짝으로
 * 붙여, 찾는 글자가 썩으면 짝이 먼저 빨개지게 한다 — 이 저장소가 실제로 앓던 병이다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DataList, describeFilterMiss, formatRowCount } from './DataList'
import type { DataListProps } from './DataList'

/** 검사용 줄. 이름 하나면 「무엇이 몇 줄 나왔는가」를 보기에 충분하다. */
interface Gear {
  readonly id: number
  readonly name: string
  readonly slot: string
}

const GEARS: readonly Gear[] = [
  { id: 1, name: '철 투구', slot: 'HEAD' },
  { id: 2, name: '가죽 갑옷', slot: 'BODY' },
  { id: 3, name: '철 장검', slot: 'WEAPON_MAIN' },
  { id: 4, name: '철 단검', slot: 'WEAPON_OFF' },
  { id: 5, name: '가죽 신', slot: 'FEET' },
]

const EMPTY_TEXT = '아직 아무것도 없다'

/** 투구 자리의 두 글자 코드(`Thumb`). 그림이 아직 없을 때 칸에 그려지는 글자다. */
const HEAD_CODE = 'HD'

/**
 * 그려진 줄 수를 센다.
 *
 * 클래스가 아니라 `<li>` 요소를 센다 — 화면이 줄에 무슨 클래스를 주든 줄은 줄이다.
 *
 * @param markup 정적 마크업.
 * @returns `<li>` 개수.
 */
function countRows(markup: string): number {
  return markup.match(/<li[\s>]/g)?.length ?? 0
}

/**
 * 주석을 걷어 낸 스타일 시트를 읽는다.
 *
 * @param name 파일 이름.
 * @returns 주석이 빠진 내용.
 */
function readStrippedCss(name: string): string {
  const path = fileURLToPath(new URL(name, import.meta.url))
  return readFileSync(path, 'utf-8').replace(/\/\*[\s\S]*?\*\//g, '')
}

/**
 * 장비 목록을 마크업 문자열로 굽는다.
 *
 * @param extra 이 검사가 더 줄 것. 기본은 이름만 적는 줄이다.
 * @returns 정적 마크업.
 */
function renderGears(extra: Partial<DataListProps<Gear>> = {}): string {
  return renderToStaticMarkup(
    <DataList<Gear>
      items={GEARS}
      rowKey={(gear, index) => `${String(gear.id)}-${String(index)}`}
      renderRow={(gear) => <span>{gear.name}</span>}
      emptyText={EMPTY_TEXT}
      {...extra}
    />,
  )
}

describe('목록 틀 — 빈 상태', () => {
  it('★ 하나도 없으면 빈 목록 문구만 적고 줄을 안 그린다', () => {
    // 「불러오는 중」·「못 닿았다」는 여기 오지 않는다 — 틀은 문구 하나만 받고,
    // 그 넷은 화면이 `LinkNoticeLine` 으로 밖에서 가른다.
    const markup = renderGears({ items: [] })
    expect(markup).toContain(EMPTY_TEXT)
    expect(countRows(markup)).toBe(0)
  })

  it('★ 거르기가 0건이면 빈 목록과 다른 문구를 적고 전체 수를 남긴다', () => {
    // 여기서 `EMPTY_TEXT` 가 뜨면 가진 것을 질의가 가리고 있다는 사실이 사라진다.
    // 그 문구가 실제로 살아 있다는 것은 바로 위 검사가 보증한다.
    const markup = renderGears({
      filterText: (gear) => gear.name,
      defaultQuery: '놋쇠',
    })
    expect(markup).toContain('걸리는 줄이 없다')
    expect(markup).toContain('전체 5줄')
    expect(markup).toContain('놋쇠')
    expect(markup).not.toContain(EMPTY_TEXT)
    expect(countRows(markup)).toBe(0)
  })

  it('단위를 바꾸면 조사도 따라간다 — 「자료가 없다」', () => {
    // 조사를 박아 두면 단위를 바꾼 화면에서 문장이 어색해진다.
    const markup = renderGears({
      unit: '자료',
      filterText: (gear) => gear.name,
      defaultQuery: '놋쇠',
    })
    expect(markup).toContain('걸리는 자료가 없다')
    expect(markup).toContain('전체 5자료')
  })

  it('거르기에 걸린 줄만 남는다', () => {
    const markup = renderGears({ filterText: (gear) => gear.name, defaultQuery: '가죽' })
    expect(countRows(markup)).toBe(2)
    expect(markup).toContain('가죽 갑옷')
    expect(markup).not.toContain('철 투구')
  })
})

describe('목록 틀 — 개수와 페이지', () => {
  it('★ 개수는 걸린 줄을 센다 — 페이지가 잘라 낸 것은 없는 것이 아니다', () => {
    const markup = renderGears({ showCount: true, pageSize: 2 })
    expect(markup).toContain('5줄')
    expect(countRows(markup)).toBe(2)
  })

  it('★ 거르면 걸린 수와 전체 수를 함께 적는다', () => {
    const markup = renderGears({
      showCount: true,
      filterText: (gear) => gear.name,
      defaultQuery: '가죽',
    })
    expect(markup).toContain('2줄 — 전체 5줄')
  })

  it('하나도 없으면 개수를 안 적는다 — 「0줄」은 빈 목록 문구와 겹친다', () => {
    // 「5줄」이 실제로 나가는 것은 위의 개수 검사가 보증한다.
    const markup = renderGears({ items: [], showCount: true })
    expect(markup).toContain(EMPTY_TEXT)
    expect(markup).not.toContain('0줄')
  })

  it('★ pageSize 를 준 목록에만 「더 보기」가 서고, 남은 수를 적는다', () => {
    const paged = renderGears({ pageSize: 2 })
    expect(paged).toContain('더 보기')
    expect(paged).toContain('남은 3줄')
    expect(countRows(paged)).toBe(2)
  })

  it('★ 고정 길이 목록에는 「더 보기」가 안 선다 — 뒤에 더 있다는 거짓말이 된다', () => {
    // 「더 보기」가 실제로 나가는 것은 바로 위 검사가 보증한다.
    const whole = renderGears({})
    expect(whole).not.toContain('더 보기')
    expect(countRows(whole)).toBe(5)
  })

  it('한 장에 다 들어가면 「더 보기」가 안 선다', () => {
    const markup = renderGears({ pageSize: 5 })
    expect(markup).not.toContain('더 보기')
    expect(countRows(markup)).toBe(5)
  })
})

describe('목록 틀 — 줄 앞 그림', () => {
  it('★ 그림을 주면 줄 앞에 서고, 안 주면 안 선다', () => {
    const withThumb = renderGears({
      items: [GEARS[0] as Gear],
      thumb: (gear) => ({ kind: gear.slot, label: gear.name }),
    })
    const without = renderGears({ items: [GEARS[0] as Gear] })
    expect(withThumb).toContain(HEAD_CODE)
    expect(without).not.toContain(HEAD_CODE)
    // 그림이 서든 말든 줄이 적는 것은 같다.
    expect(withThumb).toContain('철 투구')
    expect(without).toContain('철 투구')
  })

  it('그림 주소는 있는 줄에만 붙는다 — `exactOptionalPropertyTypes` 로 넘긴다', () => {
    // 화면이 들고 있는 값은 대개 `string | undefined` 다. 그것을 그대로 넘길 수 있어야
    // 화면마다 조건부 전개를 복사하지 않는다.
    const art: string | undefined = '/art/helm.svg'
    const markup = renderGears({
      items: [GEARS[0] as Gear],
      thumb: (gear) => ({ kind: gear.slot, label: gear.name, art }),
    })
    expect(markup).toContain('/art/helm.svg')
  })
})

describe('목록 틀 — 컨테이너', () => {
  it('★ ol 을 고르면 번호를 안 지운다 — 번호가 뜻인 목록이 있다', () => {
    const ordered = renderGears({ as: 'ol', items: GEARS.slice(0, 3) })
    const plain = renderGears({ items: GEARS.slice(0, 3) })
    expect(ordered).toContain('<ol')
    expect(ordered).not.toContain('<ul')
    expect(plain).toContain('<ul')
    expect(countRows(ordered)).toBe(3)

    // 번호는 글자가 아니라 글머리라 마크업에 안 나온다. 지워지는 자리는 CSS 하나뿐이다.
    // `slice(indexOf(…))` 로 떼지 않는다 — 못 찾은 것(-1)과 찾았는데 빈 것이 구별되지
    // 않아, 그 위의 검사가 아무것도 안 보면서 통과한다.
    const block = /\.dlist__rows--ol\s*\{([^}]*)\}/.exec(readStrippedCss('editor.css'))
    expect(block).not.toBeNull()
    expect(block?.[1] ?? '').toContain('list-style: decimal')
  })

  it('화면이 준 클래스가 목록에 붙는다 — 격자로 세는 화면이 있다', () => {
    // 틀이 `display` 를 정하면 격자 화면이 못 옮겨 온다. 붙는지만 본다.
    const markup = renderGears({ listClass: 'invg' })
    expect(markup).toContain('invg')
  })

  it('중복될 수 있는 값에도 줄이 다 그려진다 — 키에 index 가 든다', () => {
    // 접사 목록처럼 같은 글자가 두 번 오는 자리가 있다. 값만으로 키를 만들면 React 가
    // 같은 줄로 보고 하나를 지운다.
    const twins: readonly Gear[] = [
      { id: 7, name: '예리함', slot: '' },
      { id: 7, name: '예리함', slot: '' },
    ]
    const markup = renderGears({ items: twins, rowKey: (gear, index) => `${gear.name}-${String(index)}` })
    expect(countRows(markup)).toBe(2)
  })
})

describe('목록 틀 — 문구', () => {
  it('거르기 0건 문구는 친 글자와 전체 수를 함께 적는다', () => {
    expect(describeFilterMiss('놋쇠', 12, '줄')).toBe('「놋쇠」에 걸리는 줄이 없다 — 전체 12줄')
  })

  it('개수는 거르는 중일 때만 전체를 덧붙인다 — 늘 적으면 소음이다', () => {
    expect(formatRowCount(5, 5, '줄')).toBe('5줄')
    expect(formatRowCount(2, 5, '줄')).toBe('2줄 — 전체 5줄')
  })
})
