/**
 * 관리자 화면 검사.
 *
 * **가장 먼저 보는 것은 「안 보이는가」다.** 관리자가 아니면 서버가 404 로 답하므로
 * 현황이 undefined 로 남고, 그때 이 패널은 아무것도 그리면 안 된다 — 빈 패널이라도
 * 그리면 관리자 경로가 있다는 사실이 드러난다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { AdminOverview } from '../storage'
import { AdminPanel } from './AdminPanel'

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

function render(overview: AdminOverview | undefined, detail = '') {
  return renderToStaticMarkup(
    <AdminPanel
      overview={overview}
      detail={detail}
      onSetMonsterLevel={() => undefined}
      onIntervene={() => undefined}
    />,
  )
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
    expect(html).toContain('풀린 화폐')
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
    expect(html).toContain('레벨 1')
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
})
