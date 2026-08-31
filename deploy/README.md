# deploy

표준 문서 §12 가 정한 자리다. 저장소 루트에서 부른다.

```bash
cp deploy/.env.example deploy/.env     # 최초 1회. .env 는 커밋하지 않는다
mkdir -p volume                        # 배치 결과가 쌓이는 곳 (gitignore)
```

## 서비스

서빙 스택은 `up -d`, 일회성 도구는 `run --rm` 이다. 도구는 `profiles: ["tools"]` 로
묶여 있어 `up -d` 에 딸려 오지 않는다. `compose run` 은 프로파일을 자동으로 켜므로
`--profile` 을 붙일 필요는 없다.

```bash
export COMPOSE_FILE=deploy/docker-compose.yml
docker compose up -d              # frontend + backend
docker compose run --rm check     # 게이트
```

| 서비스 | 종류 | 하는 일 |
|:--|:--|:--|
| `frontend` | 상주 | `game-frontend-1:8090`. **실제 앱** — 규칙 에디터·전투 관전·사후 분석 |
| `backend` | 상주 | `game-backend-1:8000`. **자리표시자** — `/api/health` 만 200 |
| `sim` | 일회성 | 헤드리스 실행. 결과는 `volume/` 로 |
| `check` | 일회성 | 저장소 전량 게이트 (`tools/check_all.sh`) |
| `test` | 일회성 | pytest — 골든 리플레이 회귀 |
| `dev` | 일회성 | 개발 셸. 소스 바인드 마운트 |

## 도메인 라우팅

`stock.nullmovie.com` 이 이 스택을 가리킨다. 라우팅은 이 저장소가 아니라
**`/data/workspace/edge-proxy`** 에 있다 — 호스트 80을 점유하는 공용 리버스 프록시이고
vtoon·balpum 도 같은 파일에서 라우팅된다.

```
stock.nullmovie.com ─┬─ /api/ ─→ game-backend-1:8000
                     └─ /     ─→ game-frontend-1:8090
```

**`container_name` 은 edge-proxy 와의 계약이다.** 자동 생성 이름에 기대면 컴포즈
프로젝트명이 바뀌는 순간 프록시가 깨진다. 네트워크 이름 `game_net` 도 같은 이유로
고정돼 있다(`networks.game_net.name`). edge-proxy 가 external 로 조인한다.

입구가 둘이다. **edge-proxy(:80)** 와 **호스트 8090 직결**이며, 후자는 Cloudflare
Tunnel 의 ingress 가 `stock.nullmovie.com` 전체를 host:8090 으로 보내기 때문에 열어
둔다. 터널에는 경로별 분기가 없으므로 `/api/` 를 백엔드로 나누는 일을 프런트 컨테이너의
nginx 가 함께 한다(`deploy/nginx/frontend.conf`). 두 입구가 같은 결과를 내야 한다.

### 주의 — 이 도메인은 원래 주가 예측 대시보드 것이었다

2026-08-28 에 upstream 을 `stock-*` 에서 `game-*` 으로 돌렸다. **주가 대시보드는 이
도메인에서 더 이상 접근되지 않는다.** 되돌리려면:

```bash
cd /data/workspace/edge-proxy
cp nginx/nginx.conf.bak.20260828-201825 nginx/nginx.conf
docker exec edge-proxy nginx -t && docker exec edge-proxy nginx -s reload
docker compose -f /data/workspace/stock/docker-compose.yml up -d
```

edge-proxy 는 git 저장소가 아니다. 이력이 남지 않으므로 `.bak.*` 파일이 유일한
되돌림 수단이다. 지우지 말 것.

### Phase 3 에서 한 일

`frontend` 를 자리표시자에서 실제 앱으로 바꿨다(W13). **컨테이너명·포트·네트워크가
그대로라 edge-proxy 는 한 줄도 고치지 않았다** — 배관을 미리 깔아 둔 값을 여기서 받았다.
`backend` 는 아직 자리표시자다. 프런트가 파이썬 코어를 TS 로 이식해 브라우저 안에서
직접 돌리므로(게이트 G3) 지금 단계의 게임은 API 없이 완결된다.

## 프런트엔드 이미지

`deploy/Dockerfile.frontend` 다. 파이썬 쪽 `deploy/Dockerfile` 과 파일을 나눈 이유는
겹치는 계층이 하나도 없기 때문이다 — 한 파일에 두면 어느 쪽을 고쳐도 상대편 빌드 캐시가
깨지고, 게이트를 도는 `ci` 계층이 node 를 끌고 다니게 된다.

