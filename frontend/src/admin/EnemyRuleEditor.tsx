/**
 * 적 규칙표 편집기 — 기존 규칙 편집기를 그대로 쓴다.
 *
 * **적 규칙표는 플레이어 규칙표와 같은 형식이다** (`rules` 안에 priority·cpu_cost·
 * action·target·set_flag·conditions). 그래서 JSON 텍스트 대신 **이미 만들어 검증된 화면**
 * 으로 몬스터 AI 를 고칠 수 있다.
 *
 * 새 편집기를 만들지 않은 것이 이 파일의 전부다. 만들었다면 규칙 표기가 둘이 되고,
 * 도감이 보여주는 적 규칙표와 관리자가 고치는 화면이 서로 다른 문법으로 적혔을 것이다.
 *
 * **저장은 초안이다.** 여기서 게임이 바뀌지 않는다 — 발행이 그 일을 한다.
 */
import { useState } from 'react'

import { readActivePack } from '../content/pack'
import { Button, Panel, ValueExpr } from '../ds'
import { RuleEditor } from '../editor'
import { buildRuleSetPayload, parseRuleSetPayload } from '../storage'
import type { RuleSet } from '../core/schemas'

export interface EnemyRuleEditorProps {
  /** 적 규칙표 파일 전체. `rulesets` 배열을 담고 있다. */
  readonly file: Record<string, unknown> | undefined
  readonly onSave: (text: string, note: string) => void
}

/** 적 규칙표에 주는 예산. 몬스터는 규칙 3줄·CPU 4 가 기본이다 (balance.json). */
const ENEMY_CPU = 4
const ENEMY_SLOTS = 3

/**
 * 파일에서 규칙표 하나를 꺼낸다.
 *
 * @param file 적 규칙표 파일.
 * @param rulesetId 꺼낼 id.
 * @returns 규칙표. 못 읽으면 undefined.
 */
export function findEnemyRuleSet(
  file: Record<string, unknown> | undefined,
  rulesetId: string,
): RuleSet | undefined {
  const rows = (file?.rulesets ?? []) as Record<string, unknown>[]
  const found = rows.find((row) => String(row.ruleset_id) === rulesetId)
  if (found === undefined) {
    return undefined
  }
  try {
    return parseRuleSetPayload(found)
  } catch {
    return undefined
  }
}

/**
 * 고친 규칙표를 파일에 다시 넣는다.
 *
 * **다른 규칙표는 손대지 않는다.** 파일을 통째로 다시 쓰면 내가 안 연 규칙표의 주석·
 * 필드가 사라지고, 그것은 편집이 아니라 소실이다.
 *
 * @param file 적 규칙표 파일.
 * @param ruleset 고친 규칙표.
 * @returns 새 파일 절.
 */
export function buildEnemyFile(
  file: Record<string, unknown>,
  ruleset: RuleSet,
): Record<string, unknown> {
  const rows = (file.rulesets ?? []) as Record<string, unknown>[]
  const payload = buildRuleSetPayload(ruleset)
  return {
    ...file,
    rulesets: rows.map((row) =>
      String(row.ruleset_id) === ruleset.rulesetId ? { ...row, ...payload } : row,
    ),
  }
}

/**
 * 적 규칙표 편집 화면을 그린다.
 *
 * @param props 파일과 저장 콜백.
 * @returns 패널 요소.
 */
export function EnemyRuleEditor(props: EnemyRuleEditorProps): React.JSX.Element {
  const [openId, setOpenId] = useState('')
  const [draft, setDraft] = useState<RuleSet | undefined>(undefined)
  const [note, setNote] = useState('')
  const file = props.file
  const ids = ((file?.rulesets ?? []) as Record<string, unknown>[]).map((row) =>
    String(row.ruleset_id),
  )

  return (
    <Panel title="적 규칙표" meta={`${String(ids.length)}벌`} tone="panel" padded scroll>
      <div className="cat">
        <ValueExpr
          text="플레이어 규칙표와 같은 형식이라 같은 편집기를 쓴다 — 본 것을 그대로 고칠 수 있다"
          size="sm"
          dim
        />
        <div className="cat__tabs">
          {ids.map((id) => (
            <Button
              key={id}
              size="sm"
              variant={id === openId ? 'primary' : 'ghost'}
              onClick={() => {
                setOpenId(id)
                setDraft(findEnemyRuleSet(file, id))
              }}
            >
              {id}
            </Button>
          ))}
        </div>

        {draft === undefined || file === undefined ? null : (
          <>
            <RuleEditor
              ruleset={draft}
              catalog={readActivePack().catalog}
              cpuBudget={ENEMY_CPU}
              ruleSlots={ENEMY_SLOTS}
              onChange={setDraft}
            />
            <label className="cat__field">
              <span>사유</span>
              <input
                className="cat__input"
                value={note}
                placeholder="무엇을 왜 고치는가 (4자 이상)"
                onChange={(event) => {
                  setNote(event.target.value)
                }}
              />
            </label>
            <Button
              size="sm"
              variant="primary"
              title="초안으로 저장한다 — 게임에는 아직 반영되지 않는다"
              onClick={() => {
                props.onSave(JSON.stringify(buildEnemyFile(file, draft), null, 2), note)
              }}
            >
              초안 저장
            </Button>
          </>
        )}
      </div>
    </Panel>
  )
}
