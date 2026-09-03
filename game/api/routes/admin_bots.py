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

from game.api.deps import CurrentAdmin, get_pool
from game.api.schemas import AdminBotOverviewResponse, AdminBotView, AdminDoppelView
from game.app.bots.personas import MAX_RUNS_PER_HOUR, MIN_CADENCE_SEC
from game.app.store.accounts import find_player_entity
from game.app.store.admin import record_admin_action
from game.app.store.bot_view import list_bot_rows, list_doppel_rows
from game.app.store.bots import MAX_SKILL_PCT, MIN_SKILL_PCT, apply_bot_settings
from game.app.store.gifts import apply_bot_gift

router = APIRouter()


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
def apply_admin_bot(request: BotSettingsRequest, account: CurrentAdmin) -> AdminBotOverviewResponse:
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


@router.post("/api/admin/bot/gift", response_model=AdminBotOverviewResponse)
def create_bot_gift(request: BotGiftRequest, account: CurrentAdmin) -> AdminBotOverviewResponse:
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
