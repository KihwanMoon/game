"""가입과 로그인 (승격 경로).

**익명 계정을 버리지 않는다.** 토큰을 들고 가입하면 그 계정에 자격증명이 붙고, 계정 id 가
그대로라 세이브·티켓·제출이 전부 따라온다. 토큰 없이 가입하면 새 계정이 생긴다.

로그인은 **새 기기 토큰을 발급한다.** 기존 토큰을 지우지 않으므로 두 기기를 함께 쓸 수
있다 — 로그인했다고 다른 기기가 튕기면 그것은 보안이 아니라 고장으로 읽힌다.

모르는 아이디와 틀린 비밀번호를 같은 오류로 낸다. 가르면 어느 아이디가 존재하는지
알려 주는 조회 도구가 된다.
"""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from game.api.deps import TOKEN_HEADER, get_pool
from game.api.schemas import AccountResponse, CredentialRequest
from game.app.store.accounts import create_account, find_account
from game.app.store.credentials import (
    check_account_has_login,
    check_credentials,
    create_device_token,
    find_account_by_login,
    find_login_owner,
    normalize_login_id,
    read_login_id,
    register_login,
)

router = APIRouter()

# 로그인 실패에 쓰는 단일 문구. 어느 쪽이 틀렸는지 말하지 않는다.
LOGIN_FAILED = "아이디나 비밀번호가 맞지 않는다"


@router.post("/api/register", response_model=AccountResponse)
def register_account(
    request: CredentialRequest,
    token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
) -> AccountResponse:
    """가입한다. 토큰을 들고 오면 그 익명 계정을 승격시킨다.

    Args:
        request: 아이디와 비밀번호.
        token: 지금 쓰고 있는 기기 토큰. 없으면 새 계정을 만든다.

    Returns:
        가입된 계정과 기기 토큰.

    Raises:
        HTTPException: 형식을 어겼거나, 이미 가입된 계정이거나, 아이디가 이미 쓰이는 경우.
    """
    problem = check_credentials(request.login_id, request.password)
    if problem is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem.message)

    pool = get_pool()
    if find_login_owner(pool, request.login_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 쓰이는 아이디다")

    existing = find_account(pool, token) if token else None
    if existing is not None:
        if check_account_has_login(pool, existing.account_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "이 계정은 이미 가입돼 있다")
        # 승격. 계정 id 가 그대로이므로 지금까지의 진행이 전부 따라온다.
        register_login(pool, existing.account_id, request.login_id, request.password)
        return AccountResponse(
            account_id=existing.account_id,
            handle=existing.handle,
            token=token,
            login_id=normalize_login_id(request.login_id),
        )

    account, fresh_token = create_account(pool)
    register_login(pool, account.account_id, request.login_id, request.password)
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        token=fresh_token,
        login_id=normalize_login_id(request.login_id),
    )


@router.post("/api/login", response_model=AccountResponse)
def create_login_session(request: CredentialRequest) -> AccountResponse:
    """로그인해서 이 기기용 토큰을 받는다.

    Args:
        request: 아이디와 비밀번호.

    Returns:
        계정과 새 기기 토큰.

    Raises:
        HTTPException: 아이디나 비밀번호가 맞지 않는 경우.
    """
    pool = get_pool()
    account = find_account_by_login(pool, request.login_id, request.password)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        token=create_device_token(pool, account.account_id),
        login_id=read_login_id(pool, account.account_id),
    )
