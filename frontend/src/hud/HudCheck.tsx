/**
 * 확인용 페이지 — **실제 전투 로그로** 관전·진단 화면을 그려 본다 (`/hud.html`).
 *
 * 가짜 로그를 그려 보는 페이지가 아니다. 여기서 도는 것은 골든 대조를 통과한 그 엔진이고
 * 화면에 적히는 값은 전부 `TickEngine` 이 낸 것이다. 그래야 "부품은 되는데 실제 로그에서는
 * 안 되는" 자리가 남지 않는다.
 *
 * 조합 여섯은 파이썬 기준 문서(`scripts/export_analysis_golden.py`)와 같다. 화면에서 이상해
 * 보이는 것을 그대로 대조 테스트로 옮길 수 있게 하려는 것이다.
 *
 * 기록은 조합마다 한 번만 만든다. 같은 조합은 늘 같은 프레임을 내므로 다시 만들 이유가
 * 없다 (R5).
 */
import { useMemo, useState } from 'react'

import { G0_RULESETS } from '../core/resources'
import { Button } from '../ds'

import { recordBattle } from './battleRecorder'
import { DEMO_CASES } from './demoCases'
import { HudScreen } from './HudScreen'

/**
 * 확인용 페이지를 그린다.
 *
 * @returns 렌더 트리.
 * @throws 확인용 조합이 하나도 없는 경우.
 */
export function HudCheck(): React.JSX.Element {
  const [caseId, setCaseId] = useState(DEMO_CASES[0]?.caseId ?? '')
  const demo = DEMO_CASES.find((item) => item.caseId === caseId) ?? DEMO_CASES[0]
  if (demo === undefined) {
    throw new Error('확인용 조합이 하나도 없다')
  }

  const recording = useMemo(() => recordBattle(demo.setup, G0_RULESETS), [demo])

  return (
    <HudScreen
      // 조합이 바뀌면 화면 상태(재생 위치·추적 여부)도 처음으로 돌린다.
      key={demo.caseId}
      recording={recording}
      location={`1층 · ${recording.template.templateId}`}
      controls={
        <div className="hud-check">
          {DEMO_CASES.map((item) => (
            <Button
              key={item.caseId}
              size="sm"
              variant="ghost"
              active={item.caseId === demo.caseId}
              onClick={() => {
                setCaseId(item.caseId)
              }}
            >
              {item.setup.roomId} · {item.setup.rulesetId}
            </Button>
          ))}
          <span className="hud-check__note">
            {recording.entries.length}줄 · {recording.ticks}틱 · {recording.outcome}
          </span>
        </div>
      }
    />
  )
}
