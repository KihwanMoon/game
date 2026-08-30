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

from game.api.deps import (
    CurrentAdmin,
    get_context,
    get_core_version,
    get_item_catalog,
    get_pool,
)
from game.api.schemas import (
    AdminActionView,
    AdminMonsterView,
    AdminOverviewResponse,
    MonsterLevelRequest,
)
from game.app.monsters.growth import get_level_cap
from game.app.store.admin import list_admin_actions, record_admin_action
from game.app.store.monsters import find_monster, set_monster_level
from game.app.store.world_view import (
    MonsterRow,
    count_levels,
    list_world_monsters,
    read_world_summary,
)

router = APIRouter()


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
