# game

## 코딩 표준

이 저장소는 사내 파이썬 표준을 따른다. **규칙 정본은 Confluence 라벨
`python-coding-standard` 문서(RULESET_VERSION 14)이며, 저장소의 설정 파일은
그 문서로부터 생성된 사본이다.** 규칙을 바꿔야 하면 설정 파일이 아니라 정본 문서를
고치고 `RULESET_VERSION` 을 올린 뒤 각 저장소에서 재동기화한다(§11).

규칙 본문은 `.claude/rules/python-style.md` 에 있다. 파이썬 파일을 다룰 때 자동으로
적용되므로 여기에 중복해 적지 않는다.

동기화 이력은 `.claude/conventions.lock` 에 있다.

## 문서

`docs/README.md` 가 지도다. 네 갈래로 나뉜다.

| 폴더 | 무엇 | 시작점 |
|:--|:--|:--|
| `docs/기획/` | 무엇을 만드는가 | `1_통합기획서` |
| `docs/설계/` | 어떻게 만드는가 | `1_통합시스템설계` (§6 에 통합 도입 순서) |
| `docs/결정/` | 아직 안 정한 것 | **`1_결정대기목록`** — 미결 49건 |
| `docs/참고/` | 왜 그렇게 정했는가 | 실측·판정 자료 |

`기획/1_통합기획서`·`설계/1_통합시스템설계`·`설계/8_디자인명세` 는 **통합 뷰이지 정본이
아니다.** 기획·기술 정본은 `기획/2_GDD_v2`·`설계/2_TDD_v2` 이고, 시스템별 정본은
`설계/3_저장과_멀티플레이`·`4_아이템`·`5_스킬`·`6_몬스터`·`7_변조방지` 다.

**클라이언트는 적대적이라고 전제한다.** 서버에 무언가를 보내는 코드를 쓸 때는
`설계/7_변조방지` §4 의 제출 스키마 규율을 먼저 본다 — 클라이언트가 보낸 것 중 서버가
저장하는 것은 규칙표 하나뿐이고, 결과·시드·스냅샷은 **받을 자리를 만들지 않는다.**

## 강제 수단 세 계층 (§7.1)

세 계층은 대체 관계가 아니다. 잡히는 것이 서로 다르다.

| 계층 | 시점 | 커버 대상 | 보장 |
|---|---|---|---|
| `.claude/rules/python-style.md` | 코드를 쓰기 전 | Claude Code 가 쓰는 코드 | 확률적 |
| `.claude/hooks/check_python_file.sh` (PostToolUse) | 파일을 쓴 직후 | 방금 쓴 파일 하나 | 결정적, 파일 단위 |
| `tools/check_all.sh` (게이트) | `git push` 직전 | 저장소 전량 | 결정적, 최종 관문 |

게이트 트리거는 **git pre-push 훅**이다. 클론한 뒤 한 번 켜야 한다:

```bash
git config core.hooksPath .githooks
```

`--no-verify` 로 우회할 수 있으므로, 우회했다면 그 사실을 리뷰에 남긴다.

## 작업 절차

- 파일 수정 후 별도 명령을 돌릴 필요는 없다. PostToolUse 훅이 포맷·린트를 자동
  적용하고, 자동 수정되지 않는 위반은 훅이 되돌려 알려 준다.
- 훅이 위반을 알려 오면 그 자리에서 고친다. 억제로 넘기지 않는다.
- 훅은 방금 쓴 파일 하나만 본다. 저장소 전량은 `tools/check_all.sh` 가 본다 —
  커밋 전에 한 번 돌린다.
- 검사 결과는 종료 코드로 판정한다. 출력 줄을 세는 방식(`grep -c`)은 도구의 출력
  형식이 예상과 다르면 0 을 돌려주고, 그것이 "위반 없음"과 구별되지 않는다.
- 새 공용 함수를 만들기 전에 기존 모듈에 같은 기능이 있는지 먼저 검색한다.

## 예외 처리 (§11)

