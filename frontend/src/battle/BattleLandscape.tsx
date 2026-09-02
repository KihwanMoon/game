/**
 * 가로 모바일 전투 화면 (844x390) — 명세 B.
 *
 * 데스크톱의 3열(규칙표 · 도면 · 로그)이 여기서는 **2열**이 된다. 좌측 규칙표 열이 사라진
 * 것이 아니라 로그와 한 시트로 합쳐져 우측 340px 안으로 들어갔다. 데스크톱을 축소한 것이
 * 아니라 재배치한 것이며, **도면은 12x9 전체를 유지한다** — 셀만 32px 로 줄어들고 그
 * 값은 토큰이 정한다(`--plan-cell`, design/tokens/spacing.css).
 *
 * **높이가 390px 뿐이라는 것이 이 배치의 유일한 제약이다.** 상단 40 + 하단 40 을 빼면
 * 본문이 310px 이고 도면이 288px + 여백 16 + 테두리 2 = 306px 를 쓴다. 남는 4px 안에서
 * 무엇도 자라면 안 되므로, 시트 본문만 스크롤하고 나머지는 전부 고정 높이다.
 *
 * 세로 배치와 공유하는 것은 시트(`BattleSheet`)와 배속 박스(`SpeedBox`), 상태 계산
 * (`portraitSheet`·`ruleRows`)이다. 여기 있는 것은 **배열뿐**이다.
 *
 * 황동 예산 셋: 발동한 규칙 줄의 번호와 좌측 세로바(ds `RuleRow`), 도면의 플레이어 말
 * (`planRenderer`). 그래서 상단 바의 배속 박스도 탭도 황동을 쓰지 않고, 지시선은 그리지
 * 않는다 — 규칙 줄이 탭 뒤로 숨을 수 있어 선의 한쪽 끝이 사라지기 때문이다.
 */
import type { ReactNode, Ref } from 'react'

import { HpGauge, ThreatNotice } from '../ds'
import type { LogRowProps } from '../ds'
import { BattleSheet, SheetFoot } from './BattleSheet'
import { formatSettlementTabCount, type FloorSettlement } from './settlement'
import { formatOutcomeNotice, resolveOutcomeTone } from './outcomeText'
import {
  formatLogTabCount,
  formatRulesTabCount,
  formatTick,
  type SheetTab,
} from './portraitSheet'
import type { RuleRowView } from './ruleRows'
import { SpeedBox } from './SpeedBox'

/** 하단 바의 체력 막대 폭(px). 명세 B 가 정한 값이며 토큰이 아니라 prop 이다. */
const HP_BAR_WIDTH = 150

/** 물약 칸의 글리프. ds `StatusBar` 와 같은 도형을 쓴다. */


/** 물약 칸의 라벨. */

/** 틱 표기 앞의 도형. 색은 --chalk-dim 이며 황동 예산에 들지 않는다. */
const TICK_GLYPH = '◆'