```
node:22-alpine ── build ──▶ nginx:alpine ── serve
   npm ci                     dist/ 를 /usr/share/nginx/html 로
   npm run build              deploy/nginx/frontend.conf 를 default.conf 로
```

빌드 컨텍스트는 **저장소 루트**다. 프런트가 디자인 토큰(`design/`)과 밸런스 JSON
(`game/resources/`)을 사본이 아니라 vite 별칭 `@design`·`@resources` 로 **원본을 직접**
읽기 때문이다. 사본을 두면 파이썬 코어가 읽는 값과 조용히 갈라지고, 그 순간 게이트 G3
가 대조하는 두 코어가 서로 다른 데이터로 돈다. 그래서 `.dockerignore` 는 `design/` 을
빼지 않는다(`docs/` 는 뺀다 — 2.8MB PDF 이고 실행에 필요 없다).

`npm run build` 가 `tsc --noEmit && vite build` 이므로 **타입 오류는 이미지가 만들어지기
전에 걸린다.** `npm ci` 는 `package-lock.json` 과 어긋나면 실패한다 — 파이썬 쪽
`uv sync --frozen` 과 같은 규약이다.

### 왜 개발 서버(vite dev)가 아니라 프로덕션 빌드인가

이 컨테이너가 서는 자리가 공개 도메인(`stock.nullmovie.com`)이기 때문이다.

- dev 서버는 HMR 웹소켓을 요구하고 그 경로가 Cloudflare Tunnel 을 건너야 한다. 끊기면
  화면이 조용히 낡은 채로 남는다.
- dev 서버는 소스와 소스맵을 그대로 내보내고, 타입 오류를 런타임까지 미룬다.
- dev 서버는 파일 하나가 깨지면 프로세스가 죽는다. 정적 산출물에는 그런 자리가 없다.

**개발 중에는 컨테이너를 내리고 호스트에서 dev 서버를 쓴다.** 포트가 같으므로(8090,
`strictPort`) 둘을 동시에 띄울 수 없다 — 조용히 다른 포트로 옮겨 가면 터널이 빈 포트를
보게 되므로 일부러 실패하게 두었다.

```bash
docker compose -f deploy/docker-compose.yml stop frontend
cd frontend && npm run dev          # http://localhost:8090
# 끝나면
docker compose -f deploy/docker-compose.yml up -d frontend
```

빌드한 화면을 눈으로 확인하는 지점은 넷이다. `/` 가 제품 화면이고 나머지 셋은 확인용
페이지다 — `/ds.html` 디자인 시스템 부품 카탈로그, `/battle.html` 전투 렌더러,
`/hud.html` 되감기·사후 분석.

## 이미지 구성

```
base ── deps ─────── runtime    시뮬레이션 코어만. 187MB      (Dockerfile)
          └ deps-dev ─ ci ── dev   개발 도구 + git. 684MB      (Dockerfile)
build ──────────────── serve      프런트 정적 산출물 + nginx  (Dockerfile.frontend)
```

**`runtime` 에는 uv·ruff·pytest·git 이 들어가지 않는다.** Phase 1 의 런타임 의존성이
0개이기 때문이다 (TDD §1.2 — 표준 라이브러리만). 의존성이 생기면 `uv sync` 줄이
자동으로 처리하므로 Dockerfile 을 고칠 필요는 없다.

가상환경은 `/app` 이 아니라 `/opt/venv` 에 둔다. `dev`·`check` 는 `/app` 에 소스를
바인드 마운트하는데, 프로젝트 안에 두면 **호스트의 `.venv` 가 컨테이너 것을 덮어써서**
아키텍처가 다른 바이너리를 실행하게 된다.

## 버전 고정

§7.1 은 훅·pre-commit·게이트가 같은 도구 버전을 봐야 한다고 요구한다. 컨테이너는
네 번째 계층이므로 같은 값을 쓴다.

| 대상 | 값 | 함께 고쳐야 하는 곳 |
|:--|:--|:--|
| Python | 3.11 | `.python-version`, `ruff.toml` target-version, §8.5.2 CI |
| uv | 0.12.7 | `Dockerfile` ARG |
| ruff | 0.16.3 | `pyproject.toml`, `.pre-commit-config.yaml` rev |

의존성은 `uv sync --frozen` 으로 설치한다. `uv.lock` 과 어긋나면 빌드가 실패한다 —
컨테이너가 조용히 다른 버전을 쓰는 것보다 낫다.

## 결정론

