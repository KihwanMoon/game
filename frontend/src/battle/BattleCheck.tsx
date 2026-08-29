/**
 * 확인용 페이지 — 렌더러를 **실제 전투 상태로** 그려 본다 (`/battle.html`).
 *
 * 가짜 장면을 그려 보는 페이지가 아니다. 여기서 도는 것은 골든 대조를 통과한 그 엔진이고,
 * 화면이 보여주는 값은 전부 `TickEngine` 이 낸 것이다. 그래야 "렌더러는 되는데 실제
 * 상태에서는 안 되는" 자리가 남지 않는다.
 *
 * **정예 편성 토글이 있는 이유가 중요하다.** 방 다섯 개의 스폰이 전부 고블린 3종이라,
 * 덧붙이지 않으면 폭탄 슬라임이 없고 폭탄 슬라임이 없으면 **예고 타일이 한 번도 그려지지
 * 않는다** (GDD §4.2). 텔레그래프 표시를 눈으로 확인할 수 있는 유일한 길이다.
 * 세 좌표는 방 다섯 개 모두에서 바닥이고 템플릿 스폰과 겹치지 않는다.
 */
import { useMemo, useState } from 'react'

import { Button } from '../ds'
import { G0_RULESETS, ROOM_TEMPLATES } from '../core/resources'
import { BattleView } from './BattleView'
import type { BattleSetup, ExtraEnemy } from './battleSession'

/** 처음 열었을 때의 방과 규칙표. */
const INITIAL_ROOM_ID = 'pillars'
const INITIAL_RULESET_ID = 'g0_cover'

/** 확인용 고정 시드. 같은 시드는 같은 판을 낸다 (R5). */
const CHECK_SEED = 4242

/**
 * 정예 편성. 예고(자폭)·치유·대소환을 한 판에 모두 등장시킨다.
 *
 * 세 좌표는 방 다섯 개에서 모두 바닥이며 템플릿 스폰 좌표와 겹치지 않는다. 겹치면 한 쪽이
 * 조용히 덮인다.
 */
const ELITE_ENEMIES: readonly ExtraEnemy[] = [
  { kind: 'bomb_slime', x: 9, y: 1 },
  { kind: 'mender_acolyte', x: 10, y: 4 },
  { kind: 'arch_summoner', x: 9, y: 7 },
]

/**
 * 확인용 페이지를 그린다.
 *
 * @returns 렌더 트리.
 */
export function BattleCheck(): React.JSX.Element {
  const [roomId, setRoomId] = useState(INITIAL_ROOM_ID)
  const [rulesetId, setRulesetId] = useState(INITIAL_RULESET_ID)
  const [isElite, setElite] = useState(true)
  const [runCount, setRunCount] = useState(0)

  // runCount 는 값이 아니라 **새 판을 만들라는 신호**다. 같은 방·같은 시드로 다시 돌리려면
  // setup 의 참조가 바뀌어야 한다.
  const setup: BattleSetup = useMemo(
    () => ({
      roomId,
      rulesetId,
      seed: CHECK_SEED,
      extraEnemies: isElite ? ELITE_ENEMIES : [],
    }),
    [roomId, rulesetId, isElite, runCount],
  )

  const controls = (
    <div className="battle-check">
      <div className="battle-check__group">
        {ROOM_TEMPLATES.map((template) => (
          <Button
            key={template.templateId}
            size="sm"
            variant="ghost"
            active={template.templateId === roomId}
            onClick={() => {
              setRoomId(template.templateId)
            }}
          >
            {template.templateId}
          </Button>
        ))}
      </div>
      <div className="battle-check__group">
        {[...G0_RULESETS.keys()].map((id) => (
          <Button
            key={id}
            size="sm"
            variant="ghost"
            active={id === rulesetId}
            onClick={() => {
              setRulesetId(id)
            }}
          >
            {id}
          </Button>
        ))}
      </div>
      <div className="battle-check__group">
        <Button
          size="sm"
          variant="ghost"
          active={isElite}
          onClick={() => {
            setElite((value) => !value)
          }}
          title="폭탄 슬라임·수복사·대소환사를 덧붙여 예고 타일을 띄운다"
        >
          정예 편성
        </Button>
        <Button
          size="sm"
          variant="ghost"
          glyph="↺"
          onClick={() => {
            setRunCount((value) => value + 1)
          }}
        >
          다시
        </Button>
      </div>
    </div>
  )

  return (
    <BattleView
      setup={setup}
      rulesets={G0_RULESETS}
      location={`1층 · ${roomId}`}
      controls={controls}
    />
  )
}
