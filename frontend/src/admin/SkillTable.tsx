/**
 * 스킬 표 편집기.
 *
 * **고칠 수 있는 것과 없는 것을 가른다.** 계수·쿨·사거리·예고는 수치라 여기서 고치면
 * 되지만, `family`·`shape`·`target_faction` 은 **실행기가 읽는 구조**다 — 그것을 바꾸면
 * 코어 코드가 함께 바뀌어야 하고, 안 바뀌면 그 스킬이 조용히 아무 일도 안 한다.
 *
 * 그래서 구조 필드는 보여만 주고 잠근다. 잠근 이유를 화면에 적는 것이 이 편집기의 절반이다.
 *
 * **머리줄과 값줄은 칸 수가 같아야 한다** (2026-09-18). 둘은 서로 다른 격자다 — 머리줄은
 * `.skl` 의 자식이고 값줄은 목록 틀이 그리는 `<li>` 라, 칸 수가 어긋나면 어떤 폭을 줘도
 * 라벨과 값이 안 맞는다. 그래서 머리줄을 `SKILL_COLUMNS` 하나에서 그린다.
 *
 * **찾기는 켜고 페이지는 안 켠다** (2026-09-18). 열네 줄이라 고칠 재주 하나를 눈으로
 * 훑고 있었지만, 고치는 표에서 줄이 「더 보기」 뒤로 숨으면 무엇을 고쳤는지 놓친다.
 *
 * **저장은 초안이다.** 여기서 게임이 바뀌지 않는다.
 */
import { useState } from 'react'

import { DataList } from '../editor/DataList'
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

/**
 * 머리줄 칸. **값줄과 같은 수여야 한다** — 앞의 둘이 id·계열이고 뒤가 고칠 수 있는 수치다.
 *
 * 손으로 두 번 적지 않는 이유가 그것이다. 고칠 수치를 하나 늘리면 값줄에는 입력칸이
 * 하나 더 서는데 머리줄을 따로 적어 두면 거기만 안 따라오고, 그 뒤로는 모든 값이 한 칸씩
 * 밀린 채로 읽힌다.
 */
export const SKILL_COLUMNS: readonly string[] = ['id', '계열', ...EDITABLE_FIELDS]

const DECIMAL_RADIX = 10

/**
 * 재주 하나를 찾기 칸이 보는 한 줄로 적는다.
 *
 * **이름과 id 를 함께 넣는다.** 줄에 적히는 것은 id 지만 사람이 재주를 떠올리는 말은
 * 「불 굿」이고, id 로만 거르면 그 사람이 `HEX_FIRE` 를 먼저 떠올려야 한다.
 *
 * @param skill 재주 한 줄.
 * @returns 거르기가 볼 글자.
 */
export function skillSearchText(skill: Record<string, unknown>): string {
  return `${String(skill.id ?? '')} ${String(skill.label_ko ?? '')}`
}

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
    <Panel title="재주" meta={`${String(rows.length)}종`} tone="panel" padded scroll>
      <div className="cat">
        <GlyphState
          state="blocked"
          size="sm"
          label={`계열·형태·진영은 실행기가 읽는 구조라 못 고친다 (${LOCKED_FIELDS.join(' · ')})`}
        />
        <div className="skl">
          <div className="skl__head">
            {SKILL_COLUMNS.map((column) => (
              <span key={column}>{column}</span>
            ))}
          </div>
          {/* **「아직 안 왔다」를 목록 안에서 적지 않는다.** 틀은 빈 목록 문구 하나만
              받으므로 파일을 못 읽은 것까지 그리로 넘기면 불러오는 중에 「고칠 재주가
              없다」가 뜬다 — 가진 것이 없다는 말과 아직 못 읽었다는 말은 다른 사실이다. */}
          {file === undefined ? (
            <ValueExpr text="재주 파일을 불러오는 중이다" size="sm" dim />
          ) : (
            /* **페이지는 안 켠다.** 고치는 표에서 줄이 「더 보기」 뒤로 숨으면 무엇을
               고쳤는지 놓친다. 찾기는 켠다 — 거르기는 줄을 가리기만 하고 고친 값은
               초안에 그대로 남는다. */
            <DataList
              items={rows}
              rowKey={(row) => String(row.id)}
              // **틀은 `display` 를 안 정한다.** 값줄이 머리줄과 같은 격자를 써야 하는 것은
              // 이 화면의 배치이므로 여기서 이름만 준다.
              listClass="skl__rows"
              rowClass="skl__row"
              emptyText="고칠 재주가 없다"
              filterText={skillSearchText}
              filterLabel="이름·id 로 찾기"
              renderRow={(row) => (
                <>
                  <span className="cat__name">{String(row.id)}</span>
                  {/* 잠근 값은 흐리게 — 못 고친다는 것이 눈에 보여야 한다. */}
                  <ValueExpr text={String(row.family ?? '')} size="sm" dim />
                  {EDITABLE_FIELDS.map((field) => (
                    <input
                      className="cat__input skl__cell"
                      key={field}
                      inputMode="numeric"
                      aria-label={`${String(row.id)} ${field}`}
                      value={
                        row[field] === null || row[field] === undefined ? '' : String(row[field])
                      }
                      onChange={(event) => {
                        if (file !== undefined) {
                          setDraft(buildSkillFile(file, String(row.id), field, event.target.value))
                        }
                      }}
                    />
                  ))}
                </>
              )}
            />
          )}
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
