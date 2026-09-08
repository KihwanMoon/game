"""검증 서버 조립 — 컴포지션 루트 (B단계).

**서버는 결과를 받지 않는다. 입력을 받아 다시 계산한다** (docs/설계/7_변조방지 §3).
그 성질이 성립하는 이유는 두 코어가 비트 단위로 같기 때문이고(게이트 G3), 여기 붙는
모든 라우트가 그 하나에 얹혀 있다.

이 파일은 조립만 한다. 판정은 `app/services/verify_run`, 저장은 `app/store/`, HTTP 는
`api/routes/` 가 맡는다 — 규칙이 라우트 안으로 들어오면 그것을 헤드리스로 검증할 수 없다.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from game.api.deps import get_pool, init_state
from game.api.routes import (
    account,
    admin,
    admin_bot_detail,
    admin_bots,
    admin_testers,
    admin_watch,
    auction,
    auth,
    bestiary,
    catalog_admin,
    catalog_draft,
    consumables,
    content_admin,
    content_pack,
    discovery,
    health,
    items,
    maintenance,
    meta,
    replay,
    run,
    skills,
    ticket,
    unseal,
    world,
)
from game.app.store.api_errors import save_api_error
from game.app.store.connection import apply_schema, create_pool

# 5xx 만 남긴다. 4xx 는 클라이언트가 틀린 것이고, 그것까지 담으면 표가 접근 로그가 된다.
SERVER_ERROR_FLOOR = 500


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

    @server.middleware("http")
    async def record_server_errors(request: Request, call_next: Callable) -> Response:
        """5xx 를 표에 남긴다 (§6 H1). **동작은 그대로 둔다** — 다시 던진다.

        예외 처리기(`exception_handler`)가 아니라 미들웨어인 이유는 둘이다. 처리기는
        응답을 **대신 만들어야** 해서 지금의 본문이 바뀌고, 예외를 안 던지면서 5xx 를
        돌려주는 라우트는 아예 안 걸린다.

        Args:
            request: 들어온 요청.
            call_next: 다음 처리기.

        Returns:
            아래에서 만든 응답 그대로.

        Raises:
            Exception: 아래에서 난 것을 그대로 다시 던진다. 여기서 삼키면 클라이언트가
                받는 응답이 바뀌고, 그것은 기록 장치가 할 일이 아니다.
        """
        try:
            response: Response = await call_next(request)
        except Exception as error:
            save_api_error(
                get_pool(),
                request.url.path,
                request.method,
                SERVER_ERROR_FLOOR,
                f"{type(error).__name__}: {error}",
            )
            raise
        if response.status_code >= SERVER_ERROR_FLOOR:
            save_api_error(get_pool(), request.url.path, request.method, response.status_code, "")
        return response

    for module in (
        health,
        account,
        auth,
        ticket,
        run,
        meta,
        items,
        unseal,
        consumables,
        admin_bot_detail,
        maintenance,
        replay,
        skills,
        bestiary,
        world,
        auction,
        discovery,
        admin,
        admin_bots,
        admin_testers,
        admin_watch,
        catalog_admin,
        catalog_draft,
        content_admin,
        content_pack,
    ):
        server.include_router(module.router)
    return server


app = create_app()
