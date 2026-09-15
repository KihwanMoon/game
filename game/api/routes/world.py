"""랭킹·데일리·능력치 배분 (F단계).

**랭킹은 코어 버전별로 갈린다** (결정 #06). 밸런스나 블록 목록이 바뀌면 과거 기록이
재현되지 않으므로, 한 표에 섞으면 검증할 수 없는 기록이 상위에 남는다.

점수는 **누적 경험치**다. 한 판의 성적이 아니라 얼마나 멀리 왔는가를 잰다.

데일리는 하루 한 번이고 **모두 같은 시드**를 받는다. 시드가 날짜에서 파생되므로 누구나
미리 계산할 수 있다 — 그것은 데일리의 성질이며, 남는 구멍은 "받아 두고 연습한 뒤 제출"
이다. 티켓 유효 기간을 짧게 잡아 그것을 좁힌다.
"""

import hashlib
import json
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from psycopg_pool import ConnectionPool

from game.api.deps import TOKEN_HEADER, CurrentAccount, get_context, get_core_version, get_pool
from game.api.loadout_service import build_ticket_loadout
from game.api.schemas import (
    AllocationRequest,
    LeaderboardResponse,
    ProgressResponse,
    TicketResponse,
)
from game.api.schemas_doppel import (
    DoppelBout,
    DoppelRetirement,
    DoppelStanding,
    MyDoppelResponse,
)
from game.app.progression.floors import read_floor_cap
from game.app.progression.levels import STAT_KEYS, check_allocation
from game.app.store.accounts import find_player_entity
from game.app.store.doppel_bouts import (
    MODE_DOPPEL,
    count_bouts,
    list_bouts,
    list_doppel_leaderboard,
    list_my_doppels,
    list_retired_doppels,
)
from game.app.store.doppels import check_doppel_opt_in
from game.app.store.monster_snapshots import build_monster_snapshot, save_snapshots
from game.app.store.monsters import list_monsters
from game.app.store.progress import (
    MODE_PRACTICE,
    list_leaderboard,
    read_progress,
    read_reached_floor,
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
    return ProgressResponse(
        **vars(progress),
        stat_keys=list(STAT_KEYS),
        reached_floor=read_reached_floor(pool, progress.entity_id),
        floor_cap=read_floor_cap(get_context().balance),
        loadout=build_ticket_loadout(account.account_id),
    )


@router.put("/api/progress/stats", response_model=ProgressResponse)
def save_player_stats(request: AllocationRequest, account: CurrentAccount) -> ProgressResponse:
    """능력치를 배분한다.

    **되돌릴 수 없다.** 무엇을 여는지는 `progression/attributes.py` 가 정하며 (결정 #51),
    다음 런의 티켓 로드아웃에 반영된다 — 이미 발급한 티켓은 바뀌지 않는다.

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
        mode: 순위표 종류. `doppel` 이면 둔갑 승수 판이고, 그 밖에는 누적 경험치 판이다.
        token: 기기 토큰. 없어도 된다 — 순위표는 공개다.

    Returns:
        이 시즌의 순위. `core_version` 이 시즌 이름이다.
    """
    core_version = get_core_version()
    # **재는 것이 다르면 판이 달라야 한다.** 누적 경험치는 얼마나 멀리 왔는가라 오래 돌린
    # 쪽이 이기고, 둔갑 승수는 **내가 없는 동안 내 규칙표가 버틴 횟수**다 — 하나로 합치면
    # 둘 다 뜻을 잃는다. 기존 판을 안 없애는 이유는 둔갑을 안 켠 사람이 순위표에서
    # 통째로 사라지지 않게 하기 위해서다.
    if mode == MODE_DOPPEL:
        return LeaderboardResponse(
            mode=mode,
            core_version=core_version,
            entries=list(list_doppel_leaderboard(get_pool(), core_version)),
        )
    return LeaderboardResponse(
        mode=mode,
        core_version=core_version,
        entries=list(list_leaderboard(get_pool(), mode, core_version)),
    )


# 최근 전적으로 낼 줄 수. **열 줄이면 「요즘 어땠나」가 보이고, 그보다 길면 읽는 일이
# 아니라 훑는 일이 된다** — 지나간 판 목록과 같은 눈금이다.
BOUT_LIMIT = 10


@router.get("/api/doppels/mine", response_model=MyDoppelResponse)
def read_my_doppels(account: CurrentAccount) -> MyDoppelResponse:
    """내 둔갑이 지금 어디 서 있고 무엇을 했는지 본다.

    **이 게임의 거의 모든 축이 나를 따라온다** — 층 스케일도, 둔갑의 레벨도, 선공도.
    그래서 세져도 체감이 같고, 순위는 누적 경험치라 오래 돌린 쪽이 앞선다. 「내가 잘
    적었다」가 쌓이는 자리가 없었다.

    내 빌드가 남의 장에 서서 누구를 만나고 이겼는지는 **성장과 무관한 사실**이다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        서 있는 둔갑들과 전적. 그림자를 안 세우기로 한 계정이면 전부 비어 있고
        `is_opted_in` 이 거짓이다 — **비어 있는 것과 끄고 있는 것은 다르다.**
    """
    pool = get_pool()
    met, won = count_bouts(pool, account.account_id)
    return MyDoppelResponse(
        standing=[DoppelStanding(**one) for one in list_my_doppels(pool, account.account_id)],
        met=met,
        won=won,
        recent=[DoppelBout(**one) for one in list_bouts(pool, account.account_id, BOUT_LIMIT)],
        # **셈이 끝난 것을 따로 낸다.** 활자는 이길 때가 아니라 물러날 때 들어오므로,
        # 안 적으면 「이겼는데 활자가 안 늘었다」로 보인다 (2026-09-15).
        retired=[
            DoppelRetirement(**one)
            for one in list_retired_doppels(pool, account.account_id, BOUT_LIMIT)
        ],
        is_opted_in=check_doppel_opt_in(pool, account.account_id),
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
            "SELECT t.id, t.seed, t.room_id, t.floor, t.mode, t.core_version, t.loadout"
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
            loadout=json.loads(found[6]) if isinstance(found[6], str) else found[6],
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
        loadout=build_ticket_loadout(account.account_id),
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
