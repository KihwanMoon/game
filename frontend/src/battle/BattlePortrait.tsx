/**
 * 세로 모바일 전투 화면 (390×844) — 모바일 원본 명세 A.
 *
 * 데스크톱 세 열을 줄인 것이 아니라 **재배치한 것**이다. 위에서부터
 * 상단바 44 / 배속바 44 / 도면 / 상태줄 34 / 시트 / 하단바 48 여섯 줄이고, 규칙표와
 * 로그는 시트 하나를 탭으로 나눠 쓴다. 치수는 전부 토큰이 정한다(`--bar-top`·
 * `--bar-speed`·`--bar-status`·`--bar-bottom`).
 *
 * **도면은 고정이고 스크롤되지 않는다.** 12×9 전체를 유지한 채 셀만 30px 로 줄인다
 * (`--plan-cell`). 시트만 바뀌므로 규칙을 읽는 동안에도 유닛 위치가 계속 보이고, 그것이
 * 이 배치의 존재 이유다 — 도면이 밀려 나가면 "규칙을 보면서 판을 읽는다" 가 성립하지
 * 않는다.
 *
 * 시트(`BattleSheet`)와 배속 박스(`SpeedBox`)는 **가로 배치와 같은 부품**이고, 상태
 * 계산은 `portraitSheet`·`ruleRows` 가 한다. 여기 있는 것은 배열뿐이다.
 *
 * 황동 예산 셋(모바일 원본): 발동한 규칙 줄의 번호와 좌측 세로바 · 도면의 플레이어 말 ·
 * (편집 화면의 규칙 번호와 저장 버튼). 그래서 **탭 활성은 명도와 굵기로만** 표시하고
 * 배속·시트 버튼은 primary 를 쓰지 않는다. 지시선도 그리지 않는다 — 규칙 줄이 탭 뒤로
 * 숨을 수 있어 선의 한쪽 끝이 사라진다.
 *
 * **이 컴포넌트는 상태를 들지 않는다.** 탭·켜고 끈 규칙·시계는 전부 `BattleView` 가
 * 들고 있고 여기로는 값과 콜백만 내려온다. 훅이 없으므로 테스트가 이 함수를 직접 불러
 * 반환된 트리에서 핸들러를 눌러 볼 수 있다 — jsdom 없이 상호작용을 검증하는 수단이다.
 */
import type { ReactNode, Ref } from 'react'

import { HpGauge, ResourceCount, ThreatNotice } from '../ds'
import type { LogRowProps } from '../ds'
import { BattleSheet, SheetFoot } from './BattleSheet'
import { formatOutcomeNotice, resolveOutcomeTone } from './outcomeText'
import {
  formatLogTabCount,
  formatRulesTabCount,
  formatTick,
  type SheetTab,
} from './portraitSheet'
import type { RuleRowView } from './ruleRows'
import { SpeedBox } from './SpeedBox'

/**
 * 세로 하단바의 체력 막대 폭(px).
 *
 * `HpGauge` 는 폭을 토큰이 아니라 숫자 prop 으로 받는다(design/README.md 컴포넌트 계약).
 * 데스크톱 StatusBar 가 160 을 쓰는 자리이며 세로는 명세가 90 으로 정했다.
 */
const HP_BAR_WIDTH = 90

/** 물약 칸의 글리프와 라벨. ds `StatusBar` 와 같은 것을 쓴다. */
const POTION_GLYPH = '◍'

/** 주문서 글리프. 도면의 다른 글리프들처럼 유니코드 도형이다. */
const SCROLL_GLYPH = '▤'
const POTION_LABEL = '물약'

/** 틱 표기 앞의 도형. 색은 --chalk-dim 이며 황동 예산에 들지 않는다. */
const TICK_GLYPH = '◆'

/** 틱 표기의 이름. 도형과 숫자 사이의 말은 보조 기술만 읽는다. */
const TICK_NAME = '틱'

