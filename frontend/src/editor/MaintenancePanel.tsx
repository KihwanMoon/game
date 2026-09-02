/**
 * 정비 규칙 패널 (설계/4_아이템 §5).
 *
 * **전투 규칙표처럼 조립한다.** 행을 더하고 빼고 순서를 바꾼다 — 행 순서가 실행 순서다.
 * 어휘는 닫혀 있다: 행동 넷, 버리기 인자 둘. 자유 조건식은 전투 DSL 의 자리다.
 *
 * 훅이 없다. 상태는 부모가 들고, 여기는 행을 그릴 뿐이다.
 */
import { Button, Panel, ValueExpr } from '../ds'
import type { MaintenanceRowView, MaintenanceView } from '../storage'

export interface MaintenancePanelProps {
  readonly view: MaintenanceView | undefined
  readonly isOnline: boolean
  readonly detail: string
  readonly onChange: (view: MaintenanceView) => void
}

/** 행동의 한글 문장. */
const ACTION_LABELS: readonly (readonly [string, string])[] = [
  ['DISCARD', '등급의 가방 장비를 버린다 (되찾은 것은 남긴다)'],
  ['REPAIR', '파손된 착용 장비를 잔액 안에서 복구한다'],
  ['REFILL', '끼운 소모품을 잔액 안에서 보충한다'],
  ['SELL_STOCK', '가방의 소모품 재고를 전부 판다'],
]

const GRADE_OPTIONS: readonly (readonly [string, string])[] = [
  ['COMMON', '보통'],
  ['FINE', '상급'],
]

/**
 * 행 하나를 바꾼 목록을 만든다.
 *
 * @param rows 지금 행들.
 * @param index 바꿀 자리.
 * @param row 새 행. undefined 면 지운다.
 * @returns 새 목록.
 */
export function replaceRow(
  rows: readonly MaintenanceRowView[],
  index: number,
  row: MaintenanceRowView | undefined,
): readonly MaintenanceRowView[] {
  const next = [...rows]
  if (row === undefined) {
    next.splice(index, 1)
  } else {
    next[index] = row
  }
  return next
}

/**
 * 행을 한 칸 위로 올린 목록을 만든다. 순서가 실행 순서라 오르내리기가 조립의 반이다.
 *
 * @param rows 지금 행들.
 * @param index 올릴 자리. 0 이면 그대로다.
 * @returns 새 목록.
 */
export function liftRow(
  rows: readonly MaintenanceRowView[],
  index: number,
): readonly MaintenanceRowView[] {
  if (index <= 0 || index >= rows.length) {
    return rows
  }
  const next = [...rows]
  const [row] = next.splice(index, 1)
  if (row !== undefined) {
    next.splice(index - 1, 0, row)
  }
  return next
}

/**
 * 정비 규칙을 그린다.
 *
 * @param props 행들과 처리기.
 * @returns 렌더 트리.
 */
export function MaintenancePanel(props: MaintenancePanelProps): React.JSX.Element {
  const view = props.view
  if (view === undefined) {
    return (
      <Panel title="정비 규칙">
        <ValueExpr text="서버에 닿지 못했다 — 정비 규칙을 못 읽는다" size="sm" dim />
      </Panel>
    )
  }
  const disabled = !props.isOnline
  const commit = (rows: readonly MaintenanceRowView[]): void => {
    props.onChange({ rows })
  }
  return (
    <Panel title="정비 규칙">
      <ValueExpr
        text="티켓이 닫힐 때(죽거나 완주) 위에서 아래로 실행하고, 결과 줄에 한 줄로 적는다"
        size="sm"
        dim
      />
      <ul className="mnt__list">
        {view.rows.map((row, index) => (
          // 행에 고유 id 가 없다 — 순서가 곧 정체성이라 자리 번호가 key 다.
          // eslint-disable-next-line react/no-array-index-key
          <li className="mnt__row" key={index}>
            <span className="mnt__when">{`${String(index + 1)}.`}</span>
            {row.action === 'DISCARD' ? (
              <select
                className="term__field"
                value={row.grade}
                aria-label={`정비 ${String(index + 1)} 등급`}
                onChange={(event) => {
                  commit(replaceRow(view.rows, index, { ...row, grade: event.target.value }))
                }}
              >
                {GRADE_OPTIONS.map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            ) : null}
            <select
              className="term__field mnt__what"
              value={row.action}
              aria-label={`정비 ${String(index + 1)} 행동`}
              onChange={(event) => {
                const action = event.target.value
                commit(
                  replaceRow(view.rows, index, {
                    action,
                    grade: action === 'DISCARD' ? (row.grade || 'COMMON') : '',
                  }),
                )
              }}
            >
              {ACTION_LABELS.map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="ghost"
              glyph="↑"
              disabled={disabled || index === 0}
              title="한 칸 위로 — 순서가 실행 순서다"
              onClick={() => {
                commit(liftRow(view.rows, index))
              }}
            />
            <Button
              size="sm"
              variant="ghost"
              glyph="✕"
              disabled={disabled}
              title="행을 지운다"
              onClick={() => {
                commit(replaceRow(view.rows, index, undefined))
              }}
            />
          </li>
        ))}
      </ul>
      <Button
        size="sm"
        variant="secondary"
        glyph="+"
        disabled={disabled}
        onClick={() => {
          commit([...view.rows, { action: 'REFILL', grade: '' }])
        }}
      >
        규칙 추가
      </Button>
      {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
    </Panel>
  )
}
