"""티켓 라우트 — **시드는 여기서만 나온다** (docs/설계/7_변조방지 T2).

요청이 시드를 받지 않는 것이 설계다. 받으면 유리한 시드가 나올 때까지 돌려 보고 그것만
제출할 수 있다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_core_version, get_pool
from game.api.schemas import TicketRequest, TicketResponse
from game.app.store.tickets import create_ticket

router = APIRouter()


@router.post("/api/ticket", response_model=TicketResponse)
def create_run_ticket(request: TicketRequest, account: CurrentAccount) -> TicketResponse:
    """런 티켓을 발급한다.

    Args:
        request: 방과 층. 시드는 받지 않는다.
        account: 토큰으로 푼 계정.

    Returns:
        발급된 티켓. 런의 입력 전부가 여기 있다.

    Raises:
        HTTPException: 없는 방인 경우.
    """
    if request.room_id not in get_context().rooms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"없는 방이다: {request.room_id}")
    ticket = create_ticket(
        get_pool(),
        account.account_id,
        request.room_id,
        get_core_version(),
        floor=request.floor,
    )
    return TicketResponse(**vars(ticket))
