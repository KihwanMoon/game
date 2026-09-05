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
      <span className="adminrow__name">{formatWho(row)}</span>
      {/* 참/거짓을 색으로만 적지 않는다 — 글리프와 글자를 함께 쓴다. */}
      <GlyphState
        state={row.isTester ? 'true' : 'false'}
        size="sm"
        label={row.isTester ? '테스터' : '안 셈'}
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
  const minTesters = props.list?.minTesters ?? FALLBACK_MIN_TESTERS

  return (
    <div className="bots">
      <Panel
        title="테스터"
        meta={`표시 ${String(marked)}명 / 기준 ${String(minTesters)}명 · 계정 ${String(rows.length)}개`}
        tone="panel"
        padded
      >
        <ValueExpr
          text="여기서 표시한 계정만 G1 통계에 들어간다. 표시는 권한이 아니다 — 세어진다는 것뿐이다."
          size="sm"
          dim
        />
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
