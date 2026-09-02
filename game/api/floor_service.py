"""층 진행 결산 (설계/6_몬스터 §3).

`routes/run.py` 에서 갈라 나왔다 — 저쪽은 제출을 받고 재시뮬을 부르는 자리이고, 여기는
**그 결과가 층에 무엇을 하는가** 다. 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는
선은 책임이다 (§4).

**서버만 층을 올린다.** 클라이언트 보고로 올리면 "10층을 깼다" 고 적어 보내는 것이 곧
진행이 된다 (T9 와 같은 자리).
"""

from game.api.deps import get_context, get_item_catalog, get_pool
from game.api.loadout_service import build_equipped_entries, count_slot_bonus
from game.app.progression.floors import read_floor_cap
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.store.accounts import find_player_entity
from game.app.store.consumables import (
    apply_slot_spend,
    count_free_charges,
    list_consumable_slots,
)
from game.app.store.progress import apply_floor_progress, read_reached_floor
from game.app.store.tickets import IssuedTicket, apply_spent_charges, read_spent_charges
from game.schemas.loadout import parse_loadout


def apply_floor_outcome(
    account_id: int, verified: VerifiedRun, floor: int, rooms_per_floor: int = 0
) -> str:
    """연쇄를 다 이겼으면 다음 층을 연다 (설계/6_몬스터 §3).

    **재시뮬이 확정한 결과만 본다.** 클라이언트 보고로 열면 "10층을 깼다" 고 적어 보내는
    것이 곧 진행이 된다 (T9 와 같은 자리). 반려된 제출은 아무것도 안 연다.

    **마지막 층에서는 안 연다.** 끝이 있어야 「깼다」가 성립한다.

    Args:
        account_id: 대상 계정.
        verified: 서버가 확정한 결과.
        floor: 하강이 시작한 층.
        rooms_per_floor: 층 하나에 드는 방 수.

    Returns:
        화면에 적을 한 줄. 열린 것이 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    # **진 판도 몇 층까지는 깼다.** 하강이 여러 층에 걸치므로 "이겼다" 하나로는 어디까지
    # 갔는지 알 수 없다 — 깬 방 수가 그것을 말한다.
    per_floor = max(1, rooms_per_floor)
    cleared_floors = verified.cleared_rooms // per_floor
    if cleared_floors <= 0:
        return ""
    cap = read_floor_cap(get_context().balance)
    deepest = min(floor + cleared_floors - 1, cap)
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    before = read_reached_floor(pool, entity_id)
    after = apply_floor_progress(pool, entity_id, deepest, cap)
    if deepest >= cap and verified.outcome == OUTCOME_PLAYER_WIN:
        return f"{cap}층을 깼다"
    # **열린 순간만 말한다.** 이미 지나온 층을 다시 이겼을 때도 말하면 그 줄이 뜻을 잃는다.
    return f"{after}층이 열렸다" if after > before else ""


def check_descent_over(ticket: IssuedTicket, claimed: int, verified: VerifiedRun) -> bool:
    """이 제출로 하강이 끝났는가.

    **안 닫으면 죽은 뒤에도 같은 티켓으로 더 깊은 층을 청구할 수 있다.** 서버가 처음부터
    다시 돌므로 결과는 또 패배로 나오지만, 그때마다 그 층의 보상이 나간다.

    Args:
        ticket: 이 제출이 쓰는 티켓.
        claimed: 이번에 확정한 층.
        verified: 서버가 확정한 결과.

    Returns:
        끝났으면 True.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return False
    if verified.outcome != OUTCOME_PLAYER_WIN:
        return True
    span = len(ticket.room_ids) // max(1, ticket.rooms_per_floor)
    return claimed >= ticket.floor + max(0, span - 1)


def resolve_claim(ticket: IssuedTicket, wanted: int) -> int:
    """이번 제출이 확정할 층을 정한다.

    **0 은 「하강 전체」다** — 층 개념이 없던 옛 클라이언트가 그 길로 온다. 그 밖에는
    티켓이 도는 범위 안으로 접는다: 하강에 없는 층을 주장하면 방 목록 밖을 돌게 된다.

    Args:
        ticket: 이 제출이 쓰는 티켓.
        wanted: 클라이언트가 주장한 층.

    Returns:
        확정할 층. 0 이면 전체다.
    """
    if wanted <= 0 or ticket.rooms_per_floor <= 0:
        return 0
    span = len(ticket.room_ids) // ticket.rooms_per_floor
    return max(ticket.floor, min(wanted, ticket.floor + max(0, span - 1)))


def count_claim_rooms(ticket: IssuedTicket, claimed: int) -> int:
    """그 층까지 도는 데 드는 방 수.

    Args:
        ticket: 이 제출이 쓰는 티켓.
        claimed: 확정할 층. 0 이면 전체다.

    Returns:
        돌 방 수. 0 이면 전부 돈다.
    """
    if claimed <= 0 or ticket.rooms_per_floor <= 0:
        return 0
    return (claimed - ticket.floor + 1) * ticket.rooms_per_floor


def apply_charge_spend(account_id: int, ticket: IssuedTicket, verified: VerifiedRun) -> None:
    """이번 재시뮬이 쓴 만큼 소모품 칸에서 깎는다 (설계/4_아이템 §5).

    쓴 수는 **티켓이 실은 수 − 재시뮬이 남긴 수**다. 클라이언트가 「세 개 썼다」고
    보고할 자리를 만들지 않는다 (T9) — 보고를 받으면 0 개 썼다고 적어 보내면 된다.

    **층마다 처음부터 다시 도므로 그 수는 누적이다.** 티켓에 이미 깎은 만큼을 적어 두고
    그 차이만 깎는다. 이것이 있어야 **런 중에 보충해도 두 번 깎이지 않는다** — 예전에는
    그것을 막으려고 런 중 보충을 잠갔는데, 하강이 서른 방인 이 게임에서 그 잠금은 방
    사이에 규칙을 고치는 고리 자체를 막았다 (GDD §2.2).

    Args:
        account_id: 대상 계정.
        ticket: 이 런의 티켓. 실어 보낸 충전 수가 여기 있다.
        verified: 서버가 확정한 결과.
    """
    if verified.verdict != VERDICT_VERIFIED or not ticket.loadout:
        return
    issued = dict(parse_loadout(ticket.loadout).consumables)
    left = dict(verified.remaining_consumables)
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    # **읽을 때와 같은 칸 수를 본다.** 다르면 접사로 늘어난 칸에서 쓴 것이 안 깎여
    # 그 칸만 영원히 공짜가 된다.
    bonus = count_slot_bonus(build_equipped_entries(pool, entity_id, get_item_catalog()))
    slots = list_consumable_slots(pool, entity_id, bonus)
    already = read_spent_charges(pool, ticket.ticket_id)
    spent = dict(already)
    # 정렬해서 돈다 — 딕셔너리 순회 순서가 어느 칸을 먼저 비울지 정하면 안 된다 (R5).
    for use_tag in sorted(issued):
        used = issued[use_tag] - left.get(use_tag, 0)
        # **공짜분은 누적에서 한 번만 뺀다.** 정산마다 빼면 층을 깰 때마다 공짜 충전이
        # 새로 생긴다 — 실제로 그렇게 돌았다.
        payable = max(0, used - count_free_charges(slots, use_tag))
        fresh = payable - already.get(use_tag, 0)
        if fresh > 0:
            apply_slot_spend(pool, entity_id, use_tag, fresh, bonus)
        if payable > 0:
            spent[use_tag] = payable
    if spent != already:
        apply_spent_charges(pool, ticket.ticket_id, spent)
