"""익명 계정 라우트.

가입 절차가 없다. 첫 요청에 계정이 생기고 토큰이 기기에 저장된다 — G1 판정 전이라
붙잡을 자산이 없고, 재미가 검증되기 전에 가입을 요구하면 이탈만 는다.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas import AccountResponse
from game.app.store.accounts import Account, create_account
from game.app.store.credentials import read_login_id
from game.app.store.doppels import apply_doppel_opt_in, check_doppel_opt_in

router = APIRouter()


def build_account_response(pool: object, account: Account) -> AccountResponse:
    """계정 하나를 응답 모양으로 만든다.

    **토큰은 안 싣는다.** 만들 때와 로그인할 때만 나온다.

    Args:
        pool: 연결 풀.
        account: 토큰으로 푼 계정.

    Returns:
        계정 응답.
    """
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        login_id=read_login_id(pool, account.account_id),
        doppel_opt_in=check_doppel_opt_in(pool, account.account_id),
    )


@router.post("/api/account", response_model=AccountResponse)
def create_anonymous_account() -> AccountResponse:
    """익명 계정을 만든다.

    Returns:
        계정과 **평문 토큰**. 토큰은 이 응답에서만 나오고 서버는 해시만 갖는다.
    """
    account, token = create_account(get_pool())
    return AccountResponse(account_id=account.account_id, handle=account.handle, token=token)


@router.get("/api/account", response_model=AccountResponse)
def read_account(account: CurrentAccount) -> AccountResponse:
    """토큰이 가리키는 계정을 본다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        계정. 토큰은 다시 내주지 않는다.
    """
    return build_account_response(get_pool(), account)


class DoppelOptInRequest(BaseModel):
    """내 그림자를 세울지 정한다."""

    is_on: bool


@router.put("/api/account/doppel", response_model=AccountResponse)
def save_doppel_opt_in(request: DoppelOptInRequest, account: CurrentAccount) -> AccountResponse:
    """내 빌드가 남의 던전에 그림자로 서도 되는지 정한다 (2026-09-06).

    **기본은 꺼져 있다.** 그림자는 원본의 규칙표로 싸우므로, 관전하며 행동을 보면 남의
    해답이 어느 정도 역산된다 — 켜는 사람이 알고 켜야 하는 대가다.

    **이미 선 그림자는 안 지운다.** 끄는 것은 「앞으로 안 세운다」이고, 지우는 것은 남의
    던전에서 개체가 사라지는 일이라 뜻이 다르다.

    Args:
        request: 켤지 끌지.
        account: 토큰으로 푼 계정.

    Returns:
        바뀐 뒤의 계정.
    """
    pool = get_pool()
    apply_doppel_opt_in(pool, account.account_id, request.is_on)
    return build_account_response(pool, account)