/** BattleLandscape 가 받는 props. */
export interface BattleLandscapeProps {
  /** 상단 좌측의 층·실 표기. */
  readonly location: string
  readonly tick: number
  readonly speed: number
  readonly onSpeedChange: (value: number) => void
  /** 배속 박스의 `≫`. 남은 판을 끝까지 돌린다. */
  readonly onInstant: () => void
  /** 시트 하단 `한 틱`. */
  readonly onStep: () => void
  /** 시트 하단 `처음부터`. 같은 방·같은 시드로 다시 조립한다. */
  readonly onRestart: () => void
  /** 앱이 끼워 넣는 조작부(사후 분석·규칙 고치기). 없으면 그리지 않는다. */
  readonly controls?: ReactNode
  /** 도면. 토큰을 아직 읽지 못했으면 비운다. */
  readonly plan?: ReactNode
  readonly tab: SheetTab
  readonly onTabChange: (tab: SheetTab) => void
  /** 규칙표 전량. 꺼진 줄도 들어 있다. */
  readonly rows: readonly RuleRowView[]
  readonly onToggleRule: (priority: number) => void
  readonly entries: readonly LogRowProps[]
  /** 층별 정산. 상단 알림이 아니라 탭이다 — 알림은 뜰 때마다 아래 전부를 밀었다. */
  readonly settlements?: readonly FloorSettlement[]
  /** 켜진 규칙들의 누적 CPU. */
  readonly cpuUsed: number
  readonly cpuBudget: number
  readonly hp: number
  readonly hpMax: number
  readonly potions: number
  readonly potionsMax: number
  /** 남은 주문서와 실은 수. 물약과 같은 자리다 — 소모품 현황이 플레이 중에 보여야 한다. */
  readonly scrolls: number
  readonly scrollsMax: number
  readonly cooldowns?: string
  /** 코어가 낸 OUTCOME_* 값. 문구는 `outcomeText` 한 곳이 만든다. */
  readonly outcome: string
  /** 지금 걸린 예고 문구. 없으면 위협 칸을 그리지 않는다. */
  readonly threat?: string | undefined
  /** 시트 본문. 로그를 마지막 줄에 붙여 두려고 밖에서 잡는다. */
  readonly bodyRef?: Ref<HTMLDivElement>
}

/**
 * 가로 모바일 전투 화면을 그린다.
 *
 * @param props 상단·도면·시트·하단이 쓸 값 전부.
 * @returns 렌더 트리.
 */
export function BattleLandscape(props: BattleLandscapeProps): React.JSX.Element {
  const enabledRules = props.rows.filter((row) => row.enabled).length
  const counts: ReadonlyMap<SheetTab, string> = new Map([
    ['rules' as SheetTab, formatRulesTabCount(enabledRules, props.rows.length)],
    ['log' as SheetTab, formatLogTabCount(props.tick)],
    ['reward' as SheetTab, formatSettlementTabCount(props.settlements ?? [])],
  ])

  return (
    <div className="battle battle--landscape">
      <header className="battle-ls__top">
        <h1 className="battle__location">{props.location}</h1>
        <span className="battle__tick">
          <span className="battle__tick-glyph" aria-hidden="true">
            {TICK_GLYPH}
          </span>
          {`틱 ${formatTick(props.tick)}`}
        </span>
        <span className="battle-ls__gap" />
        {props.controls === undefined ? null : (
          <span className="battle-ls__controls">{props.controls}</span>
        )}
        <SpeedBox
          value={props.speed}
          onChange={props.onSpeedChange}
          onInstant={props.onInstant}
        />
      </header>

      <div className="battle-ls__body">
        <div className="battle__col battle__col--plan">
          <div className="battle__frame">{props.plan}</div>
        </div>
        <div className="battle-ls__panel">
          <BattleSheet
            tab={props.tab}
            counts={counts}
            onTabChange={props.onTabChange}
            rules={props.rows}
            onToggleRule={props.onToggleRule}
            entries={props.entries}
            settlements={props.settlements ?? []}
            cooldowns={props.cooldowns ?? ''}
            potions={props.potions}
            potionsMax={props.potionsMax}
            scrolls={props.scrolls}
            scrollsMax={props.scrollsMax}
            bodyRef={props.bodyRef}
            foot={
              <SheetFoot
                cpuUsed={props.cpuUsed}
                cpuBudget={props.cpuBudget}
                onStep={props.onStep}
                onRestart={props.onRestart}
              />
            }
          />
        </div>
      </div>

      <footer className="battle-ls__bottom">
        <span className="ds-label">hp</span>
        <HpGauge value={props.hp} max={props.hpMax} width={HP_BAR_WIDTH} />
        <span className="battle-ls__rule-line" aria-hidden="true" />
        <span className="battle-ls__gap" />
        <span
          className={`battle-ls__verdict battle__verdict--${resolveOutcomeTone(props.outcome)}`}
        >
          {formatOutcomeNotice(props.outcome)}
        </span>
        {props.threat === undefined ? null : <ThreatNotice text={props.threat} tone="danger" />}
      </footer>
    </div>
  )
}
