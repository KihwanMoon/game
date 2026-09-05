"""카탈로그 관리 라우트 — 조회·등록·폐기 (설계/4_아이템 §15.7).

**삭제가 없다.** 인스턴스·원장·경매가 `catalog_id` 를 가리키므로 지우면 과거 기록을 못
읽는다. 폐기는 "새로 안 나온다" 만 뜻한다.

**제자리 수정이 제한된다.** 접사·등급·분류를 고치면 이미 나온 아이템이 소급해 바뀐다 —
인스턴스가 굴린 접사가 없으면 카탈로그 기본값을 쓰기 때문이다. 그런 수정은 "새 id 등록 +
옛 id 폐기" 로만 한다. 그 규율은 `catalog_admin.py` 가 지킨다.

**모든 변경이 세대를 올린다.** 아이템을 고치는 것은 순위표 시즌을 가르는 일이고, 그
사실이 코어 버전 문자열에 남아야 한다 (§15.8). 세대를 안 올리면 관리자가 조용히 과거
기록을 무효로 만든다.

관리자 라우트는 404 로 답한다 — 존재 자체를 흘리지 않는다.
"""

from dataclasses import replace

from fastapi import APIRouter, HTTPException, status

from game.api.catalog_admin import build_entry_from_request, list_locked_changes
from game.api.catalog_view import format_affix
from game.api.deps import (
    CurrentAdmin,
    CurrentOwner,
    apply_catalog_reload,
    get_pool,
)
from game.api.routes.admin import check_reason
from game.api.view_schemas import (
    CatalogAdminResponse,
    CatalogAdminRow,
    CatalogEditRequest,
    CatalogItemRequest,
    CatalogRetireRequest,
    MonsterDropRequest,
    MonsterDropResponse,
    MonsterDropRow,
)
from game.app.store.admin import record_admin_action
from game.app.store.drops import (
    SOURCE_ANY,
    find_source,
    list_monster_drops,
    save_monster_drop,
    save_source,
)
from game.app.store.item_catalog import (
    DEFAULT_GRADES,
    apply_generation_bump,
    apply_retire,
    list_catalog,
    read_generation,
    save_catalog_entry,
)
from game.schemas.item import (
    COMBAT_STATS,
    ItemCatalogEntry,
    list_grades_above,
    list_unknown_stats,
    parse_affix,
)

router = APIRouter()


