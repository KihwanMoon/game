/**
 * 지나간 판을 **다시 돌려** 본다 (T11).
 *
 * **기록을 트는 것이 아니라 다시 돌리는 것이다.** 이벤트 로그는 저장하지 않는다 — 남는
 * 것은 제출(규칙표)과 판정(결과)뿐이다. 그런데 코어가 결정론이라(R5·G3) **같은 입력이면
 * 같은 판**이 나오므로, 시드·방·층·로드아웃·스냅샷을 그대로 넣고 브라우저에서 다시 돌리면
 * 그때 그 판이 눈앞에 다시 선다.
 *
 * 그래서 이 화면은 **서버가 확정한 결과를 함께 적는다.** 재생이 같은 답을 내는지 사람이
 * 눈으로 대조할 수 있어야 하기 때문이다 — 어긋나면 그것은 재생의 버그가 아니라 **두 코어가
 * 갈렸다는 신호**이고, 그것이 게이트 G3 가 지키는 것이다.
 *
 * **전투 화면을 그대로 쓴다.** `BattleView` 는 판 하나를 도는 화면이고, 재생도 판 하나를
 * 도는 일이다 — 여기서 따로 만들면 관전과 재생이 다른 것을 그리게 된다.
 */
import { useMemo } from 'react'

import { BattleView, type BattleSetup } from '../battle'
import { readActivePack } from '../content/pack'
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { RuleSet } from '../core/schemas'
import type { ReplayInput } from '../storage'

/** 적 규칙표. 재생도 관전과 같은 표를 봐야 같은 판이 돈다. */
const ENEMY_RULESETS = readActivePack().enemies

export interface ReplayViewProps {
  readonly replay: ReplayInput | undefined
  /** 재생을 닫는다. */
  readonly onClose: () => void
}

/**
 * 결과를 사람이 읽는 말로.
 *
 * @param outcome 코어가 낸 결과.
 * @returns 화면에 적을 말.
 */
export function formatOutcomeName(outcome: string): string {
  if (outcome === 'PLAYER_WIN') {
    return '승리'
  }
  if (outcome === '') {
    return '판정 전'
  }
  return '패배'
}

/**
 * 재생 화면을 그린다.
 *
 * @param props 재현 입력.
 * @returns 렌더 트리.
 */
export function ReplayView(props: ReplayViewProps): React.JSX.Element | null {
  const { replay } = props
  const ruleset = replay?.ruleset

  // **참조가 바뀌어야 새 판이 돈다.** 같은 제출을 다시 열면 같은 setup 이어야 하고,
  // 다른 제출로 옮기면 새 판이어야 한다 — 제출 id 가 그 경계다.
  const setup = useMemo<BattleSetup | undefined>(() => {
    if (replay === undefined || ruleset === undefined) {
      return undefined
    }
    return {
      roomId: replay.roomId,
      rulesetId: ruleset.rulesetId,
      seed: replay.seed,
      floor: replay.floor,
      roomsPerFloor: replay.roomsPerFloor,
      snapshots: replay.snapshots,
      ...(replay.loadout === undefined ? {} : { loadout: replay.loadout }),
      // 연쇄의 어느 방인지. 앞 방들을 다시 돌려야 인계된 HP 가 그때와 같아진다.
      ...(replay.roomIds.length === 0
        ? {}
        : {
            chain: {
              roomIds: replay.roomIds,
              index: Math.max(0, replay.roomIds.indexOf(replay.roomId)),
            },
          }),
    }
  }, [replay?.submissionId, ruleset])

  const rulesets = useMemo<ReadonlyMap<string, RuleSet>>(
    () =>
      ruleset === undefined
        ? ENEMY_RULESETS
        : new Map([...ENEMY_RULESETS, [ruleset.rulesetId, ruleset]]),
    [ruleset],
  )

  if (replay === undefined) {
    return null
  }
  if (setup === undefined) {
    return (
      <Panel title="리플레이" tone="panel" padded>
        <GlyphState
          state="danger"
          size="sm"
          label="이 제출의 규칙표를 못 읽는다 — 빈 규칙표로 돌리면 다른 판이 나온다"
        />
        <Button size="sm" variant="ghost" glyph="✕" onClick={props.onClose}>
          닫기
        </Button>
      </Panel>
    )
  }

  return (
    <div className="replay">
      <div className="replay__bar">
        <span className="replay__title">{`리플레이 · #${String(replay.submissionId)}`}</span>
        <ValueExpr text={`${replay.roomId} · ${String(replay.floor)}층`} size="sm" dim />
        <ValueExpr text={`시드 ${String(replay.seed)}`} size="sm" dim />
        {/* **서버가 확정한 결과를 함께 적는다.** 재생이 같은 답을 내는지 눈으로 대조할 수
            있어야 한다 — 어긋나면 재생의 버그가 아니라 두 코어가 갈렸다는 신호다 (G3). */}
        <GlyphState
          state={replay.outcome === 'PLAYER_WIN' ? 'true' : 'false'}
          size="sm"
          label={`그때: ${formatOutcomeName(replay.outcome)} · ${String(replay.ticks)}틱 · HP ${String(replay.playerHp)}`}
        />
        <span className="replay__spacer" />
        <Button size="sm" variant="ghost" glyph="✕" onClick={props.onClose}>
          닫기
        </Button>
      </div>
      <div className="replay__body">
        <BattleView
          setup={setup}
          rulesets={rulesets}
          location={`${replay.roomId} · ${String(replay.floor)}층`}
        />
      </div>
    </div>
  )
}
