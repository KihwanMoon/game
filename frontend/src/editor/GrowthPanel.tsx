/**
 * 성장 — 레벨·깊이·표현력과 능력치 배분 (결정 #51).
 *
 * **세계 패널에 있던 것이다.** 레벨과 능력치는 세계에 대한 사실이 아니라 **나에 대한
 * 사실**인데, 순위·경매와 한 패널에 묶여 있었다. 「내 캐릭터가 지금 뭘 찍을 수 있나」를
 * 보려고 세계를 열어야 했다.
 *
 * 캐릭터 시트와도 가른다. 저쪽은 **지금 무엇인가**(전투 입력의 최종값)이고 이쪽은
 * **무엇으로 바꿀 수 있는가**다 — 읽는 화면과 고르는 화면은 다른 일이다.
 *
 * **찍기 전에 보여야 한다.** 배분은 되돌릴 수 없으므로, 각 축이 지금 무엇을 여는지
 * 실측값으로 병기한다 (디자인 §8.2 가 조건문에 실측값을 병기하라고 한 것과 같은 이유).
 */
import { useState } from 'react'

import { buildAttributeBonus } from '../core/progression/attributes'
import { Button, Panel, ValueExpr } from '../ds'
import type { ProgressView } from '../storage'

import { LinkNoticeLine } from './LinkNoticeLine'
import { checkLinked, type LinkState } from './linkState'

export interface GrowthPanelProps {
  readonly progress: ProgressView | undefined
  readonly link: LinkState
  readonly onAllocate: (stats: Record<string, number>) => void
}

/** 못 닿았을 때 무엇을 못 보는가. 앞머리(`서버에 닿지 못했다`)는 linkState 가 든다. */
const MISSING_HINT = '레벨과 능력치는 서버가 안다'

/**
 * 층이 적을 얼마나 세게 만드는지. **`balance.json` 의 `floor_scale` 과 같아야 한다** —
 * 화면이 다른 숫자를 말하면 사람은 그 숫자로 계획을 세운다.
 */
const FLOOR_HP_PCT = 25
const FLOOR_ATTACK_PCT = 20

/** 능력치의 한글 이름. */
export const STAT_LABELS: ReadonlyMap<string, string> = new Map([
  ['str', '힘'],
  ['dex', '민첩'],
  ['int', '지능'],
])

/**
 * 이 배분이 지금 여는 것을 실측값으로 적는다 (결정 #51).
 *
 * **찍기 전에 보여야 한다.** 배분은 되돌릴 수 없고, "힘 +1" 만 적으면 그것이 공격력을
 * 얼마나 올리는지 유저가 알 수 없다.
 *
 * @param key 능력치 열쇠.
 * @param points 그 축에 찍힌 점수(확정분 + 대기분).
 * @returns 화면에 적을 문구. 0점이면 빈 문자열.
 */
export function formatAttributeEffect(key: string, points: number): string {
  if (points <= 0) {
    return ''
  }
  const bonus = buildAttributeBonus({ [key]: points })
  if (key === 'str') {
    return `공격 +${String(bonus.attack)} · 체력 +${String(bonus.hpMax)}`
  }
  if (key === 'dex') {
    return `선공 +${String(bonus.initiative)} · 방어 +${String(bonus.defense)}`
  }
  if (key === 'int') {
    return `CPU +${String(bonus.cpuBudget)} · 스킬위력 ${String(bonus.skillPowerPct)}%`
  }
  return ''
}

/**
 * 성장 패널을 그린다.
 *
 * @param props 성장 상태와 배분 처리기.
 * @returns 패널 요소.
 */
export function GrowthPanel(props: GrowthPanelProps): React.JSX.Element {
  const { progress, link } = props
  const [pending, setPending] = useState<Record<string, number>>({})
  const left = (progress?.statPoints ?? 0) - (progress?.spentPoints ?? 0)
  const staged = Object.values(pending).reduce((sum, value) => sum + value, 0)

  /**
   * 능력치 하나를 한 점 올린다. 남은 포인트를 넘기지 않는다.
   *
   * @param key 능력치 열쇠.
   */
  function addPoint(key: string): void {
    if (staged >= left) {
      return
    }
    setPending((current) => ({ ...current, [key]: (current[key] ?? 0) + 1 }))
  }

  return (
    <Panel
      title="성장"
      // **머리에 남은 포인트를 적는다.** 안 쓴 포인트는 없는 것과 같은데, 펼쳐 봐야
      // 알면 그것을 안 쓴 채로 계속 논다 — 봇이 9점씩 놀리고 있던 것과 같은 일이다.
      meta={progress === undefined ? '' : `남은 포인트 ${String(left - staged)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="wld">
        {!checkLinked(link) || progress === undefined ? (
          <LinkNoticeLine link={link} missing={MISSING_HINT} />
        ) : (
          <>
            <div className="wld__row">
              <span className="wld__label">레벨</span>
              <ValueExpr
                text={`${String(progress.level)} · ${String(progress.remainingXp)} / ${String(progress.nextXp)}`}
                size="sm"
              />
            </div>
            {/* **여기까지 내려가 봤다** (설계/6_몬스터 §3). 층이 오르면 적이 세지고
                더 깊은 방이 열리는데, 그 사실을 말하는 자리가 없으면 사람은 자기가
                어디까지 왔는지 모른 채 같은 판을 돈다. */}
            <div className="wld__row">
              <span className="wld__label">깊이</span>
              <ValueExpr
                text={`${String(progress.reachedFloor)} / ${String(progress.floorCap)}층`}
                size="sm"
              />
              <ValueExpr
                text={
                  progress.reachedFloor >= progress.floorCap
                    ? '끝까지 왔다'
                    : `층마다 적이 HP +${String(FLOOR_HP_PCT)}% · 공격 +${String(FLOOR_ATTACK_PCT)}% 로 세진다`
                }
                size="sm"
                dim
              />
            </div>
            <div className="wld__row">
              <span className="wld__label">표현력</span>
              <ValueExpr
                text={`슬롯 +${String(progress.bonusRuleSlots)} · CPU +${String(progress.bonusCpu)}`}
                size="sm"
                dim
              />
            </div>

            <div className="wld__head">능력치 · 남은 포인트 {String(left - staged)}</div>
            <ul className="wld__list">
              {progress.statKeys.map((key) => (
                <li className="wld__row" key={key}>
                  <span className="wld__label">{STAT_LABELS.get(key) ?? key}</span>
                  <ValueExpr
                    text={`${String((progress.stats[key] ?? 0) + (pending[key] ?? 0))}`}
                    size="sm"
                  />
                  <ValueExpr
                    text={formatAttributeEffect(
                      key,
                      (progress.stats[key] ?? 0) + (pending[key] ?? 0),
                    )}
                    size="sm"
                    dim
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    glyph="＋"
                    disabled={staged >= left}
                    onClick={() => {
                      addPoint(key)
                    }}
                  />
                </li>
              ))}
            </ul>
            {staged === 0 ? null : (
              <div className="wld__actions">
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => {
                    const next: Record<string, number> = { ...progress.stats }
                    for (const [key, value] of Object.entries(pending)) {
                      next[key] = (next[key] ?? 0) + value
                    }
                    props.onAllocate(next)
                    setPending({})
                  }}
                >
                  배분 확정
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setPending({})
                  }}
                >
                  취소
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </Panel>
  )
}
