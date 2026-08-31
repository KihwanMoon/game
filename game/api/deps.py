"""서버가 프로세스 수명 동안 들고 있는 것과 요청마다 푸는 것.

밸런스·카탈로그·방을 요청마다 다시 읽으면 재시뮬 94ms 가 파일 I/O 시간이 된다. 한 번
읽어 여기 둔다.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from psycopg_pool import ConnectionPool

from game.app.content_versions import read_content_versions
from game.app.items.catalog import load_item_catalog
from game.app.services.run_battle import load_balance
from game.app.services.verify_run import VerifyContext
from game.app.store.accounts import Account, find_account
from game.app.store.admin import check_is_admin
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ITEMS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets
from game.schemas.run_ticket import build_core_version

# 인증 헤더. Bearer 를 쓰지 않는 이유는 이것이 OAuth 토큰이 아니기 때문이다 — 기기에
# 저장된 익명 계정 열쇠이며, 승격 경로가 생기면 그때 표준 형식으로 옮긴다.
TOKEN_HEADER = "X-Game-Token"

_state: dict[str, object] = {}


def build_verify_context() -> VerifyContext:
    """검증에 쓸 자원을 한 번 읽는다.

    Returns:
        밸런스·카탈로그·방·적 규칙표가 실린 문맥.
    """
    return VerifyContext(
        balance=load_balance(BALANCE_PATH),
        catalog=load_block_catalog(BLOCKS_PATH),
        rooms={item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)},
        enemy_rulesets=load_rulesets(ENEMY_RULESETS_PATH),
    )


def init_state(pool: ConnectionPool) -> None:
    """프로세스 상태를 채운다. 서버가 뜰 때 한 번만 부른다.

    Args:
        pool: 열린 연결 풀.
    """
    context = build_verify_context()
    _state["pool"] = pool
    _state["items"] = load_item_catalog(ITEMS_PATH)
    _state["context"] = context
    _state["core_version"] = build_core_version(read_content_versions())


def get_pool() -> ConnectionPool:
    """열린 연결 풀을 준다.

    Returns:
        연결 풀.
    """
    pool: ConnectionPool = _state["pool"]  # type: ignore[assignment]
    return pool


def get_context() -> VerifyContext:
    """검증 문맥을 준다.

    Returns:
        검증 문맥.
    """
    context: VerifyContext = _state["context"]  # type: ignore[assignment]
    return context


def get_core_version() -> str:
    """이 서버가 도는 코어 버전.

    Returns:
        `b4.v3.e1` 형태의 문자열. 아직 준비되지 않았으면 빈 문자열.
    """
    return str(_state.get("core_version", ""))


def resolve_account(token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None) -> Account:
    """토큰에서 계정을 찾는다.

    Args:
        token: 요청 헤더의 기기 토큰.

    Returns:
        찾은 계정.

    Raises:
        HTTPException: 토큰이 없거나 모르는 토큰인 경우.
    """
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 없다")
    account = find_account(get_pool(), token)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "모르는 토큰이다")
    return account


CurrentAccount = Annotated[Account, Depends(resolve_account)]


def resolve_admin(account: CurrentAccount) -> Account:
    """관리자만 통과시킨다.

    **403 이 아니라 404 로 답한다.** 403 은 "여기 뭔가 있는데 너는 못 본다" 를 알려 주고,
    그것은 관리자 경로의 존재 자체를 노출한다 — 없는 것처럼 보이는 편이 낫다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        관리자 계정.

    Raises:
        HTTPException: 관리자가 아닌 경우.
    """
    if not check_is_admin(get_pool(), account.account_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 경로다")
    return account


CurrentAdmin = Annotated[Account, Depends(resolve_admin)]


def get_item_catalog() -> dict:
    """아이템 카탈로그를 준다.

    Returns:
        catalog_id 에서 항목으로의 대응표.
    """
    catalog: dict = _state["items"]  # type: ignore[assignment]
    return catalog
