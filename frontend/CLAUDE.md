# frontend

`frontend/` 는 Vite + React + TypeScript(strict) 앱이고, `frontend/src/core/` 는
**파이썬 코어를 그대로 이식한 것**이다. 두 코어가 같은 시드에서 비트 단위로 같은 결과를
내야 한다(게이트 G3). 상세와 이식 규약은 `frontend/README.md` 에 있다.

## 이식 규약

- 파이썬이 정본이다. 어긋나면 TS 쪽이 틀린 것이며, 골든 JSON 을 손으로 고치지 않는다.
- 64비트 값은 `BigInt` 다. `Number` 는 53비트라 SplitMix64 가 깨진다.
- 부동소수를 쓰지 않고, 객체 키 순회로 게임 상태를 만들지 않으며(정렬된 배열·Map),
  `Math.random`·`Date.now` 를 쓰지 않는다. 파이썬 쪽 불변 조건과 같은 이유다 (R5).
- 디자인 토큰과 밸런스 JSON 은 **복사하지 않고** vite 별칭 `@design`·`@resources` 로
  원본을 직접 읽는다. 사본을 두면 두 코어가 다른 데이터로 돌게 된다.

## 굽는 화면

`/` 가 제품 화면(규칙 에디터 ↔ 전투 관전 ↔ 사후 분석)이고 `/admin.html` 이 관리
화면이다. `/ds.html`·`/battle.html`·`/hud.html` 은 부품·렌더러·되감기 확인용이며
**개발 서버에서만 열린다** — 공개 도메인에 서 있던 것을 2026-09-16 에 산출물에서 뺐다.
막는 규칙 대신 안 굽는 쪽을 골랐다: 규칙은 풀 수 있지만 없는 파일은 못 연다.

`npm run dev` 는 http://localhost:8090 을 쓴다 — **컨테이너를 먼저 내려야 한다.**
나머지 명령은 `package.json` 의 `scripts` 를 본다.
