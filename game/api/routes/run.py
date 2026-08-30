"""제출 라우트 — 받아서 **다시 계산한다** (docs/설계/7_변조방지 §3·§4).

요청에 결과가 없다. 시드와 방도 받지 않는다 — 티켓이 들고 있다. 그래서 이 라우트가
저장하는 클라이언트 값은 규칙표 하나뿐이고, 그마저 서버에서 다시 검증된다.
"""

import secrets

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_context, get_item_catalog, get_pool
from game.api.schemas import SubmissionRequest, SubmissionResponse
from game.app.items.catalog import find_item as find_catalog_item
from game.app.items.loot import create_loot_roll
from game.app.services.verify_run import VerifiedRun, check_submission_version, evaluate_submission
from game.app.store.equipment import add_currency, mark_item_broken, remove_item
from game.app.store.items import create_item, list_equipment, list_inventory
from game.app.store.monsters import (
    add_monster_xp,
    apply_monster_defeat,
    create_trophy,
    load_snapshots,
)
from game.app.store.runs import (
    VERDICT_REJECTED,
    VERDICT_VERIFIED,
    StoredResult,
    save_run_result,
    save_submission,
)
from game.app.store.tickets import IssuedTicket, find_open_ticket, mark_ticket_consumed

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
    equipped = [(item.item_id, True) for item in list_equipment(pool, account_id).values()]
    carried = [
        (entry.item.item_id, False)
        for entry in list_inventory(pool, account_id)
        if entry.item is not None
    ]
    pool_of_items = equipped + carried
    if not pool_of_items:
        return ""
    item_id, was_equipped = pool_of_items[secrets.randbelow(len(pool_of_items))]
    if was_equipped:
        mark_item_broken(pool, account_id, item_id)
        return f"장착 중이던 장비가 파손됐다 (#{item_id})"
    remove_item(pool, account_id, item_id)
    return f"가방의 장비를 잃었다 (#{item_id})"


def apply_run_rewards(account_id: int, submission_id: int, verified: VerifiedRun) -> str:
    """검증된 런의 보상을 준다.

    **여기가 아이템이 세계에 들어오는 유일한 문이다** (결정 #02). 클라이언트는 아이템을
    만들 수 없고, 발급 경로가 서버 하나뿐이라는 것이 시드 파생의 '재현으로 검증' 을
    대신한다.

    Args:
        account_id: 받을 계정.
        submission_id: 이 결과의 제출 id.
        verified: 서버가 확정한 결과.

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    is_cleared = verified.outcome == OUTCOME_WIN
    roll = create_loot_roll(get_item_catalog(), is_cleared)
    add_currency(get_pool(), account_id, roll.currency)
    notes = [f"화폐 +{roll.currency}"]
    if roll.catalog_id is not None:
        item_id = create_item(get_pool(), account_id, roll.catalog_id, roll.affixes, submission_id)
        entry = find_catalog_item(get_item_catalog(), roll.catalog_id)
        notes.append(
            f"{entry.label_ko} 획득"
            if item_id is not None
            else "인벤토리가 가득 차 전리품을 놓쳤다"
        )
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


def apply_monster_outcome(
    ticket: IssuedTicket, submission_id: int, verified: VerifiedRun, account_id: int
) -> str:
    """이 런의 결과를 지속 몬스터에 반영한다 (docs/설계/6_몬스터 §3·§4, 결정 #34·#35).

    **검증된 런에서만 반영한다.** 클라이언트가 "내가 졌다" 고 보고해서 몬스터가 크는
    구조면, 자기 몬스터를 키우려고 일부러 지는 어뷰징이 열린다 (T9).

    Args:
        ticket: 이 런의 티켓.
        submission_id: 제출 id.
        verified: 서버가 확정한 결과.
        account_id: 플레이어 계정.

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    pool = get_pool()
    snapshots = load_snapshots(pool, ticket.ticket_id)
    if not snapshots:
        return ""
    notes: list[str] = []
    if verified.outcome == OUTCOME_WIN:
        # 이겼으면 그 층의 지속 몬스터가 전부 감쇠한다 — 플레이어의 승리가 세계에
        # 흔적을 남긴다 (결정 #35).
        for item in snapshots:
            level = apply_monster_defeat(pool, item.record_id, ticket.floor)
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
        return " · ".join(notes)

    # 졌으면 그 층의 몬스터가 경험치를 얻고, 하나가 장비 사본을 가져간다 (결정 #34).
    for item in snapshots:
        level = add_monster_xp(pool, item.record_id, ticket.floor, "PLAYER", submission_id)
        if level > item.level:
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
    taken = apply_trophy_transfer(account_id, snapshots[0].record_id)
    if taken:
        notes.append(taken)
    return " · ".join(notes)


def apply_trophy_transfer(account_id: int, record_id: int) -> str:
    """뽑힌 장비의 **사본**을 몬스터에게 넘긴다 (결정 #34).

    원본은 `apply_death_penalty` 가 처리한다 — 장착 중이었으면 파손, 가방이었으면 삭제.
    사본이라 아이템 총량이 늘지만, 몬스터의 것은 거래 대상이 아니므로 경제에 흘러들지
    않는다. 도감이 "내 아이템을 들고 있다" 를 말할 수 있게 하는 것이 이 사본의 목적이다.

    Args:
        account_id: 죽은 계정.
        record_id: 가져갈 몬스터.

    Returns:
        무슨 일이 있었는지. 가져갈 것이 없으면 빈 문자열.
    """
    pool = get_pool()
    equipped = list(list_equipment(pool, account_id).values())
    carried = [entry.item for entry in list_inventory(pool, account_id) if entry.item is not None]
    candidates = equipped + carried
    if not candidates:
        return ""
    picked = candidates[secrets.randbelow(len(candidates))]
    create_trophy(
        pool,
        record_id,
        picked.catalog_id,
        [
            {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
            for a in picked.affixes
        ],
        account_id,
    )
    return f"{picked.catalog_id} 를 빼앗겼다"


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
        # **서버가 조회한다.** 제출이 스냅샷을 실어 오면 약한 것으로 바꿀 수 있다 (T8).
        load_snapshots(get_pool(), ticket.ticket_id),
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
    reward = apply_run_rewards(account.account_id, submission_id, verified)
    world = apply_monster_outcome(ticket, submission_id, verified, account.account_id)
    if world:
        reward = f"{reward} · {world}" if reward else world
    return SubmissionResponse(submission_id=submission_id, reward=reward, **vars(verified))
