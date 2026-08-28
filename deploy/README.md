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
| `frontend` | 상주 | `game-frontend-1:8090`. **자리표시자** — 정적 안내 페이지 |
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

호스트 포트를 열지 않는다. 외부 접근 경로는 edge-proxy 하나뿐이다.

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

### Phase 3 에서 할 일

`frontend`·`backend` 의 `image` 를 실제 앱 빌드로 바꾸면 끝난다. **컨테이너명·포트·
네트워크가 그대로면 edge-proxy 는 손대지 않는다.** 지금 배관을 깔아 둔 이유가 이것이다.

## 이미지 구성

```
base ── deps ─────── runtime    시뮬레이션 코어만. 187MB
          └ deps-dev ─ ci ── dev   개발 도구 + git. 684MB
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

- **`frontend`·`backend` 는 nginx 자리표시자다.** 실제 규칙 에디터·전투 렌더러·API 는
  로드맵 Phase 3 (W9~W13) 산출물이다. 지금 만들지 않는 이유는 로드맵 원칙 1 이다 —
  재미 검증이 끝나기 전에는 자산을 만들지 않는다.
  없는 API 는 200 이 아니라 **501** 을 준다. 200 으로 위장하면 프런트가 그것을 붙잡고
  개발되기 시작한다.
- **`sim` 이 도는 것은 결정론 자체 점검뿐이다.** 진짜 배치 러너(표준 규칙표 × 1,000런)는
  Phase 1 W3 산출물이다. 생기면 compose 의 `command` 를 `scripts/` 의 러너로 바꾼다.
- 레지스트리 푸시는 하지 않는다. 로컬·사내 서버에서 `compose up` 까지가 현재 범위다.
- TLS 는 Cloudflare 가 종단한다. 오리진은 http:80 이다.
