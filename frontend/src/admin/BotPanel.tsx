/**
 * 봇·도플갱어 관리 패널.
 *
 * **결과를 왼쪽에 둔다.** 규칙표와 실력은 우리가 정해 준 값이라 새 사실이 없고, 알아야
 * 할 것은 「그래서 어떻게 됐는가」다 — 판·승·최고층. 승리가 0이면 그 봇은 세계에
 * 아무것도 안 남기며, 그 사실이 한눈에 보여야 봇을 늘릴지 줄일지 정할 수 있다.
 *
 * **참/거짓을 색으로만 적지 않는다.** 돌고 있음/멈춤은 글리프와 글자를 함께 쓴다
 * (design/README.md §성격 — 색·글리프·명도 3중 표기).
 *
 * 훅은 고른 줄 하나만 든다. 편집은 고른 줄의 상세에 살고, 줄마다 입력을 펴면 좁은
 * 화면에서 한 줄이 서너 줄로 꺾인다 — 장비 격자와 같은 이유다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { BotOverview, BotView } from '../storage/botAdmin'
import { InventoryGrid } from '../editor/InventoryGrid'
import type { InventoryView } from '../storage'

/** 아무것도 없을 때 적는 말. 빈 화면은 고장으로 읽힌다. */
const EMPTY_BOTS = '봇이 없다 — 러너가 처음 뜰 때 열을 세운다'

/** 10진수. `parseInt` 가 밑을 안 받으면 0 으로 시작한 값을 8진수로 읽는다. */
const DECIMAL_RADIX = 10

/** 한 시간(초). 리듬을 「시간당 몇 판」으로 되돌릴 때 쓴다. */
const HOUR_SEC = 3600

/**
 * 리듬을 사람이 읽는 말로 만든다.
 *
 * @param cadenceSec 판 사이 간격(초).
 * @returns `5판/시간` 꼴.
 */
export function formatCadence(cadenceSec: number): string {
  if (cadenceSec <= 0) {
    return '—'
  }
  const perHour = HOUR_SEC / cadenceSec
  const shown = perHour >= 1 ? String(Math.round(perHour * 10) / 10) : String(Math.round(perHour * 100) / 100)
  return `${shown}판/시간`
}

/**
 * 다음 출격까지를 사람이 읽는 말로 만든다.
 *
 * @param dueInSec 남은 초. 음수면 이미 차례다.
 * @returns `3분 뒤` 또는 `대기 중`.
 */
export function formatDue(dueInSec: number): string {
  if (dueInSec <= 0) {
    return '차례'
  }
  const minutes = Math.ceil(dueInSec / 60)
  return `${String(minutes)}분 뒤`
}

/**
 * 승률을 적는다. **분모를 함께 적는다** — 「100%」가 1판인지 100판인지 알아야 한다.
 *
 * @param wins 이긴 판.
 * @param runs 제출한 판.
 * @returns `3 / 40 (8%)`.
 */
export function formatWinRate(wins: number, runs: number): string {
  if (runs <= 0) {
    return '0 / 0'
  }
  return `${String(wins)} / ${String(runs)} (${String(Math.round((wins * 100) / runs))}%)`
}

