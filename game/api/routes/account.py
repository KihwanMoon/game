"""익명 계정 라우트.

가입 절차가 없다. 첫 요청에 계정이 생기고 토큰이 기기에 저장된다 — G1 판정 전이라
붙잡을 자산이 없고, 재미가 검증되기 전에 가입을 요구하면 이탈만 는다.
"""

from fastapi import APIRouter

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas import AccountResponse
from game.app.store.accounts import create_account
from game.app.store.credentials import read_login_id

router = APIRouter()


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
    return AccountResponse(
        account_id=account.account_id,
        handle=account.handle,
        login_id=read_login_id(get_pool(), account.account_id),
    )
