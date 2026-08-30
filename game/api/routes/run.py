"""제출 라우트 — 받아서 **다시 계산한다** (docs/설계/7_변조방지 §3·§4).

요청에 결과가 없다. 시드와 방도 받지 않는다 — 티켓이 들고 있다. 그래서 이 라우트가
저장하는 클라이언트 값은 규칙표 하나뿐이고, 그마저 서버에서 다시 검증된다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_pool
from game.api.schemas import SubmissionRequest, SubmissionResponse
from game.app.services.verify_run import VerifiedRun, check_submission_version, evaluate_submission
from game.app.store.runs import VERDICT_REJECTED, StoredResult, save_run_result, save_submission
from game.app.store.tickets import IssuedTicket, find_open_ticket, mark_ticket_consumed

router = APIRouter()


def build_rejection(detail: str) -> VerifiedRun:
    """거절 판정을 만든다.

    Args:
        detail: 거절 사유.

    Returns:
        거절로 채워진 판정.
    """
    return VerifiedRun("", 0, 0, VERDICT_REJECTED, detail)


def check_run_submission(request: SubmissionRequest, ticket: IssuedTicket) -> VerifiedRun:
    """제출 하나를 판정한다.

    코어 버전이 다르면 결과가 재현되지 않으므로 재시뮬하지 않고 거절한다. 이것은 변조가
    아니라 배포 시차일 가능성이 높으므로 사유를 그대로 남긴다.

    Args:
        request: 제출 요청.
        ticket: 이 제출이 쓰는 티켓.

    Returns:
        확정된 판정.
    """
    mismatch = check_submission_version(request.core_version, ticket.core_version)
    if mismatch:
        return build_rejection(mismatch)
    player = get_context().balance["player"]
    return evaluate_submission(
        get_context(),
        request.ruleset,
        ticket.room_id,
        ticket.seed,
        int(player["cpu_budget"]),
        int(player["rule_slots"]),
    )


@router.post("/api/run", response_model=SubmissionResponse)
def create_run_submission(
    request: SubmissionRequest, account: CurrentAccount
) -> SubmissionResponse:
    """제출을 받아 재시뮬하고 결과를 확정한다.

    Args:
        request: 티켓 id·규칙표·코어 버전. 결과는 없다.
        account: 토큰으로 푼 계정.

    Returns:
        서버가 확정한 결과.

    Raises:
        HTTPException: 쓸 수 없거나 이미 쓴 티켓인 경우.
    """
    pool = get_pool()
    ticket = find_open_ticket(pool, request.ticket_id, account.account_id)
    if ticket is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "쓸 수 없는 티켓이다")
    # 소비를 먼저 한다. 같은 티켓으로 두 번 제출하는 경쟁 상태를 여기서 끊는다 (T6).
    if not mark_ticket_consumed(pool, ticket.ticket_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 쓴 티켓이다")

    submission_id = save_submission(pool, ticket.ticket_id, request.ruleset, request.core_version)
    verified = check_run_submission(request, ticket)
    save_run_result(
        pool,
        StoredResult(
            submission_id=submission_id,
            outcome=verified.outcome,
            ticks=verified.ticks,
            player_hp=verified.player_hp,
            verdict=verified.verdict,
            detail=verified.detail,
        ),
    )
    return SubmissionResponse(submission_id=submission_id, **vars(verified))
