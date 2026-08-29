/**
 * 타겟 셀렉터 — 규칙 모듈에서 부르는 이름. 구현은 `sim/selectors.ts` 하나뿐이다.
 *
 * 파이썬 정본은 `game/app/simulation/selectors.py` 이고 TS 이식도 같은 자리에 있다.
 * 두 코어의 파일이 1:1 로 마주 보아야 게이트 G3 의 대조가 사람 눈으로도 따라가지므로
 * 구현을 옮기지 않았다. 게다가 `sim/perception.ts` 가 셀렉터를 부르므로, 구현을 이쪽으로
 * 옮기면 `sim → rules → sim` 순환이 생긴다.
 *
 * 그래서 이 파일은 이름만 빌려준다. **여기에 로직을 추가하지 마라** — 사본이 갈라지는
 * 순간 같은 규칙표가 두 답을 내고, 그것이 정확히 R5 가 막으려는 것이다.
 *
 * 이 파일과 `sim/index.ts` 는 같은 이름들을 내보낸다. 한 파일에서 두 배럴을 `export *`
 * 로 함께 펴면 어느 쪽이 들어왔는지 알 수 없게 되므로, `rules/index.ts` 는 셀렉터를
 * 넣지 않는다. 필요하면 이 경로를 직접 import 한다.
 */

export {
  ALL_SELECTORS,
  SELECTOR_BOSS,
  SELECTOR_CASTING,
  SELECTOR_HIGHEST_THREAT,
  SELECTOR_LOWEST_HP,
  SELECTOR_NEAREST,
  SELECTOR_TYPE_RANGED,
  SELECTOR_TYPE_SUMMONER,
  resolveTarget,
} from '../sim/selectors'
