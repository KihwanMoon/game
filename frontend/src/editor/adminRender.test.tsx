/**
 * 관리자 화면 검사.
 *
 * **가장 먼저 보는 것은 「안 보이는가」다.** 관리자가 아니면 서버가 404 로 답하므로
 * 현황이 undefined 로 남고, 그때 이 패널은 아무것도 그리면 안 된다 — 빈 패널이라도
 * 그리면 관리자 경로가 있다는 사실이 드러난다. 다만 **못 닿은 것은 404 가 아니다**:
 * 그때는 관리자인지 아닌지 아직 아무도 모르므로 한 줄로 그렇게 적는다.
 *
 * 목록은 클래스가 아니라 **사람이 읽는 글자**와 **`<li>` 가 몇 개 그려졌는가**로 본다.
 * 이름으로 검사를 쓰면 화면을 틀 위로 옮길 때 이름 하나에 빨개지고, 그러면 다음 사람은
 * 검사를 고치고 지나간다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { findItemArt } from '../content/itemArt'
import type { AdminActionRow, AdminHeldItem, AdminMonsterRow, AdminOverview } from '../storage'
import { AdminPanel } from './AdminPanel'
import type { LinkState } from './linkState'

const OVERVIEW: AdminOverview = {
  accounts: 42,
  registered: 7,
  monstersAlive: 3,
  items: 18,
  itemsBound: 5,
  itemsHeldByMonsters: 2,
  listingsOpen: 4,
  currencyTotal: 1234,
  verifiedRuns: 99,
  catalogItems: 11,
  enemyKinds: 8,
  coreVersion: 'b5.v2.e1',
  levelCounts: [
    { level: 1, count: 30 },
    { level: 4, count: 2 },
  ],
  monsters: [
    {
      recordId: 7,
      catalogId: 'goblin_archer',
      tier: 'ELITE',
      zoneFloor: 1,
      entitySlot: 'w1',
      level: 3,
      levelCap: 5,
      alive: true,
      heldItems: 2,
    },
  ],
  heldItems: [
    {
      itemId: 5,
      recordId: 7,
      monsterId: 'goblin_archer',
      catalogId: 'sword_short',
      takenFromHandle: '떠돌이',
      isBroken: false,
      isBound: false,
    },
  ],
  recentActions: [
    {
      handle: '관리자',
      action: 'monster.level',
      target: '#7 goblin_archer',
      detail: '1 → 3',
      createdAt: '2026-08-30T00:00:00+00:00',
    },
  ],
}

/**
 * 마크업에 실제로 붙은 그림 주소들.
 *
 * **주소를 날것으로 찾으면 안 잡힌다.** 그림이 data URI 라 안에 작은따옴표가 들어 있고,
 * React 가 그것을 `&#x27;` 로 적는다 — 그래서 제대로 붙어 있어도 `toContain` 이 못 찾는다.
 */
function listArt(html: string): string[] {
  return [...html.matchAll(/class="ds-thumb__art" src="([^"]*)"/g)].map((hit) =>
    (hit[1] ?? '').replaceAll('&#x27;', "'"),
  )
}

function render(overview: AdminOverview | undefined, detail = '', link?: LinkState) {
  return renderToStaticMarkup(
    <AdminPanel
      overview={overview}
      detail={detail}
      // 조건부 전개다. `exactOptionalPropertyTypes` 아래에서 `link={undefined}` 는
      // 「안 줬다」가 아니라 타입 오류이고, 안 준 것이 곧 기본값(`online`)이다.
      {...(link === undefined ? {} : { link })}
      onSetMonsterLevel={() => undefined}
      onIntervene={() => undefined}
    />,
  )
}

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
 * 지속 몬스터를 여러 줄 만든다.
 *
 * @param count 만들 줄 수.
 * @returns 줄들. 이름이 하나씩 다르다.
 */
function makeMonsters(count: number): AdminMonsterRow[] {
  const first = OVERVIEW.monsters[0] as AdminMonsterRow
  return Array.from({ length: count }, (_unused, index) => ({
    ...first,
    recordId: index + 1,
    catalogId: `goblin_${String(index)}`,
  }))
}

/**
 * 몬스터가 든 장비를 여러 줄 만든다.
 *
 * @param count 만들 줄 수.
 * @returns 줄들.
 */
function makeHeldItems(count: number): AdminHeldItem[] {
  const first = OVERVIEW.heldItems[0] as AdminHeldItem
  return Array.from({ length: count }, (_unused, index) => ({ ...first, itemId: index + 1 }))
}

/**
 * 개입 기록을 여러 줄 만든다.
 *
 * @param count 만들 줄 수.
 * @returns 줄들.
 */
function makeActions(count: number): AdminActionRow[] {
  const first = OVERVIEW.recentActions[0] as AdminActionRow
  return Array.from({ length: count }, (_unused, index) => ({
    ...first,
    target: `#${String(index)} goblin_archer`,
  }))
}

