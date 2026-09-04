/**
 * 정비 규칙 에디터 — **규칙표의 두 번째 탭** (설계/4_아이템 §5).
 *
 * 예전에는 가방 탭 안에 드롭다운 목록으로 있었다. 두 가지가 어긋나 있었다.
 *
 * 1. **자리가 틀렸다.** 정비는 「무엇을 가졌는가」가 아니라 「무엇을 자동으로 할 것인가」다 —
 *    전투 규칙표와 같은 종류의 물건이고(행 순서가 실행 순서다), 가방 아래에 있으면
 *    소모품 칸에 밀려 안 보인다.
 * 2. **모양이 틀렸다.** 행이 드롭다운 둘이라 목록을 훑을 때 무엇이 언제 도는지가 안
 *    보였고, 검증도 미리보기도 없어 **저장하고 판을 한 번 돌고 나서야** 무엇이 사라졌는지
 *    알았다.
 *
 * 그래서 전투 규칙과 같은 골격을 쓴다 — 왼쪽 팔레트(행동 넷), 가운데 순서 리스트,
 * 오른쪽 검증. 다른 것은 CPU 가 없다는 것뿐이고, 그 자리에 **잔액**이 선다: 정비가 재는
 * 예산은 CPU 가 아니라 돈이다.
 *
 * **행을 세우는 자리는 팔레트 하나다.** 본문에도 같은 버튼 넷을 펴 두면 어느 쪽이 진짜인지
 * 모르게 된다 — 소모품 끼우기를 두 집에 두지 않는 것과 같은 규율이다.
 *
 * 훅은 고른 행 하나뿐이다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { ConsumableView, InventoryView, MaintenanceRowView, MaintenanceView } from '../storage'

import { checkLinked, type LinkState } from './linkState'
import {
  buildMaintenancePreview,
  checkPreviewIdle,
  formatMoneyDelta,
  type MaintenancePreview,
} from './maintenancePreview'
import {
  checkBlocked,
  checkMaintenanceRows,
  duplicateRow,
  findAction,
  formatMaintenanceSentence,
  MAINTENANCE_ACTIONS,
  MAX_MAINTENANCE_ROWS,
  moveRow,
  replaceRow,
  type MaintenanceProblem,
} from './maintenanceRules'

export interface MaintenanceEditorProps {
  readonly view: MaintenanceView | undefined
  readonly link: LinkState
  readonly detail: string
  /** 미리보기가 재는 지금 가방·장비. */
  readonly inventory: InventoryView | undefined
  /** 미리보기가 재는 지금 소모품 칸. */
  readonly consumables: ConsumableView | undefined
  /**
   * 퍼센트 접사를 값으로 바꾸는 기준. 장비 교체의 저울이 쓴다.
   *
   * **실제 합산식이 쓰는 그 값이다** — 환산 상수를 지어내면 그것이 곧 아무도 안 정한
   * 밸런스 결정 하나가 된다 (`bots/upgrade`).
   */
  readonly baseStats: Readonly<Record<string, number>>
  readonly onChange: (view: MaintenanceView) => void
}

/** 언제 도는가. 화면 맨 위에 한 번 적는다 — 이것을 모르면 순서를 짤 이유가 없다. */
const WHEN_TEXT = '티켓이 닫힐 때(죽거나 완주) 위에서 아래로 한 번 돈다'

/** 미리보기가 어림이라는 사실. **확정처럼 적으면 틀렸을 때 화면이 거짓말한 것이 된다.** */
const ESTIMATE_TEXT = '지금 가방으로 잰 어림이다 — 실제로는 판이 끝난 뒤의 가방으로 돈다'

/** 인자 칸 옆에 붙일 한 줄. 고르는 값이 무엇을 뜻하는지 말한다. */
const ARG_NOTES: Readonly<Record<string, string>> = {
  DISCARD: '유물은 자동으로 안 버린다 — 되찾은 것도 남는다',
  UPGRADE_GEAR: '봇이 쓰는 저울과 같다 — 근소한 차이로는 안 바꾼다',
}

