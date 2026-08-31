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
    get_item_catalog,
    get_pool,
)
from game.api.discovery_service import record_item_discovery
from game.api.schemas import SubmissionRequest, SubmissionResponse
from game.app.items.catalog import find_item as find_catalog_item
from game.app.items.loot import create_loot_roll
from game.app.progression.levels import add_run_xp
from game.app.services.manage_meta import apply_run_result
from game.app.services.verify_run import VerifiedRun, check_submission_version, evaluate_submission
from game.app.store.accounts import find_player_entity
from game.app.store.equipment import add_currency, mark_item_broken, remove_item
from game.app.store.items import create_item, list_equipment, list_inventory
from game.app.store.meta import load_meta_payload, save_meta_payload
from game.app.store.monsters import (
    add_monster_xp,
    apply_monster_defeat,
    load_snapshots,
)
from game.app.store.progress import add_player_xp, read_progress, save_leaderboard
from game.app.store.runs import (
    VERDICT_REJECTED,
    VERDICT_VERIFIED,
    StoredResult,
    save_run_result,
    save_submission,
)
from game.app.store.tickets import IssuedTicket, find_open_ticket, mark_ticket_consumed
from game.app.store.trophies import apply_recovery, create_trophy
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

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    is_cleared = verified.outcome == OUTCOME_WIN
    roll = create_loot_roll(get_item_catalog(), is_cleared, floor)
    add_currency(get_pool(), account_id, roll.currency)
    notes = [f"화폐 +{roll.currency}"]
    if roll.catalog_id is not None:
        # **개체 id 다. 계정 id 가 아니다.** 둘 다 int 라 바꿔 넣어도 타입이 못 막는다 —
        # 실제로 한 번 그렇게 들어갔고, 외래키가 우연히 잡았다(id 가 겹쳤다면 남의 개체에
        # 아이템이 들어갔을 것이다).
        item_id = create_item(
            get_pool(),
            find_player_entity(get_pool(), account_id),
            roll.catalog_id,
            roll.affixes,
            submission_id,
        )
        entry = find_catalog_item(get_item_catalog(), roll.catalog_id)
        if item_id is not None:
            # 손에 들어온 것만 밝힌다. 가방이 가득 차 놓친 것을 밝히면 도감이 "가진 적
            # 없는 것" 을 열어 버린다.
            record_item_discovery(account_id, roll.catalog_id)
        notes.append(
            f"{entry.label_ko} 획득"
            if item_id is not None
            else "인벤토리가 가득 차 전리품을 놓쳤다"
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
        entity_id = find_player_entity(pool, account_id)
        for item in snapshots:
            level = apply_monster_defeat(pool, item.record_id, ticket.floor)
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
            # 그 개체가 들고 있던 **내 것**을 되찾는다 (`설계/6_몬스터` §5). 도감이
            # "내 아이템을 들고 있다" 고 말해 놓고 잡아도 못 돌려받으면, World Loop 의
            # 동기가 화면에만 있고 세계에는 없다.
            for catalog_id in apply_recovery(pool, item.record_id, account_id, entity_id):
                record_item_discovery(account_id, catalog_id)
                notes.append(f"{catalog_id} 되찾음")
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
    entity_id = find_player_entity(pool, account_id)
    equipped = list(list_equipment(pool, entity_id).values())
    carried = [entry.item for entry in list_inventory(pool, entity_id) if entry.item is not None]
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
    reward = apply_run_rewards(
        account.account_id,
        submission_id,
        verified,
        ticket.mode,
        ticket.core_version,
        ticket.floor,
    )
    world = apply_monster_outcome(ticket, submission_id, verified, account.account_id)
    if world:
        reward = f"{reward} · {world}" if reward else world
    apply_verified_meta(account.account_id, verified)
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
