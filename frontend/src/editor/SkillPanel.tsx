/**
 * 스킬 세팅 패널 (결정 #13 확장).
 *
 * **장비창과 같은 격자다.** 칸은 상태(이름·켬끔)만 그리고, 누르면 아래 상세에 그 스킬의
 * 수치(계수·쿨타임·사거리·모양)와 제약, 켬·끔이 모인다 — 수치는 밸런스 정본
 * (`@resources/balance/skills.json`)에서 직접 읽는다. 사본을 두면 두 코어가 다른
 * 데이터로 돈다.
 *
 * **빼기만 한다.** 스킬은 장비가 열고, 여기서는 연 것 중 안 들고 갈 것을 끈다.
 */
import { useState } from 'react'

import skillsRaw from '@resources/balance/skills.json'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import type { SkillPrefView } from '../storage'

import { formatParamLabel } from './blockOptions'

import { checkLinked, type LinkState } from './linkState'

export interface SkillPanelProps {
  readonly view: SkillPrefView | undefined
  readonly link: LinkState
  readonly detail: string
  readonly onChange: (view: SkillPrefView) => void
}

interface RawSkill {
  id: string
  shape?: { kind?: string; radius?: number }
  target_faction?: string
  coef_pct?: number
  cooldown?: number
  range?: number | null
  telegraph?: number
}

const SKILL_TABLE: ReadonlyMap<string, RawSkill> = new Map(
  ((skillsRaw as { skills: RawSkill[] }).skills ?? []).map((skill) => [skill.id, skill]),
)

const SHAPE_LABELS: ReadonlyMap<string, string> = new Map([
  ['SINGLE', '단일 대상'],
  ['AREA', '반경 범위'],
  ['SELF', '자기 자신'],
  ['SUMMON', '소환'],
])

/**
 * 스킬 하나의 수치·제약을 줄들로 편다.
 *
 * **실측값을 병기한다** (P1). 「강하다」가 아니라 「계수 140% · 쿨타임 3틱」이다.
 *
 * @param skillId 스킬 id.
 * @returns 화면에 적을 줄들. 정본에 없는 스킬이면 그 사실 한 줄.
 */
export function listSkillFacts(skillId: string): readonly string[] {
  const skill = SKILL_TABLE.get(skillId)
  if (skill === undefined) {
    return ['정본에 없는 스킬이다 — 밸런스 데이터가 앞서 나갔다']
  }
  const lines: string[] = []
  const shape = SHAPE_LABELS.get(skill.shape?.kind ?? '') ?? (skill.shape?.kind ?? '')
  lines.push(
    `${shape}${skill.shape?.radius === undefined ? '' : ` (반경 ${String(skill.shape.radius)})`}` +
      ` · 위력 계수 ${String(skill.coef_pct ?? 100)}%`,
  )
  lines.push(
    `쿨타임 ${String(skill.cooldown ?? 0)}틱 · 사거리 ${
      skill.range === null || skill.range === undefined ? '무기를 따른다' : String(skill.range)
    }`,
  )
  if ((skill.telegraph ?? 0) > 0) {
    lines.push(`예고 ${String(skill.telegraph)}틱 뒤에 터진다 — 그동안 적이 피할 수 있다`)
  }
  return lines
}

/**
 * 스킬 세팅을 그린다.
 *
 * @param props 세팅과 처리기.
 * @returns 렌더 트리.
 */
export function SkillPanel(props: SkillPanelProps): React.JSX.Element {
  const [pickedId, setPicked] = useState('')
  const view = props.view
  if (view === undefined) {
    return (
      <Panel title="스킬 세팅">
        <ValueExpr text="서버에 닿지 못했다 — 스킬을 못 읽는다" size="sm" dim />
      </Panel>
    )
  }
  const picked = view.rows.find((row) => row.skillId === pickedId)
  return (
    <Panel title="스킬 세팅">
      <ValueExpr
        text="장비가 연 스킬만 보인다 — 칸을 누르면 수치와 제약이 뜬다"
        size="sm"
        dim
      />
      <div className="invg invg--equip">
        {view.rows.map((row) => (
          <button
            type="button"
            className={`invg__cell${row.skillId === pickedId ? ' invg__cell--picked' : ''}${
              row.isOn ? '' : ' invg__cell--sealed'
            }`}
            key={row.skillId}
            aria-label={`스킬 ${formatParamLabel(row.skillId)}`}
            onClick={() => {
              setPicked((current) => (current === row.skillId ? '' : row.skillId))
            }}
          >
            <span className="invg__label">{formatParamLabel(row.skillId)}</span>
            {row.isOn ? null : <span className="invg__marks">끔</span>}
          </button>
        ))}
      </div>
      {picked === undefined ? (
        <ValueExpr text="칸을 고르면 여기에 수치·제약과 켬·끔이 뜬다" size="sm" dim />
      ) : (
        <div className="invd">
          <div className="invd__row">
            <span className="inv__name">{formatParamLabel(picked.skillId)}</span>
            {picked.isLocked ? (
              <GlyphState state="blocked" size="sm" label="기본 — 못 끈다 (폴백이 기댄다)" />
            ) : (
              <GlyphState
                state={picked.isOn ? 'true' : 'false'}
                size="sm"
                label={picked.isOn ? '다음 티켓에 실린다' : '꺼짐 — 규칙표에서 「미장착」이 된다'}
              />
            )}
          </div>
          <ul className="invd__affixes">
            {listSkillFacts(picked.skillId).map((line) => (
              <li className="invd__affix" key={line}>
                <ValueExpr text={line} size="sm" />
              </li>
            ))}
          </ul>
          {picked.isLocked ? null : (
            <div className="invd__row invd__row--tools">
              <Button
                size="sm"
                variant={picked.isOn ? 'ghost' : 'primary'}
                disabled={!checkLinked(props.link)}
                onClick={() => {
                  props.onChange({
                    rows: view.rows.map((entry) =>
                      entry.skillId === picked.skillId
                        ? { ...entry, isOn: !entry.isOn }
                        : entry,
                    ),
                  })
                }}
              >
                {picked.isOn ? '끈다 (다음 티켓부터)' : '켠다 (다음 티켓부터)'}
              </Button>
            </div>
          )}
        </div>
      )}
      {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}
    </Panel>
  )
}