- 규칙을 어겨야 하면 해당 라인에 `# noqa: RULE` 와 **사유 주석**을 함께 남긴다.
- 함수명 규칙은 `# naming: allow <사유>` 를 쓴다.
- 사유 없는 억제는 리뷰에서 반려한다.
- 설계상 피할 수 없는 규칙군은 개별 억제가 아니라 `ruff.toml` 의 `ignore` 에
  사유 주석과 함께 적고, 그 판단을 팀에 공유한다.
- 저장소 설정 파일만 개별 수정하는 것은 금지한다. 정본 문서를 고친다.

## 개발 환경

의존성은 uv 로 관리한다. Python 은 TDD §1.2 및 CI(§8.5.2)에 맞춰 **3.11** 로 고정했다
(`.python-version`).

```bash
uv sync --group dev          # .venv 구성
uv run pytest                # 테스트
uv run python -m game.main --seed 12345
./tools/check_all.sh         # 저장소 전량 게이트 — 커밋 전에 한 번
```

게이트가 쓰는 도구는 세 계층이 같은 버전을 봐야 한다(§7.1). ruff 는 `0.16.3` 으로
`pyproject.toml` 의 dependency-group 과 `.pre-commit-config.yaml` 의 rev 양쪽에
고정돼 있다. `jq` 는 훅 입력이 stdin JSON 이라 별도로 필요하다.

**`[tool.ruff]` 를 `pyproject.toml` 에 넣지 않는다.** ruff 는 `ruff.toml` 을 우선하므로
둘을 함께 두면 pyproject 쪽이 조용히 무효가 된다(§8). ruff 설정의 자리는 `ruff.toml`
하나뿐이다.

## 디렉터리 구조

표준 문서 §12 는 웹 백엔드 기준이라, 헤드리스 시뮬레이션 코어인 이 프로젝트에 맞게
변형했다 — §12 가 허용하는 범위다. `api/` 는 두지 않았고(아직 서버 API 가 없다),
계층 경계 원칙은 그대로 지켰다.

```
game/
├─ main.py            컴포지션 루트. 코어를 조립하는 유일한 지점
├─ api/               검증 서버 (B단계). FastAPI. 얇게 유지한다 — 판정은 services/,
│                     저장은 app/store/ 가 한다
├─ config.py          설정 로드
├─ schemas/           I/O 계약 (TDD §3) — TS 로 이식되는 유일한 코드 자산
├─ app/
│  ├─ core/           도메인을 모른다. RNG, 이벤트 로그, 에러 규격
│  ├─ grid/           타일·LOS·포위도
│  ├─ pathfinding/    가중 Dijkstra, 거리장 캐싱
│  ├─ rules/          RuleVM
│  ├─ combat/         전투 수식
│  ├─ simulation/     틱 엔진 7페이즈
│  ├─ items/          아이템 카탈로그·요구조건·스탯 합산
│  ├─ store/          서버 저장소 (PostgreSQL). 코어는 이것을 모른다
│  └─ services/       유스케이스. 파일 하나가 시나리오 하나
└─ resources/         밸런스 JSON, 룸 템플릿
tests/                골든 리플레이·회귀
scripts/              골든 내보내기 등 헤드리스 러너
frontend/             브라우저 앱 (Phase 3). 아래 절 참조
design/               디자인 토큰 사본
deploy/               Docker·Compose·nginx
```

## 프런트엔드 (Phase 3)

`frontend/` 는 Vite + React + TypeScript(strict) 앱이고, `frontend/src/core/` 는
**파이썬 코어를 그대로 이식한 것**이다. 두 코어가 같은 시드에서 비트 단위로 같은 결과를
내야 한다(게이트 G3). 상세와 이식 규약은 `frontend/README.md` 에 있다.

- 파이썬이 정본이다. 어긋나면 TS 쪽이 틀린 것이며, 골든 JSON 을 손으로 고치지 않는다.
- 64비트 값은 `BigInt` 다. `Number` 는 53비트라 SplitMix64 가 깨진다.
- 부동소수를 쓰지 않고, 객체 키 순회로 게임 상태를 만들지 않으며(정렬된 배열·Map),
  `Math.random`·`Date.now` 를 쓰지 않는다. 파이썬 쪽 불변 조건과 같은 이유다 (R5).