/**
 * 레벨 분포를 여러 줄 만든다.
 *
 * @param count 만들 줄 수.
 * @returns 레벨 1부터 한 줄씩.
 */
function makeLevels(count: number): { level: number; count: number }[] {
  return Array.from({ length: count }, (_unused, index) => ({ level: index + 1, count: 1 }))
}

describe('관리자가 아니면', () => {
  it('★ 아무것도 그리지 않는다 — 빈 패널도 경로의 존재를 알려 준다', () => {
    expect(render(undefined)).toBe('')
  })
})

describe('세계 현황', () => {
  it('★ 지금까지 볼 방법이 아예 없던 값들이 보인다', () => {
    const html = render(OVERVIEW)
    expect(html).toContain('지속 몬스터')
    expect(html).toContain('풀린 푼')
    expect(html).toContain('1234')
  })

  it('★ 몬스터가 남의 장비를 들고 있는 것이 보인다', () => {
    // 되찾으러 가는 동기가 World Loop 의 전부다 (설계/6_몬스터 §5).
    expect(render(OVERVIEW)).toContain('몬스터 보유')
    expect(render(OVERVIEW)).toContain('아이템 2')
  })

  it('★ 몬스터 레벨에 상한이 함께 적힌다 — 상한 없이는 높은 값인지 알 수 없다', () => {
    expect(render(OVERVIEW)).toContain('lv 3/5')
  })

  it('★ 콘텐츠는 읽기 전용이라고 화면이 말한다', () => {
    // 런타임에 바꾸면 이미 발급된 티켓이 다른 게임을 가리킨다 (결정 #06, R5).
    expect(render(OVERVIEW)).toContain('읽기 전용')
    expect(render(OVERVIEW)).toContain('resources')
  })

  it('★ 개입 기록이 보인다 — 남지 않으면 왜 이렇게 됐는지 아무도 답 못 한다', () => {
    const html = render(OVERVIEW)
    expect(html).toContain('monster.level')
    expect(html).toContain('1 → 3')
  })

  it('레벨 분포가 보인다 — 평균만 보면 한 사람이 멀리 간 것과 구분이 안 된다', () => {
    const html = render(OVERVIEW)
    expect(html).toContain('lv 1')
    expect(html).toContain('30명')
  })

  it('거절 사유를 그대로 띄운다', () => {
    expect(render(OVERVIEW, '레벨은 1 이상 5 이하다')).toContain('레벨은 1 이상 5 이하다')
  })
})

describe('개입 2단계', () => {
  it('★ 몬스터가 든 것과 원주인이 보인다 — 되찾으러 갈 동기가 그것이다', () => {
    const html = render(OVERVIEW)
    expect(html).toContain('sword_short')
    expect(html).toContain('떠돌이')
  })

  it('★ 회수는 사유 칸과 함께 있다 — 사유 없이 누를 수 있으면 원장이 알리바이가 된다', () => {
    const html = render(OVERVIEW)
    expect(html).toContain('회수')
    expect(html).toContain('placeholder="사유"')
  })

  it('빼앗긴 것이 없으면 그렇게 적는다 — 빈 목록은 고장으로 읽힌다', () => {
    expect(render({ ...OVERVIEW, heldItems: [] })).toContain('아직 빼앗긴 장비가 없다')
  })

  it('★ 빼앗긴 것에 그림이 붙는다 — `sword_short` 는 읽어야 알고 스무 줄이면 안 읽는다', () => {
    // 주소까지 못 박는다. 클래스 이름만 보면 아무 그림이나 붙어도 통과한다.
    expect(listArt(render(OVERVIEW))).toEqual([findItemArt('sword_short')])
  })

  it('그림이 없는 형태는 글자로 떨어진다 — 없는 그림을 기다리느라 줄이 비면 안 된다', () => {
    // 아직 안 그린(혹은 규약 밖) 접두사. 이때 Thumb 은 분류 코드를 그린다.
    const html = render({
      ...OVERVIEW,
      heldItems: OVERVIEW.heldItems.map((row) => ({ ...row, catalogId: 'gizmo_odd' })),
    })
    expect(html).not.toContain('ds-thumb__art')
    expect(html).toContain('EQ')
  })
})

