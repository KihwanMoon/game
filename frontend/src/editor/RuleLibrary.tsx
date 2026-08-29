/**
 * 코드 라이브러리 — 이름 붙인 규칙표 8슬롯과 공유 코드 (GDD §2.3, §10).
 *
 * 슬롯이 8개인 것은 메타 세이브의 계약이다(`game/schemas/meta_save.py`). 무한히 늘리지
 * 않는 이유는 저장 용량이 아니라 **고르는 일**이다 — 이름 붙인 규칙표가 수십 개가 되면
 * 라이브러리는 자기가 뭘 만들었는지 찾는 곳이 된다.
 *
 * 공유 코드는 한 칸에서 나가고 들어온다. 내보내기는 그 칸을 채우고 클립보드에도 넣으며,
 * 불러오기는 그 칸의 글자를 읽는다. 붙여넣기 전용 대화상자를 따로 두지 않은 것은 코드가
 * **눈에 보여야** 하기 때문이다 — 남에게 줄 코드를 확인 없이 보내게 되면 잘린 코드가
 * 그대로 나간다.
 *
 * 조작은 전부 키보드로 닿는다. 이름 칸에서 Enter 가 저장이고, 나머지는 네이티브 버튼이다.
 */
import { useState } from 'react'

import { Button, GlyphState, Panel, ValueExpr } from '../ds'
import { MAX_PRESET_SLOTS, type RulePreset } from '../storage'
import { writeClipboard } from './clipboard'

/** RuleLibrary 의 props. */
export interface RuleLibraryProps {
  readonly presets: readonly RulePreset[]
  /** 지금 규칙표를 이 이름으로 슬롯에 넣는다. */
  readonly onSave: (name: string) => void
  /** 슬롯의 규칙표를 편집기로 싣는다. */
  readonly onLoad: (index: number) => void
  readonly onRemove: (index: number) => void
  /** 공유 코드를 읽어 들인다. 실패 사유를 돌려주고, 성공이면 빈 문자열이다. */
  readonly onImport: (code: string) => string
  /** 지금 규칙표를 공유 코드로 굽는다. */
  readonly onExport: (name: string) => string
  /** 슬롯 하나를 공유 코드로 굽는다. */
  readonly onExportSlot: (index: number) => string
}

/** 알림 한 줄. 색만으로 적지 않으므로 글리프 상태를 함께 든다. */
interface Notice {
  readonly kind: 'true' | 'danger'
  readonly text: string
}

/** 이름을 비운 채 내보낼 때 코드에 실리는 이름. */
const UNNAMED = '이름 없는 규칙표'

/**
 * 코드 라이브러리를 그린다.
 *
 * @param props 슬롯 목록과 콜백들.
 * @returns 렌더 트리.
 */
export function RuleLibrary(props: RuleLibraryProps): React.JSX.Element {
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [notice, setNotice] = useState<Notice | undefined>(undefined)

  const trimmed = name.trim()
  const existing = props.presets.some((preset) => preset.name === trimmed)
  const full = props.presets.length >= MAX_PRESET_SLOTS && !existing
  const blocked = trimmed === '' ? '이름을 적어야 슬롯에 넣는다' : full ? '슬롯 8개가 다 찼다' : ''

  /**
   * 지금 규칙표를 슬롯에 넣는다.
   */
  function handleSave(): void {
    if (blocked !== '') {
      setNotice({ kind: 'danger', text: blocked })
      return
    }
    props.onSave(trimmed)
    setNotice({ kind: 'true', text: `${trimmed} 슬롯에 저장했다` })
  }

  /**
   * 코드를 칸에 채우고 클립보드에도 넣는다.
   *
   * @param text 공유 코드.
   */
  function handleCode(text: string): void {
    setCode(text)
    writeClipboard(text)
    setNotice({ kind: 'true', text: '공유 코드를 칸과 클립보드에 넣었다' })
  }

  /**
   * 칸의 코드를 읽어 들인다.
   */
  function handleImport(): void {
    const problem = props.onImport(code)
    setNotice(
      problem === ''
        ? { kind: 'true', text: '코드를 읽어 편집기에 실었다' }
        : { kind: 'danger', text: problem },
    )
  }

  return (
    <Panel
      title="코드 라이브러리"
      meta={`${String(props.presets.length)} / ${String(MAX_PRESET_SLOTS)}`}
      padded={false}
      scroll
    >
      <div className="library">
        <div className="library__row">
          <label className="library__label" htmlFor="library-name">
            이름
          </label>
          <input
            id="library-name"
            className="library__field"
            value={name}
            placeholder="근접 압박"
            onChange={(event) => {
              setName(event.target.value)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                handleSave()
              }
            }}
          />
          <Button
            size="sm"
            variant="secondary"
            glyph="⌸"
            title={blocked === '' ? '지금 규칙표를 이 이름으로 저장한다' : blocked}
            onClick={handleSave}
          >
            {existing ? '덮어쓰기' : '저장'}
          </Button>
        </div>

        {props.presets.length === 0 ? (
          <p className="library__hint">
            저장한 규칙표가 없다. 이름을 적고 저장하면 새로고침해도 남는다.
          </p>
        ) : (
          <ul className="library__slots">
            {props.presets.map((preset, at) => (
              <li className="library__slot" key={preset.name}>
                <span className="library__name" title={preset.ruleset.rulesetId}>
                  {preset.name}
                </span>
                <ValueExpr text={`규칙 ${String(preset.ruleset.rules.length)}`} size="sm" dim />
                <Button
                  size="sm"
                  variant="ghost"
                  glyph="↥"
                  title="이 규칙표를 편집기로 싣는다"
                  onClick={() => {
                    props.onLoad(at)
                    setNotice({ kind: 'true', text: `${preset.name} 을 편집기에 실었다` })
                  }}
                >
                  불러오기
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  glyph="⧉"
                  title="이 슬롯의 공유 코드를 만든다"
                  onClick={() => {
                    handleCode(props.onExportSlot(at))
                  }}
                >
                  코드
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  glyph="✕"
                  title="이 슬롯을 지운다"
                  onClick={() => {
                    props.onRemove(at)
                    setNotice({ kind: 'true', text: `${preset.name} 슬롯을 지웠다` })
                  }}
                >
                  삭제
                </Button>
              </li>
            ))}
          </ul>
        )}

        <div className="library__share">
          <label className="library__label" htmlFor="library-code">
            공유 코드
          </label>
          <textarea
            id="library-code"
            className="library__code"
            spellCheck={false}
            value={code}
            placeholder="v2:..."
            onChange={(event) => {
              setCode(event.target.value)
            }}
          />
          <div className="library__row">
            <Button
              size="sm"
              variant="ghost"
              glyph="⇧"
              title="지금 규칙표를 코드로 굽는다"
              onClick={() => {
                handleCode(props.onExport(trimmed === '' ? UNNAMED : trimmed))
              }}
            >
              내보내기
            </Button>
            <Button
              size="sm"
              variant="ghost"
              glyph="⇩"
              disabled={code.trim() === ''}
              title="칸의 코드를 읽어 편집기에 싣는다"
              onClick={handleImport}
            >
              읽어 오기
            </Button>
          </div>
        </div>

        {notice === undefined ? null : (
          <GlyphState state={notice.kind} size="sm" label={notice.text} />
        )}
      </div>
    </Panel>
  )
}
