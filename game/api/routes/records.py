"""방별 상시 기록 — 도전 티켓과 기록판 (2026-09-25).

**같은 방·같은 시드·같은 몸**에서 누가 가장 적게 써서 이기는가를 잰다. 순위표는 누적
경험치라 오래 돈 쪽이 앞서고, 이 표는 장비로 못 사는 축이라 20장을 다 돈 뒤에도 끝이 없다.
판정은 `record_service` 가 한다 — 여기는 얇게 둔다.
"""

from fastapi import APIRouter, HTTPException, Query, status

from game.api.deps import CurrentAccount, get_context, get_core_version, get_pool
from game.api.record_service import RECORD_FLOOR, build_record_loadout, build_record_seed
from game.api.schemas import TicketResponse
from game.api.schemas_record import RecordTicketRequest, RoomRecordBoard, RoomRecordRow
from game.app.store.room_records import (
    count_room_players,
    find_my_room_record,
    list_room_records,
)
from game.app.store.tickets import create_ticket
from game.schemas.run_ticket import RunMode

router = APIRouter()


def check_record_room(room_id: str) -> None:
    """기록을 잴 수 있는 방인지 본다.

    Args:
        room_id: 방 id.

    Raises:
        HTTPException: 없는 방인 경우.
    """
    if room_id not in get_context().rooms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"없는 방이다: {room_id}")


@router.post("/api/record/ticket", response_model=TicketResponse)
def create_record_ticket(request: RecordTicketRequest, account: CurrentAccount) -> TicketResponse:
    """기록 도전 티켓을 받는다. 방 하나, 서버가 정한 시드, 기본 몸이다.

    **지속 몬스터와 그림자를 세우지 않는다.** 그것들은 사람마다 다른 적을 만들고, 그러면
    같은 방의 기록이 서로 다른 싸움이 된다. 몸도 같은 이유로 새로 온 사람의 몸이다.

    Args:
        request: 고른 방.
        account: 토큰으로 푼 계정.

    Returns:
        방 하나짜리 티켓.
    """
    check_record_room(request.room_id)
    core_version = get_core_version()
    ticket = create_ticket(
        get_pool(),
        account.account_id,
        request.room_id,
        core_version,
        floor=RECORD_FLOOR,
        mode=RunMode.RECORD,
        # 서버가 정한 값이다 — 클라이언트 제안이 아니므로 T2 와 무관하다.
        forced_seed=build_record_seed(request.room_id, core_version),
        # **방 목록을 꼭 적는다.** 비우면 같은 방을 다섯 번 잇는다.
        room_ids=(request.room_id,),
        rooms_per_floor=0,
        loadout=build_record_loadout(),
    )
    return TicketResponse(**vars(ticket))


@router.get("/api/records", response_model=RoomRecordBoard)
def read_room_records(
    account: CurrentAccount, room_id: str = Query(min_length=1, max_length=64)
) -> RoomRecordBoard:
    """한 방의 기록판을 읽는다 — 윗자리와 내 자리.

    Args:
        account: 토큰으로 푼 계정.
        room_id: 방 id.

    Returns:
        기록판.
    """
    check_record_room(room_id)
    pool = get_pool()
    core_version = get_core_version()
    mine = find_my_room_record(pool, room_id, core_version, account.account_id)
    return RoomRecordBoard(
        room_id=room_id,
        core_version=core_version,
        players=count_room_players(pool, room_id, core_version),
        entries=[RoomRecordRow(**row) for row in list_room_records(pool, room_id, core_version)],
        mine=RoomRecordRow(**mine) if mine is not None else None,
    )
