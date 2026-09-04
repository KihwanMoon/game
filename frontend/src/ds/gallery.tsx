/**
 * 컴포넌트 카탈로그. `/ds.html` 로 열린다.
 *
 * 계약 17종과 그 상태를 한 화면에 늘어놓아 눈으로 대조하는 곳이다. 특히 RuleRow 의
 * 여섯 상태는 여기서만 나란히 보이므로, 규칙표를 고칠 때 이 페이지를 먼저 연다.
 *
 * 황동 예산에 대하여: 예산 "한 화면에 3곳" 은 **제품 화면**의 규칙이다. 이 페이지는
 * 부품 카탈로그라 armed 규칙 여러 줄과 primary 버튼이 한꺼번에 보인다. 아래 전투 화면
 * 골격은 예산을 지킨다 — primary 버튼 없음 / armed 규칙 한 줄 / 플레이어 말 하나.
 */
import { useState } from 'react'

import type { LogEntry } from '../core/eventLog'
import { createLogEntry } from '../core/eventLog'

import './gallery.css'
// 부품은 **배럴에서만** 가져간다. 파일을 직접 찌르면 ds.css 가 딸려오지 않아
// 스타일 없는 마크업이 나온다 (index.ts 주석 참조).
import type { GlyphStateKind } from './index'
import {
  Button,
  GlyphState,
  HpGauge,
  LogPanel,
  Panel,
  PlanActor,
  PlanGrid,
  ResourceCount,
  RuleRow,
  RuleTable,
  SegmentedGauge,
  SpeedControl,
  StatusBar,
  ThreatNotice,
  TopBar,
  ValueExpr,
} from './index'

/** 카탈로그 초기 속도. */
const INITIAL_SPEED = 1

/** 카탈로그가 보여 주는 예시 틱. */
const SAMPLE_TICK = 27

/** 예시 체력. */
const SAMPLE_HP = 18

/** 예시 최대 체력. */
const SAMPLE_HP_MAX = 30

/** 예시 낮은 체력. */
const SAMPLE_HP_LOW = 6

/** 예시 물약 수. */
const SAMPLE_POTIONS = 2

/** 예시 물약 최대. */
const SAMPLE_POTIONS_MAX = 3

/** 예시 CPU 사용량. */
const SAMPLE_CPU_USED = 5

/** 예시 CPU 예산. */
const SAMPLE_CPU_BUDGET = 8

/** 예시 CPU 초과량. */
const SAMPLE_CPU_OVER = 10

/** 예시 예고 잔여 틱. */
const SAMPLE_THREAT_TICKS = 3

/** GlyphState 다섯 상태. */
const GLYPH_KINDS: readonly GlyphStateKind[] = [
  'true',
  'false',
  'armed',
  'danger',
  'pending',
  'blocked',
]

/**
 * 로그 예시.
 *
 * **코어의 `LogEntry` 를 그대로 넘긴다.** 이 대입이 컴파일되는 것이 LogPanel 계약의
 * 핵심이다 — `engine.log.entries` 를 변환 없이 꽂을 수 있어야 한다.
 */
const SAMPLE_LOG: readonly LogEntry[] = [
  createLogEntry({
    tick: 26,
    entityId: 'player',
    phase: 'DECIDE',
    expr: '적거리(2) <= 사거리(3)',
    outcome: '사격 선택',
    rule: 1,
    fired: true,
  }),
  createLogEntry({
    tick: 26,
    entityId: 'player',
    phase: 'DECIDE',
    expr: '체력비율(60) <= 30',
    outcome: '조건 거짓',
    rule: 2,
  }),
  createLogEntry({
    tick: SAMPLE_TICK,
    entityId: 'goblin_rusher_1',
    phase: 'RESOLVE',
    expr: '돌진 명중',
    outcome: 'player 피격',
    rule: 1,
    delta: -4,
    fired: true,
    targetId: 'player',
  }),
  createLogEntry({
    tick: SAMPLE_TICK,
    entityId: 'player',
    phase: 'RESOLVE',
    expr: '물약 사용',
    outcome: '회복',
    rule: 3,
    delta: 6,
    fired: true,
    targetId: 'player',
  }),
]

/**
 * 전투 화면 골격. 56 / 320 / 가변 / 300 / 48 이고 열 사이는 1px 괘선 하나다.
 *
 * @returns 렌더 트리.
 */
