/**
 * 스킬 표 편집기.
 *
 * **잠그는 대신 고를 수 있는 것을 줄였다** (2026-09-19). 예전에는 계수·쿨·사거리·예고
 * 넷만 열고 `family`·`shape`·`target_faction` 을 잠갔다. 사유는 「실행기가 읽는 구조라
 * 바꾸면 그 스킬이 조용히 아무 일도 안 한다」였고, **자유 입력이면 그 말이 맞다.**
 *
 * 그런데 **고르개는 없는 값을 못 고른다.** 항목을 구현된 것만 담으면 같은 사고를
 * 막으면서 화면이 쓸 만해진다 — 그래서 잠금을 풀고 `skillFields` 가 항목을 든다.
 * 왜 이 항목뿐인지도 칸마다 적어 두고 화면이 그대로 보여 준다.
 *
 * **머리줄과 값줄은 규격 하나에서 나온다.** 둘은 서로 다른 격자라(머리줄은 `.skl` 의
 * 자식, 값줄은 목록 틀이 그리는 `<li>`), 칸 수가 어긋나면 어떤 폭을 줘도 라벨과 값이
 * 안 맞는다. `SKILL_FIELDS` 하나가 양쪽을 그린다.
 *
 * **찾기는 켜고 페이지는 안 켠다.** 고치는 표에서 줄이 「더 보기」 뒤로 숨으면 무엇을
 * 고쳤는지 놓친다.
 *
 * **저장은 초안이다.** 여기서 게임이 바뀌지 않는다 — 발행이 사람 손을 타는 것이 설계다.
 */
import { useState } from 'react'

import {
  SKILL_COLUMNS,
  SKILL_FIELDS,
  buildSkillFile,
  readFieldText,
  type SkillField,
} from './skillFields'
import { DataList } from '../editor/DataList'
import { EditField } from '../editor/EditParts'
import { Button, Panel, ValueExpr } from '../ds'

export interface SkillTableProps {
  /** 스킬 파일 전체. `skills` 배열을 담고 있다. */
  readonly file: Record<string, unknown> | undefined
  readonly onSave: (text: string, note: string) => void
}

export { SKILL_COLUMNS, SKILL_FIELDS, buildSkillFile }

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

/** 칸 하나를 그리는 데 드는 것. */
interface CellProps {
  readonly row: Record<string, unknown>
  readonly field: SkillField
  readonly onEdit: (field: SkillField, text: string) => void
}

/**
 * 칸 하나를 그 종류대로 그린다.
 *
 * @param props 줄·규격·변경 콜백.
 * @returns 렌더 트리.
 */
function SkillCell(props: CellProps): React.JSX.Element {
  const { row, field } = props
  const text = readFieldText(row, field)
  const id = String(row.id)
  const label = `${id} ${field.label}`

  if (field.kind === 'select') {
    return (
      <EditField
        label={label}
        value={text}
        options={[...(field.options ?? [])]}
        onChange={(value) => {
          props.onEdit(field, value)
        }}
      />
    )
  }
  if (field.kind === 'toggle') {
    return (
      <label className="skl__toggle">
        <input
          type="checkbox"
          aria-label={label}
          checked={text === 'true'}
          onChange={(event) => {
            props.onEdit(field, event.target.checked ? 'true' : 'false')
          }}
        />
        <span aria-hidden="true">{text === 'true' ? '✕ 끊김' : '· 버팀'}</span>
      </label>
    )
  }
  return (
    <input
      className="cat__input skl__cell"
      aria-label={label}
      inputMode={field.kind === 'number' ? 'numeric' : undefined}
      value={text}
      onChange={(event) => {
        props.onEdit(field, event.target.value)
      }}
    />
  )
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
        {/* **왜 이 항목뿐인지를 표 위에 적는다.** 고르개만 두면 「왜 다른 값은 없나」에
            답이 없고, 그 답이 곧 잠금을 푼 근거다. */}
        <dl className="skl__why">
          {SKILL_FIELDS.filter((one) => one.why !== undefined).map((one) => (
            <div key={one.path}>
              <dt>{one.label}</dt>
              <dd>{one.why}</dd>
            </div>
          ))}
        </dl>
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
            <DataList
              items={rows}
              rowKey={(row) => String(row.id)}
              listClass="skl__rows"
              rowClass="skl__row"
              emptyText="고칠 재주가 없다"
              filterText={skillSearchText}
              filterLabel="이름·id 로 찾기"
              renderRow={(row) => (
                <>
                  <span className="cat__name">{String(row.id)}</span>
                  {SKILL_FIELDS.map((field) => (
                    <SkillCell
                      key={field.path}
                      row={row}
                      field={field}
                      onEdit={(one, text) => {
                        if (file !== undefined) {
                          setDraft(buildSkillFile(file, String(row.id), one, text))
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
