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
import type { RewardOfferView } from '../storage'
import type { ReactNode, Ref } from 'react'

import { Button } from '../ds'
import type { LogRowProps } from '../ds'
import { BattleFrame } from './BattleFrame'
import type { FloorSettlement } from './settlement'
import { formatTick, type SheetTab } from './portraitSheet'
import type { RuleRowView } from './ruleRows'
import type { VitalRow } from './vitalRows'
import { SpeedBox } from './SpeedBox'

/**
 * 세로 하단바의 체력 막대 폭(px).
 *
 * `HpGauge` 는 폭을 토큰이 아니라 숫자 prop 으로 받는다(design/README.md 컴포넌트 계약).
 * 데스크톱 StatusBar 가 160 을 쓰는 자리이며 세로는 명세가 90 으로 정했다.
 */

/** 시간 조작 두 칸의 이름. 시트 하단에 있던 것이 배속 옆으로 왔다. */
const STEP_TEXT = '한 틱'
const RESTART_TEXT = '처음부터'

/** 물약 칸의 글리프와 라벨. ds `StatusBar` 와 같은 것을 쓴다. */


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
  /** 로그 줄들. 코어의 `engine.log.entries` 를 그대로 받는다. */
  readonly entries: readonly LogRowProps[]
  /** 층별 정산. 상단 알림이 아니라 탭이다 — 알림은 뜰 때마다 아래 전부를 밀었다. */
  readonly settlements?: readonly FloorSettlement[]
  /** 지금 고를 수 있는 층 보상 (GDD §2.2). 층이 0 이면 안 그린다. */
  readonly rewardFloor?: number
  readonly rewardOffers?: readonly RewardOfferView[]
  readonly isRewardBusy?: boolean
  readonly onTakeReward?: (rewardId: string) => void
  /**
   * 상태 탭의 줄들 — 체력·소모품·쿨타임·예산.
   *
   * **한 줄에 하나씩 쌓는다** (실제 요청). 늘 보이는 한 줄로 이어 두었더니 스킬이 둘만
   * 돼도 잘렸다 — 가로로 이으면 무엇이 들어 있는지 훑을 수 없다.
   */
  readonly vitals: readonly VitalRow[]
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
  return (
    <div className="battle battle--portrait">
      {/* **붙어 있는다.** 문서가 화면보다 길어지면 스크롤하는데, 그때 층·실과 틱이
          함께 올라가면 지금 어디의 몇 틱인지가 화면 밖으로 나간다. */}
      <header className="battle__bar battle__bar--top">
        <h1 className="battle__location">{props.location}</h1>
        <span className="battle__tick">
          <span className="battle__tick-glyph" aria-hidden="true">
            {TICK_GLYPH}
          </span>
          <span className="ds-sr">{TICK_NAME}</span>
          {formatTick(props.tick)}
        </span>
      </header>

      {/* **도면 밑이다** (2026-09-08, 실제 요청). 머리에 두면 화면을 여는 순간 눈이 먼저
          닿는 것이 「나가는 문」이 되고, 판을 보러 온 사람에게 도면이 그만큼 밀린다.
          도면을 보고 나서 무엇을 할지 고르는 순서가 맞다. */}
      {props.controls === undefined ? null : (
        <span className="battle__controls">{props.controls}</span>
      )}

      <BattleFrame
        {...(props.plan === undefined ? {} : { plan: props.plan })}
        outcome={props.outcome}
        {...(props.threat === undefined ? {} : { threat: props.threat })}
        rows={props.rows}
        onToggleRule={props.onToggleRule}
        entries={props.entries}
        tick={props.tick}
        settlements={props.settlements ?? []}
        rewardFloor={props.rewardFloor ?? 0}
        rewardOffers={props.rewardOffers ?? []}
        isRewardBusy={props.isRewardBusy === true}
        onTakeReward={props.onTakeReward ?? (() => undefined)}
        vitals={props.vitals}
        tab={props.tab}
        onTabChange={props.onTabChange}
        {...(props.bodyRef === undefined ? {} : { bodyRef: props.bodyRef })}
        foot={
          // **시간 조작을 한 줄로 모은다.** 배속은 도면 위 전용 줄에, `한 틱`·`처음부터`
          // 는 시트 맨 아래에 있어서 같은 종류가 화면 반대쪽에 앉아 있었다.
          <div className="battle__time">
            <SpeedBox
              value={props.speed}
              onChange={props.onSpeedChange}
              onInstant={props.onInstant}
            />
            <div className="battle__time-acts">
              <Button size="sm" variant="ghost" onClick={props.onStep}>
                {STEP_TEXT}
              </Button>
              <Button size="sm" variant="ghost" onClick={props.onRestart}>
                {RESTART_TEXT}
              </Button>
            </div>
          </div>
        }
      />
    </div>
  )
}