/** BotPanel 이 받는 props. */
export interface BotPanelProps {
  readonly overview: BotOverview | undefined
  readonly rulesetIds: readonly string[]
  readonly onSave: (bot: {
    accountId: number
    rulesetId: string
    skillPct: number
    cadenceSec: number
    isActive: boolean
  }) => void
  /** 내 가방의 아이템 하나를 이 봇에게 넘긴다. **한 방향이다** — 돌아오는 길은 없다. */
  readonly onGift?: (accountId: number, itemId: number) => void
  /**
   * 내 화폐를 봇에게 넘긴다 (2026-09-06).
   *
   * **밑천을 주는 자리다.** 벌이가 느린 봇은 경매에서 영영 못 산다 — 그러면 「봇이
   * 아무것도 안 산다」가 봇의 규칙이 아니라 잔액의 문제가 된다.
   */
  readonly onCoin?: (accountId: number, amount: number) => void
  /** 내 가방. */
  readonly myBag?: InventoryView | undefined
  /** 줄을 골랐을 때 부른다. 그 봇의 가방을 읽어 오라는 신호다. */
  readonly onPickBot?: (accountId: number) => void
  /**
   * 고른 봇의 상세 화면. **표 바로 아래에 선다.**
   *
   * 슬롯인 이유는 이 패널이 봇 **떼**를 다루기 때문이다 — 하나를 여는 일은 밖의
   * 몫이다. 자리가 여기인 이유는 **묻히지 않게** 하려는 것이다: 도플갱어와 두 가방
   * 뒤에 두었더니 스크롤을 한참 지나야 나왔고, 봇을 눌러 연 화면이 거기 있었다.
   */
  readonly detail?: React.ReactNode
}

/**
 * 봇 한 줄을 그린다.
 *
 * @param bot 그릴 봇.
 * @param isPicked 지금 고른 줄인가.
 * @param onPick 줄을 고른다.
 * @returns 줄 요소.
 */
function renderRow(
  bot: BotView,
  isPicked: boolean,
  onPick: (bot: BotView) => void,
): React.JSX.Element {
  return (
    <button
      type="button"
      key={bot.accountId}
      className={`botrow${isPicked ? ' botrow--picked' : ''}`}
      onClick={() => {
        onPick(bot)
      }}
    >
      <span className="botrow__name">{bot.handle}</span>
      <GlyphState
        state={bot.isActive ? 'true' : 'false'}
        size="sm"
        label={bot.isActive ? '돌림' : '멈춤'}
      />
      <span className="botrow__cell">{formatWinRate(bot.wins, bot.runs)}</span>
      <span className="botrow__cell">{`${String(bot.bestFloor)}층`}</span>
      <span className="botrow__cell">{bot.rulesetId}</span>
      <span className="botrow__cell">{`실력 ${String(bot.skillPct)}%`}</span>
      <span className="botrow__cell">{formatCadence(bot.cadenceSec)}</span>
      <span className="botrow__cell">{bot.isActive ? formatDue(bot.dueInSec) : '—'}</span>
      <span className="botrow__cell">{`화폐 ${String(bot.balance)} · 물건 ${String(bot.items)}`}</span>
    </button>
  )
}

/**
 * 봇·도플갱어 관리 패널을 그린다.
 *
 * @param props 현황과 저장 처리기.
 * @returns 패널 요소.
 */
export function BotPanel(props: BotPanelProps): React.JSX.Element {
  const [pickedId, setPickedId] = useState(0)
  const bots = props.overview?.bots ?? []
  const picked = bots.find((bot) => bot.accountId === pickedId)
  const active = bots.filter((bot) => bot.isActive).length
  const winning = bots.filter((bot) => bot.wins > 0).length

  return (
    <div className="bots">
      <Panel
        title="봇"
        meta={`${String(active)} / ${String(bots.length)} 돌림 · 이긴 봇 ${String(winning)}`}
        tone="panel"
        padded
      >
        {bots.length === 0 ? (
          <ValueExpr text={EMPTY_BOTS} size="sm" dim />
        ) : (
          <>
            {/* 승리가 0이면 그 봇은 세계에 아무것도 안 남긴다 — 먼저 말한다. */}
            {winning === 0 ? (
              <GlyphState
                state="danger"
                size="sm"
                label="아직 아무 봇도 못 이겼다 — 전리품·경매·순위가 생기지 않는다"
              />
            ) : null}
            {/* **줄에 머리글을 붙인다.** 라벨 없는 「0 / 13」은 무엇을 세는지 알 수
                없다 — 실제로 그 질문을 받았다. */}
            <div className="botrow botrow--head" aria-hidden="true">
              <span className="botrow__name">이름</span>
              <span className="botrow__cell">상태</span>
              <span className="botrow__cell">승 / 판</span>
              <span className="botrow__cell">최고</span>
              <span className="botrow__cell">규칙표</span>
              <span className="botrow__cell">실력</span>
              <span className="botrow__cell">리듬</span>
              <span className="botrow__cell">다음</span>
              <span className="botrow__cell">벌이</span>
            </div>
            <div className="bots__grid">
              {bots.map((bot) =>
                renderRow(bot, bot.accountId === pickedId, (target) => {
                  const next = pickedId === target.accountId ? 0 : target.accountId
                  setPickedId(next)
                  if (next !== 0) {
                    props.onPickBot?.(next)
                  }
                }),
              )}
            </div>
            {picked === undefined ? (
              <ValueExpr text="줄을 고르면 여기에서 고치고, 아래에서 그 봇을 연다" size="sm" dim />
            ) : (
              <BotEditor
                bot={picked}
                rulesetIds={props.rulesetIds}
                minCadenceSec={props.overview?.minCadenceSec ?? 0}
                onSave={props.onSave}
                onGift={props.onGift}
                onCoin={props.onCoin}
                myBag={props.myBag}
              />
            )}
          </>
        )}
      </Panel>

      {/* 고른 봇의 상세. **표 바로 다음이다** — 뒤로 밀면 스크롤에 묻힌다. */}
      {props.detail}

    </div>
  )
}



