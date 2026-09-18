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
 * **`판 0` 이 이 화면에서 가장 볼 것이다.** 다만 **원인을 단언하지 않는다** — 셋 중
 * 무엇이든 될 수 있다: 출격을 눌렀는데 `requestTicket` 이 실패해 `applyLocalRun()` 으로
 * 떨어졌거나(그 판은 G1 계측에서 빠진다), 관리 화면만 열었거나, `1227425`
 * (2026-09-17 11:43, 「페이지를 여는 것만으로 계정이 하나씩 생기고 있었다」) 이전에
 * 생긴 계정이거나.
 *
 * **그 셋이 섞여 있어서 수 하나로는 못 읽는다.** 그 커밋 전에 생긴 계정 118 중 티켓을
 * 받은 것이 9(8%)이고, 뒤로는 12 중 7(58%)이다 — 앞엣것은 그냥 들렀다 간 사람의
 * 기록이지 잃어버린 판이 아니다. 화면은 수를 보여 주고 판단은 사람이 한다.
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
        {/* **사실만 적고 원인은 안 적는다.** 판이 0 인 계정은 티켓을 못 받았을 수도,
            그냥 들렀다 갔을 수도 있다 — `1227425`(2026-09-17) 전에는 페이지를 여는
            것만으로 계정이 생겼으므로 그 시절 줄이 여기 그대로 섞인다. 원인을 단언하면
            아직 안 센 것을 센 것처럼 말하게 된다.

            0 이면 적지 않는다: 없는 경보를 늘 띄우면 아무도 안 읽는다. */}
        {lost === 0 ? null : (
          <GlyphState
            state="pending"
            size="sm"
            label={`${String(lost)}명은 서버에 판이 안 남았다 — 티켓을 못 받았거나 그냥 들렀다 갔다`}
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
