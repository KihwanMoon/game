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

from game.api.deps import TOKEN_HEADER, CurrentAccount, get_pool
from game.api.schemas import AccountResponse, CredentialRequest
from game.app.store.accounts import (
    apply_single_session,
    create_account,
    find_account,
    remove_device_token,
)
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
from game.app.store.throttle import (
    FAILURE_WINDOW,
    check_login_allowed,
    record_login_attempt,
)

router = APIRouter()

# 로그인 실패에 쓰는 단일 문구. 어느 쪽이 틀렸는지 말하지 않는다.
LOGIN_FAILED = "아이디나 비밀번호가 맞지 않는다"

# 잠겼을 때의 문구. 남은 시간을 초 단위로 말하지 않는다 — 정확한 창을 알려 주면 그
# 주기에 맞춰 시도하는 것이 쉬워진다.
LOGIN_LOCKED = f"시도가 너무 잦다. {int(FAILURE_WINDOW.total_seconds()) // 60}분 뒤에 다시 시도한다"


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
        HTTPException: 아이디나 비밀번호가 맞지 않거나, 시도가 너무 잦은 경우.
    """
    pool = get_pool()
    folded = normalize_login_id(request.login_id)
    # 세는 것을 비밀번호 확인보다 **먼저** 한다. 뒤에 두면 잠긴 뒤에도 scrypt 가 매번
    # 돌아, 제한이 있는데도 CPU 는 그대로 태워진다.
    if check_login_allowed(pool, folded).is_locked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, LOGIN_LOCKED)

    account = find_account_by_login(pool, request.login_id, request.password)
    record_login_attempt(pool, folded, account is not None)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_FAILED)
    token = create_device_token(pool, account.account_id)
    # **한 계정은 한 기기다.** 다른 기기의 토큰을 지운다 — 두 기기가 함께 돌면 같은
    # 계정의 상태가 두 벌 돌고, 나중에 저장한 쪽이 앞의 것을 덮는다.
    apply_single_session(pool, account.account_id, token)
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        token=token,
        login_id=read_login_id(pool, account.account_id),
    )


@router.post("/api/logout", response_model=AccountResponse)
def create_logout(
    account: CurrentAccount,
    token: Annotated[str, Header(alias=TOKEN_HEADER)],
) -> AccountResponse:
    """이 기기의 토큰을 지운다.

    **계정은 안 지운다.** 로그아웃은 이 기기가 그 계정을 그만 보는 것이지 계정이
    사라지는 것이 아니다 — 다시 로그인하면 그대로 있다.

    Args:
        account: 토큰으로 푼 계정.
        token: 지울 평문 토큰.

    Returns:
        지운 계정. 토큰 자리는 비어 있다 — 더 이상 쓸 수 없는 값을 돌려주지 않는다.
    """
    remove_device_token(get_pool(), token)
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        token="",
        login_id=read_login_id(get_pool(), account.account_id),
    )
