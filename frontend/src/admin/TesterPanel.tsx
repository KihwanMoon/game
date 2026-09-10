/**
 * 테스터 표시 패널 — G1 의 **분모**를 정하는 화면.
 *
 * 게이트는 「테스터 5명 중 3명」을 묻는데 이 게임은 익명으로 시작하므로, 자동으로 세면
 * 접속했다 떠난 계정까지 전부 테스터가 된다. 실측으로 36명 중 17명이 한 판짜리였고 그것이
 * 평균 재도전을 1.2회로 눌러 놓고 있었다 — 그 숫자는 「재미있었는가」가 아니라 「몇 명이
 * 지나갔는가」였다. 누구를 불렀는지는 사람만 알고 있으므로 사람이 표시한다.
 *
 * **제출 수로 거르는 버튼을 두지 않았다.** 「많이 논 계정」만 분모에 넣고 「평균 재도전
 * 3회」를 재면 기준이 저절로 통과된다 — 순환이다. 제출 수는 누구인지 짚는 단서로만 쓴다.
 *
 * **표시는 권한이 아니다.** 켜도 그 계정에 생기는 것은 통계에 세어진다는 것뿐이다.
 *
 * **봇도 표시할 수 있다 (2026-09-10) — 다만 G1 에는 안 센다.** 층 깊이 간 봇을 화면 위에
 * 고정해 두고 지켜보는 운영이 있는데, 목록에서 아예 빼 두면 그것이 안 된다. 대신 두 수를
 * 갈라 적는다 — 하나로 합치면 화면은 5명을 채웠다고 하는데 게이트는 안 채워진 상태가
 * 되고, 그 어긋남은 판정할 때에야 드러난다.
 */
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { TesterList, TesterView } from '../storage/testerAdmin'

/** 아무것도 없을 때 적는 말. 빈 화면은 고장으로 읽힌다. */
const EMPTY_ROWS = '계정이 없다 — 아무도 아직 접속하지 않았다'

/**
 * 아직 안 읽었을 때 쓸 기준. **서버가 주는 값이 정본이다** — 여기 박아 두면 로드맵을
 * 고쳤을 때 화면만 옛 기준으로 말한다.
 */
const FALLBACK_MIN_TESTERS = 5

/**
 * 익명 계정을 사람이 짚을 수 있는 말로 만든다.
 *
 * 익명은 번호뿐이라 **가입 아이디가 있으면 그것을 앞에 둔다** — 테스터에게 가입을
 * 부탁하면 어느 줄이 누구인지가 화면에서 바로 읽힌다.
 *
 * @param row 그릴 줄.
 * @returns 화면에 적을 이름.
 */
export function formatWho(row: TesterView): string {
  return row.loginId === '' ? row.handle : `${row.loginId} (${row.handle})`
}

/**
 * 패널 머리에 적을 한 줄.
 *
 * **두 수를 더하지 않는다.** 더하면 화면은 기준을 채웠다고 적는데 게이트는 안 채워진
 * 상태가 되고, 그 어긋남은 G1 을 판정할 때에야 드러난다.
 *
 * @param marked 표시된 사람 수.
 * @param markedBots 표시된 봇 수.
 * @param minTesters 로드맵이 전제하는 수.
 * @param total 목록에 뜬 계정 수.
 * @returns 화면에 적을 말.
 */
export function formatTesterMeta(
  marked: number,
  markedBots: number,
  minTesters: number,
  total: number,
): string {
  const bots = markedBots === 0 ? '' : ` · 봇 ${String(markedBots)}개(안 셈)`
  return `사람 ${String(marked)}명 / 기준 ${String(minTesters)}명${bots} · 계정 ${String(total)}개`
}

/** TesterPanel 이 받는 props. */
export interface TesterPanelProps {
  readonly list: TesterList | undefined
  /** 표시를 켜거나 끈다. */
  readonly onMark: (accountId: number, isTester: boolean) => void
}

/**
 * 계정 한 줄을 그린다.
 *
 * @param row 그릴 줄.
 * @param onMark 표시를 바꾼다.
 * @returns 줄 요소.
 */