def read_drop_weights() -> dict[str, int]:
    """드롭 표의 아이템 가중치를 읽는다. 표에 없으면 0 이다.

    Returns:
        catalog_id 에서 가중치로.
    """
    pool = get_pool()
    source_id = find_source(pool, SOURCE_ANY)
    if source_id is None:
        return {}
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, weight FROM drop_item_weight WHERE source_id = %s", (source_id,)
        ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def build_admin_row(entry: ItemCatalogEntry, weight: int) -> CatalogAdminRow:
    """카탈로그 항목을 관리 화면 줄로 만든다.

    Args:
        entry: 카탈로그 항목.
        weight: 드롭 표의 가중치. 0 이면 굴려도 안 나온다.

    Returns:
        관리 줄.
    """
    return CatalogAdminRow(
        catalog_id=entry.catalog_id,
        kind=str(entry.kind.value),
        label_ko=entry.label_ko,
        slot=str(entry.slot.value) if entry.slot else "",
        hands=str(entry.hands.value) if entry.hands else "",
        grade=entry.grade,
        min_floor=entry.min_floor,
        is_retired=entry.is_retired,
        affixes=[format_affix(a) for a in entry.affixes],
        affix_rows=[
            {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
            for a in entry.affixes
        ],
        requirements=[f"{r.stat} >= {r.minimum}" for r in entry.requirements],
        grants_skill=entry.grants_skill or "",
        use_tag=entry.use_tag or "",
        attack_range=entry.attack_range or 0,
        drop_weight=weight,
    )


@router.get("/api/admin/catalog/items", response_model=CatalogAdminResponse)
def read_catalog_items(account: CurrentAdmin) -> CatalogAdminResponse:
    """카탈로그 전량을 본다. 폐기된 것도 함께 낸다.

    Args:
        account: 관리자.

    Returns:
        카탈로그 줄들과 세대.
    """
    pool = get_pool()
    weights = read_drop_weights()
    catalog = list_catalog(pool)
    return CatalogAdminResponse(
        items=[build_admin_row(catalog[key], weights.get(key, 0)) for key in sorted(catalog)],
        generation=read_generation(pool),
        grades=[code for code, _rank, _label in DEFAULT_GRADES],
        stats=list(COMBAT_STATS),
    )


def apply_drop_entry(catalog_id: str, grade: str) -> None:
    """새 아이템을 드롭 표에 올린다. 가중치는 1 로 시작한다.

    올리지 않으면 등록해도 **굴려서 나오지 않는다.** 등록과 드롭 표를 따로 두면 "왜 안
    나오지" 가 되고, 그 답은 화면 어디에도 없다.

    **등급마다 한 줄씩 올린다.** 카탈로그의 `grade` 는 「이 등급부터」라는 뜻이므로, 한
    칸에만 올리면 상위 등급을 뽑았을 때 후보가 없어 굴림이 증발한다 (§15.4).

    Args:
        catalog_id: 새 아이템.
        grade: 그 아이템의 최저 등급.
    """
    pool = get_pool()
    source_id = save_source(pool, SOURCE_ANY)
    with pool.connection() as connection:
        for code in list_grades_above(grade):
            connection.execute(
                "INSERT INTO drop_item_weight (source_id, grade, catalog_id, weight)"
                " VALUES (%s, %s, %s, 1) ON CONFLICT DO NOTHING",
                (source_id, code, catalog_id),
            )


@router.post("/api/admin/catalog/item", response_model=CatalogAdminResponse)
def create_catalog_item(request: CatalogItemRequest, account: CurrentOwner) -> CatalogAdminResponse:
    """아이템 종류를 등록하거나 이름·최소 층을 고친다.

    Args:
        request: 아이템 절과 사유.
        account: 관리자.

    Returns:
        갱신된 카탈로그.

    Raises:
        HTTPException: 절이 규격을 어겼거나, 제자리에서 고칠 수 없는 것을 고치려는 경우.
    """
    reason = check_reason(request.reason)
    payload = request.model_dump(exclude={"reason"})
    try:
        entry = build_entry_from_request(payload)
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error

    pool = get_pool()
    catalog = list_catalog(pool)
    before = catalog.get(entry.catalog_id)
    if before is not None:
        # **고치기는 `/edit` 이 한다.** 여기로 오는 것은 등록뿐이고, 있는 id 로 등록하려는
        # 것은 십중팔구 "고치려던 것" 이다 — 그 사실을 사유에 적어 돌려준다.
        locked = list_locked_changes(before, entry)
        detail = (
            "이미 있는 id 다 — 이름·최소 층은 고치기로,"
            " 나머지는 새 id 로 등록하고 옛 id 를 폐기한다"
        )
        if locked:
            detail = f"{detail} ({', '.join(locked)} 이(가) 다르다)"
        raise HTTPException(status.HTTP_409_CONFLICT, detail)
    save_catalog_entry(pool, entry)
    if before is None:
        apply_drop_entry(entry.catalog_id, entry.grade)
    generation = apply_generation_bump(pool)
    apply_catalog_reload()
    record_admin_action(
        pool,
        account.account_id,
        "catalog_item",
        entry.catalog_id,
        f"세대 {generation} · {reason}",
    )
    return read_catalog_items(account)


@router.post("/api/admin/catalog/retire", response_model=CatalogAdminResponse)
def create_catalog_retire(
    request: CatalogRetireRequest, account: CurrentOwner
) -> CatalogAdminResponse:
    """아이템 종류를 폐기하거나 되살린다. 지우지 않는다.

    Args:
        request: 대상과 사유.
        account: 관리자.

    Returns:
        갱신된 카탈로그.

    Raises:
        HTTPException: 없는 id 인 경우.
    """
    reason = check_reason(request.reason)
    pool = get_pool()
    if request.catalog_id not in list_catalog(pool):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 아이템이다")
    apply_retire(pool, request.catalog_id, request.is_retired)
    generation = apply_generation_bump(pool)
    apply_catalog_reload()
    record_admin_action(
        pool,
        account.account_id,
        "catalog_retire" if request.is_retired else "catalog_restore",
        request.catalog_id,
        f"세대 {generation} · {reason}",
    )
    return read_catalog_items(account)


@router.get("/api/admin/drops/{kind_id}", response_model=MonsterDropResponse)
def read_monster_drops(kind_id: str, account: CurrentAdmin) -> MonsterDropResponse:
    """그 몬스터에게만 걸린 드롭 표를 본다 (D3).

    **소스별 표가 없으면 `ANY` 로 떨어진다.** 그 사실이 화면에 있어야 "왜 다른 게
    나오지" 를 안 겪는다.

    Args:
        kind_id: 몬스터 종.
        account: 관리자.

    Returns:
        드롭 줄들과 기본 표를 쓰는지 여부.
    """
    pool = get_pool()
    catalog = list_catalog(pool)
    rows = list_monster_drops(pool, kind_id)
    return MonsterDropResponse(
        kind_id=kind_id,
        rows=[
            MonsterDropRow(
                grade=grade,
                catalog_id=catalog_id,
                label_ko=catalog[catalog_id].label_ko if catalog_id in catalog else "",
                weight=weight,
            )
            for grade, catalog_id, weight in rows
        ],
        uses_default=not rows,
    )


@router.post("/api/admin/drops", response_model=MonsterDropResponse)
def create_monster_drop(request: MonsterDropRequest, account: CurrentOwner) -> MonsterDropResponse:
    """몬스터별 드롭 줄을 세운다 (D3).

    **첫 줄을 세우는 순간 그 몬스터는 `ANY` 를 안 본다.** 두 표를 합치면 "이 몬스터만
    떨군다" 가 성립하지 않고, 도감이 표적 목록이 되는 근거가 그 배타성이다 — 그래서
    첫 등록이 그 몬스터의 드롭을 통째로 바꾼다.

    드롭 표는 코어 버전을 안 바꾼다. 굴림은 서버 밖(재시뮬 뒤)에서 일어나므로 리플레이가
    달라지지 않는다 — 아이템 카탈로그와 다른 점이다.

    Args:
        request: 종·등급·아이템·가중치와 사유.
        account: 관리자.

    Returns:
        갱신된 드롭 표.

    Raises:
        HTTPException: 없는 아이템이거나 사유가 없는 경우.
    """
    reason = check_reason(request.reason)
    pool = get_pool()
    if request.catalog_id not in list_catalog(pool):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 아이템이다")
    save_monster_drop(pool, request.kind_id, request.grade, request.catalog_id, request.weight)
    record_admin_action(
        pool,
        account.account_id,
        "monster_drop",
        f"{request.kind_id}/{request.catalog_id}",
        f"가중치 {request.weight} · {reason}",
    )
    return read_monster_drops(request.kind_id, account)


@router.post("/api/admin/catalog/edit", response_model=CatalogAdminResponse)
def create_catalog_edit(request: CatalogEditRequest, account: CurrentOwner) -> CatalogAdminResponse:
    """이미 있는 아이템의 이름과 최소 층을 고친다 (§15.7).

    **고칠 수 있는 것만 받는다.** 접사·등급·분류를 받을 자리가 없으므로 소급 수정이
    표현 불가능하고, 그러면 "화면이 빠뜨린 필드가 바뀐 것으로 읽히는" 사고도 같이
    사라진다 — 전체 절을 받던 때는 그 사고로 이름 바꾸기가 전부 거절됐다.

    나머지 필드는 **저장된 것을 그대로 쓴다.** 부르는 쪽이 되풀이해 보내지 않는다.

    Args:
        request: 대상과 새 이름·최소 층, 사유.
        account: 관리자.

    Returns:
        갱신된 카탈로그.

    Raises:
        HTTPException: 없는 아이템이거나, 정본에 없는 스탯에 접사를 붙인 경우.
    """
    reason = check_reason(request.reason)
    pool = get_pool()
    before = list_catalog(pool).get(request.catalog_id)
    if before is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "없는 아이템이다")
    # **접사를 안 보내면 지금 것을 그대로 둔다.** 빈 목록을 "접사를 지운다" 로 읽으면
    # 이름만 고치려던 요청이 아이템을 맹탕으로 만든다.
    affixes = (
        before.affixes
        if not request.affixes
        else tuple(parse_affix(item) for item in request.affixes)
    )
    # 등록과 같은 문지기를 둔다. 여기만 비면 **실제로 쓰는 경로**가 검사를 안 받는다 —
    # 수치를 고치는 일은 등록보다 훨씬 자주 일어난다.
    unknown = list_unknown_stats(affixes)
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 스탯이다: {', '.join(unknown)}")
    save_catalog_entry(
        pool,
        replace(
            before,
            label_ko=request.label_ko,
            min_floor=request.min_floor,
            grade=request.grade or before.grade,
            affixes=affixes,
            attack_range=(
                before.attack_range if request.attack_range is None else request.attack_range
            ),
            use_tag=before.use_tag if request.use_tag is None else (request.use_tag or None),
        ),
    )
    generation = apply_generation_bump(pool)
    apply_catalog_reload()
    record_admin_action(
        pool,
        account.account_id,
        "catalog_edit",
        request.catalog_id,
        f"세대 {generation} · {reason}",
    )
    return read_catalog_items(account)
