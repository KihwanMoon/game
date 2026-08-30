/**
 * 도감 — **위키가 아니라 표적 목록** (docs/설계/6_몬스터 §8).
 *
 * 지속 몬스터가 도감의 성격을 바꿨다. "이 적은 이런 규칙을 쓴다" 만이 아니라 "지금 어디에
 * 있고, 얼마나 컸고, **내 아이템을 들고 있는가**" 를 말한다 — 그것이 되찾으러 가는
 * 동기이고 World Loop 이 성립하는 이유다.
 *
 * 등급을 색으로 칠하지 않는다. 의미색 셋이 이미 배정됐고 색은 정보의 유일한 채널이 될
 * 수 없다 — 등급은 글자로, "내 것" 은 글리프로 가른다.
 */
import { GlyphState, Panel, ValueExpr } from '../ds'
import type { BestiaryEntry } from '../storage'

export interface BestiaryPanelProps {
  readonly entries: readonly BestiaryEntry[] | undefined
  readonly isOnline: boolean
}

const OFFLINE_HINT = '서버에 닿지 못했다 — 세계의 몬스터는 서버가 안다'
const EMPTY_HINT = '아직 세계에 지속 몬스터가 없다'

/**
 * 도감 패널을 그린다.
 *
 * @param props 도감 줄들과 접속 상태.
 * @returns 패널 요소.
 */
export function BestiaryPanel(props: BestiaryPanelProps): React.JSX.Element {
  const { entries, isOnline } = props
  const mine = (entries ?? []).filter((entry) => entry.holdsMine).length

  return (
    <Panel
      title="도감"
      meta={mine === 0 ? '' : `내 것 ${String(mine)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="bst">
        {!isOnline || entries === undefined ? (
          <ValueExpr text={OFFLINE_HINT} size="sm" dim />
        ) : entries.length === 0 ? (
          <ValueExpr text={EMPTY_HINT} size="sm" dim />
        ) : (
          <ul className="bst__list">
            {entries.map((entry) => (
              <li className="bst__entry" key={entry.recordId}>
                <div className="bst__row">
                  <span className="bst__name">{entry.labelKo}</span>
                  <ValueExpr text={entry.tier} size="sm" dim />
                </div>
                <div className="bst__row">
                  <ValueExpr
                    text={`레벨 ${String(entry.level)} / ${String(entry.levelCap)}`}
                    size="sm"
                  />
                  <ValueExpr
                    text={`${String(entry.zoneFloor)}층 · 규칙 ${String(entry.ruleCount)}줄`}
                    size="sm"
                    dim
                  />
                </div>
                {entry.holdsMine ? (
                  // 되찾기 동기. 이것이 화면에 없으면 사본을 만드는 뜻이 사라진다.
                  <GlyphState
                    state="danger"
                    size="sm"
                    label={`내 장비를 들고 있다 — ${entry.trophies.join(', ')}`}
                  />
                ) : entry.trophies.length > 0 ? (
                  <ValueExpr text={`전리품 ${String(entry.trophies.length)}`} size="sm" dim />
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  )
}