function renderRow(
  row: TesterView,
  onMark: (accountId: number, isTester: boolean) => void,
): React.JSX.Element {
  return (
    <div className={`adminrow${row.isTester ? ' adminrow--picked' : ''}`} key={row.accountId}>
      <span className="adminrow__name">
        {formatWho(row)}
        {/* **봇이라는 사실이 줄에 붙어 있어야 한다.** 표시해 두고 사람 수가 안 오르는
            것을 보면 「표시가 안 먹었나」를 의심하게 되는데, 여기 적혀 있으면 그 자리에서
            답이 된다. */}
        {row.isBot ? <span className="adminrow__tag">봇</span> : null}
      </span>
      {/* 참/거짓을 색으로만 적지 않는다 — 글리프와 글자를 함께 쓴다. 봇은 표시돼도
          G1 에 안 세므로 다른 말을 적는다 — 「테스터」라 적으면 분모로 읽힌다. */}
      <GlyphState
        state={row.isTester ? (row.isBot ? 'armed' : 'true') : 'false'}
        size="sm"
        label={row.isTester ? (row.isBot ? '표시(안 셈)' : '테스터') : '안 셈'}
      />
      <span className="adminrow__cell">{`제출 ${String(row.attempts)}건`}</span>
      <span className="adminrow__cell">{row.lastSeen === '' ? '접속 기록 없음' : row.lastSeen}</span>
      <Button
        variant={row.isTester ? 'ghost' : 'primary'}
        onClick={() => {
          onMark(row.accountId, !row.isTester)
        }}
      >
        {row.isTester ? '표시 지움' : '테스터로 표시'}
      </Button>
    </div>
  )
}

/**
 * 테스터 표시 패널을 그린다.
 *
 * @param props 줄들과 표시 처리기.
 * @returns 패널 요소.
 */
export function TesterPanel(props: TesterPanelProps): React.JSX.Element {
  const rows = props.list?.rows ?? []
  const marked = props.list?.marked ?? 0
  const markedBots = props.list?.markedBots ?? 0
  const minTesters = props.list?.minTesters ?? FALLBACK_MIN_TESTERS

  return (
    <div className="bots">
      <Panel
        title="테스터"
        meta={formatTesterMeta(marked, markedBots, minTesters, rows.length)}
        tone="panel"
        padded
      >
        <ValueExpr
          text="여기서 표시한 **사람** 계정만 G1 통계에 들어간다. 표시는 권한이 아니다 — 세어진다는 것뿐이다."
          size="sm"
          dim
        />
        {/* 봇을 표시해 두었으면 그 사실을 위쪽에 적는다. 줄마다 적힌 것만으로는 목록을
            훑기 전까지 안 보이고, 그 사이에 사람 수가 왜 안 오르는지를 다시 묻게 된다. */}
        {markedBots > 0 ? (
          <GlyphState
            state="armed"
            size="sm"
            label={`봇 ${String(markedBots)}개가 표시돼 있다 — 목록 위에 고정될 뿐 G1 에는 안 센다`}
          />
        ) : null}
        {/* 분모가 모자라면 먼저 말한다. 미달로 읽히면 「분모를 안 정했다」가 판정 뒤에 숨는다. */}
        {marked < minTesters ? (
          <GlyphState
            state="danger"
            size="sm"
            label={`부른 테스터가 ${String(marked)}명이다 — 로드맵은 ${String(minTesters)}명을 전제한다`}
          />
        ) : null}
        {rows.length === 0 ? (
          <ValueExpr text={EMPTY_ROWS} size="sm" dim />
        ) : (
          <>
            <div className="adminrow adminrow--head" aria-hidden="true">
              <span className="adminrow__name">계정</span>
              <span className="adminrow__cell">셈</span>
              <span className="adminrow__cell">제출</span>
              <span className="adminrow__cell">마지막 접속</span>
              <span className="adminrow__cell" />
            </div>
            <div className="bots__grid">{rows.map((row) => renderRow(row, props.onMark))}</div>
          </>
        )}
      </Panel>
    </div>
  )
}
