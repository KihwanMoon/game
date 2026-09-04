/**
 * 고른 소모품 칸의 상세와 도구줄 (도면 그리드).
 *
 * **조작은 전부 여기에 산다.** 격자 칸은 상태만 그리고, 무엇을 하려면 칸을 골라 이
 * 상세로 온다 — 가방과 같은 규약이다.
 *
 * **견줌이 칸 전부와 붙는다.** 칸 수가 고정이 아니기 때문이다 (`compareConsumables`) —
 * 접사가 물약 칸을 늘리므로, 하나만 골라 견주면 사람이 갈아 끼우려던 칸이 견줌에서
 * 빠진다.
 *
 * 훅을 안 쓴다. 고를 것이 전부 버튼으로 펴져 있어 상태가 필요 없다.
 */
import { Button, GlyphState, SegmentedGauge, ValueExpr } from '../ds'
import type { ConsumableSlotView, ConsumableView } from '../storage'

import { CompareBlock } from './CompareRows'
import {
  compareToSlots,
  pickFromOption,
  pickFromSlot,
  type ComparePick,
  type SlotCompare,
} from './compareConsumables'
import {
  formatCharges,
  formatClearLabel,
  formatRefillLabel,
  formatSlotName,
  USE_TAG_LABELS,
  type ConsumableCell,
} from './consumableCells'
import { formatGradeClass, renderGrade } from './gradeBadge'
import { checkLinked, type LinkState } from './linkState'

export interface ConsumableDetailProps {
  readonly cell: ConsumableCell
  readonly view: ConsumableView
  readonly link: LinkState
  readonly onClear: (useTag: string, slotIndex: number) => void
  readonly onRefill: (useTag: string, slotIndex: number) => void
  readonly onSell: (catalogId: string) => void
  readonly onLoadStock: (catalogId: string) => void
}

/**
 * 옵션 줄들을 그린다.
 *
 * @param affixes 구운 옵션 줄들.
 * @returns 줄 목록. 없으면 null.
 */
function renderAffixes(affixes: readonly string[]): React.JSX.Element | null {
  if (affixes.length === 0) {
    return null
  }
  // **옵션 하나에 한 줄이다.** 가운뎃점으로 이으면 옵션 넷이 문장 하나가 되어, 어디까지가
  // 한 옵션인지 눈으로 갈라야 한다.
  return (
    <ul className="invd__affixes">
      {affixes.map((line) => (
        <li className="invd__affix" key={line}>
          <ValueExpr text={line} size="sm" />
        </li>
      ))}
    </ul>
  )
}

/**
 * 한 칸과의 견줌을 그린다.
 *
 * @param compare 칸 하나와의 견줌.
 * @returns 견줌 묶음.
 */
function renderSlotCompare(compare: SlotCompare): React.JSX.Element {
  const name = formatSlotName(compare.slot)
  const where = compare.isEmpty ? `${name} · 빈 칸` : `${name} · ${compare.slot.labelKo}`
  return (
    <div className="cnsd__compare" key={`${compare.slot.useTag}-${String(compare.slot.slotIndex)}`}>
      <CompareBlock
        heading={`${where} 와 견줌`}
        rows={compare.rows}
        sameText={`${where} 와 달라지는 것이 없다`}
      />
    </div>
  )
}

/**
 * 맞는 칸 전부와의 견줌을 그린다.
 *
 * @param picked 견줄 것.
 * @param slots 끼운 칸 전부.
 * @returns 견줌들. 맞는 칸이 없으면 그렇게 적는다.
 */
function renderCompares(
  picked: ComparePick,
  slots: readonly ConsumableSlotView[],
): React.JSX.Element {
  const compares = compareToSlots(picked, slots)
  if (compares.length === 0) {
    const label = USE_TAG_LABELS.get(picked.useTag) ?? picked.useTag
    return <ValueExpr text={`견줄 ${label} 칸이 없다`} size="sm" dim />
  }
  return <>{compares.map(renderSlotCompare)}</>
}

/**
 * 끼운 칸 하나의 상세.
 *
 * @param props 칸과 처리기들.
 * @returns 상세 요소.
 */
