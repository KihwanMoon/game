/**
 * 유입 패널 — 새로 들어온 계정을 본다 (U1).
 *
 * **볼 자리가 없어서 DB 를 직접 열어야 했다.** 계정을 보는 탭은 테스터 하나뿐이고 그것은
 * G1 의 분모를 정하는 자리다. 「어제 몇 명이 들어왔고 그중 누가 가입했나」를 볼 자리가
 * 없으면 아무도 안 본다 — 봇 탭과 지킴이 탭을 만든 것과 같은 이유다.
 *
 * **여기 뜨는 줄은 「앱을 연 사람」이 아니다.** 계정은 출격에서만 생기므로
 * (`requireAccount`: "여는 것만으로는 안 만든다"), 이 목록은 **판을 내려 한 사람**이다.
 * 그냥 들렀다 간 사람은 명부의 트래픽 줄이 센다.
 *
 * **`판 0` 이 이 화면에서 가장 중요한 값이다.** 출격을 눌러 계정까지 생겼는데 서버에
 * 아무것도 안 남았다는 뜻이고, 그러면 그 판은 G1 계측에서 통째로 빠진다 —
 * `requestTicket` 이 실패하면 화면이 `applyLocalRun()` 으로 떨어지기 때문이다(App.tsx).
 * 그 줄이 쌓이는 것은 사람이 안 논 것이 아니라 **우리가 못 받은 것**이다.
 */
import { DataList } from '../editor/DataList'
import { GlyphState, Panel, ValueExpr } from '../ds'
import type { ArrivalList, ArrivalView } from '../storage/arrivalAdmin'

/** 아무것도 없을 때 적는 말. 빈 화면은 고장으로 읽힌다. */
const EMPTY_ROWS = '이 기간에 들어온 계정이 없다'

/** ArrivalPanel 이 받는 props. */
export interface ArrivalPanelProps {
  readonly list: ArrivalList | undefined
}

/**
 * 요약 한 줄을 만든다. **깔때기로 적는다** — 수를 따로 늘어놓으면 관계를 보는 사람이
 * 스스로 계산해야 한다.
 *
 * @param list 유입 목록과 요약.
 * @returns 적을 한 줄.
 */
export function formatArrivalSummary(list: ArrivalList): string {
  const span = `${String(list.days)}일`
  return `${span} · 들어옴 ${String(list.arrived)} → 판 낸 이 ${String(list.played)} → 가입 ${String(list.joined)}`
}

/**
 * 한 줄을 그린다.
 *
 * @param row 계정 한 줄.
 * @returns 렌더 트리.
 */
function renderRow(row: ArrivalView): React.JSX.Element {
  // 서버에 판이 없는 줄. **색만으로 가르지 않는다** — 글리프와 말이 함께 선다.
  const isLost = !row.isBot && row.runs === 0
  return (
    <div className="adminrow">
      <span className="adminrow__name">{row.name}</span>
      <span className="adminrow__num">{row.createdAt}</span>
      <GlyphState
        state={row.isJoined ? 'true' : 'false'}
        size="sm"
        label={row.isJoined ? '가입' : '익명'}
      />
      <span className="adminrow__num">{`판 ${String(row.runs)}`}</span>
      <span className="adminrow__num">{`${String(row.bestFloor)}장`}</span>
      {row.isBot ? <GlyphState state="pending" size="sm" label="봇" /> : null}
      {isLost ? <GlyphState state="blocked" size="sm" label="서버에 안 남음" /> : null}
    </div>
  )
}

/**
 * 유입 패널을 그린다.
 *
 * @param props 목록.
 * @returns 렌더 트리.
 */
export function ArrivalPanel(props: ArrivalPanelProps): React.JSX.Element {
  const { list } = props
  if (list === undefined) {
    return (
      <Panel title="유입" tone="panel" padded scroll>
        <ValueExpr text="서버에 닿지 못했다 — 유입을 못 읽는다" size="sm" dim />
      </Panel>
    )
  }
  const lost = list.rows.filter((row) => !row.isBot && row.runs === 0).length
  return (
    <div className="adm__pane">
      <Panel title="유입" meta={`${String(list.rows.length)}명`} tone="panel" padded scroll>
        <ValueExpr text={formatArrivalSummary(list)} size="sm" dim />
        {/* **이 줄이 이 화면의 값이다.** 출격을 눌러 계정까지 생겼는데 서버에 판이 없는
            것은 사람이 안 논 것이 아니라 우리가 못 받은 것이다 — 그 판은 G1 계측에서
            통째로 빠진다. 0 이면 적지 않는다: 없는 경보를 늘 띄우면 아무도 안 읽는다. */}
        {lost === 0 ? null : (
          <GlyphState
            state="danger"
            size="sm"
            label={`${String(lost)}명은 출격했는데 서버에 판이 안 남았다 — 티켓을 못 받은 것이다`}
          />
        )}
        <DataList
          items={list.rows}
          rowKey={(row) => String(row.accountId)}
          listClass="bots__grid"
          emptyText={EMPTY_ROWS}
          filterText={(row) => row.name}
          unit="명"
          renderRow={(row) => renderRow(row)}
        />
      </Panel>
    </div>
  )
}
