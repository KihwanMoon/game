/**
 * 정비 규칙 패널 (설계/4_아이템 §5).
 *
 * **규칙표의 형제다.** 전투 규칙이 「조건 → 행동」이듯 정비도 「런이 끝나면 → 행동」의
 * 문장으로 적는다 — 같은 게임 문법이라는 것이 보이게. 실행은 서버가 티켓이 닫힐 때
 * 하고, 무엇을 했는지는 결과 화면의 보상 줄에 한 줄로 온다.
 *
 * 훅이 없다. 상태는 부모가 들고, 여기는 스위치를 그릴 뿐이다.
 */
import { Button, Panel, ValueExpr } from '../ds'
import type { MaintenanceView } from '../storage'

export interface MaintenancePanelProps {
  readonly view: MaintenanceView | undefined
  readonly isOnline: boolean
  readonly detail: string
  readonly onChange: (view: MaintenanceView) => void
}

/** 정비 문장 한 줄. */
function renderRule(props: {
  readonly label: string
  readonly isOn: boolean
  readonly disabled: boolean
  readonly onToggle: () => void
}): React.JSX.Element {
  return (
    <li className="mnt__row">
      <span className="mnt__when">런이 끝나면</span>
      <span className="mnt__arrow">→</span>
      <span className={`mnt__what${props.isOn ? '' : ' mnt__what--off'}`}>{props.label}</span>
      <Button size="sm" variant={props.isOn ? 'secondary' : 'ghost'} disabled={props.disabled}
        onClick={props.onToggle}
      >
        {props.isOn ? '켬' : '끔'}
      </Button>
    </li>
  )
}

/**
 * 정비 규칙을 그린다.
 *
 * @param props 규칙과 처리기.
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
  return (
    <Panel title="정비 규칙">
      <ValueExpr text="티켓이 닫힐 때(죽거나 완주) 서버가 실행하고, 결과 줄에 한 줄로 적는다" size="sm" dim />
      <ul className="mnt__list">
        {renderRule({
          label: '끼운 소모품을 잔액 안에서 보충한다',
          isOn: view.isRefillOn,
          disabled,
          onToggle: () => {
            props.onChange({ ...view, isRefillOn: !view.isRefillOn })
          },
        })}
        {renderRule({
          label: '파손된 착용 장비를 잔액 안에서 복구한다',
          isOn: view.isRepairOn,
          disabled,
          onToggle: () => {
            props.onChange({ ...view, isRepairOn: !view.isRepairOn })
          },
        })}
        {renderRule({
          label: '보통 등급 가방 장비를 버린다 (되찾은 것은 남긴다)',
          isOn: view.discardGrade === 'COMMON',
          disabled,
          onToggle: () => {
            props.onChange({
              ...view,
              discardGrade: view.discardGrade === 'COMMON' ? '' : 'COMMON',
            })
          },
        })}
      </ul>
      {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
    </Panel>
  )
}