function BattleSkeleton(): React.JSX.Element {
  const [speed, setSpeed] = useState(INITIAL_SPEED)

  return (
    <div className="gal__battle">
      <TopBar location="1층 · 파수실" tick={SAMPLE_TICK} speed={speed} onSpeedChange={setSpeed} />
      <div className="gal__cols">
        <div className="gal__col">
          <Panel title="규칙표" meta={`cpu ${String(SAMPLE_CPU_USED)} / ${String(SAMPLE_CPU_BUDGET)}`} padded={false} scroll>
            <RuleTable>
              <RuleRow
                index={1}
                state="true"
                armed
                condition="적거리(2) <= 사거리(3)"
                action="→ 가장 가까운 적에게 사격"
                cpu={{ used: 2, budget: SAMPLE_CPU_BUDGET }}
              />
              <RuleRow
                index={2}
                state="true"
                condition="체력비율(60) <= 80"
                action="→ 물약 사용"
                cpu={{ used: 4, budget: SAMPLE_CPU_BUDGET }}
              />
              <RuleRow
                index={3}
                state="false"
                condition="적수(1) >= 3"
                action="→ 후퇴"
                cpu={{ used: SAMPLE_CPU_USED, budget: SAMPLE_CPU_BUDGET }}
              />
              <RuleRow index={4} state="pending" condition="항상" action="→ 접근" />
            </RuleTable>
          </Panel>
        </div>
        <div className="gal__gap" />
        <div className="gal__plan">
          <PlanGrid>
            <PlanActor x={2} y={4} kind="self" label="me" />
            <PlanActor x={5} y={3} kind="charge" label="rush" />
            <PlanActor x={8} y={6} kind="shoot" label="bow" />
            <PlanActor x={10} y={1} kind="summon" label="sum" />
            {/* 도플갱어. 등급은 정예인데 색이 위험색이다 — 등급이 아니라 정체다. */}
            <PlanActor x={7} y={2} kind="charge" label="분신" tier="ELITE" isDanger />
          </PlanGrid>
        </div>
        <div className="gal__gap" />
        <div className="gal__col">
          <Panel title="로그" meta={`T${String(SAMPLE_TICK)}`} padded={false} scroll>
            <LogPanel entries={SAMPLE_LOG} />
          </Panel>
        </div>
      </div>
      <StatusBar
        hp={SAMPLE_HP}
        hpMax={SAMPLE_HP_MAX}
        potions={SAMPLE_POTIONS}
        potionsMax={SAMPLE_POTIONS_MAX}
        threat="폭탄 슬라임 폭발 예고"
      />
    </div>
  )
}

/**
 * 부품 카탈로그 페이지.
 *
 * @returns 렌더 트리.
 */
