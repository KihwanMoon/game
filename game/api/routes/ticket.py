"""티켓 라우트 — **시드는 여기서만 나온다** (docs/설계/7_변조방지 T2).

요청이 시드를 받지 않는 것이 설계다. 받으면 유리한 시드가 나올 때까지 돌려 보고 그것만
제출할 수 있다.
"""

import secrets

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_core_version, get_pool
from game.api.doppel_pick import build_room_doppels
from game.api.loadout_service import build_ticket_loadout
from game.api.maintenance_service import apply_maintenance
from game.api.schemas import TicketRequest, TicketResponse
from game.api.world_seed import apply_floor_seed, list_floor_range_monsters
from game.app.progression.floors import BOSS_ROOM_ID, read_boss_floor, resolve_floor
from game.app.services.build_chain import build_descent
from game.app.store.accounts import find_player_entity
from game.app.store.monster_snapshots import build_monster_snapshot, save_snapshots
from game.app.store.progress import read_reached_floor
from game.app.store.spoils import list_spoil_deltas
from game.app.store.tickets import CHAIN_LENGTH, create_ticket
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
    # **나가기 직전에 정비한다** (개정 2026-09-05). 예전에는 티켓이 닫힐 때만 돌았는데,
    # 티켓은 죽거나 마지막 층을 깨야 닫힌다 — 7층까지 이기고 그만두는 판은 영영 안 닫혀
    # **한 번도 정비가 안 돌았다.** 봇은 매판 죽어서 늘 닫히므로 봇에서만 도는 것처럼
    # 보였다. 「판과 판 사이」의 확실한 신호는 다음 판을 시작하는 이 순간뿐이다.
    #
    # **로드아웃을 짜기 전이어야 한다.** 뒤에 두면 고친 장비와 채운 물약을 두고 나가게
    # 되고, 그러면 정비가 한 판 늦게 반영된다.
    apply_maintenance(account.account_id)
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
        # **방 목록을 서버가 정한다.** 비워 두면 같은 방을 세 번 잇는다 — 방이 열 개
        # 있어도 한 판에 한 종류만 보게 되고, 방을 늘려도 사람 눈에는 안 늘어난다.
        # **하강 전체를 얼려 넣는다.** 층마다 따로 제출하면 층 사이에 인계되는 HP 를
        # 클라이언트가 보고하게 되고, 그러면 "나는 만피로 시작했다" 를 적어 보내는 것이
        # 곧 진행이 된다 (T9). 한 티켓으로 전체를 재시뮬하는 것이 그것을 막는다.
        rooms_per_floor=CHAIN_LENGTH,
        room_ids=build_descent(
            context.rooms,
            floor,
            request.room_id,
            CHAIN_LENGTH,
            BOSS_ROOM_ID,
            read_boss_floor(context.balance),
        ),
        wanted_seed=request.seed,
        # 장비·레벨을 얼려 넣는다. 없으면 화면과 서버가 다른 캐릭터로 싸운다 (결정 #13).
        loadout=build_ticket_loadout(account.account_id),
    )
    # 지속 몬스터를 **얼려 넣는다** (docs/설계/6_몬스터 §5). 이것이 있어야 런 등식이
    # f(시드, 규칙표, 코어버전, 스냅샷) 으로 유지되고, 서버가 같은 상태로 재시뮬할 수 있다.
    # **없으면 심는다.** 이 길이 없어 깊은 층이 영영 비어 있었다 — 스냅샷·도감·되찾기가
    # 전부 그 위에 서 있는데 바닥이 없었다.
    # **하강이 도는 모든 층을 심는다.** 티켓 하나가 1층부터 보스층까지 돌므로 시작
    # 층만 심으면 2층부터는 지속 몬스터가 영영 없다 — 정산이 「레벨 1→1」로 찍히던
    # 자리다(실제 신고).
    for step, offset in enumerate(range(0, len(ticket.room_ids), CHAIN_LENGTH)):
        apply_floor_seed(
            pool,
            context.rooms,
            ticket.room_ids[offset : offset + CHAIN_LENGTH],
            floor + step,
        )
    balance_by_id = {kind["id"]: kind for kind in context.balance["enemies"]}
    snapshots = sort_snapshots(
        tuple(
            # **전투로 가는 스냅샷만 뺏은 장비를 판다.** 도감은 「무엇을 들고 있다」만
            # 말하면 되고, 그것 때문에 개체마다 조회를 한 번 더 돌 이유가 없다.
            build_monster_snapshot(
                record,
                balance_by_id[record.catalog_id],
                list_spoil_deltas(pool, record.record_id),
            )
            # **방마다 그림자 하나만 세운다** (2026-09-06). 빈 자리가 있는 만큼 서던
            # 때는 4층에 열한 마리가 있었고, 자리 이름이 방을 안 담아 셋이 한 방에 섰다.
            for record in build_room_doppels(
                list_floor_range_monsters(pool, floor, ticket.room_ids, CHAIN_LENGTH),
                context.rooms,
                ticket.room_ids,
                CHAIN_LENGTH,
                floor,
                secrets.randbelow,
            )
            if record.catalog_id in balance_by_id
        )
    )
    save_snapshots(pool, ticket.ticket_id, snapshots)
    return TicketResponse(
        **vars(ticket),
        monster_snapshot=[build_snapshot_payload(item) for item in snapshots],
    )
