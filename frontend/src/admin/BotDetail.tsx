/**
 * 봇 하나를 **사람 화면과 같은 눈으로** 본다 (T11).
 *
 * 예전에는 봇 줄을 누르면 가방 하나만 열렸다. 그래서 「이 봇이 왜 이렇게 도는가」에
 * 답할 수 없었다 — 규칙표도, 찍은 능력치도, 켠 스킬도, 지나간 판도 안 보였다. 봇을
 * 관리하려고 연 창인데 관리에 필요한 것이 거기 없었다.
 *
 * **사람 화면의 부품을 그대로 쓴다.** `InventoryGrid`·`CharacterPanel`·`SkillPanel` 을
 * 부르는 이유는, 여기서 따로 만들면 두 화면이 다른 것을 그리게 되기 때문이다 — 봇 가방이
 * 한 번 그렇게 갈렸고, 그때 「봇에게 뭐가 있지」를 답하려던 화면이 답을 틀리게 했다.
 *
 * **읽기 전용이다.** 장비를 직접 입히는 길은 두지 않는다 — 관리자가 봇에게 장비를 채워
 * 넣기 시작하면 그 봇이 만든 순위·경매 기록이 무엇을 뜻하는지 알 수 없게 된다. 봇은
 * 받은 것을 **제 규칙으로** 입어야 한다 (`bots/upgrade`). 넘기기는 그대로 열려 있다:
 * 주는 것과 입히는 것은 다른 일이다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import {
  CharacterPanel,
  formatMaintenanceSentence,
  InventoryGrid,
  MAINTENANCE_ACTIONS,
} from '../editor'
import type { BotDetail, InventoryView } from '../storage'

/** 이 화면이 여는 탭들. 사람 화면의 탭 이름을 그대로 쓴다 — 같은 것을 다르게 부르지 않는다. */
const TABS: readonly (readonly [string, string])[] = [
  ['combat', '전투 규칙'],
  ['upkeep', '정비 규칙'],
  ['me', '캐릭터'],
  ['bag', '가방'],
  ['skill', '스킬'],
  ['replay', '리플레이'],
]

export interface BotDetailProps {
  readonly detail: BotDetail | undefined
  /** 이 봇의 가방. 사람 화면과 같은 라우트로 읽어 온 것이다. */
  readonly bag: InventoryView | undefined
  /** 캐릭터 탭이 쓰는 기본 스탯·목록. 사람 화면과 같은 값을 넘긴다. */
  readonly baseStats: Record<string, number>
  readonly allSkills: readonly string[]
  readonly allItems: readonly string[]
  /** 가방 칸을 골랐을 때. 관리 화면은 넘기기를 건다 — 착용은 걸지 않는다. */
  readonly onPickCell?: (itemId: number) => void
}

/**
 * 판 하나의 결과를 사람이 읽는 말로.
 *
 * @param outcome 코어가 낸 결과 문자열.
 * @returns 화면에 적을 말.
 */
export function formatRunOutcome(outcome: string): string {
  if (outcome === 'PLAYER_WIN') {
    return '승리'
  }
  if (outcome === '') {
    return '아직'
  }
  return '패배'
}

/**
 * 판정 상태를 글리프로.
 *
 * **아직 안 본 것과 틀린 것을 가른다.** 둘을 같이 적으면 서버가 밀렸을 뿐인데 부정이
 * 있었던 것처럼 읽힌다.
 *
 * @param verdict 서버 판정.
 * @returns 글리프 상태.
 */
export function resolveVerdictState(verdict: string): 'true' | 'danger' | 'pending' {
  if (verdict === 'verified') {
    return 'true'
  }
  if (verdict === '') {
    return 'pending'
  }
  return 'danger'
}

/**
 * 리플레이 — 지나간 판들.
 *
 * **기록이지 재생이 아니다.** 이벤트 로그는 저장하지 않으므로(제출과 판정만 남는다) 여기서
 * 낼 수 있는 것은 「어떤 판을 돌았고 어떻게 끝났는가」까지다. 시드를 함께 적는 이유는
 * 그것과 규칙표가 있으면 **같은 판을 다시 돌릴 수 있기** 때문이다 (R5·G3) — 지금은 사람이
 * 그 시드를 손으로 옮겨 담아야 한다.
 *
 * @param props 판들.
 * @returns 렌더 트리.
 */
export function BotRuns(props: { readonly runs: BotDetail['runs'] }): React.JSX.Element {
  if (props.runs.length === 0) {
    return <ValueExpr text="아직 돈 판이 없다" size="sm" dim />
  }
  return (
    <ul className="botd__runs">
      {props.runs.map((run) => (
        <li className="botd__run" key={run.submissionId}>
          <span className="botd__run-room">{run.roomId}</span>
          <span className="botd__run-floor">{`${String(run.floor)}층`}</span>
          <GlyphState
            state={run.outcome === 'PLAYER_WIN' ? 'true' : 'false'}
            size="sm"
            label={formatRunOutcome(run.outcome)}
          />
          <span className="botd__run-num">{`${String(run.ticks)}틱`}</span>
          <span className="botd__run-num">{`HP ${String(run.playerHp)}`}</span>
          {/* 시드를 적는다 — 이것과 규칙표가 있으면 그 판이 그대로 재현된다. */}
          <span className="botd__run-seed">{`시드 ${String(run.seed)}`}</span>
          <GlyphState
            state={resolveVerdictState(run.verdict)}
            size="sm"
            label={run.verdict === '' ? '검증 전' : run.verdict === 'verified' ? '검증됨' : run.verdict}
          />
        </li>
      ))}
    </ul>
  )
}

