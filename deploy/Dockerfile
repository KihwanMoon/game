# syntax=docker/dockerfile:1

# Python 은 3.11 로 고정한다. .python-version, ruff 의 target-version(py311),
# 표준 문서 §8.5.2 의 CI setup-python 이 모두 3.11 이다. 계층마다 버전이 갈리면
# 훅이 통과시킨 코드를 게이트가 막는다 (§7.1).
ARG PYTHON_VERSION=3.11

# uv 를 핀으로 박는다. 잠금 파일을 읽는 도구가 환경마다 다르면 --frozen 의 의미가 없다.
ARG UV_VERSION=0.12.7

# 바인드 마운트한 소스에 컨테이너가 쓸 수 있어야 하므로 호스트 사용자와 uid 를 맞춘다.
ARG APP_UID=1000
ARG APP_GID=1000


# ─────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

ARG APP_UID
ARG APP_GID

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # 가상환경을 /app 밖에 둔다. dev·ci 는 /app 에 소스를 바인드 마운트하는데,
    # 프로젝트 안에 두면 호스트의 .venv 가 컨테이너 것을 덮어써 버린다.
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash app

WORKDIR /app


# ─────────────────────────────────────────────────────────────────────────────
# 의존성 설치 계층. 소스보다 먼저 넣어야 소스 수정이 이 계층의 캐시를 깨지 않는다.
FROM base AS deps

ARG UV_VERSION
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

COPY pyproject.toml uv.lock ./

# 런타임 의존성은 현재 0개다 (TDD §1.2 — Phase 1 은 표준 라이브러리만).
# 그래도 uv 를 거치는 이유는, 나중에 의존성이 생겨도 이 줄을 고칠 필요가 없게 하기 위해서다.
RUN uv sync --frozen --no-dev --no-install-project

FROM deps AS deps-dev
RUN uv sync --frozen --no-install-project

# 검증 서버용 (B단계). **시뮬레이션 코어는 여전히 의존성이 0개다** — 코어를 부르는
# 껍데기에만 붙는다. runtime 계층과 갈라 두어, 헤드리스 배치는 fastapi 없이 돈다.
FROM deps AS deps-api
RUN uv sync --frozen --no-dev --group api --no-install-project


# ─────────────────────────────────────────────────────────────────────────────
# 배치 실행용. 시뮬레이션 코어만 담는다. uv 도 개발 도구도 들어가지 않는다.
FROM base AS runtime

COPY --from=deps --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app game/ ./game/

# 배치 결과가 실행마다 재현되어야 한다 (TDD §1.1). 코어는 hash() 를 쓰지 않지만,
# 누가 무심코 집합 순회를 끼워 넣어도 배치 산출물만은 흔들리지 않도록 못박는다.
# ci 계층에는 일부러 넣지 않는다 — 거기서는 무작위 시드가 그 실수를 드러내야 한다.
ENV PYTHONHASHSEED=0

USER app
CMD ["python", "-m", "game.main"]


# ─────────────────────────────────────────────────────────────────────────────
# 검증 서버. 코어를 부르는 껍데기이며, 여기만 fastapi·psycopg 를 갖는다.
FROM base AS api

COPY --from=deps-api --chown=app:app /opt/venv /opt/venv
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app game/ ./game/
# 운영이 부르는 명령들. **이것이 없으면 관리자 권한을 줄 방법이 아예 없다** —
# 승격은 API 로 열지 않았으므로(그 하나가 뚫리면 세계 전체가 뚫린다) 길이 이 스크립트
# 하나뿐인데, 그것이 이미지에 없으면 길이 없는 것과 같다. 실제로 그렇게 배포됐다.
#
# 세계 틱과 G1 계측도 같은 처지였다. 셋 다 psycopg 만 쓰므로 이 계층에서 돈다 —
# 골든 내보내기 같은 개발 도구는 dev 의존성이 없어 여기서 돌지 않고, 그것이 맞다.
COPY --chown=app:app scripts/ ./scripts/

# 서버도 재현되어야 한다. 재시뮬 결과가 프로세스마다 달라지면 검증이 성립하지 않는다.
ENV PYTHONHASHSEED=0

USER app
EXPOSE 8000
# 워커 하나다. 재시뮬이 CPU 를 쓰므로 프로세스를 늘리는 것은 코어 수를 보고 정한다 —
# 지금 규모(초당 40건)에서는 하나로 충분하고, 늘릴 때 연결 풀 상한도 함께 본다.
CMD ["uvicorn", "game.api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ─────────────────────────────────────────────────────────────────────────────
# 게이트 실행용. tools/check_all.sh 가 git ls-files 를 쓰므로 git 이 필요하다.
FROM deps-dev AS ci

RUN apt-get update \
    && apt-get install --no-install-recommends --yes git \
    && rm -rf /var/lib/apt/lists/*

USER app
# 바인드 마운트한 저장소의 소유자가 호스트 사용자라 uid 가 맞아도 git 이 까다롭게 굴 수 있다.
RUN git config --global --add safe.directory '*'

# PYTHONHASHSEED 를 고정하지 않는다. 파이썬 기본값인 무작위 시드가
# hash() 순서에 기댄 코드를 드러내 준다 (R5).
CMD ["./tools/check_all.sh"]


# ─────────────────────────────────────────────────────────────────────────────
# 개발용. 소스를 바인드 마운트해서 쓴다.
FROM ci AS dev

CMD ["bash"]
