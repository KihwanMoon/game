"""구글 로그인 — 승격과 로그인을 한 문으로 받는다 (2026-09-16).

`auth.py` 에서 갈라 두었다. 저쪽은 **아이디와 비밀번호**이고 여기는 **남이 서명한 신원**
이다. 검증하는 것도 실패하는 모양도 다르다.

**세 규율을 그대로 탄다.**

1. **익명으로 시작해 승격된다.** 토큰을 들고 오면 그 계정의 빈 칸에 구글을 채운다 —
   계정 id 가 안 바뀌므로 지금까지의 진행이 전부 따라온다.
2. **한 계정은 한 기기다.** 로그인이 그 계정의 다른 기기 토큰을 지운다.
3. **클라이언트가 보낸 것을 안 믿는다.** 이메일도 이름도 안 받는다 — 받는 것은 구글이
   서명한 토큰 하나이고, 서버가 그 서명을 직접 본다 (설계/7_변조방지 §4).

**이메일로 계정을 잇지 않는다.** 아이디·비밀번호로 가입한 사람이 같은 이메일의 구글로
들어와도 **새 계정**이 된다. 이메일이 같다는 것은 같은 사람이라는 증거가 아니고(이메일은
재사용된다), 그것으로 이으면 남의 계정을 가져가는 길이 열린다. 이미 로그인한 사람이
**직접 연결**하는 길만 둔다 — 그때는 두 자격증명이 한 계정에 함께 붙는다.
"""

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from psycopg_pool import ConnectionPool

from game.api.deps import TOKEN_HEADER, get_pool
from game.api.google_identity import read_client_id, resolve_google_subject
from game.api.schemas import (
    AccountResponse,
    GoogleAuthRequest,
    GoogleConfigResponse,
    NonceResponse,
)
from game.app.store.accounts import apply_single_session, create_account, find_account
from game.app.store.credentials import create_device_token, read_login_id
from game.app.store.google_link import (
    apply_google_link,
    apply_nonce_use,
    check_account_has_google,
    create_auth_nonce,
    find_google_owner,
)

router = APIRouter()

OFF_MESSAGE = "구글 로그인이 켜져 있지 않다"
NONCE_MESSAGE = "로그인 요청이 만료됐다 — 다시 눌러 달라"
# **무엇이 틀렸는지 자세히 말하지 않는다.** 어디까지 맞췄는지 알려 주는 셈이다.
TOKEN_MESSAGE = "구글 계정을 확인하지 못했다"
LINKED_MESSAGE = "이 계정에는 이미 다른 구글 계정이 연결돼 있다"


@router.get("/api/auth/google/config", response_model=GoogleConfigResponse)
def read_google_config() -> GoogleConfigResponse:
    """구글 로그인이 켜져 있는지와 클라이언트 id 를 낸다.

    **논스를 여기서 안 낸다.** 이 경로는 화면이 뜰 때마다 불리는데, 부를 때마다 논스를
    남기면 표가 아무 목적 없이 자란다 — 논스는 실제로 버튼을 누를 때 받는다.

    Returns:
        켜짐 여부와 클라이언트 id. 꺼져 있으면 id 는 빈 문자열이다.
    """
    client_id = read_client_id()
    return GoogleConfigResponse(is_enabled=bool(client_id), client_id=client_id)


@router.get("/api/auth/google/nonce", response_model=NonceResponse)
def read_auth_nonce() -> NonceResponse:
    """일회용 논스를 받는다.

    **가로챈 토큰을 다시 보내는 것을 막는 유일한 자리다.** 서명은 남의 토큰에서도 맞으므로,
    한 번 쓰면 사라지는 값이 없으면 재생이 통과한다.

    Returns:
        논스. 구글 버튼에 그대로 넘긴다.

    Raises:
        HTTPException: 구글 로그인이 꺼져 있는 경우.
    """
    if not read_client_id():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, OFF_MESSAGE)
    return NonceResponse(nonce=create_auth_nonce(get_pool()))


@router.post("/api/auth/google", response_model=AccountResponse)
def create_google_session(
    request: GoogleAuthRequest,
    token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
) -> AccountResponse:
    """구글로 들어온다. 처음이면 승격하거나 새로 만들고, 아니면 로그인한다.

    Args:
        request: 구글이 준 ID 토큰과 서버가 발급했던 논스.
        token: 지금 쓰고 있는 기기 토큰. 있으면 그 익명 계정을 승격시킨다.

    Returns:
        계정과 기기 토큰.

    Raises:
        HTTPException: 구글 로그인이 꺼져 있거나, 논스가 만료됐거나, 토큰이 어긋나거나,
            이미 다른 구글 계정이 연결된 계정인 경우.
    """
    client_id = read_client_id()
    if not client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, OFF_MESSAGE)
    pool = get_pool()
    # **논스를 먼저 쓴다.** 검증 뒤에 쓰면 실패한 시도가 논스를 남기고, 같은 논스로
    # 몇 번이고 다시 시도할 수 있게 된다.
    if not apply_nonce_use(pool, request.nonce):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, NONCE_MESSAGE)
    try:
        subject = resolve_google_subject(request.credential, client_id, request.nonce)
    except ValueError as error:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, TOKEN_MESSAGE) from error

    owner = find_google_owner(pool, subject)
    if owner != 0:
        return build_session(pool, owner)
    existing = find_account(pool, token) if token else None
    if existing is None:
        account, fresh_token = create_account(pool)
        apply_google_link(pool, account.account_id, subject)
        return AccountResponse(
            account_id=account.account_id, handle=account.handle, token=fresh_token, login_id=None
        )
    if check_account_has_google(pool, existing.account_id):
        raise HTTPException(status.HTTP_409_CONFLICT, LINKED_MESSAGE)
    apply_google_link(pool, existing.account_id, subject)
    return AccountResponse(
        account_id=existing.account_id,
        handle=existing.handle,
        token=token,
        login_id=read_login_id(pool, existing.account_id),
    )


def build_session(pool: ConnectionPool, account_id: int) -> AccountResponse:
    """그 계정으로 이 기기를 만든다 — **다른 기기는 끊긴다**.

    아이디·비밀번호 로그인과 같은 규율이다 (`auth.create_login_session`). 같은 계정이 두
    기기에서 돌면 상태가 두 벌 돌고, 나중에 저장한 쪽이 앞의 것을 덮는다.

    Args:
        pool: 연결 풀.
        account_id: 들어온 계정.

    Returns:
        계정과 새 기기 토큰.

    Raises:
        HTTPException: 계정을 다시 읽지 못한 경우.
    """
    fresh_token = create_device_token(pool, account_id)
    apply_single_session(pool, account_id, fresh_token)
    account = find_account(pool, fresh_token)
    if account is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "계정을 읽지 못했다")
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        token=fresh_token,
        login_id=read_login_id(pool, account.account_id),
    )
