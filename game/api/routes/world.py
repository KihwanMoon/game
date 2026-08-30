"""랭킹·데일리·능력치 배분 (F단계).

**랭킹은 코어 버전별로 갈린다** (결정 #06). 밸런스나 블록 목록이 바뀌면 과거 기록이
재현되지 않으므로, 한 표에 섞으면 검증할 수 없는 기록이 상위에 남는다.

점수는 **누적 경험치**다. 한 판의 성적이 아니라 얼마나 멀리 왔는가를 잰다.

데일리는 하루 한 번이고 **모두 같은 시드**를 받는다. 시드가 날짜에서 파생되므로 누구나
미리 계산할 수 있다 — 그것은 데일리의 성질이며, 남는 구멍은 "받아 두고 연습한 뒤 제출"
이다. 티켓 유효 기간을 짧게 잡아 그것을 좁힌다.
"""

import hashlib
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from psycopg_pool import ConnectionPool

from game.api.deps import TOKEN_HEADER, CurrentAccount, get_context, get_core_version, get_pool
from game.api.schemas import (
    AllocationRequest,
    LeaderboardResponse,
    ProgressResponse,
    TicketResponse,
)
from game.app.progression.levels import STAT_KEYS, check_allocation
from game.app.store.accounts import find_player_entity
from game.app.store.monsters import build_monster_snapshot, list_monsters, save_snapshots
from game.app.store.progress import (
    MODE_PRACTICE,
    list_leaderboard,
    read_progress,
    save_allocation,
)
from game.app.store.tickets import create_ticket
from game.schemas.monster_snapshot import build_snapshot_payload, sort_snapshots
from game.schemas.run_ticket import MAX_SEED, RunMode

router = APIRouter()

# 데일리 티켓 유효 기간. 짧게 잡는 이유는 "받아 두고 연습한 뒤 제출" 을 좁히기 위해서다 —
# 런 목표가 15~25분이므로 그 안에서 끝나야 한다.
DAILY_TTL = timedelta(minutes=40)

# 데일리 방. 지금은 하나이고, 층 사슬이 붙으면 날짜에서 방도 고른다.
DAILY_ROOM = "corridor"


def build_daily_seed(day: date, core_version: str) -> int:
    """그 날의 시드를 만든다.

    날짜와 코어 버전에서 파생한다 — **모두가 같은 시드를 받아야** 데일리가 성립한다.
    코어 버전을 섞는 이유는 밸런스가 바뀌면 같은 날짜라도 다른 판이 되어야 하기 때문이다.

    Args:
        day: 대상 날짜.
        core_version: 이 서버의 코어 버전.

    Returns:
        0 이상 MAX_SEED 이하의 정수.
    """
    digest = hashlib.sha256(f"{day.isoformat()}:{core_version}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (MAX_SEED + 1)


@router.get("/api/progress", response_model=ProgressResponse)
def read_player_progress(account: CurrentAccount) -> ProgressResponse:
    """내 레벨·경험치·능력치 배분을 본다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        성장 상태.
    """
    pool = get_pool()
    progress = read_progress(pool, find_player_entity(pool, account.account_id))
    return ProgressResponse(**vars(progress), stat_keys=list(STAT_KEYS))


@router.put("/api/progress/stats", response_model=ProgressResponse)
def save_player_stats(request: AllocationRequest, account: CurrentAccount) -> ProgressResponse:
    """능력치를 배분한다.

    **무엇을 여는지는 아직 정해지지 않았다** (미결 #51). 배분은 받아 두고, 변환표가
    정해지면 그것을 읽는 쪽이 생긴다.

    Args:
        request: 배분표.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 성장 상태.

    Raises:
        HTTPException: 포인트가 모자라거나 모르는 능력치인 경우.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    progress = read_progress(pool, entity_id)
    problem = check_allocation(request.stats, progress.level)
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    save_allocation(pool, entity_id, request.stats)
    return read_player_progress(account)


@router.get("/api/leaderboard", response_model=LeaderboardResponse)
def read_leaderboard(
    mode: str = MODE_PRACTICE,
    token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
) -> LeaderboardResponse:
    """순위표를 본다. 로그인하지 않아도 볼 수 있다.

    Args:
        mode: 순위표 종류.
        token: 기기 토큰. 없어도 된다 — 순위표는 공개다.

    Returns:
        이 시즌의 순위. `core_version` 이 시즌 이름이다.
    """
    core_version = get_core_version()
    return LeaderboardResponse(
        mode=mode,
        core_version=core_version,
        entries=list(list_leaderboard(get_pool(), mode, core_version)),
    )


@router.post("/api/daily", response_model=TicketResponse)
def create_daily_ticket(account: CurrentAccount) -> TicketResponse:
    """오늘의 데일리 티켓을 받는다. 하루 한 번이다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        데일리 티켓. 이미 받았으면 그때 것을 다시 준다.

    Raises:
        HTTPException: 데일리 방이 없는 경우.
    """
    pool = get_pool()
    context = get_context()
    if DAILY_ROOM not in context.rooms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"없는 방이다: {DAILY_ROOM}")

    today = date.today()
    core_version = get_core_version()
    with pool.connection() as connection:
        found = connection.execute(
            "SELECT t.id, t.seed, t.room_id, t.floor, t.mode, t.core_version"
            " FROM daily_entry d JOIN run_ticket t ON t.id = d.ticket_id"
            " WHERE d.account_id = %s AND d.day = %s",
            (account.account_id, today),
        ).fetchone()
    if found is not None:
        return TicketResponse(
            ticket_id=str(found[0]),
            seed=int(found[1]),
            room_id=str(found[2]),
            floor=int(found[3]),
            mode=str(found[4]),
            core_version=str(found[5]),
            monster_snapshot=[],
        )

    ticket = create_ticket(
        pool,
        account.account_id,
        DAILY_ROOM,
        core_version,
        mode=RunMode.DAILY,
        # 서버가 정한 값이다 — 클라이언트 제안이 아니므로 T2 와 무관하다.
        forced_seed=build_daily_seed(today, core_version),
        ttl=DAILY_TTL,
    )
    snapshots = build_daily_snapshots(pool, ticket.ticket_id, ticket.floor)
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO daily_entry (account_id, day, ticket_id) VALUES (%s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            (account.account_id, today, ticket.ticket_id),
        )
    return TicketResponse(**vars(ticket), monster_snapshot=snapshots)


def build_daily_snapshots(pool: ConnectionPool, ticket_id: str, floor: int) -> list[dict]:
    """데일리 티켓에도 지속 몬스터를 얼려 넣는다.

    연습과 같은 규칙이다 — 넣지 않으면 화면과 서버가 다른 판을 돈다.

    Args:
        pool: 연결 풀.
        ticket_id: 티켓 id.
        floor: 층.

    Returns:
        스냅샷 절들.
    """
    by_id = {kind["id"]: kind for kind in get_context().balance["enemies"]}
    snapshots = sort_snapshots(
        tuple(
            build_monster_snapshot(record, by_id[record.catalog_id])
            for record in list_monsters(pool, floor)
            if record.catalog_id in by_id
        )
    )
    save_snapshots(pool, ticket_id, snapshots)
    return [build_snapshot_payload(item) for item in snapshots]
