/**
 * 도면 격자 칸 하나의 렌더 — **세 화면이 함께 쓴다** (가방·소모품 칸·경매장).
 *
 * `InventoryGrid` 안에 갇혀 있던 것을 꺼냈다. 소모품 칸과 경매장이 같은 격자를 쓰게
 * 되면서, 안 꺼내면 같은 칸이 세 벌로 복사되기 때문이다 — 봇 가방이 유저 가방과 다른
 * 목록으로 그려지던 것이 정확히 그 병이었고, 그때 갈라야 했던 것도 렌더였다.
 *
 * **칸은 상태만 그리고 조작은 밖에 산다.** 칸마다 버튼을 펴면 좁은 화면에서 칸 하나가
 * 서너 줄로 꺾인다 — 고른 칸의 상세를 부르는 쪽이 붙인다.
 */
import { formatGradeClass } from './gradeBadge'
import type { CellFace } from './gridCell'

/**
 * 격자 칸 하나를 그린다.
 *
 * @param cell 그릴 칸의 겉면.
 * @param isPicked 지금 고른 칸인가.
 * @param onPick 칸을 고른다. 겉면을 그대로 돌려주므로 부르는 쪽이 알맹이를 찾는다.
 * @returns 칸 버튼.
 */
export function renderCell<T extends CellFace>(
  cell: T,
  isPicked: boolean,
  onPick: (cell: T) => void,
): React.JSX.Element {
  const state = cell.isSealedSlot ? ' invg__cell--sealed' : ''
  const picked = isPicked ? ' invg__cell--picked' : ''
  return (
    <button
      type="button"
      className={`invg__cell${state}${picked}`}
      key={cell.key}
      // 고름은 색·명도만으로 알리지 않는다. 화면을 못 보는 경로에서는 이것이
      // 유일한 채널이다 — 참/거짓을 3중으로 적는 것과 같은 규칙이다.
      aria-pressed={isPicked}
      aria-label={`${cell.code} ${cell.label === '' ? '빈 칸' : cell.label}`}
      onClick={() => {
        onPick(cell)
      }}
    >
      <span className="invg__code">{cell.code}</span>
      {cell.isSealedSlot ? (
        <span className="invg__mark">▨</span>
      ) : cell.label === '' ? (
        <span className="invg__empty">·</span>
      ) : (
        <span className={`invg__label${formatGradeClass(cell.grade)}`}>{cell.label}</span>
      )}
      {/* **무엇을 해 주는가 한 줄.** 이것이 없으면 격자를 봐서는 어느 게 더 좋은지
          알 수 없어 칸을 하나씩 눌러야 한다. 54px 안에 들려고 한 글자 표기를 쓴다. */}
      {cell.fact === '' ? null : <span className="invg__fact">{cell.fact}</span>}
      {cell.countText === '' ? null : <span className="invg__count">{cell.countText}</span>}
      {cell.marks.length === 0 ? null : (
        <span className="invg__marks">{cell.marks.join(' ')}</span>
      )}
    </button>
  )
}
