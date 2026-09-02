/**
 * 인벤토리·장비 패널 (D단계).
 *
 * **요구조건에 실측값을 병기한다.** "장착할 수 없습니다" 만 띄우면 무엇이 얼마나 모자란지
 * 알 수 없고, 그것은 규칙 에디터의 조건문 표기(`적거리(2) <= 사거리(3)`)와 같은 이유로
 * P1 위반이다 (GDD §8.2).
 *
 * **등급을 색으로 칠하지 않는다.** 의미색 셋이 이미 배정돼 있고 색은 정보의 유일한
 * 채널이 될 수 없다 (design/README.md §성격). 파손·봉인은 글리프와 취소선으로 가른다.
 *
 * 자체 브레이크포인트를 두지 않는다. 높이는 `--btn-tap-h` 가 정하므로 터치 배치에서
 * 저절로 44px 가 된다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, Thumb, ValueExpr } from '../ds'
import type { AffixView, InventoryView, ItemView, SlotView } from '../storage'

/** 십진수 파싱. 앞의 0 을 8진수로 읽는 사고를 막는다. */
const DECIMAL_RADIX = 10
const PERCENT_BASE = 100

export interface InventoryPanelProps {
  readonly inventory: InventoryView | undefined
  readonly isOnline: boolean
  readonly detail: string
  readonly onEquip: (itemId: number, slot: string) => void
  readonly onUnequip: (slot: string) => void
  readonly onDiscard: (itemId: number) => void
  /**
   * 경매에 건다. **서버에는 처음부터 있던 길인데 화면에 없었다** — 팔 방법이 없으면
   * 경제의 절반(파는 쪽)이 돌지 않는다.
   */
  readonly onList: (itemId: number, price: number) => void
  /**
   * 봉인 한 칸을 연다 (§17). **결과는 서버가 정한다** — 요청에 무엇을 받을지 적을
   * 자리가 없다.
   */
  readonly onUnseal: (itemId: number) => void
  /** 걸 때 떼는 수수료율(%). 걸기 전에 얼마가 나가는지 알아야 한다. */
  readonly feePercent: number
  readonly onRepair: (itemId: number) => void
  /**
   * 가방의 소모품을 빈 소모품 칸에 끼운다.
   *
   * **가방 행에 있어야 한다.** 장비 행에는 「착용」이 있는데 소모품 행에는 아무것도
   * 없으면, 끼우는 길이 다른 패널에만 있다는 것을 알 방법이 없다 — 실제로 못 찾았다.
   */
  readonly onLoadConsumable: (catalogId: string) => void
}

/**
 * 등급의 한글 이름.
 *
 * **색만으로 가르지 않는다.** 이름을 함께 적어야 색을 못 가르는 사람에게도 등급이 보이고,
 * 그것이 이 저장소가 참·거짓을 색·글리프·명도 셋으로 적는 것과 같은 규율이다.
 */
const GRADE_LABELS: ReadonlyMap<string, string> = new Map([
  ['COMMON', '보통'],
  ['FINE', '상급'],
  ['RELIC', '유물'],
])

/**
 * 등급의 글리프.
 *
 * **색이 유일한 채널이 되면 안 된다.** 이 저장소는 참·거짓을 색·글리프·명도 셋으로 적고,
 * 등급도 같은 규율을 따른다 — 색을 못 가르는 사람에게 채워진 마름모와 빈 마름모는
 * 노랑과 주황보다 확실하다. 괘선 굵기로 가르지 않는 이유는 `--bw-accent` 가 「활성 규칙
 * 좌측 세로바만 예외」로 못박혀 있기 때문이다.
 */
const GRADE_GLYPHS: ReadonlyMap<string, string> = new Map([
  ['COMMON', '·'],
  ['FINE', '◇'],
  ['RELIC', '◆'],
])

/**
 * 등급에 붙는 class 를 정한다.
 *
 * @param grade 등급 코드.
 * @returns class 이름. 모르는 등급이면 빈 문자열 — 색을 안 입힌다.
 */