function renderSlotDetail(
  slot: ConsumableSlotView,
  props: ConsumableDetailProps,
): React.JSX.Element {
  const { view } = props
  // **런 중에도 잠그지 않는다.** 하강이 서른 방이라, 잠그면 방 사이에 규칙을 고치는
  // 내내 칸을 못 건드린다 (GDD §2.2). 지금 채운 것이 이번 런에 안 실릴 뿐이다.
  const locked = !checkLinked(props.link)
  const refill = formatRefillLabel(slot)
  const isEmpty = slot.catalogId === ''
  return (
    <div className="invd">
      <div className="invd__row">
        <span className="cns__slot">{formatSlotName(slot)}</span>
        <span className={`inv__name${formatGradeClass(slot.grade)}`}>
          {isEmpty ? '빈 칸' : slot.labelKo}
        </span>
        {renderGrade(slot.grade)}
        {/* **다 썼다고 옵션이 사라지는 것이 아니다.** 처음에는 파손된 장비에 빗댔는데
            그 비유가 틀렸다 — 그렇게 두면 안 마시는 것이 이득이 되고, 그것은 물약의
            존재 이유와 정반대다 (`list_loaded_consumables`). 못 하는 것은 마시는 것뿐이고
            화면이 그렇게 적어야 「옵션이 없어졌나」를 안 겪는다. */}
        {!isEmpty && slot.charges <= 0 ? (
          <GlyphState state="danger" size="sm" label="다 씀 — 못 마신다 (옵션은 그대로)" />
        ) : null}
      </div>
      {isEmpty ? (
        <ValueExpr text={formatCharges(slot, view.freeCharges)} size="sm" dim />
      ) : (
        // **충전을 눈금으로 그린다.** 체력·CPU 와 같은 부품이다 — 숫자를 함께 적으므로
        // 색을 못 보는 경로도 남는다.
        <SegmentedGauge value={slot.charges} max={slot.chargeMax} readout />
      )}
      {renderAffixes(slot.affixes)}
      {/* 빈 칸은 견줄 것이 없다 — 무엇과 견주는지가 없다. */}
      {isEmpty ? null : renderCompares(pickFromSlot(slot), view.slots)}
      {isEmpty ? null : (
        <div className="invd__row invd__row--tools">
          {refill === '' ? null : (
            <Button
              size="sm"
              variant="secondary"
              glyph="✚"
              disabled={locked}
              onClick={() => {
                props.onRefill(slot.useTag, slot.slotIndex)
              }}
            >
              {refill}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            glyph="↥"
            disabled={locked}
            onClick={() => {
              props.onClear(slot.useTag, slot.slotIndex)
            }}
          >
            {formatClearLabel(slot)}
          </Button>
        </div>
      )}
    </div>
  )
}

/**
 * 고른 소모품 칸의 상세를 그린다.
 *
 * @param props 고른 칸과 처리기들.
 * @returns 상세 요소.
 */
export function ConsumableDetail(props: ConsumableDetailProps): React.JSX.Element {
  const { cell, view } = props
  const slot = cell.slot
  if (cell.kind === 'slot' && slot !== undefined) {
    return renderSlotDetail(slot, props)
  }
  const option = cell.option
  if (option === undefined) {
    return (
      <div className="invd">
        <ValueExpr text="이 칸의 내용을 못 읽는다" size="sm" dim />
      </div>
    )
  }
  const locked = !checkLinked(props.link)
  return (
    <div className="invd">
      <div className="invd__row">
        <span className={`inv__name${formatGradeClass(option.grade)}`}>{option.labelKo}</span>
        {renderGrade(option.grade)}
        <ValueExpr
          text={`x${String(option.stock)} · ${String(option.charges)}충전`}
          size="sm"
          dim
        />
      </div>
      {/* **소모품 등급에는 봉인 칸이 없다.** 장비의 등급이 봉인 칸을 정하듯 소모품의
          등급은 충전 용량을 정한다 (§5) — 상급 물약에 봉인 해제가 없는 것은 빠진 것이
          아니라 그렇게 설계된 것이고, 화면이 그 사실을 말해야 「없는데?」가 안 나온다. */}
      <ValueExpr text="등급은 충전 용량을 정한다 — 봉인 칸은 장비의 것" size="sm" dim />
      {renderAffixes(option.affixes)}
      {renderCompares(pickFromOption(option), view.slots)}
      <div className="invd__row invd__row--tools">
        <Button
          size="sm"
          variant="primary"
          glyph="↧"
          disabled={locked}
          title={`${String(option.charges)}충전 — 빈 칸부터 채운다`}
          onClick={() => {
            props.onLoadStock(option.catalogId)
          }}
        >
          끼우기
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={locked}
          onClick={() => {
            props.onSell(option.catalogId)
          }}
        >
          {`팔기 ${String(option.sellPrice)}`}
        </Button>
      </div>
    </div>
  )
}
