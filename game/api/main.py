"""검증 서버 조립 — 컴포지션 루트 (B단계).

**서버는 결과를 받지 않는다. 입력을 받아 다시 계산한다** (docs/설계/7_변조방지 §3).
그 성질이 성립하는 이유는 두 코어가 비트 단위로 같기 때문이고(게이트 G3), 여기 붙는
모든 라우트가 그 하나에 얹혀 있다.

이 파일은 조립만 한다. 판정은 `app/services/verify_run`, 저장은 `app/store/`, HTTP 는
`api/routes/` 가 맡는다 — 규칙이 라우트 안으로 들어오면 그것을 헤드리스로 검증할 수 없다.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from game.api.deps import init_state
from game.api.routes import account, auth, bestiary, health, items, meta, run, ticket
from game.app.store.connection import apply_schema, create_pool


@asynccontextmanager
async def manage_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """연결 풀과 스키마를 준비한다.

    **연결이 없으면 서버가 뜨지 않는다.** 지연 연결로 두면 설정이 틀린 채로 배포가
    성공하고 첫 사용자가 그것을 발견한다.

    Args:
        app: 조립 중인 앱.

    Yields:
        None: 준비가 끝난 뒤의 실행 구간. 이 구간이 끝나면 풀을 닫는다.
    """
    pool = create_pool()
    apply_schema(pool)
    init_state(pool)
    yield
    pool.close()


def create_app() -> FastAPI:
    """앱을 조립한다.

    Returns:
        라우트가 붙은 앱.
    """
    # 문서 경로를 끄는 이유는 공개 도메인에 붙기 때문이다. 스키마를 열어 두면 아직
    # 안정되지 않은 계약이 그대로 공개된다.
    server = FastAPI(
        title="game 검증 서버", docs_url=None, redoc_url=None, lifespan=manage_lifespan
    )
    for module in (health, account, auth, ticket, run, meta, items, bestiary):
        server.include_router(module.router)
    return server


app = create_app()