export function formatGradeClass(grade: string): string {
  return GRADE_LABELS.has(grade) ? ` inv__name--${grade.toLowerCase()}` : ''
}

/**
 * 등급 이름표를 그린다.
 *
 * @param grade 등급 코드.
 * @returns 요소. 모르는 등급이면 아무것도 안 그린다.
 */
export function renderGrade(grade: string): React.JSX.Element | null {
  const label = GRADE_LABELS.get(grade)
  if (label === undefined) {
    return null
  }
  return (
    <span className={`inv__grade inv__grade--${grade.toLowerCase()}`}>
      {`${GRADE_GLYPHS.get(grade) ?? ''} ${label}`}
    </span>
  )
}

/** 장비 슬롯 순서. 파이썬 `SLOT_ORDER` 와 같아야 화면과 합산이 같은 순서를 본다. */
const SLOT_ORDER: readonly string[] = [
  'WEAPON_MAIN',
  'WEAPON_OFF',
  'HEAD',
  'BODY',
  'FEET',
  'HANDS',
]

const SLOT_LABELS: ReadonlyMap<string, string> = new Map([
  ['WEAPON_MAIN', '주무기'],
  ['WEAPON_OFF', '보조'],
  ['HEAD', '투구'],
  ['BODY', '갑옷'],
  ['FEET', '신발'],
  ['HANDS', '장갑'],
])

const EMPTY_HINT = '아직 없다 — 판을 끝내면 서버가 전리품을 준다'
const OFFLINE_HINT = '서버에 닿지 못했다 — 아이템은 서버가 발급한다'

/**
 * 요구조건 줄들을 그린다.
 *
 * @param item 볼 아이템.
 * @returns 요소. 요구조건이 없으면 null.
 */
function renderRequirements(item: ItemView): React.JSX.Element | null {
  if (item.requirements.length === 0) {
    return null
  }
  return (
    <ul className="inv__reqs">
      {item.requirements.map((need) => (
        <li className="inv__req" key={need.stat}>
          <GlyphState
            state={need.isMet ? 'true' : 'false'}
            size="sm"
            label={`${need.stat}(${String(need.actual)}) >= 요구(${String(need.minimum)})`}
          />
        </li>
      ))}
    </ul>
  )
}

/**
 * 접사 하나를 사람이 읽는 한 줄로 만든다.
 *
 * **부호를 붙여 적는다.** 저주 접사는 음수이고(`설계/4_아이템` §9), 「방어 -3」과
 * 「방어 3」이 같아 보이면 저주가 장점으로 읽힌다.
 *
 * @param affix 볼 접사.
 * @returns 화면에 적을 문자열.
 */
export function formatAffix(affix: AffixView): string {
  const parts: string[] = []
  if (affix.flat !== 0) {
    parts.push(`${affix.flat > 0 ? '+' : ''}${String(affix.flat)}`)
  }
  if (affix.percent !== 0) {
    parts.push(`${affix.percent > 0 ? '+' : ''}${String(affix.percent)}%`)
  }
  const label = affix.statLabel || affix.stat
  const name = affix.labelKo
  // **이름이 능력치를 되풀이하면 한 번만 적는다.** 「공격력 · 공격력 +3」 은 아무것도 더
  // 말해 주지 않고, 관리자가 이름 칸을 비웠을 때 영어 키가 그대로 새던 자리이기도 하다.
  const head = name === '' || name === affix.stat || name === label ? label : `${name} · ${label}`
  return parts.length === 0 ? head : `${head} ${parts.join(' ')}`
}

/**
 * 이 아이템이 주는 것을 그린다.
 *
 * **끼기 전에 보여야 한다** — 무엇을 주는지 모르고 끼우면 캐릭터 시트를 보고 나서야
 * 알게 되고, 그때는 이미 다른 것을 벗은 뒤다.
 *
 * @param item 볼 아이템.
 * @returns 요소. 접사가 없으면 null.
 */
