/**
 * 값 트리 편집기 — 절의 모양은 두고 값만 바꾼다.
 *
 * 밸런스 수치와 몬스터 스탯이 여기서 고쳐진다. **키를 더하거나 지울 수 없다** —
 * 스키마는 그것을 읽는 코드가 정하고, 화면이 정하면 로더가 못 읽는 절이 만들어진다.
 * 그 사실을 화면이 먼저 말한다.
 *
 * 깊이가 깊은 절(블록 카탈로그)은 가지를 접어 둔다. 다 펴 놓으면 스크롤 싸움이 되고,
 * 그러면 아무도 여기서 안 고친다.
 *
 * **여기는 목록이 아니라 편집기다.** 공용 목록 틀(`DataList`)로 옮기지 않는다 — 사람이
 * 값을 고치는 자리라 「더 보기」가 끼면 고치던 줄이 화면에서 사라진다.
 */
import { Fragment, useState } from 'react'

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
  /**
   * 첫 질의. **DOM 없이 도는 검사가 거른 결과를 볼 수 있는 유일한 문이다** —
   * `DataList.defaultQuery` 와 같은 뜻이며, 화면은 안 준다.
   */
  readonly defaultQuery?: string
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

/** 이 글자 **뒤에서** 줄을 끊어도 된다. 키는 낱말을 밑줄로 잇는다. */
const BREAK_AFTER = '_'

/**
 * 긴 이름을 끊어도 되는 자리에서 자른다.
 *
 * **`cpu_cost_by_term_count` 는 브라우저에게 한 낱말이다.** 끊을 자리가 없으면 폰에서
 * 그 한 줄이 화면 밖으로 나가고, 그 줄만이 아니라 절 전체가 옆으로 밀린다. 밑줄 뒤가
 * 사람이 읽을 때도 끊기는 자리라 거기에 끊을 자리를 심는다.
 *
 * @param text 자를 이름.
 * @returns 조각들. 끊을 자리가 없으면 통째로 한 조각.
 */
export function splitKeyParts(text: string): readonly string[] {
  const parts: string[] = []
  let from = 0
  for (let at = 0; at < text.length; at += 1) {
    // 마지막 글자가 밑줄이면 끊어 봐야 빈 조각이 남는다.
    if (text.charAt(at) === BREAK_AFTER && at + 1 < text.length) {
      parts.push(text.slice(from, at + 1))
      from = at + 1
    }
  }
  parts.push(text.slice(from))
  return parts
}

/**
 * 이 가지가 처음에 펴져 있는가.
 *
 * **찾을 때는 펴 둔다.** 걸린 가지가 접혀 있으면 찾은 것이 안 보이고, 그러면 찾기가
 * 「몇 개 걸렸는지만 알려주는 기능」이 된다.
 *
 * @param depth 가지의 깊이.
 * @param isNote 설명 가지인가.
 * @param needle 찾는 말.
 * @returns 펴 두면 참.
 */
export function checkOpenByDefault(depth: number, isNote: boolean, needle: string): boolean {
  return needle !== '' || (depth <= OPEN_DEPTH && !isNote)
}

/**
 * 이 가지가 아래로 물려줄 찾는 말.
 *
 * **이름이 걸린 가지는 통째로 보인다.** `enemies` 로 찾았을 때 그 말을 그대로 물려주면
 * 자식 키(`0`·`1`…)는 아무것도 안 걸려서 **가지 이름만 서고 속은 텅 빈다** — 찾아 놓고
 * 못 고치는 화면이 된다. 이름이 이미 걸렸으면 거를 이유가 없으니 거르기를 끈다.
 *
 * 목록 항목은 이름이 `3 · bomb_slime · 폭탄 슬라임` 이라, 몬스터 이름으로 찾으면 그
 * 한 마리의 스탯이 전부 선다. 반대로 `hp_max` 로 찾으면 어느 이름에도 안 걸리므로
 * 열넷의 `hp_max` 만 나란히 선다 — 둘 다 실제로 하는 편집이다.
 *
 * @param label 이 가지의 이름.
 * @param needle 찾는 말. 소문자로 온다.
 * @returns 자식에게 줄 말. 이미 걸렸으면 빈 말.
 */
export function readChildNeedle(label: string, needle: string): string {
  return label.toLowerCase().includes(needle) ? '' : needle
}

/**
 * 이름을 끊을 자리와 함께 그린다.
 *
 * @param props 적을 이름.
 * @returns 렌더 트리. 글자는 그대로고 끊을 자리만 심는다.
 */
function KeyText(props: { readonly text: string }): React.JSX.Element {
  return (
    <>
      {splitKeyParts(props.text).map((part, at) => (
        <Fragment key={`${String(at)}:${part}`}>
          {at === 0 ? null : <wbr />}
          {part}
        </Fragment>
      ))}
    </>
  )
}

/**
 * 가지 하나를 그린다. 잎이면 입력 칸, 가지면 접히는 절이다.
 *
 * @param props 값·자리·이름·깊이·편집 콜백.
 * @returns 렌더 트리.
 */
function Branch(props: BranchProps): React.JSX.Element | null {
  // 손으로 접거나 편 것. **어느 말로 찾던 중이었는지와 함께 든다** — 찾는 말이 바뀌면
  // 그 전에 접어 둔 것이 새 결과를 덮는다.
  const [toggled, setToggled] = useState<{ needle: string; isOpen: boolean } | undefined>(undefined)
  const kind = readLeafKind(props.value)
  if (!checkMatches(props.rawKey, props.value, props.needle)) {
    return null
  }

  if (kind !== undefined) {
    return (
      <label className="vtr__leaf">
        <span className="vtr__key">
          <KeyText text={props.label} />
        </span>
        {/* 값은 제 칸에 든다. 이름이 길어 줄이 접힐 때 **이름과 값이 따로 접히면**
            라벨과 값이 어긋나 읽힌다 — 칸을 나눠 두면 폭은 CSS 가 정할 수 있다. */}
        <span className="vtr__val">
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
        </span>
      </label>
    )
  }

  const entries: [string, unknown][] = Array.isArray(props.value)
    ? props.value.map((item, index) => [String(index), item])
    : Object.entries((props.value ?? {}) as Record<string, unknown>)
  const isOpen =
    toggled?.needle === props.needle
      ? toggled.isOpen
      : checkOpenByDefault(props.depth, props.isNote, props.needle)
  const childNeedle = readChildNeedle(props.label, props.needle)

  return (
    <div className="vtr__branch">
      <button
        className="vtr__toggle"
        type="button"
        aria-expanded={isOpen}
        onClick={() => {
          setToggled({ needle: props.needle, isOpen: !isOpen })
        }}
      >
        <span aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
        {/* 이름을 제 칸에 둔다. 글자만 두면 폭을 줄일 손잡이가 없어서, 긴 이름이
            개수 뱃지를 화면 밖으로 밀어낸다. */}
        <span className="vtr__name">
          <KeyText text={props.label} />
        </span>
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
              needle={childNeedle}
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
  const [needle, setNeedle] = useState(props.defaultQuery ?? '')
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