export function Gallery(): React.JSX.Element {
  const [speed, setSpeed] = useState(INITIAL_SPEED)
  const [picked, setPicked] = useState(0)

  return (
    <main className="gal">
      <h1 className="gal__title">디자인 시스템 부품 카탈로그</h1>
      <p className="gal__note">
        design/README.md 의 컴포넌트 계약 17종. 참/거짓은 색·글리프·명도 세 채널로 적히므로
        흑백으로 인쇄해도 구분돼야 한다. 키보드 Tab 으로 이동하면 06 포커스 상태를 볼 수 있다.
      </p>

      <Panel title="전투 화면 골격" meta="56 / 320 / 가변 / 300 / 48" padded={false}>
        <BattleSkeleton />
      </Panel>

      <div className="gal__grid">
        <Panel title="Button" meta="variant · size · active">
          <div className="gal__stack">
            <div className="gal__row">
              <Button variant="primary" glyph="▶">
                실행
              </Button>
              <Button variant="secondary">되돌리기</Button>
              <Button variant="ghost">취소</Button>
            </div>
            <div className="gal__row">
              <Button size="sm" variant="secondary" active>
                활성 sm
              </Button>
              <Button size="sm" variant="ghost">
                기본 sm
              </Button>
              <Button variant="secondary" disabled>
                비활성
              </Button>
            </div>
            <Button variant="secondary" block glyph="＋">
              규칙 추가 (block)
            </Button>
          </div>
        </Panel>

        <Panel title="GlyphState" meta="5 상태">
          <div className="gal__stack">
            {GLYPH_KINDS.map((kind) => (
              <GlyphState key={kind} state={kind} label={kind} />
            ))}
          </div>
        </Panel>

        <Panel title="SegmentedGauge" meta="tone 4 · 초과">
          <div className="gal__stack">
            <SegmentedGauge value={SAMPLE_CPU_USED} max={SAMPLE_CPU_BUDGET} tone="cpu" label="cpu" readout />
            <SegmentedGauge value={SAMPLE_CPU_OVER} max={SAMPLE_CPU_BUDGET} tone="cpu" label="cpu 초과" readout />
            <SegmentedGauge value={SAMPLE_POTIONS} max={SAMPLE_POTIONS_MAX} tone="hp" label="물약" readout />
            <SegmentedGauge value={1} max={SAMPLE_POTIONS_MAX} tone="danger" label="위험" readout />
            <SegmentedGauge value={1} max={SAMPLE_POTIONS_MAX} tone="dim" label="비활성" readout />
          </div>
        </Panel>

        <Panel title="ValueExpr" meta="실측값 병기">
          <div className="gal__stack">
            <ValueExpr text="적거리(2) <= 사거리(3)" />
            <ValueExpr text="체력비율(60) <= 30" size="sm" />
            <ValueExpr text="적수(1) >= 3" dim />
          </div>
        </Panel>

        <Panel title="HpGauge · ResourceCount">
          <div className="gal__stack">
            <HpGauge value={SAMPLE_HP} max={SAMPLE_HP_MAX} />
            <HpGauge value={SAMPLE_HP_LOW} max={SAMPLE_HP_MAX} />
            <ResourceCount label="물약" count={SAMPLE_POTIONS} max={SAMPLE_POTIONS_MAX} glyph="◍" />
            <ResourceCount label="열쇠" count={0} max={2} />
          </div>
        </Panel>

        <Panel title="SpeedControl" meta={`현재 ×${String(speed)}`}>
          <SpeedControl value={speed} onChange={setSpeed} />
        </Panel>

        <Panel title="ThreatNotice" meta="tone 2">
          <div className="gal__stack">
            <ThreatNotice text="폭탄 슬라임 폭발" ticks={SAMPLE_THREAT_TICKS} tone="danger" />
            <ThreatNotice text="문이 닫힌다" ticks={1} tone="neutral" glyph="◇" />
          </div>
        </Panel>

        <Panel title="Panel" meta="tone 3">
          <div className="gal__stack">
            <Panel title="panel" tone="panel">
              기본 면
            </Panel>
            <Panel title="raised" tone="raised">
              한 단 밝은 면
            </Panel>
            <Panel title="plan" tone="plan">
              도면 바탕 (가장 어두움)
            </Panel>
          </div>
        </Panel>
      </div>

      <Panel title="RuleRow — 여섯 상태" meta={`선택 ${String(picked)}`} padded={false}>
        <RuleTable>
          <RuleRow
            index={1}
            state="pending"
            condition="적거리(–) <= 사거리(3)"
            action="→ 01 기본 · 편집 가능"
            cpu={2}
            onClick={() => {
              setPicked(1)
            }}
          />
          <RuleRow
            index={2}
            state="true"
            condition="적거리(2) <= 사거리(3)"
            action="→ 02 조건 참·미발동 · 배경 안 칠함"
            cpu={{ used: 4, budget: SAMPLE_CPU_BUDGET }}
            onClick={() => {
              setPicked(2)
            }}
          />
          <RuleRow
            index={3}
            state="false"
            condition="체력비율(60) <= 30"
            action="→ 03 조건 거짓 · 명도 한 단 낮춤"
            cpu={{ used: SAMPLE_CPU_USED, budget: SAMPLE_CPU_BUDGET }}
            onClick={() => {
              setPicked(3)
            }}
          />
          <RuleRow
            index={4}
            state="true"
            armed
            condition="적수(2) >= 1"
            action="→ 04 이번 틱 발동 · 좌측 황동 세로바"
            cpu={{ used: 7, budget: SAMPLE_CPU_BUDGET }}
            onClick={() => {
              setPicked(4)
            }}
          />
          <RuleRow
            index={5}
            state="true"
            condition="아군거리(4) >= 2"
            action="→ 05 CPU 예산 초과 · 본문 명도 유지"
            cpu={{ used: SAMPLE_CPU_OVER, budget: SAMPLE_CPU_BUDGET }}
            onClick={() => {
              setPicked(5)
            }}
          />
          <RuleRow
            index={6}
            state="pending"
            condition="항상"
            action="→ 06 Tab 으로 포커스하면 황동 외곽선"
            cpu={2}
            onClick={() => {
              setPicked(6)
            }}
          />
        </RuleTable>
      </Panel>
    </main>
  )
}
