/**
 * 고른 칸의 상세와 도구줄 (도면 그리드).
 *
 * **조작은 전부 여기에 산다.** 격자 칸은 상태만 그리고, 무엇을 하려면 칸을 골라 이
 * 상세로 온다 — 예전에는 행마다 모든 버튼이 펴져 있어 좁은 화면에서 행 하나가 서너
 * 줄로 꺾였다.
 *
 * 훅은 경매 호가 하나뿐이다. 입력값이라 어쩔 수 없고, 나머지는 전부 props 로 받는다.
 */
import { useState } from 'react'

import { Button, GlyphState, ValueExpr } from '../ds'
import type { ItemView, SlotView } from '../storage'

import { formatGradeClass, renderGrade } from './gradeBadge'
import { EQUIP_CELL_LABELS } from './inventoryCells'
import { formatAffix } from './InventoryPanel'

import { checkLinked, type LinkState } from './linkState'

/** 십진수 파싱. 앞의 0 을 8진수로 읽는 사고를 막는다. */
const DECIMAL_RADIX = 10
const PERCENT_BASE = 100

/** 고른 칸. 장비 칸인지 가방 칸인지가 도구줄을 가른다. */
export interface CellChoice {
  readonly kind: 'equip' | 'bag'
  /** 장비 칸이면 슬롯 id. */
  readonly slot: string
  readonly entry: SlotView
}

export interface InventoryDetailProps {
  readonly choice: CellChoice
  readonly link: LinkState
  readonly repairCost: number
  readonly feePercent: number
  readonly onEquip: (itemId: number, slot: string) => void
  readonly onUnequip: (slot: string) => void
  readonly onDiscard: (itemId: number) => void
  readonly onRepair: (itemId: number) => void
  readonly onUnseal: (itemId: number) => void
  readonly onList: (itemId: number, price: number) => void
}

/**
 * 능력치 줄들을 그린다.
 *
 * @param item 아이템.
 * @returns 능력치 줄. 없으면 null.
 */
function renderAffixes(item: ItemView): React.JSX.Element | null {
  const lines: string[] = []
  if (item.attackRange > 0) {
    lines.push(`사거리 ${String(item.attackRange)}`)
  }
  lines.push(...item.affixes.map(formatAffix))
  if (lines.length === 0) {
    return null
  }
  // **옵션 하나에 한 줄이다.** 가운뎃점으로 이으면 옵션 넷이 문장 하나가 되어, 어디까지가
  // 한 옵션인지 눈으로 갈라야 한다(실제 요청).
  return (
    <ul className="invd__affixes">
      {lines.map((line) => (
        <li className="invd__affix" key={line}>
          <ValueExpr text={line} size="sm" />
        </li>
      ))}
    </ul>
  )
}

/**
 * 요구조건 줄을 그린다. **실측값을 병기한다** — "장착할 수 없습니다" 만 띄우면 무엇이
 * 얼마나 모자란지 알 수 없다 (GDD §8.2, P1).
 *
 * @param item 아이템.
 * @returns 요구조건 줄. 없으면 null.
 */
function renderRequirements(item: ItemView): React.JSX.Element | null {
  if (item.requirements.length === 0) {
    return null
  }
  return (
    <div className="invd__reqs">
      {item.requirements.map((need) => (
        <GlyphState
          key={need.stat}
          state={need.isMet ? 'true' : 'false'}
          size="sm"
          label={`${need.stat}(${String(need.actual)}) >= 요구(${String(need.minimum)})`}
        />
      ))}
    </div>
  )
}

/**
 * 경매 걸기 줄. 호가를 적고 건다 — 수수료는 걸 때 나가고 내려도 안 돌아온다.
 *
 * @param props 아이템 id 와 처리기.
 * @returns 걸기 줄.
 */
function AuctionRow(props: {
  readonly itemId: number
  readonly feePercent: number
  readonly onList: (itemId: number, price: number) => void
}): React.JSX.Element {
  const [price, setPrice] = useState('')
  const asked = Number.parseInt(price, DECIMAL_RADIX)
  const isValid = Number.isFinite(asked) && asked > 0
  const fee = isValid ? Math.max(1, Math.floor((asked * props.feePercent) / PERCENT_BASE)) : 0
  return (
    <div className="invd__row">
      <input
        className="invd__price"
        inputMode="numeric"
        placeholder="호가"
        value={price}
        aria-label="경매 호가"
        onChange={(event) => {
          setPrice(event.target.value)
        }}
      />
      <ValueExpr text={`수수료 ${props.feePercent}%${isValid ? ` = ${String(fee)}` : ''}`} size="sm" dim />
      <Button
        size="sm"
        variant="secondary"
        glyph="⇪"
        disabled={!isValid}
        title="경매에 건다 — 수수료는 걸 때 나가고 내려도 안 돌아온다"
        onClick={() => {
          props.onList(props.itemId, asked)
          setPrice('')
        }}
      >
        걸기
      </Button>
    </div>
  )
}

