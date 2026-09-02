/**
 * 층 보상 안내 검사 (로드맵 W14).
 *
 * **서버는 이미 주고 있었다.** 층 경계마다 정산이 돌아 화폐·경험치·전리품이 들어오는데,
 * 그 결과가 뜨는 자리는 편집기뿐이라 플레이 중에는 무엇을 벌었는지 알 수 없었다.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { FloorRewardNotice, formatFloorReward } from './FloorRewardNotice'

describe('층 보상 안내', () => {
  it('★ 몇 층에서 벌었는지 함께 적는다 — 층 없이 적으면 어느 층 것인지 알 수 없다', () => {
    expect(formatFloorReward(3, '화폐 +85 · 경험치 +40')).toBe('3층 정산 — 화폐 +85 · 경험치 +40')
  })

  it('★ 정산한 층이 없으면 안 적는다 — 늘 떠 있으면 방금 들어온 것과 구별이 안 된다', () => {
    expect(formatFloorReward(0, '화폐 +85')).toBe('')
  })

  it('★ 벌어들인 것이 없으면 안 적는다 — 빈 줄은 「정산이 안 됐다」로 읽힌다', () => {
    expect(formatFloorReward(3, '   ')).toBe('')
  })

  it('★ 서버가 준 문자열을 그대로 쓴다 — 화면이 짜 맞추면 실제로 들어온 것과 달라진다', () => {
    const html = renderToStaticMarkup(
      <FloorRewardNotice floor={4} reward="화폐 +120 · 사슬 갑옷(FINE) 획득" />,
    )
    expect(html).toContain('사슬 갑옷(FINE) 획득')
    expect(html).toContain('4층 정산')
  })

  it('★ 어디로 들어갔는지 말한다 — 벌었다는 말만으로는 어디서 찾을지 모른다', () => {
    const html = renderToStaticMarkup(<FloorRewardNotice floor={2} reward="화폐 +40" />)
    expect(html).toContain('가방에 들어와 있다')
  })

  it('★ 정산 전에는 아무것도 안 그린다', () => {
    expect(renderToStaticMarkup(<FloorRewardNotice floor={0} reward="" />)).toBe('')
  })
})
