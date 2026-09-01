"""티켓 라우트 — **시드는 여기서만 나온다** (docs/설계/7_변조방지 T2).

요청이 시드를 받지 않는 것이 설계다. 받으면 유리한 시드가 나올 때까지 돌려 보고 그것만
제출할 수 있다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_core_version, get_pool
from game.api.loadout_service import build_ticket_loadout
from game.api.schemas import TicketRequest, TicketResponse
from game.app.progression.floors import resolve_floor
from game.app.store.accounts import find_player_entity
from game.app.store.monsters import build_monster_snapshot, list_monsters, save_snapshots
from game.app.store.progress import read_reached_floor
from game.app.store.tickets import create_ticket
from game.schemas.monster_snapshot import build_snapshot_payload, sort_snapshots

router = APIRouter()


@router.post("/api/ticket", response_model=TicketResponse)
def create_run_ticket(request: TicketRequest, account: CurrentAccount) -> TicketResponse:
    """런 티켓을 발급한다.

    Args:
        request: 방·층과 (연습 모드에 한해) 제안 시드.
        account: 토큰으로 푼 계정.

    Returns:
        발급된 티켓. 런의 입력 전부가 여기 있다.

    Raises:
        HTTPException: 없는 방인 경우.
    """
    context = get_context()
    if request.room_id not in context.rooms:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"없는 방이다: {request.room_id}")
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    # **층을 서버가 정한다.** 요청한 층은 「어디로 갈까」의 제안일 뿐이고, 도달 층을
    # 넘길 수 없다 — 넘기면 1층 캐릭터로 10층 보상을 뽑는다 (T2 와 같은 자리).
    floor = resolve_floor(request.floor, read_reached_floor(pool, entity_id))
    ticket = create_ticket(
        pool,
        account.account_id,
        request.room_id,
        get_core_version(),
        floor=floor,
        wanted_seed=request.seed,
        # 장비·레벨을 얼려 넣는다. 없으면 화면과 서버가 다른 캐릭터로 싸운다 (결정 #13).
        loadout=build_ticket_loadout(account.account_id),
    )
    # 지속 몬스터를 **얼려 넣는다** (docs/설계/6_몬스터 §5). 이것이 있어야 런 등식이
    # f(시드, 규칙표, 코어버전, 스냅샷) 으로 유지되고, 서버가 같은 상태로 재시뮬할 수 있다.
    balance_by_id = {kind["id"]: kind for kind in context.balance["enemies"]}
    snapshots = sort_snapshots(
        tuple(
            build_monster_snapshot(record, balance_by_id[record.catalog_id])
            for record in list_monsters(pool, floor)
            if record.catalog_id in balance_by_id
        )
    )
    save_snapshots(pool, ticket.ticket_id, snapshots)
    return TicketResponse(
        **vars(ticket),
        monster_snapshot=[build_snapshot_payload(item) for item in snapshots],
    )
