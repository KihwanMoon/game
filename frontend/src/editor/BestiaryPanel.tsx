/**
 * 도감 — **위키가 아니라 표적 목록** (docs/설계/6_몬스터 §8).
 *
 * 지속 몬스터가 도감의 성격을 바꿨다. "이 적은 이런 규칙을 쓴다" 만이 아니라 "지금 어디에
 * 있고, 얼마나 컸고, **내 아이템을 들고 있는가**" 를 말한다 — 그것이 되찾으러 가는
 * 동기이고 World Loop 이 성립하는 이유다.
 *
 * **규칙표를 그대로 낸다.** 줄 수로 접으면 카운터를 설계할 수 없다 — 도감이 표적 목록인
 * 이유가 바로 그것인데, 예전에는 화면이 「규칙 4줄」이라고만 적어 그 뜻이 사라져 있었다.
 * 서버는 처음부터 규칙표를 보내고 있었다.
 *
 * 등급을 색으로 칠하지 않는다. 의미색 셋이 이미 배정됐고 색은 정보의 유일한 채널이 될
 * 수 없다 — 등급은 글자로, "내 것" 은 글리프로 가른다.
 */
import { useState } from 'react'

import { formatRuleText } from './ruleText'
import { Button, GlyphState, Panel, Thumb, ValueExpr } from '../ds'
import type { BestiaryEntry } from '../storage'

export interface BestiaryPanelProps {
  readonly entries: readonly BestiaryEntry[] | undefined
  readonly isOnline: boolean
}

const OFFLINE_HINT = '서버에 닿지 못했다 — 세계의 몬스터는 서버가 안다'
const EMPTY_HINT = '아직 세계에 지속 몬스터가 없다'

/**
 * 그 개체의 규칙표를 사람이 읽는 줄들로 만든다.
 *
 * **에디터와 같은 표기를 쓴다.** 도감이 다른 문법으로 적으면, 본 것을 그대로 자기
 * 규칙표에 옮길 수 없다 — 카운터 설계가 목적인데 옮겨 적기부터 막힌다.
 *
 * @param entry 도감 줄.
 * @returns 규칙 줄들. 규칙표가 없으면 빈 배열.
 */
export function listRuleLines(entry: BestiaryEntry): readonly string[] {
  if (entry.ruleset === undefined) {
    return []
  }
  // 첫 줄은 파일 머리말이라 뺀다 — 화면에는 규칙만 필요하다.
  return formatRuleText(entry.ruleset).split('\n').slice(1)
}

/**
 * 도감 패널을 그린다.
 *
 * @param props 도감 줄들과 접속 상태.
 * @returns 패널 요소.
 */
export function BestiaryPanel(props: BestiaryPanelProps): React.JSX.Element {
  const { entries, isOnline } = props
  const [openId, setOpenId] = useState<number | undefined>(undefined)
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
                  {/* 그림 자리. 지금은 등급 코드가 그려지고, 자산이 들어오면 같은
                      틀 안에서 그림으로 바뀐다 — 배치가 흔들리지 않는다. */}
                  <Thumb kind={entry.tier} label={entry.labelKo} size="sm" />
                  <span className="bst__name">{entry.labelKo}</span>
                  <ValueExpr
                    text={`${entry.tier} · lv ${String(entry.level)}/${String(entry.levelCap)}`}
                    size="sm"
                  />
                </div>

                {/* **얼마나 센가.** 규칙표만으로는 어떻게 싸우는지만 알 수 있고,
                    이길 수 있는지는 알 수 없다. */}
                <ValueExpr
                  text={`층${String(entry.zoneFloor)} · hp ${String(entry.hpMax)} · 공 ${String(entry.attack)} · 방 ${String(entry.defense)}`}
                  size="sm"
                  dim
                />

                {entry.affixes.length === 0 ? null : (
                  <ValueExpr text={`접사 ${entry.affixes.join(' · ')}`} size="sm" />
                )}

                {entry.holdsMine ? (
                  <GlyphState
                    state="armed"
                    size="sm"
                    label={`내 장비 보유 — ${entry.trophies.join(' · ')}`}
                  />
                ) : null}

                {entry.ruleset === undefined ? null : (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      glyph={openId === entry.recordId ? '▾' : '▸'}
                      title="이 적이 어떻게 싸우는지 본다 — 카운터는 여기서 나온다"
                      onClick={() => {
                        setOpenId(openId === entry.recordId ? undefined : entry.recordId)
                      }}
                    >
                      규칙표 {String(entry.ruleset.rules.length)}줄
                    </Button>
                    {openId === entry.recordId ? (
                      <ol className="bst__rules">
                        {listRuleLines(entry).map((line) => (
                          <li className="bst__rule" key={line}>
                            <ValueExpr text={line} size="sm" />
                          </li>
                        ))}
                      </ol>
                    ) : null}
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  )
}