function renderAffixes(item: ItemView): React.JSX.Element | null {
  if (item.affixes.length === 0 && item.attackRange === 0) {
    return null
  }
  return (
    <ul className="inv__affixes">
      {/* 사거리는 무기의 것이지 접사가 아니다 (§2.2). **접사에서 필드로 옮기면서 한 번
          안 보이게 됐다** — 접사였을 때는 「먼 사거리 +3」 으로 뜨던 것이 사라졌었다. */}
      {item.attackRange === 0 ? null : (
        <li className="inv__affix" key="attack_range">
          <ValueExpr text={`사거리 ${String(item.attackRange)}`} size="sm" dim />
        </li>
      )}
      {item.affixes.map((affix) => (
        <li className="inv__affix" key={`${affix.stat}:${affix.labelKo}`}>
          <ValueExpr text={formatAffix(affix)} size="sm" dim />
        </li>
      ))}
    </ul>
  )
}

/** 경매 등록 줄이 받는 props. */
export interface ListingRowProps {
  readonly item: ItemView
  readonly feePercent: number
  readonly onList: (itemId: number, price: number) => void
}

/**
 * 가방 아이템 하나를 경매에 거는 줄.
 *
 * **걸 수 없는 것에는 줄 자체를 그리지 않는다.** 귀속·파손은 서버가 거절하는데, 그
 * 사실을 누른 뒤에 알면 이미 "왜 안 되지" 를 겪은 뒤다 — 가방 줄에 「귀속 · 거래 불가」
 * 가 이미 적혀 있으므로 이유는 그쪽이 말한다.
 *
 * 수수료는 **호가를 적는 동안** 보인다. 걸고 나서 알면 그때는 이미 나간 뒤다.
 *
 * @param props 아이템·수수료율·콜백.
 * @returns 렌더 트리. 걸 수 없는 아이템이면 null.
 */
export function ListingRow(props: ListingRowProps): React.JSX.Element | null {
  const [price, setPrice] = useState('')
  const { item } = props
  if (item.isBound || item.isBroken) {
    return null
  }
  const asked = Number.parseInt(price, DECIMAL_RADIX)
  const isValid = Number.isFinite(asked) && asked > 0
  const fee = isValid ? Math.floor((asked * props.feePercent) / PERCENT_BASE) : 0

  return (
    <div className="inv__list-row">
      <input
        className="inv__price"
        inputMode="numeric"
        value={price}
        placeholder="호가"
        aria-label={`${item.labelKo} 호가`}
        onChange={(event) => {
          setPrice(event.target.value)
        }}
      />
      <ValueExpr
        text={
          isValid
            ? `수수료 ${String(fee)} 는 안 돌아온다`
            : `수수료 ${String(props.feePercent)}%`
        }
        size="sm"
        dim={!isValid}
      />
      <Button
        size="sm"
        variant="secondary"
        glyph="⇪"
        disabled={!isValid}
        title="경매에 건다 — 수수료는 걸 때 나가고 내려도 안 돌아온다"
        onClick={() => {
          props.onList(item.itemId, asked)
          setPrice('')
        }}
      >
        걸기
      </Button>
    </div>
  )
}

/**
 * 인벤토리·장비 패널을 그린다.
 *
 * @param props 인벤토리와 처리기.
 * @returns 패널 요소.
 */