`runtime` 만 `PYTHONHASHSEED=0` 을 박는다. 배치 산출물은 실행마다 재현되어야 하기
때문이다 (TDD §1.1).

`ci` 에는 **일부러 넣지 않는다.** 파이썬 기본값인 무작위 해시 시드가 `hash()` 순서에
기댄 코드를 드러내 준다 (R5). 여기서 고정해 버리면 검사가 그 실수를 못 본다.

호스트와 컨테이너가 같은 시드에서 같은 수열을 내는 것을 확인했다. 게이트 G3 가
Python 코어와 TypeScript 코어에 요구하는 것과 같은 성질의 검증이며, 그 예행이다.

```bash
GAME_SEED=424242 uv run python -m game.main | grep 'first draws'
docker compose -f deploy/docker-compose.yml run --rm -e GAME_SEED=424242 sim | grep 'first draws'
```

## 아직 안 된 것

- **`backend` 는 여전히 nginx 자리표시자다.** 없는 API 는 200 이 아니라 **501** 을 준다.
  200 으로 위장하면 프런트가 그것을 붙잡고 개발되기 시작한다. 프런트는 파이썬 코어를
  TS 로 이식해 브라우저 안에서 직접 돌리므로 지금은 API 가 없어도 게임이 완결된다 —
  서버가 필요해지는 시점은 저장·랭킹·데일리 챌린지(Phase 4)다.
- **메타 진행이 브라우저 메모리에만 있다.** 새로고침하면 규칙표가 초기값으로 돌아간다.
  저장(localStorage 또는 백엔드)은 다음 단계다.
- **`sim` 이 도는 것은 결정론 자체 점검뿐이다.** 진짜 배치 러너(표준 규칙표 × 1,000런)는
  Phase 1 W3 산출물이다. 생기면 compose 의 `command` 를 `scripts/` 의 러너로 바꾼다.
- 레지스트리 푸시는 하지 않는다. 로컬·사내 서버에서 `compose up` 까지가 현재 범위다.
- TLS 는 Cloudflare 가 종단한다. 오리진은 http:80 이다.

## 운영 명령

`api` 이미지에 `scripts/` 가 함께 실린다. **관리자 승격을 API 로 열지 않았으므로**(그
하나가 뚫리면 세계 전체가 뚫린다) 길이 이 스크립트뿐이고, 그것이 이미지에 없으면 길이
없는 것과 같다 — 실제로 그렇게 한 번 배포됐다.

`uv` 는 런타임에 없다(의존성 0개가 설계다). `/opt/venv` 의 파이썬을 직접 부른다.

```bash
export COMPOSE_FILE=deploy/docker-compose.yml
RUN="docker compose run --rm --entrypoint /opt/venv/bin/python backend"

$RUN -m scripts.grant_admin <아이디>            # 관리자 부여
$RUN -m scripts.grant_admin <아이디> --revoke   # 해제
$RUN -m scripts.run_world_tick <시드>           # 세계 한 틱 (몬스터끼리 전투)
$RUN -m scripts.report_g1                       # G1 판정 자료
```

**가입한 계정만 관리자가 될 수 있다.** 익명은 토큰만 있으면 되므로, 그 계정이 관리자면
토큰 하나가 곧 세계 전체다.

골든 내보내기 같은 개발 도구는 dev 의존성이 없어 이 이미지에서 돌지 않는다 — 그것이
맞다. 운영이 부르는 것과 개발이 부르는 것은 계층이 다르다.


## 아이템 카탈로그 스냅샷

**아이템 카탈로그의 정본은 DB 다** (`설계/4_아이템` §15.7). `resources/balance/items.json`
은 파생물이며, 헤드리스 러너와 골든이 DB 없이 돌기 위한 사본이다.

빈 DB 는 서버가 뜰 때 그 파일로 한 번 채워진다(`apply_catalog_seed`). **그 뒤로는 파일이
DB 를 덮지 않는다** — 뜰 때마다 덮으면 관리자가 고친 것이 배포 한 번에 사라진다.

관리자가 카탈로그를 고친 뒤에는 스냅샷을 다시 내보내고 커밋한다.

```bash
docker compose run --rm test uv run python -m scripts.export_items
```

내보내기는 **빈 카탈로그를 쓰지 않는다.** 이 파일은 파생물이면서 동시에 빈 DB 를 채우는
씨앗이라, 한 번 비우면 되살릴 곳이 없다.

스냅샷의 `item_list_version` 은 DB 의 카탈로그 세대이고, 그 값이 `core_version` 의 `i`
축이다 — 아이템을 고치는 것은 순위표 시즌을 가르는 일이다.
