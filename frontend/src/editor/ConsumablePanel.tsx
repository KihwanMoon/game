/**
 * 소모품 칸 패널 (설계/4_아이템 §5).
 *
 * **가방과 다른 화면이다.** 가방은 「가진 것」, 여기는 「들고 갈 것」이다. 예전에는 가방에
 * 든 것을 전부 세서 들고 갔고, 그래서 「몇 개를 들고 갈까」가 선택이 아니었다 — 주운
 * 만큼이 답이었다.
 *
 * **빈 칸도 그린다.** 안 그리면 「칸이 없다」와 「비었다」를 구분할 수 없고, 빈 칸이
 * 출격할 때 공짜로 한 개를 받는다는 사실이 어디에도 안 적힌다.
 *
 * 훅을 안 쓴다. 고를 것을 전부 버튼으로 펴 두었으므로 상태가 필요 없고, 이 저장소의
 * 렌더 검사는 jsdom 없이 돌아 훅 안의 문구를 못 본다.
 */
import { Button, GlyphState, Panel, SegmentedGauge, ValueExpr } from '../ds'
import type { ConsumableOptionView, ConsumableSlotView, ConsumableView } from '../storage'

import { formatGradeClass, renderGrade } from './gradeBadge'

/** 칸 쓰임새의 한글 이름. */
const TAG_LABELS: ReadonlyMap<string, string> = new Map([
  ['POTION', '물약'],
  ['SCROLL', '주문서'],
])

export interface ConsumablePanelProps {
  readonly view: ConsumableView | undefined
  readonly isOnline: boolean
  readonly detail: string
  /** 칸을 비운다. 남은 충전은 안 돌아온다. */
  readonly onClear: (useTag: string, slotIndex: number) => void
  /** 돈을 내고 빈 충전을 채운다. */
  readonly onRefill: (useTag: string, slotIndex: number) => void
  /** 남는 것을 판다. */
  readonly onSell: (catalogId: string) => void
  /**
   * 보유 재고 하나를 **빈 칸부터** 끼운다.
   *
   * 가방 격자에서 소모품 조작을 뺐으므로(두 집 금지) 여기가 유일한 끼우기 자리다.
   */
  readonly onLoadStock: (catalogId: string) => void
}

/**
 * 칸 이름을 적는다.
 *
 * @param slot 칸.
 * @returns `물약 1` 같은 한 줄.
 */
export function formatSlotName(slot: ConsumableSlotView): string {
  const label = TAG_LABELS.get(slot.useTag) ?? slot.useTag
  return `${label} ${String(slot.slotIndex + 1)}`
}

/**
 * 충전 상태를 적는다.
 *
 * **실측값을 병기한다** — `2/4` 처럼 남은 것과 한도를 함께 적어야 「채울 게 있는가」가
 * 눈에 보인다. 규칙 에디터가 `적거리(2) <= 사거리(3)` 을 적는 것과 같은 이유다 (P1).
 *
 * @param slot 칸.
 * @param freeCharges 빈 칸이 출격 때 받는 공짜 충전.
 * @returns 화면에 적을 한 줄.
 */
export function formatCharges(slot: ConsumableSlotView, freeCharges: number): string {
  if (slot.catalogId === '') {
    return `빈 칸 — 출격 시 ${String(freeCharges)}개가 공짜로 찬다`
  }
  return `${String(slot.charges)} / ${String(slot.chargeMax)}`
}

/**
 * 빼기 버튼에 적을 말.
 *
 * **가득 찬 칸은 가방으로 돌아가고, 쓴 칸은 남은 충전이 버려진다.** 그 차이를 누르기
 * 전에 말해야 한다 — 눌러 보고 알게 하면 「아이템이 사라졌다」가 된다(실제 신고).
 *
 * @param slot 칸.
 * @returns 버튼 글자.
 */
export function formatClearLabel(slot: ConsumableSlotView): string {
  if (slot.charges >= slot.chargeMax) {
    return '빼기 (가방으로)'
  }
  return `빼기 (남은 ${String(slot.charges)}충전 버려짐)`
}

/**
 * 보충 버튼에 적을 말.
 *
 * @param slot 칸.
 * @returns 버튼 글자. 채울 것이 없으면 빈 문자열이다.
 */
export function formatRefillLabel(slot: ConsumableSlotView): string {
  if (slot.catalogId === '' || slot.refillCost <= 0) {
    return ''
  }
  return `보충 ${String(slot.refillCost)}`
}

/**
 * 이 칸에 끼울 수 있는 가방 속 후보들.
 *
 * @param options 가방 후보 전부.
 * @param useTag 칸의 쓰임새.
 * @returns 그 칸에 맞는 것들.
 */
export function listSlotOptions(
  options: readonly ConsumableOptionView[],
  useTag: string,
): readonly ConsumableOptionView[] {
  return options.filter((option) => option.useTag === useTag)
}