- 디자인 토큰과 밸런스 JSON 은 **복사하지 않고** vite 별칭 `@design`·`@resources` 로
  원본을 직접 읽는다. 사본을 두면 두 코어가 다른 데이터로 돌게 된다.

```bash
cd frontend
npm ci
npm run dev        # http://localhost:8090 (컨테이너를 먼저 내려야 한다)
npm run build      # tsc --noEmit && vite build
npm test           # vitest — 골든 대조 포함
```

화면은 넷이다. `/` 가 제품 화면(규칙 에디터 ↔ 전투 관전 ↔ 사후 분석)이고, `/ds.html`·
`/battle.html`·`/hud.html` 은 부품·렌더러·되감기 확인용 페이지다.

어디에 둘지 헷갈리면 **"이것이 우리 도메인을 아는가"** 를 묻는다(§12). 모르면 `core/`,
하나만 알면 도메인 모듈, 여러 개를 엮으면 `services/` 다. 의존은 한 방향으로만 흐른다.

## 이 프로젝트의 불변 조건

TDD §1.1 이 코어 원칙으로 둔 것이며, 깨지면 리플레이·데일리 챌린지·헤드리스 밸런싱이
한꺼번에 무너진다(R5).

- **모든 무작위성은 `game.app.core.rng.DeterministicRng` 를 거친다.** 파이썬 `random`,
  `os.urandom`, 시스템 시간을 코어에서 쓰지 않는다.
- **집합·딕셔너리를 순회해 게임 상태를 만들지 않는다.** 순서가 보장되지 않는다.
  정렬된 시퀀스로 바꿔서 쓴다.
- **부동소수를 피한다.** 확률은 정수 비교로 표현한다 — 30% 는 `rng.get_below(100) < 30`.
- 난수원을 축별로 가를 때는 `create_stream(label)` 을 쓴다. 한 축의 호출 횟수가 바뀔 때
  다른 축까지 흔들리면 회귀 검증이 불가능해진다.
- 골든 테스트(`tests/test_rng.py`)의 기대값을 고치기 전에, 그것이 저장된 리플레이를
  전부 무효화한다는 사실을 먼저 확인한다.

## 디자인

Claude Design 프로젝트 `fae25530-140a-4873-b9f9-684645b541c6` 가 정본이다. 토큰 사본만
`design/` 에 가져왔고, 토큰을 고칠 일이 생기면 이 사본이 아니라 Design 프로젝트를
고치고 다시 가져온다. 상세와 컴포넌트 계약은 `design/README.md` 참조.

성격은 기계 도면이다 — 황동은 화면당 3곳까지, 그림자 없음, 4px 모듈, 1px 괘선,
참/거짓은 색·글리프·명도 3중 표기.

**디자인이 코어의 출력 계약을 정하는 지점이 있다.** UI 취향이 아니라 Phase 1 에서
이벤트 로그를 설계할 때 반영해야 하는 것들이다.

- 조건문은 `적거리(2) <= 사거리(3)` 처럼 **각 항의 실측값을 병기**한다. RuleVM 은
  참/거짓만이 아니라 항별 실제 값을 내보내야 한다 (GDD §8.2, P1).
- 규칙 상태는 3종이다 — 참·발동, 참·미발동, 거짓. "더 높은 우선순위가 이미 발동해서
  실행되지 않았다"를 코어가 구분해 내보내야 한다.
- CPU 예산 초과는 오류가 아니라 수치다. `cpu 10 / 8` 로 표시되고 그 상태에서도 편집이
  계속된다.
- 로그 레코드 필드는 `tick, rule, expr, outcome, delta, fired` 다.

## 배포

Docker + Compose. 파일은 표준 §12 가 정한 `deploy/` 에 있고, 상세는
`deploy/README.md` 를 본다.

```bash
export COMPOSE_FILE=deploy/docker-compose.yml
docker compose up -d             # 서빙 스택 (frontend + backend + postgres)
docker compose run --rm check    # 게이트
docker compose run --rm test     # pytest
docker compose run --rm sim      # 헤드리스 실행
docker compose run --rm dev      # 개발 셸
```

