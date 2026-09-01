/**
 * 룸 격자 편집기 — 문자열이 아니라 칸을 칠한다.
 *
 * 룸은 `rows: ["####", "#..#", ...]` 로 저장된다. 그것을 텍스트로 고치면 **한 줄의 길이가
 * 어긋난 것을 눈으로 못 잡는다** — 12x9 격자에서 한 글자가 모자란 줄은 읽을 때가 아니라
 * 판이 설 때 드러난다.
 *
 * 칸을 눌러 다음 지형으로 넘긴다. 종류는 `legend` 가 정한다 — 화면이 목록을 따로 들면
 * 지형을 하나 늘릴 때 두 곳이 갈린다.
 *
 * **저장은 초안이다.** 여기서 게임이 바뀌지 않는다.
 */
import { useState } from 'react'

import { Button, Panel, ValueExpr } from '../ds'

export interface RoomGridProps {
  /** 룸 파일 전체. `templates`·`legend`·`legend_ko` 를 담고 있다. */
  readonly file: Record<string, unknown> | undefined
  readonly onSave: (text: string, note: string) => void
}

/**
 * 칸 하나를 다음 지형으로 넘긴 줄들을 만든다.
 *
 * **줄 길이를 바꾸지 않는다.** 문자를 갈아 끼우기만 하므로 격자가 어긋날 수 없다 —
 * 텍스트 편집이 못 지키던 것이 이것이다.
 *
 * @param rows 지금 줄들.
 * @param row 세로 자리.
 * @param col 가로 자리.
 * @param glyphs 순환할 지형 문자들.
 * @returns 새 줄들.
 */
export function applyPaint(
  rows: readonly string[],
  row: number,
  col: number,
  glyphs: readonly string[],
): readonly string[] {
  const line = rows[row]
  if (line === undefined || col < 0 || col >= line.length || glyphs.length === 0) {
    return rows
  }
  const at = glyphs.indexOf(line[col] ?? '')
  const next = glyphs[(at + 1) % glyphs.length] ?? line[col] ?? ''
  return rows.map((text, index) =>
    index === row ? text.slice(0, col) + next + text.slice(col + 1) : text,
  )
}

/**
 * 고친 방을 파일에 다시 넣는다. 그 방만 바꾸고 나머지는 원본 객체 그대로 둔다.
 *
 * @param file 룸 파일.
 * @param roomId 고친 방.
 * @param rows 새 줄들.
 * @returns 새 파일 절.
 */
export function buildRoomFile(
  file: Record<string, unknown>,
  roomId: string,
  rows: readonly string[],
): Record<string, unknown> {
  const templates = (file.templates ?? []) as Record<string, unknown>[]
  return {
    ...file,
    templates: templates.map((room) =>
      String(room.id) === roomId ? { ...room, rows: [...rows] } : room,
    ),
  }
}

/**
 * 룸 격자 편집기를 그린다.
 *
 * @param props 파일과 저장 콜백.
 * @returns 패널 요소.
 */
export function RoomGrid(props: RoomGridProps): React.JSX.Element {
  const [draft, setDraft] = useState<Record<string, unknown> | undefined>(undefined)
  const [openId, setOpenId] = useState('')
  const [note, setNote] = useState('')
  const file = draft ?? props.file
  const templates = (file?.templates ?? []) as Record<string, unknown>[]
  const legend = (file?.legend ?? {}) as Record<string, number>
  const names = (file?.legend_ko ?? {}) as Record<string, string>
  const glyphs = Object.keys(legend)
  const room = templates.find((item) => String(item.id) === openId)
  const rows = (room?.rows ?? []) as string[]

  return (
    <Panel title="룸" meta={`${String(templates.length)}개`} tone="panel" padded scroll>
      <div className="cat">
        <ValueExpr
          text="칸을 눌러 지형을 바꾼다 — 줄 길이가 안 바뀌므로 격자가 어긋날 수 없다"
          size="sm"
          dim
        />
        {/* **고르기 전에 있어야 한다.** 방을 연 뒤에 범례를 보면, 이미 무슨 뜻인지 모르는
            글자를 한 번 누른 뒤다. */}
        <ValueExpr
          text={glyphs.map((glyph) => `${glyph} ${names[glyph] ?? ''}`).join(' · ')}
          size="sm"
          dim
        />
        <div className="cat__tabs">
          {templates.map((item) => (
            <Button
              key={String(item.id)}
              size="sm"
              variant={String(item.id) === openId ? 'primary' : 'ghost'}
              onClick={() => {
                setOpenId(String(item.id))
              }}
            >
              {String(item.id)}
            </Button>
          ))}
        </div>

        {room === undefined ? null : (
          <>
            <ValueExpr text={String(room.purpose ?? '')} size="sm" />
            <div className="rmg">
              {rows.map((line, rowIndex) => (
                // 줄 자체가 열쇠다 — 같은 내용의 줄이 둘일 수 있어 자리를 함께 붙인다.
                <div className="rmg__row" key={`${String(rowIndex)}:${line}`}>
                  {[...line].map((glyph, colIndex) => (
                    <button
                      className="rmg__cell"
                      key={`${String(colIndex)}:${glyph}`}
                      type="button"
                      title={names[glyph] ?? glyph}
                      aria-label={`${String(rowIndex)},${String(colIndex)} ${names[glyph] ?? glyph}`}
                      onClick={() => {
                        if (file !== undefined) {
                          setDraft(
                            buildRoomFile(
                              file,
                              openId,
                              applyPaint(rows, rowIndex, colIndex, glyphs),
                            ),
                          )
                        }
                      }}
                    >
                      {glyph}
                    </button>
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
          </>
        )}
      </div>
    </Panel>
  )
}