/**
 * 행 하나를 그린다.
 *
 * **문장 한 줄과 조작이 한 행에 산다.** 전투 규칙 행과 같은 결이다 — 무엇이 언제 도는지는
 * 문장이 말하고, 고치는 것은 행을 골라 아래 상세에서 한다.
 *
 * @param props 행과 처리기들.
 * @returns 행 요소.
 */
function MaintenanceRow(props: {
  readonly row: MaintenanceRowView
  readonly index: number
  readonly total: number
  readonly isPicked: boolean
  readonly preview: string
  readonly isActive: boolean
  readonly problems: readonly MaintenanceProblem[]
  readonly disabled: boolean
  readonly onPick: (index: number) => void
  readonly onMove: (from: number, to: number) => void
  readonly onDuplicate: (index: number) => void
  readonly onRemove: (index: number) => void
}): React.JSX.Element {
  const { index, row } = props
  const picked = props.isPicked ? ' mnt__row--picked' : ''
  // 하는 일이 없는 행은 명도로 뒤로 물린다 — 규칙표의 비활성 행과 같은 문법이다.
  const idle = props.isActive ? '' : ' mnt__row--idle'
  return (
    <li className={`mnt__row${picked}${idle}`}>
      <button
        type="button"
        className="mnt__hit"
        aria-pressed={props.isPicked}
        aria-label={`정비 ${String(index + 1)} 고르기`}
        onClick={() => {
          props.onPick(index)
        }}
      >
        <span className="mnt__when">{`${String(index + 1)}.`}</span>
        <span className="mnt__lines">
          <span className="mnt__what">{formatMaintenanceSentence(row)}</span>
          {/* **실측값을 병기한다.** 「버린다」가 아니라 「지금이면 2개 버림」이다 —
              조건문에 각 항의 값을 적는 것과 같은 규칙이다 (GDD §8.2, P1). */}
          <span className="mnt__now">{props.preview}</span>
        </span>
      </button>
      <span className="mnt__ops">
        <Button
          size="sm"
          variant="ghost"
          glyph="↑"
          disabled={props.disabled || index === 0}
          title="한 칸 위로 — 순서가 실행 순서다"
          onClick={() => {
            props.onMove(index, index - 1)
          }}
        />
        <Button
          size="sm"
          variant="ghost"
          glyph="↓"
          disabled={props.disabled || index >= props.total - 1}
          title="한 칸 아래로"
          onClick={() => {
            props.onMove(index, index + 1)
          }}
        />
        <Button
          size="sm"
          variant="ghost"
          glyph="⧉"
          disabled={props.disabled || props.total >= MAX_MAINTENANCE_ROWS}
          title="복제 — 등급만 바꿔 하나 더 두는 데 쓴다"
          onClick={() => {
            props.onDuplicate(index)
          }}
        />
        <Button
          size="sm"
          variant="ghost"
          glyph="✕"
          disabled={props.disabled}
          title="행을 지운다"
          onClick={() => {
            props.onRemove(index)
          }}
        />
      </span>
      {props.problems.length === 0 ? null : (
        // **문제는 그 줄 아래에 적는다.** 목록만 따로 있으면 어느 줄이 문제인지 사람이
        // 다시 찾아야 한다 — 전투 규칙 검증과 같은 규율이다 (P1).
        <ul className="mnt__problems">
          {props.problems.map((problem) => (
            <li key={problem.text}>
              <GlyphState
                state={problem.isBlocking ? 'danger' : 'pending'}
                size="sm"
                label={problem.text}
              />
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

/**
 * 고른 행의 상세를 그린다. 인자가 있는 행동만 고칠 것이 있다.
 *
 * @param props 행과 처리기.
 * @returns 상세 요소.
 */
function MaintenanceRowDetail(props: {
  readonly row: MaintenanceRowView
  readonly index: number
  readonly disabled: boolean
  readonly onChange: (row: MaintenanceRowView) => void
}): React.JSX.Element {
  const action = findAction(props.row.action)
  return (
    <div className="invd">
      <div className="invd__row">
        <span className="mnt__when">{`${String(props.index + 1)}.`}</span>
        <ValueExpr text={formatMaintenanceSentence(props.row)} size="sm" />
      </div>
      {action !== undefined && action.args.length > 0 ? (
        <div className="invd__row">
          <label className="wld__label" htmlFor="mnt-arg">
            {action.argLabel}
          </label>
          <select
            id="mnt-arg"
            className="term__field"
            value={props.row.grade}
            disabled={props.disabled}
            onChange={(event) => {
              props.onChange({ ...props.row, grade: event.target.value })
            }}
          >
            {action.args.map(([value, label]) => (
              <option value={value} key={value}>
                {label}
              </option>
            ))}
          </select>
          {/* 그 인자가 무엇을 뜻하는지 한 줄. 「공격」만 있으면 무엇을 기준으로 고르는지
              모른다 — 팔레트의 설명이 여기까지 따라오지 않는다. */}
          <ValueExpr text={ARG_NOTES[props.row.action] ?? ''} size="sm" dim />
        </div>
      ) : (
        <ValueExpr text="이 행동은 고칠 인자가 없다 — 순서만 정한다" size="sm" dim />
      )}
    </div>
  )
}

/**
 * 정비 행동 팔레트를 그린다.
 *
 * 전투 규칙의 블록 팔레트와 같은 자리다 — **누르면 맨 아래에 행이 하나 선다.** 예전에는
 * 「규칙 추가」 버튼 하나가 늘 `REFILL` 을 놓았고, 다른 행동을 쓰려면 드롭다운을 다시
 * 열어야 했다.
 *
 * @param props 처리기와 잠금.
 * @returns 팔레트 요소.
 */
export function MaintenancePalette(props: {
  readonly disabled: boolean
  readonly isFull: boolean
  readonly onAdd: (action: string) => void
}): React.JSX.Element {
  return (
    <Panel title="정비 행동" meta="누르면 맨 아래에 선다" tone="panel" padded scroll>
      <div className="mnt__palette">
        {MAINTENANCE_ACTIONS.map((action) => (
          <button
            type="button"
            className="mnt__block"
            key={action.id}
            disabled={props.disabled || props.isFull}
            title={action.note}
            onClick={() => {
              props.onAdd(action.id)
            }}
          >
            <span className="mnt__block-name">{action.label}</span>
            <span className="mnt__block-note">{action.note}</span>
          </button>
        ))}
      </div>
      {props.isFull ? (
        <GlyphState
          state="pending"
          size="sm"
          label={`행이 ${String(MAX_MAINTENANCE_ROWS)}개다 — 더 두려면 하나를 지운다`}
        />
      ) : null}
    </Panel>
  )
}

/**
 * 정비 검증과 미리보기를 그린다.
 *
 * 전투 규칙의 검증 열과 같은 자리다. 다른 것은 **미리보기가 함께 산다**는 것이다 —
 * 정비는 조용히 도는 자동화라, 「이 배치가 옳은가」보다 「이 배치가 무엇을 하는가」가
 * 먼저 답해져야 한다.
 *
 * @param props 검증 결과와 미리보기.
 * @returns 검증 요소.
 */
export function MaintenanceCheck(props: {
  readonly problems: readonly MaintenanceProblem[]
  readonly preview: MaintenancePreview
  readonly hasRows: boolean
}): React.JSX.Element {
  const blocking = props.problems.filter((problem) => problem.isBlocking)
  const notes = props.problems.filter((problem) => !problem.isBlocking)
  return (
    <Panel
      title="검증과 미리보기"
      meta={blocking.length === 0 ? '통과' : String(blocking.length)}
      scroll
    >
      {blocking.length === 0 ? (
        <GlyphState state="true" label="저장할 수 있는 정비 규칙이다" size="sm" />
      ) : (
        <ul className="check-list">
          {blocking.map((problem) => (
            <li key={problem.text}>
              <GlyphState
                state="danger"
                size="sm"
                label={problem.index < 0 ? problem.text : `[${String(problem.index + 1)}] ${problem.text}`}
              />
            </li>
          ))}
        </ul>
      )}
      {notes.length === 0 ? null : (
        <ul className="check-list">
          {notes.map((problem) => (
            <li key={problem.text}>
              <GlyphState
                state="pending"
                size="sm"
                label={problem.index < 0 ? problem.text : `[${String(problem.index + 1)}] ${problem.text}`}
              />
            </li>
          ))}
        </ul>
      )}

      <div className="mnt__sum">
        <ValueExpr text={ESTIMATE_TEXT} size="sm" dim />
        {!props.hasRows ? (
          <ValueExpr text="행이 없다 — 정비는 아무것도 안 한다" size="sm" dim />
        ) : checkPreviewIdle(props.preview) ? (
          // **「돌긴 도는데 하는 일이 없다」를 말해야 한다.** 안 그러면 켜 놓고
          // 도는 줄 알았던 정비가 몇 판 내내 아무것도 안 한다.
          <GlyphState state="pending" size="sm" label="지금 상태로는 아무것도 안 한다" />
        ) : null}
        {/* 잔액이 CPU 의 자리다 — 정비가 재는 예산은 돈이다. */}
        <ValueExpr
          text={`잔액 ${String(props.preview.balance)} → ${String(props.preview.balanceAfter)} (${formatMoneyDelta(props.preview.moneyDelta)})`}
          size="sm"
        />
        {props.preview.isShort ? (
          <GlyphState state="danger" size="sm" label="잔액이 말라 못 하는 일이 있다" />
        ) : null}
      </div>
    </Panel>
  )
}

/**
 * 정비 규칙 에디터를 그린다.
 *
 * @param props 행들과 처리기.
 * @returns 렌더 트리.
 */
export function MaintenanceEditor(props: MaintenanceEditorProps): React.JSX.Element {
  const [pickedIndex, setPickedIndex] = useState(-1)
  const view = props.view
  if (view === undefined) {
    return (
      <Panel title="정비 규칙" tone="panel" padded scroll>
        <ValueExpr text="서버에 닿지 못했다 — 정비 규칙을 못 읽는다" size="sm" dim />
      </Panel>
    )
  }
  const disabled = !checkLinked(props.link)
  const rows = view.rows
  const problems = checkMaintenanceRows(rows)
  const preview = buildMaintenancePreview(rows, props.inventory, props.consumables, props.baseStats)
  const picked = rows[pickedIndex]

  const commit = (next: readonly MaintenanceRowView[]): void => {
    props.onChange({ rows: next })
  }

  return (
    <Panel
      title="정비 규칙"
      meta={`행 ${String(rows.length)} / ${String(MAX_MAINTENANCE_ROWS)}`}
      padded
      scroll
    >
      <div className="mnt">
        <ValueExpr text={WHEN_TEXT} size="sm" dim />
        {checkBlocked(problems) ? (
          <GlyphState state="danger" size="sm" label="이대로는 서버가 저장을 거절한다" />
        ) : null}
        {rows.length === 0 ? (
          <ValueExpr
            text="정비 규칙이 없다 — 「정비 행동」에서 하나를 눌러 세운다. 없으면 아무것도 안 한다"
            size="sm"
            dim
          />
        ) : (
          <ul className="mnt__list">
            {rows.map((row, index) => (
              <MaintenanceRow
                // 행에 고유 id 가 없다 — 순서가 곧 정체성이라 자리 번호가 key 다.
                key={`mnt-${String(index)}`}
                row={row}
                index={index}
                total={rows.length}
                isPicked={index === pickedIndex}
                preview={preview.rows[index]?.text ?? ''}
                isActive={preview.rows[index]?.isActive ?? false}
                problems={problems.filter((problem) => problem.index === index)}
                disabled={disabled}
                onPick={(at) => {
                  setPickedIndex((current) => (current === at ? -1 : at))
                }}
                onMove={(from, to) => {
                  commit(moveRow(rows, from, to))
                  setPickedIndex(to)
                }}
                onDuplicate={(at) => {
                  commit(duplicateRow(rows, at))
                  setPickedIndex(at + 1)
                }}
                onRemove={(at) => {
                  commit(replaceRow(rows, at, undefined))
                  setPickedIndex(-1)
                }}
              />
            ))}
          </ul>
        )}
        {picked === undefined ? null : (
          <MaintenanceRowDetail
            row={picked}
            index={pickedIndex}
            disabled={disabled}
            onChange={(next) => {
              commit(replaceRow(rows, pickedIndex, next))
            }}
          />
        )}
        {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
      </div>
    </Panel>
  )
}