`stock.nullmovie.com` 이 이 스택을 가리킨다. 라우팅은 이 저장소가 아니라
`/data/workspace/edge-proxy` 에 있고, vtoon·balpum 도 같은 파일에서 라우팅된다 —
고칠 때 세 도메인이 함께 걸린다. **`container_name`(`game-frontend-1`·`game-backend-1`)
과 네트워크명 `game_net` 은 edge-proxy 와의 계약이므로 바꾸지 않는다.**

`frontend` 는 실제 앱이다(W13). `deploy/Dockerfile.frontend` 가 vite 로 굽고 nginx 가
정적 산출물을 서빙한다 — **개발 서버가 아니라 프로덕션 빌드다.** 공개 도메인에 dev
서버를 두면 HMR 웹소켓이 터널을 건너야 하고, 타입 오류가 런타임까지 미뤄지며, 파일
하나가 깨지면 프로세스가 죽는다. `backend` 는 이제 실제 검증 서버다(FastAPI + PostgreSQL). **서버는 결과를 받지 않고
재시뮬해서 확정한다** — 시드는 서버가 발급하고, 티켓은 1회용이며, 제출에는 결과를 받을
자리가 없다. 그래도 **서버가 없어도 게임은 돈다**: 코어가 브라우저 안에서 직접 돌고
서버는 보관과 검증만 맡는다.
컨테이너명·포트·네트워크가 그대로라 edge-proxy 는 손대지 않았다. 상세는
`deploy/README.md`.

`POSTGRES_PASSWORD` 는 `deploy/.env` 에 있고 커밋되지 않는다. 기본값을 두지 않았으므로
없으면 스택이 뜨지 않는다 — 개발용 비밀번호가 배포까지 따라가는 사고는 기본값에서 시작한다.

컨테이너는 도구 버전을 맞춰야 하는 **네 번째 계층**이다(§7.1). Python 3.11 · uv 0.12.7 ·
ruff 0.16.3 이 `.python-version`·`pyproject.toml`·`.pre-commit-config.yaml`·Dockerfile 에
같은 값으로 박혀 있다. 하나를 올리면 전부 올린다.

`runtime` 이미지에는 uv·ruff·pytest·git 이 없다 — Phase 1 의 런타임 의존성이 0개다.
가상환경은 `/opt/venv` 에 둔다. `/app` 에 두면 바인드 마운트한 호스트 `.venv` 가
컨테이너 것을 덮어쓴다.

`PYTHONHASHSEED=0` 은 `runtime` 에만 박는다. `ci` 는 파이썬 기본 무작위 시드로 두어야
`hash()` 순서에 기댄 코드가 드러난다 (R5).

## 알려진 이슈

전체 목록은 **`docs/결정/3_알려진이슈.md`** 에 있다 — 표준 문서 결함 17건, 정본·사본
드리프트 3건, 미검증 5건, 운영 3건.

일상 작업에 영향을 주는 것만:

- **D1~D4 는 로컬 수정했다.** `python`/`python3`, `pipefail` 아래 0건 처리, 예외 정규식
  `**/tests/**`, pre-commit 훅 직접 배치. 사유는 `.claude/conventions.lock`
- **D7 로 게이트가 한 단계 늘었다.** `tools/check_module_length.py` 가 §4 의 모듈 400줄
  상한을 본다. 테스트도 대상이다 — §1 이 테스트에 면제하는 것은 독스트링·타입 힌트·함수명
  셋뿐이다. 켤 때 걸린 존량 11건은 "책임이 둘 이상" 기준으로 분해해 0으로 만들었다
- **D5 는 미해결이다.** §8.9 `BANNED` 목록이 정본 PDF 에서 잘렸다. `check_structure.sh`
  에 `TODO(victor)` 가 있고, Confluence 원문 확인이 필요하다
- 정본이 `RULESET_VERSION 15` 로 개정되면 로컬 수정을 지우고 재동기화한다
