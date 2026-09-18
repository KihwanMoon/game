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

import { findItemArt } from '../content/itemArt'
import { Button, GlyphState, Thumb, ValueExpr } from '../ds'
import type { ItemView, SlotView } from '../storage'

import { formatParamLabel } from './blockOptions'
import { formatGradeClass, renderGrade } from './gradeBadge'
import { EQUIP_CELL_LABELS, RANGE_SLOT } from './inventoryCells'
import { CompareBlock } from './CompareRows'
import { buildRangeRow, compareToWorn } from './compareItems'
import { formatAffix } from './InventoryPanel'
import { AffixList, type AffixLine } from './AffixList'

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
  /**
   * 지금 그 자리에 낀 것. 가방 칸을 골랐을 때 견줄 상대다.
   *
   * 빈 자리면 undefined — 그때는 「지금 아무것도 없다」가 답이고, 견줌이 전부 이득으로
   * 나오는 것이 맞다.
   */
  readonly worn: ItemView | undefined
  readonly link: LinkState
  readonly repairCost: number
  /** 가진 활자. 모자라면 다시 찍기 단추가 막힌다. */
  readonly letters: number
  /** 한 줄을 다시 찍는 값(활자). 서버가 정한다. */
  readonly recastCost: number
  readonly feePercent: number
  readonly onEquip: (itemId: number, slot: string) => void
  readonly onUnequip: (slot: string) => void
  readonly onDiscard: (itemId: number) => void
  readonly onRepair: (itemId: number) => void
  readonly onUnseal: (itemId: number) => void
  readonly onRecast: (itemId: number, affixIndex: number) => void
  readonly onList: (itemId: number, price: number) => void
}

/**
 * 지금 낀 것과의 차이를 그린다.
 *
 * 표기는 `CompareRows` 가 든다 — 같은 표가 경매장·소모품 칸에도 서고, 세 곳이 각자
 * 그리면 견줌의 표기를 하나 고칠 때 **고친 화면에서만** 바뀐다.
 *
 * @param picked 고른 아이템.
 * @param worn 그 자리에 지금 낀 것. 없으면 빈 자리다.
 * @returns 견줌 줄들. 차이가 없으면 그렇게 적는다.
 */
function renderCompare(picked: ItemView, worn: ItemView | undefined): React.JSX.Element {
  const where = worn === undefined ? '빈 자리와' : `${worn.labelKo} 와`
  // **사거리는 접사가 아니라 필드다** — 접사만 견주면 활과 단검을 바꿔도 「달라지는 것이
  // 없다」가 나온다. 자리가 주무기일 때만 뜻이 있다 (`items/loadout.replace_range`).
  const range =
    picked.slot === RANGE_SLOT ? buildRangeRow(picked.attackRange, worn?.attackRange ?? 0) : undefined
  return (
    <CompareBlock
      heading={`${where} 견줌`}
      rows={[
        ...compareToWorn(picked.affixes, worn?.affixes ?? []),
        ...(range === undefined ? [] : [range]),
      ]}
      sameText={`${where} 견줘 달라지는 것이 없다`}
    />
  )
}

/**
 * 능력치 줄들을 그린다.
 *
 * @param item 아이템.
 * @returns 능력치 줄. 없으면 null.
 */
function renderAffixes(item: ItemView, recast: RecastOffer): React.JSX.Element | null {
  const lines: AffixLine[] = []
  if (item.attackRange > 0) {
    // **사거리는 접사가 아니라 필드다.** 다시 찍을 수 없으므로 단추가 안 붙는다 —
    // 예전에는 첨자 -1 로 갈랐는데, 그 -1 이 접사 첨자와 같은 칸을 타고 다녔다.
    lines.push({ text: `사거리 ${String(item.attackRange)}` })
  }
  item.affixes.forEach((affix, index) => {
    // **단추에 실리는 첨자는 `item.affixes` 안의 자리다.** 화면이 몇 줄을 그렸는지와
    // 무관해야 서버가 갈 줄을 옳게 찾는다 — 그래서 목록에 거르기·페이지를 안 켠다.
    lines.push({ text: formatAffix(affix), trail: renderRecastButton(item, index, recast) })
  })
  // **옵션 하나에 한 줄이다.** 가운뎃점으로 이으면 옵션 넷이 문장 하나가 되어, 어디까지가
  // 한 옵션인지 눈으로 갈라야 한다(실제 요청).
  return <AffixList lines={lines} />
}

/** 한 줄을 다시 찍는 단추에 필요한 것. */
interface RecastOffer {
  readonly letters: number
  readonly cost: number
  readonly disabled: boolean
  readonly onRecast: (itemId: number, affixIndex: number) => void
}

/**
 * 봉인에서 나온 줄에만 「다시 찍기」를 붙인다.
 *
 * **드롭이 달고 나온 접사에는 안 붙는다.** 어디부터가 봉인에서 나온 것인지는 서버가
 * `recastFrom` 으로 말한다 — 등급별 칸 수를 화면이 다시 들면 정본이 둘이 된다.
 *
 * **모자랄 때도 단추를 지우지 않는다.** 사라지면 「이 줄은 못 바꾸는 것」으로 읽히는데,
 * 사실은 「지금 활자가 없는 것」이다 — 둘은 사람이 할 일이 다르다 (P1).
 *
 * @param item 아이템.
 * @param index `item.affixes` 안의 자리. 그대로 서버에 실린다.
 * @param recast 값과 가진 활자.
 * @returns 단추. 다시 찍을 수 없는 줄이면 null.
 */
