"""제출 라우트 — 받아서 **다시 계산한다** (docs/설계/7_변조방지 §3·§4).

요청에 결과가 없다. 시드와 방도 받지 않는다 — 티켓이 들고 있다. 그래서 이 라우트가
저장하는 클라이언트 값은 규칙표 하나뿐이고, 그마저 서버에서 다시 검증된다.
"""

import secrets

from fastapi import APIRouter, HTTPException, status

from game.api.deps import (
    CurrentAccount,
    get_context,
    get_core_version,
    get_pool,
)
from game.api.doppel_service import apply_doppel_from_death
from game.api.floor_service import (
    apply_charge_spend,
    apply_floor_outcome,
    check_descent_over,
    count_claim_rooms,
    count_floor_rooms,
    resolve_claim,
)
from game.api.loot_service import create_run_drops, list_floor_defeats
from game.api.maintenance_service import apply_maintenance
from game.api.monster_service import apply_monster_outcome
from game.api.schemas import SubmissionRequest, SubmissionResponse
from game.app.items.loot import compute_run_currency
from game.app.progression.levels import add_run_xp
from game.app.services.manage_meta import apply_run_result
from game.app.services.verify_run import VerifiedRun, check_submission_version, evaluate_submission
from game.app.store.accounts import find_player_entity
from game.app.store.equipment import add_currency, mark_item_broken, remove_item
from game.app.store.items import list_equipment, list_inventory
from game.app.store.meta import load_meta_payload, save_meta_payload
from game.app.store.monster_snapshots import load_snapshots
from game.app.store.progress import (
    add_player_xp,
    read_progress,
    save_leaderboard,
)
from game.app.store.runs import (
    VERDICT_REJECTED,
    VERDICT_VERIFIED,
    StoredResult,
    save_run_result,
    save_submission,
)
from game.app.store.tickets import (
    IssuedTicket,
    apply_floor_claim,
    find_open_ticket,
    mark_ticket_consumed,
)
from game.schemas.loadout import parse_loadout
from game.schemas.meta_save import MetaSave, build_meta_payload, parse_meta_save

router = APIRouter()

# 승리로 세는 결과 문자열. 코어가 내는 값과 같아야 한다.
OUTCOME_WIN = "PLAYER_WIN"


