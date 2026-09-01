/**
 * 값 트리 편집기 — 절의 모양은 두고 값만 바꾼다.
 *
 * 밸런스 수치와 몬스터 스탯이 여기서 고쳐진다. **키를 더하거나 지울 수 없다** —
 * 스키마는 그것을 읽는 코드가 정하고, 화면이 정하면 로더가 못 읽는 절이 만들어진다.
 * 그 사실을 화면이 먼저 말한다.
 *
 * 깊이가 깊은 절(블록 카탈로그)은 가지를 접어 둔다. 다 펴 놓으면 스크롤 싸움이 되고,
 * 그러면 아무도 여기서 안 고친다.
 */
import { useState } from 'react'

import {
  applyValueAt,
  formatKeyLabel,
  parseLeafText,
  readLeafKind,
  type ValuePath,
} from './valueTree'
import { Button, GlyphState, Panel, ValueExpr } from '../ds'

export interface ValueTreeProps {
  readonly file: Record<string, unknown> | undefined
  readonly title: string
  readonly onSave: (text: string, note: string) => void
}

interface BranchProps {
  readonly value: unknown
  readonly path: ValuePath
  readonly label: string
  readonly depth: number
  readonly onEdit: (path: ValuePath, next: unknown) => void
}

/** 처음부터 펴 둘 깊이. 이보다 깊으면 접힌 채로 뜬다. */
const OPEN_DEPTH = 1

/**
 * 가지 하나를 그린다. 잎이면 입력 칸, 가지면 접히는 절이다.
 *
 * @param props 값·자리·이름·깊이·편집 콜백.
 * @returns 렌더 트리.
 */
function Branch(props: BranchProps): React.JSX.Element {
  const [isOpen, setOpen] = useState(props.depth <= OPEN_DEPTH)
  const kind = readLeafKind(props.value)

  if (kind !== undefined) {
    return (
      <label className="vtr__leaf">
        <span className="vtr__key">{props.label}</span>
        {kind === 'boolean' ? (
          <Button
            size="sm"
            variant={props.value === true ? 'primary' : 'ghost'}
            onClick={() => {
              props.onEdit(props.path, props.value !== true)
            }}
          >
            {props.value === true ? '참' : '거짓'}
          </Button>
        ) : (
          <input
            className="cat__input vtr__input"
            inputMode={kind === 'number' ? 'numeric' : 'text'}
            aria-label={props.path.join('.')}
            value={props.value === null ? '' : String(props.value)}
            placeholder={kind === 'null' ? '비어 있음' : ''}
            onChange={(event) => {
              props.onEdit(props.path, parseLeafText(kind, event.target.value, props.value))
            }}
          />
        )}
      </label>
    )
  }

  const entries: [string, unknown][] = Array.isArray(props.value)
    ? props.value.map((item, index) => [String(index), item])
    : Object.entries((props.value ?? {}) as Record<string, unknown>)

  return (
    <div className="vtr__branch">
      <button
        className="vtr__toggle"
        type="button"
        onClick={() => {
          setOpen(!isOpen)
        }}
      >
        <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
        {props.label}
        <span className="vtr__count">{entries.length}</span>
      </button>
      {isOpen ? (
        <div className="vtr__children">
          {entries.map(([key, item]) => (
            <Branch
              key={key}
              value={item}
              path={[...props.path, Array.isArray(props.value) ? Number(key) : key]}
              label={formatKeyLabel(key)}
              depth={props.depth + 1}
              onEdit={props.onEdit}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

/**
 * 값 트리 편집기를 그린다.
 *
 * @param props 파일·제목·저장 콜백.
 * @returns 패널 요소.
 */
export function ValueTree(props: ValueTreeProps): React.JSX.Element {
  const [draft, setDraft] = useState<Record<string, unknown> | undefined>(undefined)
  const [note, setNote] = useState('')
  const file = draft ?? props.file

  return (
    <Panel title={props.title} tone="panel" padded scroll>
      <div className="cat">
        <GlyphState
          state="blocked"
          size="sm"
          label="값만 바꾼다 — 키를 더하거나 지우려면 원문 편집기를 쓴다"
        />
        {file === undefined ? (
          <ValueExpr text="아직 안 읽었다" size="sm" dim />
        ) : (
          <div className="vtr">
            {Object.entries(file).map(([key, value]) => (
              <Branch
                key={key}
                value={value}
                path={[key]}
                label={formatKeyLabel(key)}
                depth={0}
                onEdit={(path, next) => {
                  setDraft(applyValueAt(file, path, next) as Record<string, unknown>)
                }}
              />
            ))}
          </div>
        )}
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