/**
 * 고른 칸의 상세를 그린다.
 *
 * @param props 고른 칸과 처리기들.
 * @returns 상세 요소.
 */
export function InventoryDetail(props: InventoryDetailProps): React.JSX.Element {
  const { choice } = props
  const item = choice.entry.item

  // 소모품 스택 칸: **조작이 여기 없다.** 들고 갈 것을 고르는 일은 소모품 칸의 몫이다 —
  // 두 집에 살면 어느 쪽이 진짜인지 알 수 없다(실제로 그렇게 헷갈렸다).
  if (item === null) {
    const label =
      choice.entry.stackLabelKo === ''
        ? (choice.entry.stackCatalogId ?? '')
        : choice.entry.stackLabelKo
    return (
      <div className="invd">
        <div className="invd__row">
          <span className={`inv__name${formatGradeClass(choice.entry.stackGrade)}`}>{label}</span>
          {renderGrade(choice.entry.stackGrade)}
          <ValueExpr text={`x${String(choice.entry.stackCount)}`} size="sm" />
        </div>
        <ValueExpr text="소모품이다 — 끼우기·팔기는 아래 소모품 칸에서 한다" size="sm" dim />
        {/* **소모품 등급에는 봉인 칸이 없다.** 장비의 등급이 봉인 칸을 정하듯 소모품의
            등급은 충전 용량을 정한다 (§5) — 상급 물약에 봉인 해제가 없는 것은 빠진 것이
            아니라 그렇게 설계된 것이고, 화면이 그 사실을 말해야 「없는데?」가 안 나온다. */}
        <ValueExpr text="등급은 충전 용량을 정한다 — 봉인 칸은 장비의 것" size="sm" dim />
      </div>
    )
  }

  const disabled = !checkLinked(props.link)
  return (
    <div className="invd">
      <div className="invd__row">
        <span className={`inv__name${formatGradeClass(item.grade)}`}>{item.labelKo}</span>
        {renderGrade(item.grade)}
        {choice.kind === 'equip' ? (
          <ValueExpr
            text={`착용 중 · ${EQUIP_CELL_LABELS.get(choice.slot) ?? choice.slot}`}
            size="sm"
            dim
          />
        ) : item.slot === null ? null : (
          <ValueExpr text={`부위 · ${EQUIP_CELL_LABELS.get(item.slot) ?? item.slot}`} size="sm" dim />
        )}
        {item.isBroken ? <GlyphState state="danger" size="sm" label="파손 · 효과 없음" /> : null}
        {item.sealedSlots > 0 ? (
          <GlyphState state="pending" size="sm" label={`봉인 ${String(item.sealedSlots)}칸`} />
        ) : null}
        {item.isBound ? <GlyphState state="blocked" size="sm" label="귀속 · 거래 불가" /> : null}
        {item.isRecovered ? (
          <GlyphState state="true" size="sm" label="되찾음 · 빼앗겼던 것" />
        ) : null}
      </div>
      {renderAffixes(item)}
      {renderRequirements(item)}
      <div className="invd__row invd__row--tools">
        {choice.kind === 'equip' ? (
          <Button
            size="sm"
            variant="secondary"
            glyph="↥"
            disabled={disabled}
            onClick={() => {
              props.onUnequip(choice.slot)
            }}
          >
            벗기
          </Button>
        ) : item.slot !== null && !item.isBroken ? (
          <Button
            size="sm"
            variant="primary"
            glyph="↧"
            disabled={disabled || !item.canEquip}
            onClick={() => {
              props.onEquip(item.itemId, item.slot ?? '')
            }}
          >
            착용
          </Button>
        ) : null}
        {item.isBroken ? (
          <Button
            size="sm"
            variant="secondary"
            glyph="✚"
            disabled={disabled}
            onClick={() => {
              props.onRepair(item.itemId)
            }}
          >
            {`복구 ${String(props.repairCost)}`}
          </Button>
        ) : null}
        {item.sealedSlots > 0 ? (
          <Button
            size="sm"
            variant="secondary"
            glyph="◈"
            disabled={disabled}
            title="화폐를 내고 옵션 하나를 연다 — 결과는 서버가 정한다"
            onClick={() => {
              props.onUnseal(item.itemId)
            }}
          >
            {`봉인 해제 ${String(item.unsealCost)}`}
          </Button>
        ) : null}
        {choice.kind === 'bag' ? (
          <Button
            size="sm"
            variant="ghost"
            glyph="✕"
            disabled={disabled}
            title="버린다 — 되돌릴 수 없다"
            onClick={() => {
              props.onDiscard(item.itemId)
            }}
          >
            버리기
          </Button>
        ) : null}
      </div>
      {choice.kind === 'bag' && !item.isBound ? (
        <AuctionRow itemId={item.itemId} feePercent={props.feePercent} onList={props.onList} />
      ) : null}
    </div>
  )
}