/** BattlePortrait 가 받는 props. 상태는 하나도 들지 않는다. */
export interface BattlePortraitProps {
  /** 상단 바의 층·실 표기. */
  readonly location: string
  readonly tick: number
  /** ds `SpeedControl` 과 같은 숫자 단계. */
  readonly speed: number
  readonly onSpeedChange: (value: number) => void
  /** 배속 박스의 `≫`. 남은 판을 끝까지 돌린다. */
  readonly onInstant: () => void
  /** 시트 하단 `한 틱`. */
  readonly onStep: () => void
  /** 시트 하단 `처음부터`. 같은 방·같은 시드로 다시 조립한다. */
  readonly onRestart: () => void
  /**
   * 앱이 끼워 넣는 조작부(사후 분석·다시·규칙 고치기).
   *
   * 명세 A 의 상단바에는 층·실과 틱뿐이지만, 이것을 그리지 않으면 세로에서 **에디터로
   * 돌아갈 길이 사라진다** — 고쳐서 다시 보내는 것이 이 게임의 유일한 동사이므로(GDD
   * §2.1) 화면 밖으로 나가는 문이 없는 배치는 성립하지 않는다. 층·실과 틱 사이에 두고,
   * 넘치면 그 칸 안에서만 가로로 밀리게 해 두 표기를 밀어내지 않는다.
   */
  readonly controls?: ReactNode
  /** 코어가 낸 OUTCOME_* 값. 상태줄이 이것을 문구로 바꾼다. */
  readonly outcome: string
  /** 지금 걸린 예고 문구. 없으면 위협 칸을 그리지 않는다. */
  readonly threat?: string | undefined
  /** 도면. 토큰을 아직 읽지 못했으면 비운다. */
  readonly plan?: ReactNode
  /** 규칙표 전량. 꺼진 줄도 들어 있다 — 다시 켜려면 보여야 한다. */
  readonly rows: readonly RuleRowView[]
  /** 규칙 줄을 눌렀을 때. 켜고 끄는 것이 세로 화면의 유일한 규칙 조작이다. */
  readonly onToggleRule: (priority: number) => void
  /** 켜진 규칙들의 누적 CPU. */
  readonly cpuUsed: number
  readonly cpuBudget: number
  /** 로그 줄들. 코어의 `engine.log.entries` 를 그대로 받는다. */
  readonly entries: readonly LogRowProps[]
  readonly hp: number
  readonly hpMax: number
  readonly potions: number
  readonly potionsMax: number
  /** 남은 주문서와 실은 수. 물약과 같은 자리다 — 소모품 현황이 플레이 중에 보여야 한다. */
  readonly scrolls: number
  readonly scrollsMax: number
  readonly tab: SheetTab
  readonly onTabChange: (tab: SheetTab) => void
  /** 시트 본문. 로그를 마지막 줄에 붙여 두려고 밖에서 잡는다. */
  readonly bodyRef?: Ref<HTMLDivElement>
}

/**
 * 세로 모바일 전투 화면을 그린다.
 *
 * @param props 상단·도면·시트·하단이 쓸 값 전부와 조작 콜백들.
 * @returns 렌더 트리.
 */
export function BattlePortrait(props: BattlePortraitProps): React.JSX.Element {
  const enabledRules = props.rows.filter((row) => row.enabled).length
  const counts: ReadonlyMap<SheetTab, string> = new Map([
    ['rules' as SheetTab, formatRulesTabCount(enabledRules, props.rows.length)],
    ['log' as SheetTab, formatLogTabCount(props.tick)],
  ])

  return (
    <div className="battle battle--portrait">
      <header className="battle__bar battle__bar--top">
        <h1 className="battle__location">{props.location}</h1>
        {props.controls === undefined ? null : (
          <span className="battle__controls">{props.controls}</span>
        )}
        <span className="battle__tick">
          <span className="battle__tick-glyph" aria-hidden="true">
            {TICK_GLYPH}
          </span>
          <span className="ds-sr">{TICK_NAME}</span>
          {formatTick(props.tick)}
        </span>
      </header>

      <div className="battle__speed-bar">
        <SpeedBox
          value={props.speed}
          onChange={props.onSpeedChange}
          onInstant={props.onInstant}
        />
      </div>

      <div className="battle__col battle__col--plan">
        <div className="battle__frame">{props.plan}</div>
      </div>

      <div className="battle__status">
        <span className={`battle__verdict battle__verdict--${resolveOutcomeTone(props.outcome)}`}>
          {formatOutcomeNotice(props.outcome)}
        </span>
        {props.threat === undefined ? null : <ThreatNotice text={props.threat} tone="danger" />}
      </div>

      <BattleSheet
        tab={props.tab}
        counts={counts}
        onTabChange={props.onTabChange}
        rules={props.rows}
        onToggleRule={props.onToggleRule}
        entries={props.entries}
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

      <footer className="battle__bar battle__bar--bottom">
        <HpGauge value={props.hp} max={props.hpMax} width={HP_BAR_WIDTH} />
        <ResourceCount
          label={POTION_LABEL}
          count={props.potions}
          max={props.potionsMax}
          glyph={POTION_GLYPH}
        />
        <ResourceCount
          label="주문서"
          count={props.scrolls}
          max={props.scrollsMax}
          glyph={SCROLL_GLYPH}
        />
      </footer>
    </div>
  )
}