/**
 * 이 소모품을 끼울 칸을 고른다.
 *
 * **빈 칸이 먼저다.** 찬 칸을 먼저 고르면 끼우는 순간 남의 충전이 날아가고, 그것은
 * 되돌릴 수 없다. 빈 칸이 없으면 undefined 를 돌려 부르는 쪽이 말하게 한다 — 조용히
 * 아무 칸이나 덮으면 「왜 물약이 바뀌었지」가 된다.
 *
 * @param view 소모품 칸 화면. 없으면 고를 수 없다.
 * @param catalogId 끼울 소모품.
 * @returns 끼울 칸. 맞는 빈 칸이 없으면 undefined.
 */
export function findFreeConsumableSlot(
  view: ConsumableView | undefined,
  catalogId: string,
): ConsumableSlotView | undefined {
  const option = view?.options.find((entry) => entry.catalogId === catalogId)
  if (view === undefined || option === undefined) {
    return undefined
  }
  return view.slots.find((slot) => slot.useTag === option.useTag && slot.catalogId === '')
}

/**
 * 칸 한 줄을 그린다.
 *
 * @param slot 칸.
 * @param props 패널 props.
 * @returns 렌더 트리.
 */
function renderSlot(slot: ConsumableSlotView, props: ConsumablePanelProps): React.JSX.Element {
  const view = props.view
  // **런 중에도 잠그지 않는다.** 하강이 서른 방이라, 잠그면 방 사이에 규칙을 고치는
  // 내내 칸을 못 건드린다 (GDD §2.2). 지금 채운 것이 이번 런에 안 실릴 뿐이고,
  // 그 사실은 위의 안내가 말한다.
  const locked = !props.isOnline
  const refill = formatRefillLabel(slot)
  return (
    <li className="cns__card" key={`${slot.useTag}-${String(slot.slotIndex)}`}>
      <div className="cns__card-head">
        <span className="cns__slot">{formatSlotName(slot)}</span>
        <span className={`inv__name${formatGradeClass(slot.grade)}`}>
          {slot.catalogId === '' ? '빈 칸' : slot.labelKo}
        </span>
        {renderGrade(slot.grade)}
      </div>
      {slot.catalogId === '' ? (
        <ValueExpr text={formatCharges(slot, view?.freeCharges ?? 0)} size="sm" dim />
      ) : (
        // **충전을 눈금으로 그린다.** 체력·CPU 와 같은 부품이다 — 숫자를 함께 적으므로
        // 색을 못 보는 경로도 남는다.
        <SegmentedGauge value={slot.charges} max={slot.chargeMax} readout />
      )}
      {slot.affixes.length === 0 ? null : (
        <ul className="invd__affixes">
          {slot.affixes.map((affix) => (
            <li className="invd__affix" key={affix}>
              <ValueExpr text={affix} size="sm" dim />
            </li>
          ))}
        </ul>
      )}
      {slot.catalogId === '' ? null : (
        <div className="cns__tools">
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
    </li>
  )
}

/**
 * 소모품 칸을 그린다.
 *
 * @param props 칸 화면과 조작들.
 * @returns 렌더 트리.
 */
export function ConsumablePanel(props: ConsumablePanelProps): React.JSX.Element {
  const view = props.view
  if (view === undefined) {
    return (
      <Panel title="소모품 칸">
        <ValueExpr text="서버에 닿지 못했다 — 칸을 못 읽는다" size="sm" dim />
      </Panel>
    )
  }
  return (
    <Panel title="소모품 칸">
      <div className="cns__head">
        <ValueExpr text={`잔액 ${String(view.balance)}`} size="sm" />
        {view.isRunOpen ? (
          <GlyphState
            state="pending"
            size="sm"
            label="런이 도는 중 — 지금 채운 것은 다음 런부터 실린다"
          />
        ) : null}
      </div>
      {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
      <ul className="cns__list">{view.slots.map((slot) => renderSlot(slot, props))}</ul>
      {view.options.length === 0 ? null : (
        <>
          <div className="cns__head-label">보유 재고 — 끼우면 가방에서 하나가 나간다 · 등급은 충전 용량이다 (봉인 칸은 장비의 것)</div>
          <ul className="cns__list">
            {view.options.map((option) => (
              <li className="cns__card" key={`sell-${option.catalogId}`}>
                <div className="cns__card-head">
                  <span className={`inv__name${formatGradeClass(option.grade)}`}>
                    {option.labelKo}
                  </span>
                  {renderGrade(option.grade)}
                  <ValueExpr
                    text={`x${String(option.stock)} · ${String(option.charges)}충전`}
                    size="sm"
                    dim
                  />
                </div>
                {option.affixes.length === 0 ? null : (
                  <ul className="invd__affixes">
                    {option.affixes.map((affix) => (
                      <li className="invd__affix" key={affix}>
                        <ValueExpr text={affix} size="sm" dim />
                      </li>
                    ))}
                  </ul>
                )}
                <div className="cns__tools">
              <Button
                size="sm"
                variant="primary"
                glyph="↧"
                disabled={!props.isOnline}
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
                disabled={!props.isOnline}
                onClick={() => {
                  props.onSell(option.catalogId)
                }}
              >
                {`팔기 ${String(option.sellPrice)}`}
              </Button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  )
}
