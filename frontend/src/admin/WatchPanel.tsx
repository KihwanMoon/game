/**
 * 지킴이 화면 — 세계가 지금 어떤지, 배포하면 무엇이 깨지는지.
 *
 * **로그에서 죽고 있었다.** 지킴이는 5분마다 정확히 판단해 컨테이너 로그에 뱉었고,
 * 컨테이너 로그를 읽는 사람은 없다 (알려진이슈 Z1). 관리 화면의 다른 곳은 **수치는
 * 있는데 소견이 없다** — 「매물 3건」은 있어도 「그 3건이 창을 지나도록 안 팔린다」는
 * 없다.
 *
 * **나쁜 것부터 놓는다.** 여덟 줄이 등급 없이 늘어서면 무엇을 먼저 볼지가 안 정해지고,
 * 그러면 결국 안 읽힌다.
 *
 * **「언제부터」를 함께 적는다.** 지킴이를 붙인 이유가 「그날 안에 드러난다」이고, 그것은
 * 시간축이 있어야 성립한다.
 *
 * **게이트를 여기서 안 돌린다.** 화면이 `pytest`·`npm` 을 띄울 길을 만들면 그것이 임의
 * 실행 통로가 된다 — 복사할 명령만 보여 준다.
 */
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { GlyphStateKind } from '../ds'
import type { WatchEvent, WatchRow, WatchView } from '../storage/watchAdmin'

/** 아직 한 번도 안 돌았을 때. 빈 화면은 고장으로 읽힌다. */
const EMPTY_ROWS = '지킴이가 아직 아무것도 안 남겼다 — 5분마다 도므로 곧 찬다'

/**
 * 등급을 글리프 상태로. **색으로만 적지 않는다** — 색·글리프·글자 3중 표기다.
 *
 * DS 의 상태 어휘는 규칙 평가용(`참`·`거짓`·`발동`)이라 심각도와 일대일이 아니다.
 * 셋이 **서로 다른 도형**이면 되고, 실제 등급 이름은 `label` 로 함께 나간다 —
 * 그것이 색을 못 보는 경로의 마지막 채널이다.
 */
const LEVEL_STATE: Readonly<Record<string, GlyphStateKind>> = {
  OK: 'true',
  살핌: 'armed',
  틀림: 'danger',
}

/**
 * 등급을 글리프 상태로 바꾼다.
 *
 * @param level 서버가 준 등급.
 * @returns 글리프 상태. 모르는 값이면 살핌으로 둔다 — 모르는 것을 괜찮다고 하면 안 된다.
 */
export function resolveLevelState(level: string): GlyphStateKind {
  return LEVEL_STATE[level] ?? 'armed'
}

export interface WatchPanelProps {
  readonly view: WatchView | undefined
  /** 다시 읽는다. 지킴이가 5분마다 남기므로 화면이 저절로 새로워지지 않는다. */
  readonly onRefresh: () => void
}

/**
 * 지표 한 줄을 그린다.
 *
 * @param row 그릴 줄.
 * @returns 줄 요소.
 */
function renderRow(row: WatchRow): React.JSX.Element {
  return (
    <div className="adminrow" key={row.key}>
      <span className="adminrow__name">{row.key}</span>
      <GlyphState state={resolveLevelState(row.level)} size="sm" label={row.level} />
      <span className="adminrow__cell">{row.text}</span>
      <span className="adminrow__cell">{row.detail}</span>
      {/* OK 인 줄에 「언제부터」를 적으면 잡음이다 — 달라진 것에만 적는다. */}
      <span className="adminrow__cell">{row.level === 'OK' ? row.seenAt : `${row.changedAt} 부터`}</span>
    </div>
  )
}

/**
 * 바뀐 순간 한 줄을 그린다.
 *
 * @param event 그릴 순간.
 * @param index 목록 안 자리. 같은 지표가 같은 시각에 두 번 바뀔 수 있어 키에 함께 쓴다.
 * @returns 줄 요소.
 */
function renderEvent(event: WatchEvent, index: number): React.JSX.Element {
  return (
    <div className="adminrow" key={`${event.key}-${event.happenedAt}-${String(index)}`}>
      <span className="adminrow__name">{event.happenedAt}</span>
      <GlyphState state={resolveLevelState(event.level)} size="sm" label={event.level} />
      <span className="adminrow__cell">{event.key}</span>
      <span className="adminrow__cell">{event.text}</span>
      <span className="adminrow__cell">{event.detail}</span>
    </div>
  )
}

