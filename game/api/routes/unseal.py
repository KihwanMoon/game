"""봉인 해제 — 화폐를 내면 서버가 옵션을 부여한다 (설계/4_아이템 §17).

**서버가 굴린다.** 클라이언트가 굴리면 마음에 드는 값이 나올 때까지 다시 굴릴 수 있고,
그러면 봉인이 아무것도 막지 않는다.

**돈을 먼저 뺀다.** 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생기고, 그 창이
공짜 해제가 된다. 차감이 되고 여는 데 실패하면 되돌린다 — 그쪽은 되돌릴 수 있다.

`items.py` 에서 갈라 둔 이유는 그 파일이 400줄 상한에 가깝기 때문이고, 책임도 다르다 —
저쪽은 가방을 다루고 이쪽은 굴림을 다룬다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas import ItemActionRequest, WalletResponse
from game.app.items.sealed import (
    GRADE_SEALED_SLOTS,
    compute_unseal_cost,
    create_sealed_affix,
)
from game.app.store.accounts import find_player_entity
from game.app.store.equipment import REPAIR_COST, add_currency, read_balance
from game.app.store.items import apply_unseal, find_item, list_affix_pool, record_item_event

router = APIRouter()

EVENT_UNSEAL = "unseal"


@router.post("/api/item/unseal", response_model=WalletResponse)
def create_unseal(request: ItemActionRequest, account: CurrentAccount) -> WalletResponse:
    """봉인 한 칸을 연다. 결과는 서버가 정한다.

    Args:
        request: 아이템 id.
        account: 토큰으로 푼 계정.

    Returns:
        해제 뒤 잔액.

    Raises:
        HTTPException: 가진 아이템이 아니거나, 열 칸이 없거나, 잔액이 모자란 경우.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    stored = find_item(pool, entity_id, request.item_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "가진 아이템이 아니다")
    if stored.sealed_slots <= 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "열 봉인이 없다")

    opened = count_opened(stored)
    cost = compute_unseal_cost(opened)
    if read_balance(pool, account.account_id) < cost:
        raise HTTPException(status.HTTP_409_CONFLICT, f"화폐가 모자란다 — {cost} 이 필요하다")

    # **먼저 뺀다.** 굴린 뒤에 빼면 굴림은 성공하고 차감이 실패하는 창이 생긴다.
    add_currency(pool, account.account_id, -cost)
    try:
        affix = create_sealed_affix(list_affix_pool(pool))
    except ValueError as error:
        add_currency(pool, account.account_id, cost)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    if not apply_unseal(pool, request.item_id, affix):
        add_currency(pool, account.account_id, cost)
        raise HTTPException(status.HTTP_409_CONFLICT, "열 봉인이 없다")
    record_item_event(pool, entity_id, request.item_id, EVENT_UNSEAL, affix.label_ko)
    return WalletResponse(balance=read_balance(pool, account.account_id), repair_cost=REPAIR_COST)


def count_opened(stored: object) -> int:
    """이미 연 칸 수를 센다.

    등급이 준 칸에서 남은 칸을 뺀다. 인스턴스가 등급을 복사해 갖고 있으므로 카탈로그를
    안 봐도 된다 — 카탈로그를 고쳐도 이 값이 흔들리지 않는 이유다 (§15.5).

    Args:
        stored: 보관된 아이템.

    Returns:
        연 칸 수. 등급을 모르면 0.
    """
    total = GRADE_SEALED_SLOTS.get(getattr(stored, "grade", ""), 0)
    return max(0, total - int(getattr(stored, "sealed_slots", 0)))
