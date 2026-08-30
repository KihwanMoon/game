"""관리자 라우트 — 세계를 보고, 필요하면 손댄다.

**두 가지를 지킨다.**

1. **관리자가 아니면 404 다.** 403 은 "여기 뭔가 있는데 너는 못 본다" 를 알려 주고,
   그것은 관리자 경로의 존재 자체를 노출한다.
2. **개입은 반드시 원장에 남는다.** 남지 않으면 "이 몬스터 레벨이 왜 이렇지" 를 나중에
   아무도 답할 수 없다.

**콘텐츠는 여기서 고치지 않는다.** 아이템 카탈로그·레벨 곡선·방 구성은
`resources/*.json` 이고 그것은 `core_version` 에 묶여 있다 — 런타임에 바꾸면 이미 발급된
티켓이 다른 게임을 가리키고, 브라우저(빌드에 박힌 JSON)와 서버가 다른 값을 보게 되며,
골든 리플레이와 랭킹 시즌이 함께 무너진다 (결정 #06, R5). 그래서 이 라우트가 카탈로그에
대해 하는 일은 **보여주는 것뿐**이고, 고치는 것은 파일을 고쳐 배포하는 경로다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.catalog_view import (
    build_curve_caps,
    build_enemy_rows,
    build_item_rows,
    build_level_curve,
)
from game.api.deps import (
    CurrentAdmin,
    get_context,
    get_core_version,
    get_item_catalog,
    get_pool,
)
from game.api.schemas import (
    AdminActionView,
    AdminCatalogResponse,
    AdminHeldItemView,
    AdminMonsterView,
    AdminOverviewResponse,
    AdminReasonRequest,
    MonsterLevelRequest,
)
from game.app.monsters.growth import get_level_cap
from game.app.store.admin import list_admin_actions, record_admin_action
from game.app.store.admin_actions import apply_item_recall, apply_listing_cancel
from game.app.store.monsters import find_monster, set_monster_level
from game.app.store.world_view import (
    MonsterRow,
    count_levels,
    list_held_items,
    list_world_monsters,
    read_world_summary,
)

router = APIRouter()

# 개입 사유의 최소 길이. 한두 글자로 때우면 원장이 기록이 아니라 알리바이가 된다.
MIN_REASON_LENGTH = 4


@router.get("/api/admin/overview", response_model=AdminOverviewResponse)
def read_admin_overview(account: CurrentAdmin) -> AdminOverviewResponse:
    """세계 현황을 한 화면으로 본다.

    Args:
        account: 관리자 계정.

    Returns:
        요약·몬스터·레벨 분포·최근 개입.
    """
    pool = get_pool()
    summary = read_world_summary(pool)
    catalog = get_item_catalog()
    return AdminOverviewResponse(
        **vars(summary),
        catalog_items=len(catalog),
        enemy_kinds=len(get_context().balance["enemies"]),
        core_version=get_core_version(),
        level_counts=[{"level": level, "count": count} for level, count in count_levels(pool)],
        monsters=[build_monster_view(row) for row in list_world_monsters(pool)],
        held_items=[
            AdminHeldItemView(
                item_id=row.item_id,
                record_id=row.record_id,
                monster_id=row.monster_id,
                catalog_id=row.catalog_id,
                taken_from_handle=row.taken_from_handle,
                is_broken=row.is_broken,
                is_bound=row.is_bound,
            )
            for row in list_held_items(pool)
        ],
        recent_actions=[
            AdminActionView(
                handle=item.handle,
                action=item.action,
                target=item.target,
                detail=item.detail,
                created_at=item.created_at.isoformat(),
            )
            for item in list_admin_actions(pool)
        ],
    )


def build_monster_view(row: MonsterRow) -> AdminMonsterView:
    """몬스터 한 줄을 응답 절로 옮긴다.

    Args:
        row: 조회 결과 한 줄.

    Returns:
        응답 절.
    """
    return AdminMonsterView(
        record_id=row.record_id,
        catalog_id=row.catalog_id,
        tier=row.tier,
        zone_floor=row.zone_floor,
        entity_slot=row.entity_slot,
        level=row.level,
        level_cap=get_level_cap(row.zone_floor),
        total_xp=row.total_xp,
        alive=row.alive,
        held_items=row.held_items,
    )


@router.put("/api/admin/monster/level", response_model=AdminOverviewResponse)
def save_monster_level(
    request: MonsterLevelRequest, account: CurrentAdmin
) -> AdminOverviewResponse:
    """지속 몬스터의 레벨을 고친다.

    **층 상한을 넘길 수 없다.** 관리자라도 넘기면 폭주 방지(결정 #35)가 뚫리고, 그
    개체를 만난 플레이어는 이길 수 없는 판을 받는다.

    Args:
        request: 대상과 새 레벨.
        account: 관리자 계정.

    Returns:
        갱신된 현황.

    Raises:
        HTTPException: 없는 개체이거나 상한을 넘는 경우.
    """
    pool = get_pool()
    record = find_monster(pool, request.record_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 몬스터다")
    cap = get_level_cap(record.zone_floor)
    if not 1 <= request.level <= cap:
        raise HTTPException(status.HTTP_409_CONFLICT, f"레벨은 1 이상 {cap} 이하다")
    set_monster_level(pool, request.record_id, request.level)
    record_admin_action(
        pool,
        account.account_id,
        "monster.level",
        f"#{request.record_id} {record.catalog_id}",
        f"{record.level} → {request.level}",
    )
    return read_admin_overview(account)


def check_reason(reason: str) -> str:
    """개입 사유를 확인한다.

    **비면 거절한다.** 무엇을 했는지만 남으면 "왜 그랬지" 를 나중에 아무도 답할 수 없고,
    그때 원장은 기록이 아니라 알리바이가 된다.

    Args:
        reason: 받은 사유.

    Returns:
        다듬은 사유.

    Raises:
        HTTPException: 사유가 비었거나 너무 짧은 경우.
    """
    text = reason.strip()
    if len(text) < MIN_REASON_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"사유를 {MIN_REASON_LENGTH}자 이상 적는다 — 되돌릴 수 없는 조작이다",
        )
    return text


@router.post("/api/admin/auction/cancel", response_model=AdminOverviewResponse)
def create_listing_cancel(
    request: AdminReasonRequest, account: CurrentAdmin
) -> AdminOverviewResponse:
    """열린 매물을 강제로 내린다.

    수수료는 돌려주지 않는다 — 일반 취소와 같다. 관리자가 내렸다고 되돌리면 "관리자에게
    부탁하면 수수료가 없다" 가 되고, 그 순간 유일한 화폐 배출구가 샌다.

    Args:
        request: 매물 id 와 사유.
        account: 관리자 계정.

    Returns:
        갱신된 현황.

    Raises:
        HTTPException: 사유가 없거나 내릴 수 없는 매물인 경우.
    """
    reason = check_reason(request.reason)
    detail = apply_listing_cancel(get_pool(), request.target_id)
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "내릴 수 없는 매물이다")
    record_admin_action(get_pool(), account.account_id, "auction.cancel", detail, reason)
    return read_admin_overview(account)


@router.post("/api/admin/item/recall", response_model=AdminOverviewResponse)
def create_item_recall(request: AdminReasonRequest, account: CurrentAdmin) -> AdminOverviewResponse:
    """아이템 하나를 세계에서 거둔다.

    **지우지 않고 파손으로 둔다.** 원장이 이 id 를 가리키므로, 지우면 "이 아이템이 어디로
    갔나" 를 추적할 수 없다.

    발급하는 짝은 만들지 않았다 — 서버가 검증된 런의 결과로만 아이템을 만든다는
    결정 #02 가 관리자 경로 하나로 뚫리면, 그 뒤로는 어떤 아이템도 "정상적으로 나온
    것" 이라고 말할 수 없다.

    Args:
        request: 아이템 id 와 사유.
        account: 관리자 계정.

    Returns:
        갱신된 현황.

    Raises:
        HTTPException: 사유가 없거나 없는 아이템인 경우.
    """
    reason = check_reason(request.reason)
    outcome = apply_item_recall(get_pool(), request.target_id)
    if outcome is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 아이템이다")
    record_admin_action(
        get_pool(),
        account.account_id,
        "item.recall",
        f"#{outcome.item_id} {outcome.catalog_id} (개체 {outcome.owner_entity_id})",
        reason,
    )
    return read_admin_overview(account)


@router.get("/api/admin/catalog", response_model=AdminCatalogResponse)
def read_admin_catalog(account: CurrentAdmin) -> AdminCatalogResponse:
    """콘텐츠 카탈로그와 레벨 곡선을 본다.

    **게임이 읽는 그대로 보여 준다.** 별도 표를 만들어 두면 화면에 적힌 값과 전투가
    쓰는 값이 갈라지고, 그때 이 뷰어는 도움이 아니라 오해의 근원이 된다.

    Args:
        account: 관리자 계정.

    Returns:
        아이템·적·레벨 곡선.
    """
    return AdminCatalogResponse(
        core_version=get_core_version(),
        items=build_item_rows(get_item_catalog()),
        enemies=build_enemy_rows(get_context().balance),
        level_curve=build_level_curve(count_levels(get_pool())),
        caps=build_curve_caps(),
    )
