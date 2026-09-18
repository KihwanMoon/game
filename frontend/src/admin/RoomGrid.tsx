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
 * **방 고르기는 공용 목록 틀(`DataList`)이 진다** (2026-09-18). 마흔 곳을 손으로 짠 탭
 * 줄에 한꺼번에 세우고 있었고, 폰에서는 그 줄 하나가 화면을 덮었다 — 찾는 방법은 브라우저
 * 찾기뿐이었다. 틀이 지는 것은 바깥 넷(거르기·페이지·빈 문구·컨테이너)이고, 줄 안쪽의
 * 단추는 여기서 그대로 그린다.
 *
 * **칸 격자는 손으로 그린 채 둔다.** 그것은 목록이 아니라 판이다 — 거르기도 페이지도
 * 뜻이 없고, 줄마다 틀을 하나씩 세우면 `.rmg__row` 의 배치가 한 겹 더 깊어진다.
 *
 * **저장은 초안이다.** 여기서 게임이 바뀌지 않는다.
 */
import { useState } from 'react'

import { DataList } from '../editor/DataList'
import { Button, Panel, ValueExpr } from '../ds'

export interface RoomGridProps {
  /** 룸 파일 전체. `templates`·`legend`·`legend_ko` 를 담고 있다. */
  readonly file: Record<string, unknown> | undefined
  readonly onSave: (text: string, note: string) => void
}

/**
 * 한 장에 세울 방 수.
 *
 * 마흔 곳이다. 한꺼번에 세우면 폰에서 단추 줄만으로 화면이 차고, 고치려던 격자는 그
 * 아래 어딘가에 있다. 열둘이면 좁은 폭에서도 두어 줄로 접힌다.
 */
export const ROOM_PAGE = 12

/**
 * 방 한 곳을 찾기 칸이 보는 한 줄로 적는다.
 *
 * **이름과 장을 함께 넣는다.** id 로만 거르면 「너른 마당」을 찾는 사람이 `open_field` 를
 * 먼저 떠올려야 하고, 「몇 장짜리 방인가」는 아예 못 묻는다 — 방을 고를 때 사람이 드는
 * 기준이 그 둘이다.
 *
 * @param room 방 한 곳.
 * @returns 거르기가 볼 글자.
 */
export function roomSearchText(room: Record<string, unknown>): string {
  const floor = room.min_floor === undefined ? '' : `${String(room.min_floor)}장`
  return `${String(room.id ?? '')} ${String(room.label_ko ?? '')} ${floor}`
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
    <Panel title="방" meta={`${String(templates.length)}개`} tone="panel" padded scroll>
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
        {/* **「아직 안 왔다」를 목록 안에서 적지 않는다.** 틀은 빈 목록 문구 하나만 받으므로
            파일을 못 읽은 것까지 그리로 넘기면 불러오는 중에 「고칠 방이 없다」가 뜬다 —
            가진 것이 없다는 말과 아직 못 읽었다는 말은 다른 사실이다. */}
        {file === undefined ? (
          <ValueExpr text="방 파일을 불러오는 중이다" size="sm" dim />
        ) : (
          <DataList
            items={templates}
            rowKey={(item) => String(item.id)}
            // **틀은 `display` 를 안 정한다.** 탭 줄이 접히는 것은 이 화면의 배치이므로
            // 여기서 준다.
            listClass="cat__tabs"
            emptyText="고칠 방이 없다"
            pageSize={ROOM_PAGE}
            unit="곳"
            filterText={roomSearchText}
            filterLabel="이름·장으로 찾기"
            renderRow={(item) => (
              <Button
                size="sm"
                variant={String(item.id) === openId ? 'primary' : 'ghost'}
                onClick={() => {
                  setOpenId(String(item.id))
                }}
              >
                {String(item.id)}
              </Button>
            )}
          />
        )}

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
