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
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { AffixView, InventoryView, ItemView, SlotView } from '../storage'

export interface InventoryPanelProps {
  readonly inventory: InventoryView | undefined
  readonly isOnline: boolean
  readonly detail: string
  readonly onEquip: (itemId: number, slot: string) => void
  readonly onUnequip: (slot: string) => void
  readonly onDiscard: (itemId: number) => void
  readonly onRepair: (itemId: number) => void
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
  const name = affix.labelKo || affix.stat
  return parts.length === 0 ? name : `${name} ${parts.join(' ')}`
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
  if (item.affixes.length === 0) {
    return null
  }
  return (
    <ul className="inv__affixes">
      {item.affixes.map((affix) => (
        <li className="inv__affix" key={`${affix.stat}:${affix.labelKo}`}>
          <ValueExpr text={formatAffix(affix)} size="sm" dim />
        </li>
      ))}
    </ul>
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
                return (
                  <li className="inv__slot" key={slot}>
                    <span className="inv__slot-label">{SLOT_LABELS.get(slot) ?? slot}</span>
                    {sealed ? (
                      // 양손무기가 막은 자리. 「불가」와 같은 해칭을 쓴다 — 뜻이 같다.
                      <GlyphState state="blocked" size="sm" label="양손 점유" />
                    ) : entry?.item ? (
                      <>
                        <span className="inv__name">{entry.item.labelKo}</span>
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
                          <span className="inv__name">{entry.stackCatalogId}</span>
                          <ValueExpr text={`x${String(entry.stackCount)}`} size="sm" />
                        </div>
                      </li>
                    )
                  ) : (
                    <li className="inv__bag" key={entry.slotIndex}>
                      <div className="inv__row">
                        <span className="inv__name">{entry.item.labelKo}</span>
                        {entry.item.isBroken ? (
                          <GlyphState state="danger" size="sm" label="파손" />
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