/**
 * 정비 규칙을 문장으로 편다. **사람 화면과 같은 문장이다.**
 *
 * @param props 정비 행들.
 * @returns 렌더 트리.
 */
function BotUpkeep(props: { readonly rows: BotDetail['maintenance']['rows'] }): React.JSX.Element {
  if (props.rows.length === 0) {
    return <ValueExpr text="정비 규칙이 없다 — 이 봇은 판 뒤에 아무것도 안 한다" size="sm" dim />
  }
  return (
    <ul className="mnt__list">
      {props.rows.map((row, index) => (
        // 행에 고유 id 가 없다 — 순서가 곧 정체성이라 자리 번호가 key 다.
        <li className="mnt__row" key={`upkeep-${String(index)}`}>
          <span className="mnt__when">{`${String(index + 1)}.`}</span>
          <span className="mnt__what">{formatMaintenanceSentence(row)}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * 봇 하나의 상세를 탭으로 그린다.
 *
 * @param props 상세와 가방.
 * @returns 렌더 트리.
 */
export function BotDetailPanel(props: BotDetailProps): React.JSX.Element {
  const [tabId, setTabId] = useState('combat')
  const { detail } = props
  if (detail === undefined) {
    return (
      <Panel title="봇 상세" tone="panel" padded>
        <ValueExpr text="봇 줄을 고르면 그 봇의 규칙표·가방·판을 연다" size="sm" dim />
      </Panel>
    )
  }
  return (
    <Panel title={`봇 · ${detail.handle}`} meta={detail.rulesetId} tone="panel" padded scroll>
      <nav className="botd__tabs" aria-label="봇 화면">
        {TABS.map(([id, label]) => (
          <Button
            key={id}
            size="sm"
            variant={id === tabId ? 'primary' : 'ghost'}
            active={id === tabId}
            onClick={() => {
              setTabId(id)
            }}
          >
            {label}
          </Button>
        ))}
      </nav>

      {tabId === 'combat' ? (
        <div className="botd__body">
          {/* **절이 아니라 id 다.** 봇의 전투 규칙표는 우리가 고른 견본이고, 그 내용은
              사람 화면의 견본 목록에 이미 있다 — 여기 베끼면 두 곳이 갈린다. */}
          <ValueExpr text={`전투 규칙표 · ${detail.rulesetId}`} size="sm" />
          <ValueExpr
            text="견본 하나를 그대로 돌린다 — 고치려면 위의 봇 표에서 규칙표를 바꾼다"
            size="sm"
            dim
          />
        </div>
      ) : null}

      {tabId === 'upkeep' ? (
        <div className="botd__body">
          <ValueExpr
            text={`정비 행동 ${String(MAINTENANCE_ACTIONS.length)}종 중 이 봇이 켠 것`}
            size="sm"
            dim
          />
          <BotUpkeep rows={detail.maintenance.rows} />
        </div>
      ) : null}

      {tabId === 'me' ? (
        <div className="botd__body">
          <CharacterPanel
            progress={detail.progress}
            baseStats={props.baseStats}
            allSkills={props.allSkills}
            allItems={props.allItems}
            link="online"
          />
        </div>
      ) : null}

      {tabId === 'bag' ? (
        <div className="botd__body">
          {/* **착용을 걸지 않는다.** 관리자가 봇에게 장비를 입히기 시작하면 그 봇이 만든
              순위·경매 기록이 무엇을 뜻하는지 알 수 없게 된다 — 넘기는 것까지가 관리다. */}
          <ValueExpr text="보기만 한다 — 입히는 것은 봇이 제 규칙으로 한다" size="sm" dim />
          <InventoryGrid
            inventory={props.bag}
            pickedKey=""
            ownerLabel={detail.handle}
            onPick={(cell) => {
              const itemId = cell.entry?.item?.itemId
              if (itemId !== undefined && props.onPickCell !== undefined) {
                props.onPickCell(itemId)
              }
            }}
          />
        </div>
      ) : null}

      {tabId === 'skill' ? (
        <div className="botd__body">
          {detail.skills.rows.length === 0 ? (
            <ValueExpr text="장비가 연 스킬이 없다" size="sm" dim />
          ) : (
            <ul className="botd__skills">
              {detail.skills.rows.map((row) => (
                <li className="botd__skill" key={row.skillId}>
                  <GlyphState
                    state={row.isOn ? 'true' : 'false'}
                    size="sm"
                    label={row.skillId}
                  />
                  {row.isLocked ? <ValueExpr text="못 끈다" size="sm" dim /> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {tabId === 'replay' ? (
        <div className="botd__body">
          <ValueExpr
            text={`최근 ${String(detail.runs.length)}판 — 기록이지 재생이 아니다 (이벤트 로그는 안 남긴다)`}
            size="sm"
            dim
          />
          <BotRuns runs={detail.runs} />
        </div>
      ) : null}
    </Panel>
  )
}