describe('관리 현황을 언제 읽는가', () => {
  it('★ **접속하자마자 읽는다** — 안 읽으면 권한을 줘도 탭이 안 생긴다', () => {
    // 예전에는 refreshWorld() 안에서만 불렀는데, 그것은 경매를 조작해야 돈다.
    // 그래서 관리자 권한을 줘도 화면에 아무 일이 없었다.
    const source = readFileSync(fileURLToPath(new URL('../App.tsx', import.meta.url)), 'utf8')
    // 계정 상태는 loadAccountState 한 자리에서 읽는다 — 갈라 두면 한쪽만 고치고 끝난다.
    const boot = source.slice(source.indexOf('const token = await ensureToken'))
    expect(boot.slice(0, boot.indexOf('readServerMeta'))).toContain('loadAccountState')
    const loader = source.slice(source.indexOf('async function loadAccountState'))
    expect(loader.slice(0, loader.indexOf('\n  }'))).toContain('readAdminOverview')
  })

  it('★ 로그인 뒤에도 다시 읽는다 — 계정이 바뀌면 권한도 바뀐다', () => {
    // 관리자로 로그인해도 안 뜨거나, 관리자에서 일반 계정으로 갈아탔는데 남아 있으면
    // 둘 다 틀렸다.
    const source = readFileSync(fileURLToPath(new URL('../App.tsx', import.meta.url)), 'utf8')
    const login = source.slice(source.indexOf('async function applyLogin'))
    expect(login.slice(0, login.indexOf('return \'\''))).toContain('loadAccountState')
  })
})

describe('현황이 없을 때', () => {
  it('★ 못 닿은 것과 404 를 가른다 — 한 값으로 접으면 「못 닿았다」조차 안 뜬다', () => {
    // 404 는 "관리자가 아니다" 이고 그때만 아무것도 그리지 않는다. 못 닿았거나 아직
    // 물어보는 중이면 관리자인지 아닌지 **아직 아무도 모른다** — 그 상태의 빈 화면은
    // 고장과 구별되지 않는다.
    expect(render(undefined, '', 'offline')).toContain('서버에 닿지 못했다')
    expect(render(undefined, '', 'probing')).toContain('서버에 연결하는 중이다')
    expect(render(undefined, '', 'online')).toBe('')
  })

  it('확인 중을 위험으로 적지 않는다 — 매번 뜨는 경보는 아무도 안 읽는다', () => {
    expect(render(undefined, '', 'probing')).not.toContain('서버에 닿지 못했다')
  })
})

describe('긴 목록', () => {
  it('★ 200줄이 와도 한 번에 펴지 않는다 — 다 쏟으면 찾는 길이 브라우저 찾기뿐이다', () => {
    const many = render({ ...OVERVIEW, monsters: makeMonsters(200) })
    expect(many).toContain('더 보기 · 남은 190줄')
    // 한 줄이던 목록이 열 줄이 됐다. 200줄이 아니다.
    expect(countRows(many) - countRows(render(OVERVIEW))).toBe(9)
  })

  it('★ 레벨 분포는 상한이 없다 — 곡선이 길어지는 만큼 줄이 늘어서 페이지를 켠다', () => {
    expect(render({ ...OVERVIEW, levelCounts: makeLevels(30) })).toContain('더 보기 · 남은 10줄')
  })

  it('★ 고정 길이 목록에는 「더 보기」가 안 선다 — 뒤에 더 있다는 거짓말이 된다', () => {
    // 요약 아홉 줄·콘텐츠 두 줄은 서버가 늘 같은 수로 준다. 그 글자가 실제로 뜬다는
    // 것은 바로 위 두 검사가 보증한다.
    expect(render(OVERVIEW)).not.toContain('더 보기')
  })

  it('★ 거르기는 긴 목록 둘에만 선다 — 고정 길이 목록에 내밀면 거를 것이 없다', () => {
    const html = render(OVERVIEW)
    expect(html).toContain('이름·장으로 거르기')
    expect(html).toContain('이름·원주인으로 거르기')
    // 지속 몬스터와 보유 장비, 둘뿐이다.
    expect(html.match(/type="search"/g)?.length).toBe(2)
  })
})

describe('상한에 닿았을 때', () => {
  it('★ 잘린 사실을 적는다 — 200이 전부인 것처럼 적히면 세는 사람이 틀린 수를 든다', () => {
    // 요약이 센 전체(212)와 실려 온 줄(200)이 다르다. 그 차이가 화면 어디에도 없으면
    // "몬스터 보유 212" 옆에 200줄짜리 목록이 나란히 서고, 아무도 그것을 못 읽는다.
    const html = render({ ...OVERVIEW, heldItems: makeHeldItems(200), itemsHeldByMonsters: 212 })
    expect(html).toContain('잘렸다')
    expect(html).toContain('전체 212줄')
  })

  it('전체 수를 모르는 목록도 잘렸다고는 적는다 — 몰라서 침묵하면 200이 전부가 된다', () => {
    // 몬스터 목록은 죽은 것까지 실어 오는데 요약은 살아 있는 것만 센다. 그래서 여기엔
    // 줄 수 있는 전체가 없다.
    expect(render({ ...OVERVIEW, monsters: makeMonsters(200) })).toContain('잘렸다')
  })

  it('목록마다 상한이 다르다 — 최근 개입은 50에서 잘린다', () => {
    expect(render({ ...OVERVIEW, recentActions: makeActions(50) })).toContain(
      '상한 50줄에서 잘렸다',
    )
  })

  it('★ 상한 아래면 안 적는다 — 늘 붙어 있는 줄은 읽히지 않는다', () => {
    expect(render(OVERVIEW)).not.toContain('잘렸다')
  })
})
