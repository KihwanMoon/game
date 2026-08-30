/**
 * 튜토리얼 — 규칙 셋짜리 단계 다섯 (로드맵 W20, 결정 #17).
 *
 * **가르치는 것은 설명문이 아니라 대비다.** 각 단계는 시작 규칙표로는 지고 해답
 * 규칙표로는 이긴다. 실패한 판을 한 번 보고 나서 고치는 것이 이 게임의 학습 방식이고
 * (P1 실패는 정보다), 그래서 단계를 열면 **틀린 규칙표가 먼저 실린다.**
 *
 * 진행 상태는 기기에 남는다. 서버에 올리지 않는 이유는 튜토리얼이 보상도 순위도 주지
 * 않기 때문이다 — 검증할 것이 없으면 서버가 알 이유도 없다.
 */
import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { TutorialStage } from '../core/schemas'

export interface TutorialPanelProps {
  readonly stages: readonly TutorialStage[]
  /** 통과한 단계 id 들. */
  readonly cleared: readonly string[]
  /** 지금 열려 있는 단계 id. 없으면 목록만 보인다. */
  readonly activeId: string | undefined
  readonly onOpen: (stage: TutorialStage) => void
  readonly onHint: (stage: TutorialStage) => void
  readonly onClose: () => void
}

/**
 * 튜토리얼 패널을 그린다.
 *
 * @param props 단계 목록과 진행 상태.
 * @returns 패널 요소.
 */
export function TutorialPanel(props: TutorialPanelProps): React.JSX.Element {
  const { stages, cleared, activeId } = props
  const done = stages.filter((stage) => cleared.includes(stage.stageId)).length
  const active = stages.find((stage) => stage.stageId === activeId)

  return (
    <Panel
      title="튜토리얼"
      meta={`${String(done)} / ${String(stages.length)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="tut">
        {active === undefined ? (
          <ul className="tut__list">
            {stages.map((stage, index) => (
              <li className="tut__row" key={stage.stageId}>
                <GlyphState
                  state={cleared.includes(stage.stageId) ? 'true' : 'pending'}
                  label={`${String(index + 1)}. ${stage.titleKo}`}
                />
                <Button
                  size="sm"
                  variant="ghost"
                  glyph="▸"
                  onClick={() => {
                    props.onOpen(stage)
                  }}
                >
                  열기
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <div className="tut__open">
            <div className="tut__head">{active.titleKo}</div>
            <ValueExpr text={active.teachesKo} size="sm" />
            <ValueExpr text={active.briefKo} size="sm" dim />
            <div className="tut__actions">
              <Button
                size="sm"
                variant="ghost"
                glyph="?"
                title="막히면 본다. 봐도 통과로 친다 — 벽에 부딪힌 사람을 세워 두지 않는다"
                onClick={() => {
                  props.onHint(active)
                }}
              >
                힌트
              </Button>
              <Button size="sm" variant="ghost" glyph="↰" onClick={props.onClose}>
                목록
              </Button>
            </div>
          </div>
        )}
      </div>
    </Panel>
  )
}