/**
 * 묶음 하나를 그린다.
 *
 * @param title 머리글.
 * @param lines 적을 줄들.
 * @param empty 비었을 때 적을 말.
 * @returns 요소.
 */
function renderList(title: string, lines: readonly string[], empty: string): React.JSX.Element {
  return (
    <div className="watch__block" key={title}>
      <ValueExpr text={title} size="sm" />
      {lines.length === 0 ? (
        <ValueExpr text={empty} size="sm" dim />
      ) : (
        lines.map((line) => <ValueExpr key={line} text={`· ${line}`} size="sm" dim />)
      )}
    </div>
  )
}

/**
 * 지킴이 화면을 그린다.
 *
 * @param props 읽은 것과 새로고침 처리기.
 * @returns 패널 요소.
 */
export function WatchPanel(props: WatchPanelProps): React.JSX.Element {
  const rows = props.view?.rows ?? []
  const events = props.view?.events ?? []
  const deploy = props.view?.deploy
  const alarms = rows.filter((row) => row.level === '틀림').length
  const watched = rows.filter((row) => row.level === '살핌').length

  return (
    <div className="bots">
      <Panel
        title="세계 지킴이"
        meta={`틀림 ${String(alarms)} · 살핌 ${String(watched)} / 지표 ${String(rows.length)}`}
        tone="panel"
        padded
      >
        {/* 가장 나쁜 것을 먼저 말한다. 여덟 줄을 다 읽게 하면 결국 안 읽힌다. */}
        <GlyphState
          state={alarms > 0 ? 'danger' : watched > 0 ? 'armed' : 'true'}
          size="sm"
          label={
            alarms > 0
              ? `${String(alarms)}개 지표가 틀렸다 — 고치기 전에 배포하지 않는다`
              : watched > 0
                ? `${String(watched)}개 지표를 살피고 있다`
                : '여덟 지표가 모두 괜찮다'
          }
        />
        {rows.length === 0 ? (
          <ValueExpr text={EMPTY_ROWS} size="sm" dim />
        ) : (
          <>
            <div className="adminrow adminrow--head" aria-hidden="true">
              <span className="adminrow__name">지표</span>
              <span className="adminrow__cell">등급</span>
              <span className="adminrow__cell">소견</span>
              <span className="adminrow__cell">실측</span>
              <span className="adminrow__cell">언제부터 / 마지막</span>
            </div>
            <div className="bots__grid">{rows.map(renderRow)}</div>
          </>
        )}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            props.onRefresh()
          }}
        >
          다시 읽기
        </Button>
      </Panel>

      <Panel title="배포하면 무엇이 깨지나" tone="panel" padded>
        {renderList('무엇이 바뀌는가', deploy?.changes ?? [], '나갈 것이 없다')}
        {renderList('누가 만들었는가', deploy?.authors ?? [], '—')}
        {renderList('무엇이 깨지는가', deploy?.breakage ?? [], '아무것도 안 깨진다')}
        {/* 넷째가 없으면 컨펌이 아니라 도박이다 — 나갈 것이 없어도 늘 적는다. */}
        {renderList('되돌리는 법', deploy?.undo ?? [], '—')}
        {renderList(
          '게이트 — 여기서 안 돌린다. 그대로 옮겨 친다',
          deploy?.gateCommands ?? [],
          '—',
        )}
      </Panel>

      <Panel
        title="등급이 바뀐 순간"
        meta={`${String(events.length)}건`}
        tone="panel"
        padded
      >
        {events.length === 0 ? (
          <ValueExpr text="아직 바뀐 적이 없다" size="sm" dim />
        ) : (
          <>
            <div className="adminrow adminrow--head" aria-hidden="true">
              <span className="adminrow__name">때</span>
              <span className="adminrow__cell">등급</span>
              <span className="adminrow__cell">지표</span>
              <span className="adminrow__cell">소견</span>
              <span className="adminrow__cell">실측</span>
            </div>
            <div className="bots__grid">{events.map(renderEvent)}</div>
          </>
        )}
      </Panel>
    </div>
  )
}
