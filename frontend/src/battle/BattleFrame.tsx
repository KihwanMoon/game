/**
 * 전투 화면의 **속** — 시간 조작부 · 도면 · 판정줄 · 시트.
 *
 * **세 화면이 같은 것을 그린다.** 관전(엔진을 앞으로 민다)·되감기(`/hud.html`)·사후 분석은
 * 시간축만 다르고 그리는 것은 하나다 — 지금 이 틱의 도면, 그 틱의 규칙표와 로그, 남은 체력.
 * 셋이 각자 골격을 들고 있으면 한 곳을 고쳐도 나머지 둘은 옛 모양으로 남고, 실제로 그
 * 상태였다: 되감기와 갤러리는 **데스크톱 3열 골격을 그대로 들고 있어서** 데스크톱 토큰이
 * 사라진 날 `100% 1px 1fr 1px 100%` 짜리 격자가 됐다.
 *
 * **바는 여기 없다.** 상·하단 바는 화면마다 다른 것을 싣고(관전은 층·실과 틱, 되감기는
 * 확인용 조작부, 사후 분석은 다이얼로그 머리), 다이얼로그 안에 바를 한 벌 더 세우면
 * 한 화면에 상단 바가 둘이 된다. 바깥 껍데기는 부르는 쪽이 정한다.
 *
 * **시간 조작부도 슬롯이다.** 앞으로만 가는 화면은 배속 박스를, 프레임 위를 걷는 화면은
 * 스크러버를 끼운다 — 이 부품은 둘 중 무엇인지 모른다.
 *
 * 상태를 들지 않는다. 값과 콜백만 받으므로 테스트가 직접 불러 트리를 볼 수 있다.
 */
import type { ReactNode, Ref } from 'react'

import { ThreatNotice } from '../ds'
import type { LogRowProps } from '../ds'

import { BattleSheet } from './BattleSheet'
import { formatSettlementTabCount, type FloorSettlement } from './settlement'
import { formatOutcomeNotice, resolveOutcomeTone } from './outcomeText'
import { formatLogTabCount, formatRulesTabCount, type SheetTab } from './portraitSheet'
import type { RuleRowView } from './ruleRows'

/** BattleFrame 이 받는 props. */
export interface BattleFrameProps {
  /**
   * 시간 조작부. 배속 박스(앞으로) 또는 스크러버(앞뒤).
   *
   * 없으면 그 줄을 아예 안 그린다 — 빈 줄을 남기면 도면이 그만큼 아래로 밀린다.
   */
  readonly timeBox?: ReactNode
  /** 도면. 토큰을 아직 읽지 못했으면 비운다. */
  readonly plan?: ReactNode
  /** 코어가 낸 OUTCOME_* 값. 상태줄이 이것을 문구로 바꾼다. */
  readonly outcome: string
  /** 지금 걸린 예고 문구. 없으면 위협 칸을 그리지 않는다. */
  readonly threat?: string | undefined
  /** 규칙표 전량. 꺼진 줄도 들어 있다 — 다시 켜려면 보여야 한다. */
  readonly rows: readonly RuleRowView[]
  /** 규칙 줄을 눌렀을 때. 되감기처럼 고칠 수 없는 자리는 아무것도 안 하는 것을 넘긴다. */
  readonly onToggleRule: (priority: number) => void
  /** 로그 줄들. 코어의 `engine.log.entries` 를 그대로 받는다. */
  readonly entries: readonly LogRowProps[]
  /** 지금 틱. 로그 탭의 개수 표기가 이 값을 쓴다. */
  readonly tick: number
  /** 층별 정산. 없으면 정산 탭이 0 으로 선다. */
  readonly settlements?: readonly FloorSettlement[]
  readonly potions: number
  readonly potionsMax: number
  readonly scrolls: number
  readonly scrollsMax: number
  readonly cooldowns?: string
  readonly tab: SheetTab
  readonly onTabChange: (tab: SheetTab) => void
  /** 시트 본문. 로그를 마지막 줄에 붙여 두려고 밖에서 잡는다. */
  readonly bodyRef?: Ref<HTMLDivElement>
  /** 시트 하단. 관전은 CPU 와 `한 틱`·`처음부터`, 되감기는 비운다. */
  readonly foot?: ReactNode
  /**
   * 바깥이 고정 프레임인가.
   *
   * 세로 전투는 문서 흐름이라 이 부품이 자리를 차지하지 않아야 하고(`display:contents`),
   * 다이얼로그 안에서는 제 상자가 있어야 시트가 그 안에서 스크롤한다.
   */
  readonly isPanel?: boolean
}

/**
 * 전투 화면의 속을 그린다.
 *
 * @param props 도면·시트가 쓸 값 전부와 조작 콜백들.
 * @returns 렌더 트리.
 */
export function BattleFrame(props: BattleFrameProps): React.JSX.Element {
  const enabledRules = props.rows.filter((row) => row.enabled).length
  const counts: ReadonlyMap<SheetTab, string> = new Map([
    ['rules' as SheetTab, formatRulesTabCount(enabledRules, props.rows.length)],
    ['log' as SheetTab, formatLogTabCount(props.tick)],
    ['reward' as SheetTab, formatSettlementTabCount(props.settlements ?? [])],
  ])

  return (
    <div className={`battle-frame${props.isPanel === true ? ' battle-frame--panel' : ''}`}>
      {props.timeBox === undefined ? null : (
        <div className="battle__speed-bar">{props.timeBox}</div>
      )}

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
        settlements={props.settlements ?? []}
        cooldowns={props.cooldowns ?? ''}
        potions={props.potions}
        potionsMax={props.potionsMax}
        scrolls={props.scrolls}
        scrollsMax={props.scrollsMax}
        bodyRef={props.bodyRef}
        {...(props.foot === undefined ? {} : { foot: props.foot })}
      />
    </div>
  )
}