function renderRecastButton(
  item: ItemView,
  index: number,
  recast: RecastOffer,
): React.JSX.Element | null {
  if (index < item.recastFrom) {
    return null
  }
  const poor = recast.letters < recast.cost
  return (
    <Button
      size="sm"
      variant="ghost"
      glyph="⟳"
      disabled={recast.disabled || poor}
      title={
        poor
          ? // 모자람은 저잣거리·정비와 **같은 꼴**로 적는다 (`auctionCells.findBuyBlocker`).
            // 같은 「필요·보유」를 화면마다 다른 문형으로 적으면 실측값 병기가 규율이
            // 아니라 취향으로 보인다.
            `활자가 모자란다 (${String(recast.cost)} 필요 · ${String(recast.letters)} 있음)`
          : '활자를 내고 이 줄을 다시 찍는다 — 결과는 서버가 정한다'
      }
      onClick={() => {
        recast.onRecast(item.itemId, index)
      }}
    >
      {`다시 찍기 ${String(recast.cost)}`}
    </Button>
  )
}

/**
 * 요구조건에 적을 능력치 한글 이름.
 *
 * **정본은 `game/schemas/item.py` 의 `STAT_LABELS` 다.** 접사는 서버가 `statLabel` 을
 * 실어 보내지만 `RequirementView` 에는 그 칸이 없어, 옮겨 적는 자리가 여기밖에 없다 —
 * 그래서 한 카드 안에서 접사는 「최대체력」, 요구조건은 `hp_max` 로 갈리고 있었다.
 *
 * **표에 없는 키는 원문을 남긴다.** 빈칸으로 두면 값만 뜬 줄이 되어 무엇이 모자란지가
 * 사라진다 — 파이썬 `format_stat_label` 과 같은 규율이다.
 */
const REQUIREMENT_STAT_LABELS: ReadonlyMap<string, string> = new Map([
  ['hp_max', '최대체력'],
  ['attack', '공격력'],
  ['defense', '방어력'],
  ['attack_range', '사거리'],
  ['initiative', '선공권'],
  ['cpu_budget', 'CPU'],
])

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
          label={`${REQUIREMENT_STAT_LABELS.get(need.stat) ?? need.stat}(${String(need.actual)}) >= 요구(${String(need.minimum)})`}
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
        aria-label="저잣거리 호가"
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
        title="저잣거리에 건다 — 수수료는 걸 때 나가고 내려도 안 돌아온다"
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
    // 소모품은 **쓰임새**가 형태를 가른다 — 접두사가 전부 `scroll` 이라 축지·눈밝이·불이
    // 부적과 한 그림으로 떨어진다 (`content/itemArt`).
    const stackArt = findItemArt(choice.entry.stackCatalogId ?? '', '', choice.entry.stackUseTag)
    return (
      <div className="invd">
        <div className="invd__row">
          <Thumb
            kind="CONSUMABLE"
            label={label}
            grade={choice.entry.stackGrade}
            {...(stackArt === undefined ? {} : { art: stackArt })}
          />
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
  // **그림은 상세가 직접 고른다** (2026-09-16). 격자가 이미 같은 계산을 하지만, 그 값을
  // `CellChoice` 에 얹어 나르면 무엇을 그릴지 정하는 자리가 둘이 되고 — 한쪽만 고친 날
  // 격자와 상세가 다른 그림을 띄운다. 드는 값(`catalogId`·`hands`)은 이미 여기 있다.
  const art = findItemArt(item.catalogId, item.hands ?? '')
  return (
    <div className="invd">
      <div className="invd__row">
        {/* **이름을 안 지운다.** 아직 안 그린 형태가 섞여 있고, 한 그림을 나눠 쓰는
            셋(비수·환도·사인검)은 이름만이 어느 것인지를 말한다. */}
        <Thumb
          kind={item.slot ?? item.kind}
          label={item.labelKo}
          grade={item.grade}
          {...(art === undefined ? {} : { art })}
        />
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
        {/* **무엇을 열어 주는지 적는다** (2026-09-17 요청). 스킬을 다는 장비가 그
            사실을 어디에도 안 적고 있었다 — 카탈로그 화면은 적는데 정작 **가진 사람이
            보는 자리**가 비어 있었다. 그 장비를 껴야 규칙표에 그 재주를 쓸 수 있으니,
            「무엇을 해 주는가」 중에 가장 큰 것이 이것이다.
            이름은 규칙 편집기와 같은 말을 쓴다 — 여기만 `SKILL_1` 로 적으면 두 화면이
            같은 것을 다르게 부른다. */}
        {item.grantsSkill === '' ? null : (
          <GlyphState
            state="armed"
            size="sm"
            label={`재주 · ${formatParamLabel(item.grantsSkill)}`}
          />
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
      {renderAffixes(item, {
        letters: props.letters,
        cost: props.recastCost,
        disabled,
        onRecast: props.onRecast,
      })}
      {/* **가방 칸에서만 견준다.** 장비 칸을 고르면 견줄 상대가 자기 자신이다. */}
      {choice.kind === 'equip' ? null : renderCompare(item, props.worn)}
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
            {`복구 ${String(props.repairCost)}푼`}
          </Button>
        ) : null}
        {item.sealedSlots > 0 ? (
          <Button
            size="sm"
            variant="secondary"
            glyph="◈"
            disabled={disabled}
            title="푼을 내고 옵션 하나를 연다 — 결과는 서버가 정한다"
            onClick={() => {
              props.onUnseal(item.itemId)
            }}
          >
            {`봉인 해제 ${String(item.unsealCost)}푼`}
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
