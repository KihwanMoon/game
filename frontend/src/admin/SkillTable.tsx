/**
 * 스킬 표 편집기.
 *
 * **고칠 수 있는 것과 없는 것을 가른다.** 계수·쿨·사거리·예고는 수치라 여기서 고치면
 * 되지만, `family`·`shape`·`target_faction` 은 **실행기가 읽는 구조**다 — 그것을 바꾸면
 * 코어 코드가 함께 바뀌어야 하고, 안 바뀌면 그 스킬이 조용히 아무 일도 안 한다.
 *
 * 그래서 구조 필드는 보여만 주고 잠근다. 잠근 이유를 화면에 적는 것이 이 편집기의 절반이다.
 *
 * **저장은 초안이다.** 여기서 게임이 바뀌지 않는다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'

export interface SkillTableProps {
  /** 스킬 파일 전체. `skills` 배열을 담고 있다. */
  readonly file: Record<string, unknown> | undefined
  readonly onSave: (text: string, note: string) => void
}

/** 여기서 고칠 수 있는 수치. 나머지는 실행기가 읽는 구조라 잠근다. */
export const EDITABLE_FIELDS: readonly string[] = ['coef_pct', 'cooldown', 'range', 'telegraph']

/** 잠근 필드. 바꾸면 코어 코드가 함께 바뀌어야 한다. */
export const LOCKED_FIELDS: readonly string[] = ['family', 'shape', 'target_faction']

const DECIMAL_RADIX = 10

/**
 * 고친 값을 파일에 다시 넣는다.
 *
 * **그 스킬만 바꾸고 나머지는 원본 객체 그대로 둔다.** 통째로 다시 쓰면 `_note` 처럼
 * 아무도 안 읽지만 사람이 적어 둔 것이 사라진다.
 *
 * @param file 스킬 파일.
 * @param skillId 고친 스킬.
 * @param field 고친 필드.
 * @param value 새 값. 빈 문자열은 null 로 넣는다 — `range` 가 null 이면 사거리를 엔티티가 정한다.
 * @returns 새 파일 절.
 */
export function buildSkillFile(
  file: Record<string, unknown>,
  skillId: string,
  field: string,
  value: string,
): Record<string, unknown> {
  const rows = (file.skills ?? []) as Record<string, unknown>[]
  const parsed = value.trim() === '' ? null : Number.parseInt(value, DECIMAL_RADIX)
  return {
    ...file,
    skills: rows.map((row) =>
      String(row.id) === skillId
        ? { ...row, [field]: Number.isNaN(parsed) ? row[field] : parsed }
        : row,
    ),
  }
}

/**
 * 스킬 표를 그린다.
 *
 * @param props 파일과 저장 콜백.
 * @returns 패널 요소.
 */
export function SkillTable(props: SkillTableProps): React.JSX.Element {
  const [draft, setDraft] = useState<Record<string, unknown> | undefined>(undefined)
  const [note, setNote] = useState('')
  const file = draft ?? props.file
  const rows = (file?.skills ?? []) as Record<string, unknown>[]

  return (
    <Panel title="스킬" meta={`${String(rows.length)}종`} tone="panel" padded scroll>
      <div className="cat">
        <GlyphState
          state="blocked"
          size="sm"
          label={`계열·형태·진영은 실행기가 읽는 구조라 못 고친다 (${LOCKED_FIELDS.join(' · ')})`}
        />
        <div className="skl">
          <div className="skl__head">
            <span>id</span>
            <span>계열</span>
            {EDITABLE_FIELDS.map((field) => (
              <span key={field}>{field}</span>
            ))}
          </div>
          {rows.map((row) => (
            <div className="skl__row" key={String(row.id)}>
              <span className="cat__name">{String(row.id)}</span>
              {/* 잠근 값은 흐리게 — 못 고친다는 것이 눈에 보여야 한다. */}
              <ValueExpr text={String(row.family ?? '')} size="sm" dim />
              {EDITABLE_FIELDS.map((field) => (
                <input
                  className="cat__input skl__cell"
                  key={field}
                  inputMode="numeric"
                  aria-label={`${String(row.id)} ${field}`}
                  value={row[field] === null || row[field] === undefined ? '' : String(row[field])}
                  onChange={(event) => {
                    if (file !== undefined) {
                      setDraft(buildSkillFile(file, String(row.id), field, event.target.value))
                    }
                  }}
                />
              ))}
            </div>
          ))}
        </div>

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
          disabled={draft === undefined}
          title="초안으로 저장한다 — 게임에는 아직 반영되지 않는다"
          onClick={() => {
            if (draft !== undefined) {
              props.onSave(JSON.stringify(draft, null, 2), note)
            }
          }}
        >
          초안 저장
        </Button>
      </div>
    </Panel>
  )
}
