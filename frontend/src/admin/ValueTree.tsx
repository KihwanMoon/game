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
  checkIsNote,
  checkMatches,
  formatItemLabel,
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
  /** 찾는 말. 소문자다. 안 걸리는 가지는 아예 안 그린다. */
  readonly needle: string
  /** 원래 키. 찾기가 보는 값이라 꾸민 이름과 따로 든다. */
  readonly rawKey: string
  /** 설명 가지인가. 기본으로 접힌다. */
  readonly isNote: boolean
}

/** 처음부터 펴 둘 깊이. 이보다 깊으면 접힌 채로 뜬다. */
const OPEN_DEPTH = 1

/**
 * 가지 하나를 그린다. 잎이면 입력 칸, 가지면 접히는 절이다.
 *
 * @param props 값·자리·이름·깊이·편집 콜백.
 * @returns 렌더 트리.
 */
function Branch(props: BranchProps): React.JSX.Element | null {
  // **찾을 때는 펴 둔다.** 걸린 가지가 접혀 있으면 찾은 것이 안 보이고, 그러면 찾기가
  // 「몇 개 걸렸는지만 알려주는 기능」이 된다.
  const [isOpen, setOpen] = useState(props.depth <= OPEN_DEPTH && !props.isNote)
  const kind = readLeafKind(props.value)
  if (!checkMatches(props.rawKey, props.value, props.needle)) {
    return null
  }

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
              // **목록 항목은 번호가 아니라 이름으로 부른다.** 절 안에 이미 이름이
              // 들어 있는데 화면이 그것을 안 읽어서 적 열넷이 `0 1 2 …` 로 서 있었다.
              label={Array.isArray(props.value) ? formatItemLabel(Number(key), item) : formatKeyLabel(key)}
              depth={props.depth + 1}
              onEdit={props.onEdit}
              needle={props.needle}
              rawKey={key}
              isNote={checkIsNote(key)}
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
  const [needle, setNeedle] = useState('')
  const file = draft ?? props.file
  const search = needle.trim().toLowerCase()
  const entries = Object.entries(file ?? {})
  const shown = entries.filter(([key, value]) => checkMatches(key, value, search)).length

  return (
    <Panel title={props.title} tone="panel" padded scroll>
      <div className="cat">
        <GlyphState
          state="blocked"
          size="sm"
          label="값만 바꾼다 — 키를 더하거나 지우려면 원문 편집기를 쓴다"
        />
        {/* **찾기가 없으면 눈으로 훑는 수밖에 없다.** 이 파일 하나에 값이 300개 가까이
            있어서, 고치려는 그 하나를 찾는 데 화면을 위아래로 몇 번씩 굴리게 된다. */}
        <label className="vtr__find">
          <span className="vtr__key">찾기</span>
          <input
            className="cat__input vtr__input"
            aria-label="키 이름으로 찾기"
            placeholder="키 이름 — 예: hp_max, goblin, floor"
            value={needle}
            onChange={(event) => {
              setNeedle(event.target.value)
            }}
          />
          {search === '' ? null : (
            <ValueExpr text={`${String(shown)} / ${String(entries.length)} 절`} size="sm" dim />
          )}
        </label>
        {file === undefined ? (
          <ValueExpr text="아직 안 읽었다" size="sm" dim />
        ) : (
          <div className="vtr">
            {entries.map(([key, value]) => (
              <Branch
                key={key}
                value={value}
                path={[key]}
                label={formatKeyLabel(key)}
                depth={0}
                onEdit={(path, next) => {
                  setDraft(applyValueAt(file, path, next) as Record<string, unknown>)
                }}
                needle={search}
                rawKey={key}
                isNote={checkIsNote(key)}
              />
            ))}
            {search !== '' && shown === 0 ? (
              <ValueExpr text={`「${needle}」 를 품은 절이 없다`} size="sm" dim />
            ) : null}
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
