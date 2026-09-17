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
import { GRADE_GLYPHS, GRADE_LABELS, formatGradeClass } from './gradeBadge'
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
  const state = cell.isSealedSlot ? ' invg__cell--sealed' : cell.isOff === true ? ' invg__cell--off' : ''
  const picked = isPicked ? ' invg__cell--picked' : ''
  return (
    <button
      type="button"
      className={`invg__cell${state}${picked}`}
      key={cell.key}
      // 고름은 색·명도만으로 알리지 않는다. 화면을 못 보는 경로에서는 이것이
      // 유일한 채널이다 — 참/거짓을 3중으로 적는 것과 같은 규칙이다.
      aria-pressed={isPicked}
      // 자리 코드가 없는 칸(스킬)도 있다. 그냥 이어 붙이면 앞에 빈칸이 남는다.
      // **등급도 여기 든다** — 색과 글리프를 못 보는 경로에서는 이것이 유일한 채널이다.
      aria-label={[
        cell.code,
        GRADE_LABELS.get(cell.grade) ?? '',
        cell.label === '' ? '빈 칸' : cell.label,
        cell.isOff === true ? '끔' : '',
      ]
        .filter((part) => part !== '')
        .join(' ')}
      onClick={() => {
        onPick(cell)
      }}
    >
      <span className="invg__code">{cell.code}</span>
      {/* **등급은 색 하나에 안 맡긴다** (2026-09-16, 실제 신고: 「가방에 아이템 등급
          색깔이 사라졌어」). 원인은 그림을 붙이면서 이름줄이 `--under` 로 흐려진 것인데,
          색만 되살리면 같은 일이 또 일어난다 — 색을 못 가르는 사람에게는 애초에 없던
          채널이기도 하다. 글리프를 왼쪽 아래에 세워 **누르지 않아도 갈리게** 한다.
          오른쪽 위는 상태 글리프(파손·봉인·귀속)가 쓰고 있어 자리를 나눈다. */}
      {GRADE_GLYPHS.has(cell.grade) ? (
        <span className={`invg__grade invg__grade--${cell.grade.toLowerCase()}`} aria-hidden="true">
          {GRADE_GLYPHS.get(cell.grade)}
        </span>
      ) : null}
      {cell.isSealedSlot ? (
        <span className="invg__mark">▨</span>
      ) : cell.label === '' ? (
        <span className="invg__empty">·</span>
      ) : (
        <>
          {/* **그림이 있으면 얹고 이름은 남긴다** (2026-09-16). 그림만 남기면 아직 안
              그린 형태가 빈 칸으로 보이고, 같은 형태를 나눠 쓰는 넷(비수·환도·사인검)이
              구별되지 않는다 — 형태는 그림이 말하고 어느 것인지는 이름이 말한다. */}
          {cell.art === undefined ? null : (
            <img className="invg__art" src={cell.art} alt="" width="48" height="48" />
          )}
          <span
            className={`invg__label${formatGradeClass(cell.grade)}${
              cell.art === undefined ? '' : ' invg__label--under'
            }`}
          >
            {cell.label}
          </span>
        </>
      )}
      {/* **무엇을 해 주는가 한 줄.** 이것이 없으면 격자를 봐서는 어느 게 더 좋은지
          알 수 없어 칸을 하나씩 눌러야 한다. 54px 안에 들려고 한 글자 표기를 쓴다. */}
      {cell.fact === '' ? null : (
        // **아래 구석을 쓰는 것이 있으면 그만큼 비킨다** (2026-09-17, 실제 스크린샷).
        // 등급 글리프와 개수는 absolute 라 흐름에서 자리를 안 차지하고, 그래서 이 줄
        // 위에 그대로 겹쳐 찍혔다 — 비각 칸의 `NORMAL` 위에 `lv2` 가 그것이었다.
        <span
          className={`invg__fact${GRADE_GLYPHS.has(cell.grade) ? ' invg__fact--left' : ''}${
            cell.countText === '' ? '' : ' invg__fact--right'
          }`}
        >
          {cell.fact}
        </span>
      )}
      {cell.countText === '' ? null : <span className="invg__count">{cell.countText}</span>}
      {cell.marks.length === 0 ? null : (
        <span className="invg__marks">{cell.marks.join(' ')}</span>
      )}
    </button>
  )
}