/** BotEditor 가 받는 props. */
interface BotEditorProps {
  readonly bot: BotView
  readonly rulesetIds: readonly string[]
  readonly minCadenceSec: number
  readonly onSave: BotPanelProps['onSave']
  readonly onGift?: BotPanelProps['onGift']
  readonly onCoin?: BotPanelProps['onCoin']
  /** 내 가방. 여기서 골라 넘긴다 — id 를 손으로 적게 하지 않는다. */
  readonly myBag?: InventoryView | undefined
}

/**
 * 고른 봇의 상세와 조작을 그린다.
 *
 * **멈춤은 지움이 아니다.** 지우는 조작을 두지 않는다 — 지우면 그 봇이 벌어 둔 장비·
 * 도감·순위가 함께 사라지고, 다시 세우면 다른 계정이 된다.
 *
 * @param props 고른 봇과 저장 처리기.
 * @returns 상세 요소.
 */
function BotEditor(props: BotEditorProps): React.JSX.Element {
  const { bot } = props
  const [pickedKey, setPickedKey] = useState('')
  // 고른 칸이 아니라 **넘길 아이템**을 따로 든다. 칸을 고르는 것과 넘기는 것을 한 번에
  // 묶으면 잘못 누른 칸이 곧 되돌릴 수 없는 이관이 된다.
  const [giftId, setGiftId] = useState(0)
  const [coin, setCoin] = useState('')
  return (
    <div className="bots__edit">
      <span className="bots__edit-name">{`${bot.handle} · ${bot.label}`}</span>
      <select
        className="bots__field"
        aria-label="규칙표"
        value={bot.rulesetId}
        onChange={(event) => {
          props.onSave({ ...toDraft(bot), rulesetId: event.target.value })
        }}
      >
        {props.rulesetIds.map((id) => (
          <option value={id} key={id}>
            {id}
          </option>
        ))}
      </select>
      <label className="bots__label" htmlFor={`skill-${String(bot.accountId)}`}>
        실력 %
      </label>
      <input
        id={`skill-${String(bot.accountId)}`}
        className="bots__field bots__field--num"
        type="number"
        min={20}
        max={100}
        defaultValue={bot.skillPct}
        onBlur={(event) => {
          props.onSave({ ...toDraft(bot), skillPct: Number.parseInt(event.target.value, 10) || 20 })
        }}
      />
      <label className="bots__label" htmlFor={`cad-${String(bot.accountId)}`}>
        간격 초
      </label>
      <input
        id={`cad-${String(bot.accountId)}`}
        className="bots__field bots__field--num"
        type="number"
        min={props.minCadenceSec}
        defaultValue={bot.cadenceSec}
        onBlur={(event) => {
          props.onSave({
            ...toDraft(bot),
            cadenceSec: Number.parseInt(event.target.value, 10) || props.minCadenceSec,
          })
        }}
      />
      <Button
        size="sm"
        variant={bot.isActive ? 'ghost' : 'primary'}
        glyph={bot.isActive ? '‖' : '▶'}
        title={bot.isActive ? '이 봇을 멈춘다 — 지우는 것이 아니다' : '다시 돌린다'}
        onClick={() => {
          props.onSave({ ...toDraft(bot), isActive: !bot.isActive })
        }}
      >
        {bot.isActive ? '멈춤' : '돌림'}
      </Button>
      <ValueExpr
        text={`간격은 서버가 ${String(props.minCadenceSec)}초 아래로는 안 내린다`}
        size="sm"
        dim
      />
      {/* **여기에는 내 가방만 둔다.** 봇의 가방은 아래 상세의 「가방」 탭에 있다 — 같은
          것을 한 화면에 두 번 그리면 어느 쪽이 최신인지 알 수 없고, 실제로 넘긴 뒤에
          한쪽만 갱신되는 창이 생긴다. 여기 남길 이유는 하나뿐이다: **넘길 물건을 고르는
          곳**이라는 것. */}
      {/* **화폐는 가방과 따로다.** 물건을 고르는 흐름에 숫자 입력이 끼면 「무엇을
          넘기는 중인지」가 흐려진다. */}
      {props.onCoin === undefined ? null : (
        <div className="bots__gift">
          <ValueExpr text={`화폐 ${String(bot.balance)} · ${bot.handle} 에게 넘김`} size="sm" />
          <input
            className="cat__input"
            inputMode="numeric"
            value={coin}
            placeholder="양"
            aria-label="넘길 화폐"
            onChange={(event) => {
              setCoin(event.target.value)
            }}
          />
          <Button
            size="sm"
            variant="ghost"
            disabled={!(Number.parseInt(coin, DECIMAL_RADIX) > 0)}
            title="한 방향이다 — 넘긴 화폐는 돌아오지 않는다"
            onClick={() => {
              props.onCoin?.(bot.accountId, Number.parseInt(coin, DECIMAL_RADIX))
              setCoin('')
            }}
          >
            넘기기
          </Button>
        </div>
      )}
      {props.onGift === undefined ? null : (
        <div className="bots__bags">
          <div className="inv bots__inv">
            <InventoryGrid
              inventory={props.myBag}
              pickedKey={pickedKey}
              ownerLabel="내"
              onPick={(cell) => {
                setPickedKey((current) => (current === cell.key ? '' : cell.key))
                setGiftId(cell.entry?.item?.itemId ?? 0)
              }}
            />
          </div>
        </div>
      )}
      {props.onGift === undefined || giftId === 0 ? null : (
        <div className="bots__gift">
          <ValueExpr text={`#${String(giftId)} 를 ${bot.handle} 에게`} size="sm" />
          <Button
            size="sm"
            variant="primary"
            glyph="→"
            title="이 아이템을 이 봇에게 넘긴다. 도착하면 귀속되어 되돌릴 수 없다"
            onClick={() => {
              props.onGift?.(bot.accountId, giftId)
              setGiftId(0)
            }}
          >
            넘기기
          </Button>
          <ValueExpr text="넘기면 귀속된다 — 되돌릴 수 없다" size="sm" dim />
        </div>
      )}
      {/* **되돌릴 수 없다고 먼저 말한다.** 귀속은 눌러 본 뒤에 알면 늦다. */}
    </div>
  )
}


/**
 * 봇 한 줄을 저장 요청 모양으로 옮긴다.
 *
 * @param bot 봇.
 * @returns 저장 요청 절.
 */
function toDraft(bot: BotView): {
  accountId: number
  rulesetId: string
  skillPct: number
  cadenceSec: number
  isActive: boolean
} {
  return {
    accountId: bot.accountId,
    rulesetId: bot.rulesetId,
    skillPct: bot.skillPct,
    cadenceSec: bot.cadenceSec,
    isActive: bot.isActive,
  }
}