export function InventoryPanel(props: InventoryPanelProps): React.JSX.Element {
  const { inventory, isOnline } = props
  const equippedBySlot = new Map<string, SlotView>(
    (inventory?.equipment ?? []).map((entry) => [entry.slot ?? '', entry]),
  )

  return (
    <Panel
      title="장비와 가방"
      meta={inventory === undefined ? '' : `화폐 ${String(inventory.balance)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="inv">
        {!isOnline || inventory === undefined ? (
          <ValueExpr text={OFFLINE_HINT} size="sm" dim />
        ) : (
          <>
            <div className="inv__head">장비</div>
            <ul className="inv__slots">
              {SLOT_ORDER.map((slot) => {
                const entry = equippedBySlot.get(slot)
                const sealed = entry?.isSealed ?? false
                // 콜백 안에서 `entry.item` 을 다시 읽으면 좁혀 둔 타입이 풀린다.
                const equipped = entry?.item ?? undefined
                return (
                  <li className="inv__slot" key={slot}>
                    <span className="inv__slot-label">{SLOT_LABELS.get(slot) ?? slot}</span>
                    {sealed ? (
                      // 양손무기가 막은 자리. 「불가」와 같은 해칭을 쓴다 — 뜻이 같다.
                      <GlyphState state="blocked" size="sm" label="양손 점유" />
                    ) : entry?.item ? (
                      <>
                        <Thumb kind={slot} label={entry.item.labelKo} size="sm" />
                        <span className={`inv__name${formatGradeClass(entry.item.grade)}`}>
                          {entry.item.labelKo}
                        </span>
                        {renderGrade(entry.item.grade)}
                        {entry.item.isBroken ? (
                          <GlyphState state="danger" size="sm" label="파손" />
                        ) : null}
                        <Button
                          size="sm"
                          variant="ghost"
                          glyph="↥"
                          title="벗는다"
                          onClick={() => {
                            props.onUnequip(slot)
                          }}
                        />
                        {/* **낀 것이 무엇을 주는지 여기서 보인다.** 예전에는 능력치 줄이
                            가방 칸에만 붙어 있어서, 낀 장비의 효과를 볼 데가 아예 없었다 —
                            그래서 "가방에 있는 것이 적용되는 것 같다" 로 읽혔다.
                            합산은 예나 지금이나 `equipment_slot` 만 본다.

                            접었다 펴는 요소를 쓴다. 여섯 자리를 늘 펴 두면 장비 목록이
                            화면 한 판을 넘고, 그러면 가방이 안 보인다. */}
                        {entry.item.sealedSlots > 0 ? (
                          <GlyphState
                            state="pending"
                            size="sm"
                            label={`봉인 ${String(entry.item.sealedSlots)}칸`}
                          />
                        ) : null}
                        {/* **낀 채로 고치고 연다.** 서버는 처음부터 낀 것도 받았는데
                            버튼이 가방 칸에만 있었다 — 고치거나 열려면 벗었다가 다시
                            껴야 했고, 벗은 사이에 스탯이 흔들린다. */}
                        {entry.item.isBroken ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            glyph="✚"
                            title={`복구 ${String(inventory.repairCost)}`}
                            onClick={() => {
                              props.onRepair(equipped?.itemId ?? 0)
                            }}
                          >
                            복구
                          </Button>
                        ) : null}
                        {entry.item.sealedSlots === 0 ? null : (
                          <Button
                            size="sm"
                            variant="secondary"
                            glyph="◈"
                            title={`해제 ${String(entry.item.unsealCost)} — 무엇이 나올지는 열어야 안다`}
                            onClick={() => {
                              props.onUnseal(equipped?.itemId ?? 0)
                            }}
                          >
                            봉인 해제
                          </Button>
                        )}
                        {renderAffixes(entry.item) === null ? null : (
                          <details className="inv__more">
                            <summary className="inv__more-head">능력치</summary>
                            {renderAffixes(entry.item)}
                          </details>
                        )}
                      </>
                    ) : (
                      <ValueExpr text="비어 있다" size="sm" dim />
                    )}
                  </li>
                )
              })}
            </ul>

            <div className="inv__head">가방</div>
            {inventory.slots.length === 0 ? (
              <ValueExpr text={EMPTY_HINT} size="sm" dim />
            ) : (
              <ul className="inv__slots">
                {inventory.slots.map((entry) =>
                  entry.item === null ? (
                    // 소모품은 아이템 인스턴스가 아니라 **쌓인 칸**이다. 개수를 안 적으면
                    // 물약이 1개인지 9개인지 모르고 규칙표를 짠다 (#54).
                    entry.stackCatalogId === null ? null : (
                      <li className="inv__bag" key={entry.slotIndex}>
                        <div className="inv__row">
                          <Thumb kind="CONSUMABLE" label={entry.stackCatalogId} size="sm" />
                          <span className={`inv__name${formatGradeClass(entry.stackGrade)}`}>
                            {entry.stackLabelKo === '' ? entry.stackCatalogId : entry.stackLabelKo}
                          </span>
                          {renderGrade(entry.stackGrade)}
                          <ValueExpr text={`x${String(entry.stackCount)}`} size="sm" />
                          {entry.stackUseTag === '' ? null : (
                            <Button
                              size="sm"
                              variant="ghost"
                              glyph="↧"
                              disabled={!props.isOnline}
                              onClick={() => {
                                props.onLoadConsumable(entry.stackCatalogId ?? '')
                              }}
                            >
                              끼우기
                            </Button>
                          )}
                        </div>
                      </li>
                    )
                  ) : (
                    <li className="inv__bag" key={entry.slotIndex}>
                      <div className="inv__row">
                        <Thumb
                          kind={entry.item.slot === null ? entry.item.kind : entry.item.slot}
                          label={entry.item.labelKo}
                          size="sm"
                        />
                        <span className={`inv__name${formatGradeClass(entry.item.grade)}`}>
                          {entry.item.labelKo}
                        </span>
                        {renderGrade(entry.item.grade)}
                        {entry.item.isBroken ? (
                          <GlyphState state="danger" size="sm" label="파손" />
                        ) : null}
                        {entry.item.isRecovered ? (
                          <GlyphState
                            state="true"
                            size="sm"
                            label="되찾음 · 빼앗겼던 것"
                          />
                        ) : null}
                        {entry.item.sealedSlots > 0 ? (
                          // 봉인 칸은 등급이 준다. **무엇이 들어올지는 화면도 모른다** —
                          // 서버가 열 때 굴리고, 그래서 열 이유가 남는다.
                          <GlyphState
                            state="pending"
                            size="sm"
                            label={`봉인 ${String(entry.item.sealedSlots)}칸`}
                          />
                        ) : null}
                        {entry.item.isBound ? (
                          // 산 물건은 다시 팔 수 없다 (결정 #07). 걸기 전에 보여야
                          // 하므로 가방 줄에 적는다 — 해칭은 「불가」와 뜻이 같다.
                          <GlyphState state="blocked" size="sm" label="귀속 · 거래 불가" />
                        ) : null}
                        {entry.item.isBroken ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            glyph="✚"
                            title={`복구 ${String(inventory.repairCost)}`}
                            onClick={() => {
                              props.onRepair(entry.item?.itemId ?? 0)
                            }}
                          >
                            복구
                          </Button>
                        ) : entry.item.slot !== null ? (
                          <Button
                            size="sm"
                            variant="primary"
                            glyph="↧"
                            disabled={!entry.item.canEquip}
                            onClick={() => {
                              props.onEquip(entry.item?.itemId ?? 0, entry.item?.slot ?? '')
                            }}
                          >
                            착용
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="ghost"
                          glyph="✕"
                          title="버린다"
                          onClick={() => {
                            props.onDiscard(entry.item?.itemId ?? 0)
                          }}
                        />
                      </div>
                      {renderAffixes(entry.item)}
                      {renderRequirements(entry.item)}
                      {entry.item.sealedSlots === 0 ? null : (
                        <div className="inv__list-row">
                          <ValueExpr
                            text={`해제 ${String(entry.item.unsealCost)} · 무엇이 나올지는 열어야 안다`}
                            size="sm"
                            dim
                          />
                          <Button
                            size="sm"
                            variant="secondary"
                            glyph="◈"
                            title="화폐를 내고 옵션 하나를 연다 — 결과는 서버가 정한다"
                            onClick={() => {
                              props.onUnseal(entry.item?.itemId ?? 0)
                            }}
                          >
                            봉인 해제
                          </Button>
                        </div>
                      )}
                      <ListingRow
                        item={entry.item}
                        feePercent={props.feePercent}
                        onList={props.onList}
                      />
                    </li>
                  ),
                )}
              </ul>
            )}
          </>
        )}
        {props.detail === '' ? null : (
          <div className="inv__warn">
            <GlyphState state="danger" size="sm" label={props.detail} />
          </div>
        )}
      </div>
    </Panel>
  )
}
