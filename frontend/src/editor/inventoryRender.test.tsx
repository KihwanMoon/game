/**
 * 인벤토리 화면 검사 (D단계).
 *
 * 여기서 지키는 것은 넷이다.
 *
 * 1. **요구조건에 실측값을 병기한다.** "장착할 수 없습니다" 만으로는 무엇이 얼마나
 *    모자란지 알 수 없다 (P1).
 * 2. **등급을 색으로 칠하지 않는다.** 의미색 셋이 이미 배정됐고 색은 정보의 유일한
 *    채널이 될 수 없다.
 * 3. **봉인은 「불가」와 같은 해칭을 쓴다.** 뜻이 같다 — 해당 없음.
 * 4. **서버가 없으면 그렇게 말한다.** 아이템은 서버가 발급하므로 빈 화면과 구분돼야 한다.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { InventoryPanel } from './InventoryPanel'
import type { InventoryView } from '../storage'

const noop = () => undefined

/** 요구조건을 못 채운 장갑 하나가 가방에 있다. */
const INVENTORY: InventoryView = {
  slots: [
    {
      slotIndex: 0,
      slot: null,
      isSealed: false,
      item: {
        itemId: 1,
        catalogId: 'gloves_core',
        labelKo: '연산 장갑',
        kind: 'EQUIPMENT',
        slot: 'HANDS',
        hands: null,
        equippedSlot: null,
        isBroken: false,
        canEquip: false,
        requirements: [{ stat: 'cpu_budget', actual: 4, minimum: 6, isMet: false }],
      },
    },
  ],
  equipment: [
    {
      slotIndex: 0,
      slot: 'WEAPON_OFF',
      isSealed: true,
      item: null,
    },
  ],
  balance: 250,
  repairCost: 120,
}

/**
 * 파일을 읽는다.
 *
 * @param relative 이 파일 기준 상대 경로.
 * @returns 파일 내용.
 */
function readText(relative: string): string {
  return readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8')
}

describe('인벤토리 패널', () => {
  const markup = renderToStaticMarkup(
    <InventoryPanel
      inventory={INVENTORY}
      isOnline
      detail=""
      onEquip={noop}
      onUnequip={noop}
      onDiscard={noop}
      onRepair={noop}
    />,
  )

  it('★ 요구조건에 실측값을 병기한다', () => {
    // 규칙 에디터의 조건문 표기와 같은 규약이다 (GDD §8.2).
    expect(markup).toContain('cpu_budget(4) &gt;= 요구(6)')
  })

  it('못 채운 요구조건이면 착용을 잠근다', () => {
    expect(markup).toContain('disabled')
  })

  it('★ 봉인된 자리는 「불가」와 같은 해칭을 쓴다', () => {
    // 새 표기를 만들지 않는다 — 뜻이 같다(해당 없음).
    expect(markup).toContain('ds-glyph--blocked')
    expect(markup).toContain('양손 점유')
  })

  it('여섯 슬롯을 모두 보여준다', () => {
    for (const label of ['주무기', '보조', '투구', '갑옷', '신발', '장갑']) {
      expect(markup).toContain(label)
    }
  })

  it('화폐를 적는다', () => {
    expect(markup).toContain('250')
  })
})

describe('인벤토리 패널 — 서버 없음', () => {
  it('★ 빈 가방과 구분해서 말한다 — 아이템은 서버가 발급한다', () => {
    const markup = renderToStaticMarkup(
      <InventoryPanel
        inventory={undefined}
        isOnline={false}
        detail=""
        onEquip={noop}
        onUnequip={noop}
        onDiscard={noop}
        onRepair={noop}
      />,
    )
    expect(markup).toContain('서버에 닿지 못했다')
    expect(markup).toContain('서버가 발급한다')
  })
})

describe('인벤토리 스타일', () => {
  const css = readText('./editor.css')
  const block = css.slice(css.indexOf('/* ── 인벤토리·장비 패널'))

  it('★ 등급 색을 새로 쓰지 않는다', () => {
    expect(block).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
  })

  it('자체 미디어쿼리를 두지 않는다 — 브레이크포인트는 한 곳에만 있다', () => {
    expect(block).not.toContain('@media')
  })

  it('터치 높이 토큰을 쓴다', () => {
    expect(block).toContain('var(--btn-tap-sm-h)')
  })
})
