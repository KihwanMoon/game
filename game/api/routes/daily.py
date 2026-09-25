"""오늘의 도전 — 하루 한 판, 모두가 같은 하강 (`world.py` 에서 갈라 나왔다, 2026-09-25).

**데일리는 한 번도 안 돌았다** (2026-09-25 에 드러났다). 버튼은 티켓을 받아 두기만 하고
출격은 늘 새 연습 티켓을 받았다. 받은 데일리 티켓을 돌렸더라도, 방 하나를 다섯 번 잇고
층 수가 0 이라 층 청구가 성립하지 않아 `cleared_floor` 가 영영 0 이었다 — 순위표는 전원
「받아 둠」이었다.

그래서 데일리를 **진짜 하강**으로 낸다. 방은 그날의 시드에서 결정적으로 고르므로 누구나
같은 방을 같은 순서로 돌고, 층 수가 있으니 층을 깰 때마다 순위에 남는다.

시드가 날짜에서 파생되므로 누구나 미리 계산할 수 있다 — 그것은 데일리의 성질이며, 남는
구멍은 「받아 두고 연습한 뒤 제출」이다. 티켓 유효 기간을 짧게 잡아 그것을 좁힌다.
"""

import hashlib
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_core_version, get_pool
from game.api.loadout_service import build_ticket_loadout
from game.api.schemas import TicketResponse
from game.api.schemas_world import DailyBoardResponse, DailyRow
from game.app.core.rng import DeterministicRng
from game.app.progression.floors import FIRST_FLOOR, read_floor_bosses, read_floor_cap
from game.app.services.build_chain import build_descent
from game.app.store.daily_board import count_daily_players, list_daily_board, read_daily_entry
from game.app.store.tickets import CHAIN_LENGTH, create_ticket, find_open_ticket
from game.schemas.run_ticket import MAX_SEED, RunMode

router = APIRouter()

# 데일리 티켓 유효 기간. 짧게 잡는 이유는 「받아 두고 연습한 뒤 제출」을 좁히기 위해서다 —
# 런 목표가 15~25분이므로 그 안에서 끝나야 한다.
DAILY_TTL = timedelta(minutes=40)

# 데일리의 첫 방. 이후 방은 그날의 시드가 고른다.
DAILY_ROOM = "corridor"

# 방을 고르는 난수 축의 이름. 전투 난수와 갈라 둔다 — 한 축의 호출 횟수가 바뀔 때 다른
# 축까지 흔들리면 같은 날의 판이 서버 배포 한 번에 달라진다 (CLAUDE.md 불변 조건).
ROOM_STREAM = "daily_rooms"


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


def build_daily_rooms(seed: int) -> tuple[str, ...]:
    """그날의 하강 방 목록을 시드에서 결정적으로 고른다.

    **`secrets` 로 고르면 사람마다 다른 방을 돈다** — 같은 시드여도 방이 다르면 같은 판이
    아니다. 여기서는 그날의 시드로 난수 축을 하나 세워 고른다.

    Args:
        seed: 그날의 시드.

    Returns:
        1장부터 마지막 장까지의 방 id 들.
    """
    context = get_context()
    return build_descent(
        context.rooms,
        FIRST_FLOOR,
        DAILY_ROOM,
        CHAIN_LENGTH,
        read_floor_cap(context.balance),
        read_floor_bosses(context.balance),
        DeterministicRng(seed).create_stream(ROOM_STREAM).get_below,
    )


@router.get("/api/daily", response_model=DailyBoardResponse)
def read_daily_board(account: CurrentAccount) -> DailyBoardResponse:
    """오늘의 도전 상태를 읽는다 — 내 것과 남의 것.

    **내 자리는 윗자리 밖에서도 찾는다.** 스무 줄 안에 없다고 내 기록을 안 보여 주면,
    잘 못한 사람에게는 이 표가 남의 것만 적힌 종이가 된다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        오늘의 순위와 내 자리.
    """
    pool = get_pool()
    today = date.today()
    rows = list_daily_board(pool, today)
    mine = read_daily_entry(pool, today, account.account_id)
    my_rank = 0
    for row in rows:
        if row["account_id"] == account.account_id:
            my_rank = row["rank"]
    return DailyBoardResponse(
        day=today.isoformat(),
        players=count_daily_players(pool, today),
        rows=[DailyRow(**row) for row in rows],
        has_entry=mine is not None,
        my_floor=0 if mine is None else mine["floor"],
        my_rank=my_rank,
    )


@router.post("/api/daily", response_model=TicketResponse)
def create_daily_ticket(account: CurrentAccount) -> TicketResponse:
    """오늘의 데일리 티켓을 받는다. 하루 한 번이다.

    **지속 몬스터·그림자를 세우지 않는다.** 그것들은 시간에 따라, 사람에 따라 다른 적을
    만든다 — 「오늘 모두가 같은 판」이 그 순간 깨진다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        데일리 티켓. 이미 받았고 아직 도는 중이면 그 티켓을 다시 준다.

    Raises:
        HTTPException: 데일리 방이 없거나, 오늘 판을 이미 끝냈거나 시간이 지난 경우.
    """
    pool = get_pool()
    if DAILY_ROOM not in get_context().rooms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"없는 방이다: {DAILY_ROOM}")

    today = date.today()
    entry = read_daily_entry(pool, today, account.account_id)
    if entry is not None:
        # **아직 한 층도 안 낸 판만 다시 준다.** 끝났거나 시간이 지났으면 안 준다 — 하루 한
        # 판이다. 층을 이미 청구한 판을 다시 주면 처음부터 돌게 되고, 지나온 층의 제출이
        # 「이미 지나온 층」으로 반려되어 판이 망가진 것처럼 보인다.
        found = find_open_ticket(pool, entry["ticket_id"], account.account_id)
        if found is None or found.cleared_floor > 0:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "오늘 판은 이미 끝났다 — 내일 새 판이 열린다"
            )
        return TicketResponse(**vars(found))

    core_version = get_core_version()
    seed = build_daily_seed(today, core_version)
    ticket = create_ticket(
        pool,
        account.account_id,
        DAILY_ROOM,
        core_version,
        mode=RunMode.DAILY,
        # 서버가 정한 값이다 — 클라이언트 제안이 아니므로 T2 와 무관하다.
        forced_seed=seed,
        loadout=build_ticket_loadout(account.account_id),
        ttl=DAILY_TTL,
        room_ids=build_daily_rooms(seed),
        rooms_per_floor=CHAIN_LENGTH,
    )
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO daily_entry (account_id, day, ticket_id) VALUES (%s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            (account.account_id, today, ticket.ticket_id),
        )
    return TicketResponse(**vars(ticket))
