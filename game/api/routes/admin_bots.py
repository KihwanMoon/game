"""봇·도플갱어 관리 라우트 (T11, 결정 #48 준비).

**우리가 들인 봇은 우리가 볼 수 있어야 한다.** 표시만 해 두고 보는 자리가 없으면
「몇 마리가 돌고 있고 무엇을 하고 있는지」를 DB 로만 알 수 있고, 그러면 실질적으로 아무도
안 본다 — 봇 판정 기준(#48)을 세울 근거도 거기서 나온다.

성격(규칙표·실력)은 우리가 정해 준 값이라 화면에 적어도 새 사실이 없다. 알아야 할 것은
**그래서 어떻게 됐는가** 다: 몇 판을 돌았고, 몇 번 이겼고, 어디까지 내려갔고, 무엇을
벌었는가. 승리가 0이면 그 봇은 세계에 아무것도 안 남긴다.

**멈춤은 지움이 아니다.** 지우면 그 봇이 벌어 둔 장비·도감·순위가 함께 사라지고, 다시
세우면 다른 계정이 된다. 여기서 하는 것은 멈춤·재개와 성격 고치기뿐이다.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from game.api.deps import (
    CurrentAdmin,
    CurrentOperator,
    get_item_catalog,
    get_pool,
)
from game.api.routes.items import build_inventory_response
from game.api.schemas import (
    AdminBotOverviewResponse,
    AdminBotView,
    AdminDoppelView,
    InventoryResponse,
    InventorySlotView,
    ItemView,
)
from game.app.bots.personas import MAX_RUNS_PER_HOUR, MIN_CADENCE_SEC
from game.app.store.accounts import find_player_entity
from game.app.store.admin import record_admin_action
from game.app.store.bot_view import list_bot_rows, list_doppel_rows
from game.app.store.bots import (
    MAX_SKILL_PCT,
    MIN_SKILL_PCT,
    apply_bot_settings,
    check_is_bot,
)
from game.app.store.doppels import read_doppel_gear
from game.app.store.gifts import apply_bot_coin_gift, apply_bot_gift

router = APIRouter()


class BotCoinRequest(BaseModel):
    """내 화폐를 봇에게 넘긴다.

    **한 방향이다.** 아이템 선물과 같은 규율이며(결정 #07), 돌려받는 길을 두면 봇을
    금고로 쓰는 계정이 생긴다.
    """

    account_id: int = Field(ge=1)
    amount: int = Field(ge=1)


class BotGiftRequest(BaseModel):
    """내 아이템 하나를 봇에게 넘기는 요청."""

    account_id: int = Field(ge=1)
    item_id: int = Field(ge=1)


class BotSettingsRequest(BaseModel):
    """봇 하나의 성격을 고치는 요청."""

    account_id: int = Field(ge=1)
    ruleset_id: str = Field(min_length=1, max_length=64)
    skill_pct: int = Field(ge=MIN_SKILL_PCT, le=MAX_SKILL_PCT)
    # 상한은 서버가 다시 물린다. 여기서 받는 것은 **더 느리게** 두려는 값이다.
    cadence_sec: int = Field(ge=MIN_CADENCE_SEC, le=86400)
    is_active: bool = True


def build_bot_overview(account: CurrentAdmin) -> AdminBotOverviewResponse:
    """봇·도플갱어 현황을 만든다.

    Args:
        account: 관리자 계정. 라우트가 이미 검증했다.

    Returns:
        현황 응답.
    """
    pool = get_pool()
    return AdminBotOverviewResponse(
        max_runs_per_hour=MAX_RUNS_PER_HOUR,
        min_cadence_sec=MIN_CADENCE_SEC,
        bots=[AdminBotView(**vars(row)) for row in list_bot_rows(pool)],
        doppels=[AdminDoppelView(**vars(row)) for row in list_doppel_rows(pool)],
    )


@router.get("/api/admin/bots", response_model=AdminBotOverviewResponse)
def read_admin_bots(account: CurrentAdmin) -> AdminBotOverviewResponse:
    """봇과 도플갱어 현황을 본다.

    Args:
        account: 관리자 계정.

    Returns:
        봇 목록과 도플갱어 목록.
    """
    return build_bot_overview(account)


@router.put("/api/admin/bot", response_model=AdminBotOverviewResponse)
def apply_admin_bot(
    request: BotSettingsRequest, account: CurrentOperator
) -> AdminBotOverviewResponse:
    """봇 하나의 성격을 고친다.

    Args:
        request: 고칠 값들.
        account: 관리자 계정.

    Returns:
        고친 뒤의 현황.

    Raises:
        HTTPException: 없는 봇인 경우 404.
    """
    pool = get_pool()
    found = next((row for row in list_bot_rows(pool) if row.account_id == request.account_id), None)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 봇이다: {request.account_id}")
    apply_bot_settings(
        pool,
        request.account_id,
        request.ruleset_id,
        request.skill_pct,
        request.cadence_sec,
        request.is_active,
    )
    # **개입은 반드시 남는다.** 「이 봇이 왜 멈춰 있지」를 나중에 답할 수 있어야 한다.
    record_admin_action(
        pool,
        account.account_id,
        "bot.settings",
        f"#{request.account_id} {found.handle}",
        f"{found.ruleset_id}/{found.skill_pct}% → {request.ruleset_id}/{request.skill_pct}%"
        f" · {'돌림' if request.is_active else '멈춤'}",
    )
    return build_bot_overview(account)


@router.get("/api/admin/bot/bag", response_model=InventoryResponse)
def read_bot_bag(account_id: int, account: CurrentAdmin) -> InventoryResponse:
    """봇 하나의 가방을 본다.

    **사람 화면과 같은 모양으로 만든다** (`build_inventory_response`). 여기서 따로
    만들면 두 화면이 다른 것을 그리게 되고, 「봇에게 뭐가 있지」를 답하려던 화면이 답을
    틀리게 한다.

    **봇만 본다.** 아무 계정이나 볼 수 있으면 이것은 관리자가 남의 가방을 들여다보는
    길이 된다 — 봇을 관리하려고 연 창이 그것이어서는 안 된다.

    Args:
        account_id: 볼 봇의 계정.
        account: 관리자 계정.

    Returns:
        그 봇의 인벤토리와 장비.

    Raises:
        HTTPException: 봇이 아닌 계정이면 404.
    """
    if not check_is_bot(get_pool(), account_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 봇이다: {account_id}")
    return build_inventory_response(account_id)


@router.get("/api/admin/doppel/gear", response_model=InventoryResponse)
def read_doppel_bag(record_id: int, account: CurrentAdmin) -> InventoryResponse:
    """도플갱어가 끼고 있던 장비를 본다.

    **가진 아이템이 아니라 얼려 둔 기록이다.** 도플갱어는 어떤 아이템도 소유하지 않는다 —
    그것이 전리품 차단의 뿌리이고(잡아도 떨어질 것이 없다), 그래서 여기 뜨는 것에는
    `item_id` 가 없다. 사람 가방과 같은 모양으로 내는 이유는 화면이 같은 격자를 쓰기
    때문이다 — 같은 것을 두 모양으로 그리면 답이 갈린다.

    Args:
        record_id: 볼 개체.
        account: 관리자 계정.

    Returns:
        장비 자리에 얼려 둔 것을 채운 인벤토리. 가방은 늘 비어 있다.

    Raises:
        HTTPException: 도플갱어가 아니면 404.
    """
    pool = get_pool()
    gear = read_doppel_gear(pool, record_id)
    if not gear and not any(row.record_id == record_id for row in list_doppel_rows(pool)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 도플갱어다: {record_id}")
    catalog = get_item_catalog()
    return InventoryResponse(
        size=0,
        slots=[],
        equipment=[
            AdminDoppelGearView(index, item, catalog).build() for index, item in enumerate(gear)
        ],
        balance=0,
        repair_cost=0,
    )


@router.post("/api/admin/bot/gift", response_model=AdminBotOverviewResponse)
def create_bot_gift(request: BotGiftRequest, account: CurrentOperator) -> AdminBotOverviewResponse:
    """내 가방의 아이템 하나를 봇에게 넘긴다.

    **한 방향이다.** 도착하는 순간 귀속되고(결정 #07), 귀속된 물건은 경매에 못 걸린다 —
    한 번 봇에게 간 것은 어떤 경로로도 사람에게 돌아오지 않는다. 봇 → 사람이 열리면
    그것은 봇 파밍이 최적 전략이 되는 길이다 (T11, 결정 #02).

    낀 것은 못 준다. 가방에 있는 것만 넘어간다 — 장착 중인 물건을 빼내면 그 봇도 아니고
    이 사람도 아닌 상태가 한 틱 생긴다.

    Args:
        request: 받을 봇과 넘길 아이템.
        account: 관리자 계정. **주는 쪽은 이 계정 자신이다.**

    Returns:
        넘긴 뒤의 현황.

    Raises:
        HTTPException: 봇이 아니거나, 가진 물건이 아니거나, 봇의 가방이 찬 경우.
    """
    pool = get_pool()
    try:
        catalog_id = apply_bot_gift(
            pool, request.item_id, find_player_entity(pool, account.account_id), request.account_id
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    record_admin_action(
        pool,
        account.account_id,
        "bot.gift",
        f"#{request.account_id}",
        f"{catalog_id} (#{request.item_id}) 넘김 — 귀속됨",
    )
    return build_bot_overview(account)


@router.post("/api/admin/bot/coin", response_model=AdminBotOverviewResponse)
def create_bot_coin(request: BotCoinRequest, account: CurrentOperator) -> AdminBotOverviewResponse:
    """내 화폐를 봇에게 넘긴다 (2026-09-06).

    **봇에게 밑천을 주는 자리다.** 봇이 경매에서 사려면 화폐가 있어야 하는데, 벌이가
    느린 봇은 영영 못 산다 — 그러면 「봇이 아무것도 안 산다」가 봇의 규칙이 아니라 잔액의
    문제가 되고, 우리가 보려던 것(봇이 무엇을 고르는가)이 안 보인다.

    **한 방향이다.** 아이템 선물과 같은 규율이며(결정 #07), 돌려받는 길을 두면 봇을
    금고로 쓰는 계정이 생긴다.

    **화폐를 만들지 않는다.** 주는 쪽에서 빠진 만큼만 들어가므로 총량이 그대로다 —
    늘리는 문은 검증된 런 하나뿐이다 (결정 #02).

    Args:
        request: 받을 봇과 넘길 양.
        account: 관리자 계정. **주는 쪽은 이 계정 자신이다.**

    Returns:
        넘긴 뒤의 현황.

    Raises:
        HTTPException: 봇이 아니거나, 잔액이 모자라거나, 자기 자신에게 주는 경우.
    """
    pool = get_pool()
    if not check_is_bot(pool, request.account_id):
        # 사람에게 넘기는 길을 두면 계정 사이 화폐 이동이 열리고, 그 순간 봇 파밍으로
        # 번 것을 사람 계정에 모을 수 있다 (T11).
        raise HTTPException(status.HTTP_409_CONFLICT, "봇에게만 넘길 수 있다")
    try:
        left = apply_bot_coin_gift(pool, request.amount, account.account_id, request.account_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    record_admin_action(
        pool,
        account.account_id,
        "bot.coin",
        f"#{request.account_id}",
        f"{request.amount} 넘김 — 남은 잔액 {left}",
    )
    return build_bot_overview(account)


class AdminDoppelGearView:
    """얼려 둔 장비 한 벌을 인벤토리 칸 모양으로 옮긴다.

    **`item_id` 가 0 이다.** 이것은 아이템이 아니라 기록이고, 0 은 「가리킬 행이 없다」는
    뜻이다 — 진짜 id 를 지어내면 화면이 그것으로 조작을 걸 수 있다.
    """

    def __init__(self, index: int, gear: dict, catalog: dict) -> None:
        """옮길 값을 받는다.

        Args:
            index: 칸 번호.
            gear: 얼려 둔 장비 한 건.
            catalog: 아이템 카탈로그. 이름을 여기서 찾는다.
        """
        self.index = index
        self.gear = gear
        self.catalog = catalog

    def build(self) -> InventorySlotView:
        """칸 하나를 만든다.

        Returns:
            인벤토리 칸.
        """
        catalog_id = str(self.gear.get("catalog_id", ""))
        entry = self.catalog.get(catalog_id)
        slot = str(self.gear.get("slot", ""))
        return InventorySlotView(
            slot_index=self.index,
            item=ItemView(
                item_id=0,
                catalog_id=catalog_id,
                label_ko=getattr(entry, "label_ko", "") or catalog_id,
                kind="EQUIPMENT",
                slot=slot,
                equipped_slot=slot,
                is_broken=bool(self.gear.get("is_broken")),
                grade=getattr(entry, "grade", "") or "",
                affixes=list(self.gear.get("affixes") or []),
            ),
            stack_catalog_id=None,
            stack_count=0,
            slot=slot,
        )
