"""제출이 남기는 알림 (2026-09-25).

`routes/run.py` 가 제출을 확정한 뒤 **그 결과를 알림 한 건으로 적는다.** 보상 줄은
`apply_run_rewards` 가 만든 그대로 본문에 넣는다 — 화면이 다시 짜면 실제로 들어온 것과
다른 말을 한다.

**방 하나를 이긴 것은 안 적는다.** 방은 3초마다 넘어가므로 방마다 적으면 알림이 판을
따라잡지 못하고 쌓이기만 한다. 층 정산과 판 종료가 보상이 들어오는 단위이고, 제출도 그
단위로만 온다.
"""

from game.api.deps import get_context, get_pool
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.store.notices import (
    KIND_FLOOR,
    KIND_RECORD,
    KIND_REJECTED,
    KIND_RUN,
    save_notice,
)
from game.app.store.tickets import IssuedTicket
from game.schemas.run_ticket import RunMode

# 판의 성격을 제목 머리에 붙인다. 연습은 기본이라 안 붙인다 — 붙이면 모든 알림이 같은
# 말로 시작해 눈이 제목을 못 훑는다.
MODE_PREFIX = {str(RunMode.DAILY): "오늘의 도전 · ", str(RunMode.RECORD): "기록 도전 · "}


def build_run_title(ticket: IssuedTicket, verified: VerifiedRun, claimed: int) -> tuple[str, str]:
    """제출 결과의 알림 종류와 제목을 정한다.

    Args:
        ticket: 이 제출의 티켓.
        verified: 서버가 확정한 결과.
        claimed: 이번에 확정한 층. 0 이면 하강 전체다.

    Returns:
        (종류, 제목).
    """
    prefix = MODE_PREFIX.get(ticket.mode, "")
    if verified.verdict != VERDICT_VERIFIED:
        return KIND_REJECTED, f"{prefix}서버가 이 판을 인정하지 않았다"
    is_won = verified.outcome == OUTCOME_PLAYER_WIN
    if ticket.mode == str(RunMode.RECORD):
        room = get_context().rooms.get(ticket.room_id)
        name = room.label_ko if room is not None and room.label_ko else ticket.room_id
        return KIND_RECORD, f"{prefix}{name} — {'이겼다' if is_won else '졌다'}"
    if claimed > 0:
        if is_won:
            return KIND_FLOOR, f"{prefix}{claimed}장 돌파"
        return KIND_RUN, f"{prefix}{claimed}장에서 쓰러졌다"
    return KIND_RUN, f"{prefix}판 종료 — {'이겼다' if is_won else '졌다'}"


def apply_run_notice(
    account_id: int, ticket: IssuedTicket, verified: VerifiedRun, reward: str, claimed: int
) -> None:
    """제출 결과를 알림 한 건으로 적는다.

    **반려도 적는다.** 서버가 판을 인정하지 않은 것은 치트의 증거가 아니라 대개 두 코어가
    갈린 것이고(설계/7 §8), 그 사실이 조용히 사라지면 보상이 왜 안 들어왔는지 모른다.

    Args:
        account_id: 제출한 계정.
        ticket: 이 제출의 티켓.
        verified: 서버가 확정한 결과.
        reward: 보상 줄. 반려면 빈 문자열이고, 그때는 반려 사유를 본문에 둔다.
        claimed: 이번에 확정한 층.
    """
    kind, title = build_run_title(ticket, verified, claimed)
    body = verified.detail if kind == KIND_REJECTED else reward
    save_notice(get_pool(), account_id, kind, title, body)