def apply_death_penalty(account_id: int) -> str:
    """사망 손실을 적용한다 (결정 #34).

    **장착·인벤토리를 통틀어 장비 하나만 뽑는다.** 뽑힌 것이 장착 중이었으면 파손되고
    복구비용을 내야 다시 쓰며, 가방에 있었으면 사라진다 — 그 차이가 "좋은 건 끼고
    다녀라" 는 유인을 만든다.

    몬스터가 사본을 가져가는 절반은 아직 없다. 지속 몬스터가 E단계이고, 받을 개체가
    없는 상태에서 사본만 만들면 주인 없는 아이템이 쌓인다.

    Args:
        account_id: 죽은 계정.

    Returns:
        무슨 일이 있었는지. 잃을 것이 없으면 빈 문자열.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    equipped = [(item.item_id, True) for item in list_equipment(pool, entity_id).values()]
    carried = [
        (entry.item.item_id, False)
        for entry in list_inventory(pool, entity_id)
        if entry.item is not None
    ]
    pool_of_items = equipped + carried
    if not pool_of_items:
        return ""
    item_id, was_equipped = pool_of_items[secrets.randbelow(len(pool_of_items))]
    if was_equipped:
        mark_item_broken(pool, entity_id, item_id)
        return f"장착 중이던 장비가 파손됐다 (#{item_id})"
    remove_item(pool, entity_id, item_id)
    return f"가방의 장비를 잃었다 (#{item_id})"


def apply_run_rewards(
    account_id: int,
    submission_id: int,
    verified: VerifiedRun,
    mode: str,
    core_version: str,
    floor: int = 1,
    ticket_id: str = "",
    start_floor: int = 1,
    rooms_per_floor: int = 0,
) -> str:
    """검증된 런의 보상을 준다.

    **여기가 아이템이 세계에 들어오는 유일한 문이다** (결정 #02). 클라이언트는 아이템을
    만들 수 없고, 발급 경로가 서버 하나뿐이라는 것이 시드 파생의 '재현으로 검증' 을
    대신한다.

    Args:
        account_id: 받을 계정.
        submission_id: 이 결과의 제출 id.
        verified: 서버가 확정한 결과.
        mode: 런 모드. 순위표를 가르는 값이다.
        core_version: 이 서버의 코어 버전. 시즌을 가르는 값이다.
        floor: 이 런의 층. 화폐가 이것에 비례한다 — 안 넘기면 깊이 들어가도 1층 값이다.
        ticket_id: 이 런의 티켓. 처치별 굴림이 스냅샷에서 개체 레벨을 찾는다.
        start_floor: 하강이 시작한 층. 이번 층의 처치만 골라내는 데 쓴다.
        rooms_per_floor: 층 하나에 드는 방 수.

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    is_cleared = verified.outcome == OUTCOME_WIN
    add_currency(get_pool(), account_id, compute_run_currency(is_cleared, floor))
    notes = [f"화폐 +{compute_run_currency(is_cleared, floor)}"]
    # **처치마다 굴린다** (설계/4_아이템 §15.3). 런 단위로 굴리면 몬스터 레벨이 개입할
    # 자리가 없다. 재시뮬이 확정한 처치 목록만 쓴다 — 클라이언트 보고로 굴리면 "많이
    # 잡았다" 고 적어 보내는 것이 곧 파밍이 된다.
    notes.extend(
        create_run_drops(
            account_id,
            submission_id,
            list_floor_defeats(verified.room_kinds, start_floor, floor, rooms_per_floor),
            floor,
            ticket_id,
        )
    )
    # 경험치는 **검증된 런에서만** 오른다. 클라이언트 보고로 오르면 순위표가 곧
    # 거짓이 된다 — 순위의 근거가 누적 경험치이기 때문이다.
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    gained = add_run_xp(is_cleared)
    level = add_player_xp(pool, entity_id, gained)
    notes.append(f"경험치 +{gained}")
    progress = read_progress(pool, entity_id)
    save_leaderboard(pool, str(mode), core_version, account_id, progress.total_xp, level)

    if not is_cleared:
        penalty = apply_death_penalty(account_id)
        if penalty:
            notes.append(penalty)
    return " · ".join(notes)


def build_rejection(detail: str) -> VerifiedRun:
    """거절 판정을 만든다.

    Args:
        detail: 거절 사유.

    Returns:
        거절로 채워진 판정.
    """
    return VerifiedRun("", 0, 0, VERDICT_REJECTED, detail)


def check_run_submission(
    request: SubmissionRequest, ticket: IssuedTicket, claimed: int = 0
) -> VerifiedRun:
    """제출 하나를 판정한다.

    코어 버전이 다르면 결과가 재현되지 않으므로 재시뮬하지 않고 거절한다. 이것은 변조가
    아니라 배포 시차일 가능성이 높으므로 사유를 그대로 남긴다.

    Args:
        request: 제출 요청.
        ticket: 이 제출이 쓰는 티켓.
        claimed: 여기까지 깼다고 주장하는 층. 0 이면 하강 전체를 돈다.

    Returns:
        확정된 판정.
    """
    mismatch = check_submission_version(request.core_version, ticket.core_version)
    if mismatch:
        return build_rejection(mismatch)
    player = get_context().balance["player"]
    loadout = parse_loadout(ticket.loadout) if ticket.loadout else None
    # **한도도 티켓에서 온다.** 기본값으로 검증하면 레벨·장비로 늘어난 CPU·슬롯이
    # 에디터에서는 쓰이는데 제출에서 반려된다 — 성장이 벌이 된다.
    return evaluate_submission(
        get_context(),
        request.ruleset,
        ticket.room_id,
        ticket.seed,
        loadout.cpu_budget if loadout else int(player["cpu_budget"]),
        loadout.rule_slots if loadout else int(player["rule_slots"]),
        # **서버가 조회한다.** 제출이 스냅샷을 실어 오면 약한 것으로 바꿀 수 있다 (T8).
        load_snapshots(get_pool(), ticket.ticket_id),
        # 로드아웃도 티켓에서 온다. 제출이 실어 오면 강한 캐릭터로 바꿔 보낼 수 있다.
        loadout,
        # 방 목록도 티켓에서 온다. 제출이 실어 오면 쉬운 방만 골라 담을 수 있다 (T2).
        ticket.room_ids,
        # 층도 티켓에서 온다. 제출이 실어 오면 1층으로 적어 보내 쉬운 판으로 검증받는다.
        ticket.floor,
        ticket.rooms_per_floor,
        # **청구한 층까지만 돈다.** 층 단위 보상이 이것을 쓴다 — 서버는 늘 처음부터 그
        # 층까지 다시 돌므로 인계 HP 를 클라이언트가 보고할 자리가 없다 (T9).
        count_claim_rooms(ticket, claimed),
    )


def build_world_notes(
    request: SubmissionRequest,
    ticket: IssuedTicket,
    verified: VerifiedRun,
    account_id: int,
    submission_id: int,
    claimed: int,
) -> str:
    """이 제출이 세계에 남긴 것을 한 줄로 모은다.

    라우트에서 떼어 낸 이유는 복잡도다 — 세계 반영이 늘어날 때마다 라우트가 길어지면
    「무엇을 검사했고 무엇을 확정했는가」가 그 사이에 묻힌다 (§4).

    Args:
        request: 제출 요청.
        ticket: 이 런의 티켓.
        verified: 서버가 확정한 결과.
        account_id: 플레이어 계정.
        submission_id: 제출 id.
        claimed: 확정한 층.

    Returns:
        보상 줄에 이어 붙일 말. 없으면 빈 문자열.
    """
    notes: list[str] = []
    # **싸운 층만 반영한다.** 티켓은 하강 전체를 싣는데 한 제출은 일부 층만 돈다 —
    # 안 가르면 1층에서 죽은 판이 9층 몬스터를 키운다 (실측).
    world = apply_monster_outcome(ticket, submission_id, verified, account_id, claimed)
    if world:
        notes.append(world)
    # **봇이 깊은 층에서 죽으면 그 자리에 그림자가 선다** (T11). 서버가 판단한다 —
    # 러너가 「나 죽었으니 세워 줘」라고 말하는 구조면 세계 상태를 클라이언트가 정한다 (T9).
    shadow = apply_doppel_from_death(
        get_pool(),
        get_context().rooms,
        account_id,
        verified,
        ticket.floor if claimed <= 0 else claimed,
        count_floor_rooms(ticket, claimed),
        ticket.loadout or {},
        request.ruleset,
    )
    if shadow:
        notes.append(shadow)
    return " · ".join(notes)


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
    claimed = resolve_claim(ticket, request.floor)
    # **먼저 자리를 잡는다.** 층 단위 보상 때문에 한 티켓으로 여러 번 제출하는데, 같은
    # 층을 두 번 제출해 보상을 두 번 받는 경쟁 상태를 여기서 끊는다 — T6 의 「한 티켓
    # 한 제출」을 「더 깊은 층으로만」으로 다시 세운 자리다.
    if claimed > 0:
        if not apply_floor_claim(pool, ticket.ticket_id, claimed):
            raise HTTPException(status.HTTP_409_CONFLICT, "이미 지나온 층이다")
    elif not mark_ticket_consumed(pool, ticket.ticket_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 쓴 티켓이다")

    submission_id = save_submission(pool, ticket.ticket_id, request.ruleset, request.core_version)
    verified = check_run_submission(request, ticket, claimed)
    # **런이 끝났으면 티켓을 닫는다.** 졌거나 마지막 층을 깼을 때다 — 안 닫으면 죽은 뒤에도
    # 같은 티켓으로 더 깊은 층을 청구할 수 있다.
    is_run_closed = claimed <= 0 or check_descent_over(ticket, claimed, verified)
    if claimed > 0 and is_run_closed:
        mark_ticket_consumed(pool, ticket.ticket_id)
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
    reward = apply_run_rewards(
        account.account_id,
        submission_id,
        verified,
        ticket.mode,
        ticket.core_version,
        ticket.floor if claimed <= 0 else claimed,
        ticket.ticket_id,
        ticket.floor,
        ticket.rooms_per_floor,
    )
    world = build_world_notes(request, ticket, verified, account.account_id, submission_id, claimed)
    if world:
        reward = f"{reward} · {world}" if reward else world
    apply_charge_spend(account.account_id, ticket, verified)
    depth = apply_floor_outcome(account.account_id, verified, ticket.floor, ticket.rooms_per_floor)
    if depth:
        reward = f"{reward} · {depth}" if reward else depth
    apply_verified_meta(account.account_id, verified)
    # **닫힐 때만 정비한다.** 층 청구마다 돌면 런 중에 가방이 바뀐다 — 죽기 전에 주운
    # 것이 층 정산 한 번에 사라질 수 있다. 보상·전리품이 다 들어온 뒤라야 새로 주운
    # 것까지 버리기 규칙이 본다.
    if is_run_closed and verified.verdict == VERDICT_VERIFIED:
        upkeep = apply_maintenance(account.account_id)
        if upkeep:
            reward = f"{reward} · {upkeep}" if reward else upkeep
    # `summary` 는 응답에 싣지 않는다 — 서버가 무엇으로 세이브를 갱신했는지는 클라이언트가
    # 알 필요가 없고, 실으면 그것을 되보내려는 경로가 생긴다.
    fields = {key: value for key, value in vars(verified).items() if key != "summary"}
    return SubmissionResponse(submission_id=submission_id, reward=reward, **fields)


def apply_verified_meta(account_id: int, verified: VerifiedRun) -> None:
    """검증된 런의 결산을 메타 세이브에 반영한다 (GDD §2.3).

    **이것이 메타 세이브를 갱신하는 유일한 경로다.** 예전에는 브라우저가 계산한 세이브를
    통째로 받아 저장했는데, 그러면 해금·도감·최고 층이 전부 클라이언트가 쓴 값이 되어
    순위의 근거가 될 수 없다.

    반려된 제출은 아무것도 바꾸지 않는다 — 규칙표가 예산을 넘겨도 도감이 차면
    "제출만 하면 채워지는" 경로가 열린다.

    Args:
        account_id: 대상 계정.
        verified: 재시뮬 결과.
    """
    if verified.summary is None or verified.verdict != VERDICT_VERIFIED:
        return
    pool = get_pool()
    stored = load_meta_payload(pool, account_id)
    meta = parse_meta_save(stored) if stored else MetaSave()
    updated = apply_run_result(meta, verified.summary, get_context().catalog)
    save_meta_payload(pool, account_id, build_meta_payload(updated), get_core_version())
