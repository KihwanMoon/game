"""내 판을 다시 돌려 본다 (결정 #09).

**기록을 트는 것이 아니라 다시 돌리는 것이다.** 이벤트 로그는 저장하지 않는다 — 남는
것은 제출(규칙표)과 판정(결과)뿐이다. 그런데 코어가 결정론이라(R5·G3) 같은 입력이면
같은 판이 나오므로, 시드·방·층·로드아웃·스냅샷을 그대로 넣고 브라우저에서 다시 돌리면
그때 그 판이 눈앞에 다시 선다.

**관리자 경로에서 갈라 나왔다.** 저쪽은 남의 판을 보는 일이라 관리자만 열 수 있고,
여기는 **내 판만** 본다 — 같은 라우트에 권한만 느슨하게 걸면 제출 id 를 훑어 남의
규칙표를 읽는 길이 된다. 그래서 조회 자체에 `account_id` 를 건다.

**클라이언트가 보낸 것은 하나도 안 실린다** (설계/7_변조방지 §4). 여기서 나가는 값은
전부 티켓이 얼려 둔 것이고, 그것이 재현을 재현이게 한다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas_replay import ReplayResponse, RunHistoryResponse, RunHistoryRow
from game.app.store.monster_snapshots import load_snapshots
from game.app.store.runs import list_recent_runs

router = APIRouter()

# 목록에 낼 판 수. 열 판이면 「최근에 무엇을 했는지」가 보이고, 그보다 길면 고르는 일이
# 된다 — 고르게 하려면 검색이 필요하고 그것은 다른 기능이다.
HISTORY_LIMIT = 10


@router.get("/api/runs", response_model=RunHistoryResponse)
def read_run_history(account: CurrentAccount) -> RunHistoryResponse:
    """내가 최근에 돈 판들을 새것부터 읽는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        최근 판들. 없으면 빈 목록이다.
    """
    rows = list_recent_runs(get_pool(), account.account_id, HISTORY_LIMIT)
    return RunHistoryResponse(runs=[RunHistoryRow(**vars(row)) for row in rows])


@router.get("/api/replay", response_model=ReplayResponse)
def read_own_replay(submission_id: int, account: CurrentAccount) -> ReplayResponse:
    """내 판 하나를 다시 돌릴 입력을 읽는다.

    **`account_id` 를 조회에 건다.** 찾고 나서 주인을 보면 「없다」와 「남의 것이다」가
    다른 응답이 되고, 그 차이만으로 남의 제출 id 범위를 훑을 수 있다.

    Args:
        submission_id: 볼 제출.
        account: 토큰으로 푼 계정.

    Returns:
        그 판을 재현할 입력 전부와 그때의 결과.

    Raises:
        HTTPException: 없거나 내 것이 아니면 404.
    """
    pool = get_pool()
    with pool.connection() as connection:
        found = connection.execute(
            "SELECT s.id, s.ruleset, t.id, t.room_id, t.seed, t.floor,"
            " COALESCE(t.rooms_per_floor, 0), t.room_ids, t.loadout,"
            " COALESCE(r.outcome, ''), COALESCE(r.ticks, 0), COALESCE(r.player_hp, 0)"
            " FROM run_submission s"
            " JOIN run_ticket t ON t.id = s.ticket_id"
            " LEFT JOIN run_result r ON r.submission_id = s.id"
            " WHERE s.id = %s AND t.account_id = %s",
            (submission_id, account.account_id),
        ).fetchone()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 제출이다: {submission_id}")
    return ReplayResponse(
        submission_id=int(found[0]),
        ruleset=dict(found[1] or {}),
        room_id=str(found[3] or ""),
        seed=int(found[4] or 0),
        floor=int(found[5] or 1),
        rooms_per_floor=int(found[6] or 0),
        room_ids=list(found[7] or []),
        loadout=dict(found[8] or {}),
        snapshots=[vars(one) for one in load_snapshots(pool, str(found[2]))],
        outcome=str(found[9] or ""),
        ticks=int(found[10] or 0),
        player_hp=int(found[11] or 0),
    )
