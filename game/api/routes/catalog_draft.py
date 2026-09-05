"""아이템 카탈로그 초안·발행 라우트 (설계/9_에이전트_운영 §3.2).

**아이템만 문이 열려 있었다.** 스킬·블록·밸런스·룸·적 규칙표는 사람이 발행을 눌러야
반영되는데, 카탈로그는 정본이 DB 라 등록·수정·폐기가 **즉시** 세계를 바꿨다. 그 상태로
아이템 에이전트를 붙이면 검토 없이 세계가 바뀐다.

이제 셋 다 초안으로 간다. `author` 가 올리고 `owner` 가 발행한다.

**세대는 발행이 한 번만 올린다.** 예전에는 조작마다 올라서 아이템 열 개를 손보면 시즌
경계가 열 번 그였다 (§15.8). 한 번 발행이 한 번 경계다.

**검사는 두 번 돈다.** 올릴 때와 발행할 때다 — 그 사이에 카탈로그가 움직이기 때문이고,
올릴 때도 하는 이유는 올린 사람이 그 자리에서 알아야 하기 때문이다.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from game.api.catalog_apply import (
    CatalogConflictError,
    CatalogMissingError,
    apply_draft,
    check_draft,
    check_edit,
    check_item,
    check_retire,
)
from game.api.deps import (
    CurrentAdmin,
    CurrentAuthor,
    CurrentOwner,
    apply_catalog_reload,
    get_pool,
)
from game.api.routes.admin import check_reason
from game.api.routes.catalog_admin import read_catalog_items
from game.api.view_schemas import (
    CatalogAdminResponse,
    CatalogEditRequest,
    CatalogItemRequest,
    CatalogRetireRequest,
)
from game.app.store.admin import record_admin_action
from game.app.store.catalog_draft import (
    ACTION_EDIT,
    ACTION_ITEM,
    ACTION_RESTORE,
    ACTION_RETIRE,
    list_catalog_drafts,
    purge_catalog_drafts,
    remove_catalog_draft,
    save_catalog_draft,
)
from game.app.store.item_catalog import apply_generation_bump, read_generation

router = APIRouter()

PUBLISH_HINT = (
    "초안은 아직 아이템이 아니다 — 굴림에도 화면에도 안 나온다."
    " 발행해야 카탈로그에 들어가고, 그때 세대가 한 번 오른다."
)


class CatalogDraftRow(BaseModel):
    """쌓여 있는 조작 한 줄."""

    catalog_id: str
    action: str
    reason: str
    # 누가 올렸는가. **에이전트와 사람을 화면에서 갈라야** 검토가 무엇을 보는 일인지
    # 흐려지지 않는다.
    handle: str
    updated_at: str
    # 지금 카탈로그에 대고 다시 검사한 결과. 통과면 빈 문자열이다. 발행 버튼을 누르기
    # 전에 보여야 한다 — 눌러서 알게 하면 절반이 반영된 상태를 상상하게 된다.
    problem: str


class CatalogDraftResponse(BaseModel):
    """초안 화면 하나."""

    drafts: list[CatalogDraftRow] = Field(default_factory=list)
    generation: int = 0
    hint: str = PUBLISH_HINT


class CatalogDiscardRequest(BaseModel):
    """초안 하나를 버린다."""

    catalog_id: str = Field(min_length=1, max_length=64)


class CatalogPublishRequest(BaseModel):
    """쌓인 것을 전부 반영한다.

    **세대를 손으로 적어야 눌린다.** 콘텐츠 발행과 같은 규율이다 (설계/4_아이템 §18) —
    시즌을 가르는 행위라 실수로 눌리면 안 된다.
    """

    generation: int
    reason: str = ""


def build_draft_response() -> CatalogDraftResponse:
    """초안 화면을 만든다. 줄마다 지금 성립하는지 다시 검사한다.

    Returns:
        초안들과 지금 세대.
    """
    pool = get_pool()
    rows = []
    for draft in list_catalog_drafts(pool):
        problem = ""
        try:
            check_draft(pool, draft)
        except ValueError as error:
            problem = str(error)
        rows.append(
            CatalogDraftRow(
                catalog_id=draft.catalog_id,
                action=draft.action,
                reason=draft.reason,
                handle=draft.handle,
                updated_at=draft.updated_at,
                problem=problem,
            )
        )
    return CatalogDraftResponse(drafts=rows, generation=read_generation(pool))


def save_one(action: str, catalog_id: str, payload: dict, reason: str, account_id: int) -> None:
    """초안 하나를 쌓는다.

    Args:
        action: 무슨 조작인가.
        catalog_id: 대상 아이템.
        payload: 조작에 필요한 절.
        reason: 왜 하는가.
        account_id: 올린 계정.
    """
    pool = get_pool()
    save_catalog_draft(pool, catalog_id, action, payload, reason, account_id)
    # 초안도 원장에 남긴다. 발행만 남기면 "누가 이걸 올렸지" 를 나중에 못 읽는다 —
    # 에이전트가 올리기 시작하면 그 질문이 잦아진다.
    record_admin_action(pool, account_id, f"catalog_draft_{action}", catalog_id, reason)


@router.post("/api/admin/catalog/item", response_model=CatalogDraftResponse)
def create_catalog_item(
    request: CatalogItemRequest, account: CurrentAuthor
) -> CatalogDraftResponse:
    """아이템 등록을 **초안으로** 올린다.

    Args:
        request: 아이템 절과 사유.
        account: 초안을 쓸 수 있는 계정.

    Returns:
        쌓인 초안들.

    Raises:
        HTTPException: 절이 규격을 어겼으면 400, 이미 있는 id 면 409.
    """
    reason = check_reason(request.reason)
    payload = request.model_dump(exclude={"reason"})
    try:
        entry = check_item(get_pool(), payload)
    except CatalogConflictError as error:
        # 「고치려던 것」과 「잘못 썼다」는 다른 답이다.
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    save_one(ACTION_ITEM, entry.catalog_id, payload, reason, account.account_id)
    return build_draft_response()


@router.post("/api/admin/catalog/edit", response_model=CatalogDraftResponse)
def create_catalog_edit(
    request: CatalogEditRequest, account: CurrentAuthor
) -> CatalogDraftResponse:
    """아이템 수정을 **초안으로** 올린다.

    Args:
        request: 대상과 고칠 값들, 사유.
        account: 초안을 쓸 수 있는 계정.

    Returns:
        쌓인 초안들.

    Raises:
        HTTPException: 없는 아이템이면 404, 정본에 없는 스탯이면 400.
    """
    reason = check_reason(request.reason)
    payload = request.model_dump(exclude={"reason"})
    try:
        check_edit(get_pool(), payload)
    except CatalogMissingError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    save_one(ACTION_EDIT, request.catalog_id, payload, reason, account.account_id)
    return build_draft_response()


@router.post("/api/admin/catalog/retire", response_model=CatalogDraftResponse)
def create_catalog_retire(
    request: CatalogRetireRequest, account: CurrentAuthor
) -> CatalogDraftResponse:
    """폐기·복구를 **초안으로** 올린다. 삭제가 아니다.

    Args:
        request: 대상과 사유.
        account: 초안을 쓸 수 있는 계정.

    Returns:
        쌓인 초안들.

    Raises:
        HTTPException: 없는 아이템인 경우.
    """
    reason = check_reason(request.reason)
    try:
        check_retire(get_pool(), request.catalog_id)
    except ValueError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    action = ACTION_RETIRE if request.is_retired else ACTION_RESTORE
    save_one(action, request.catalog_id, {}, reason, account.account_id)
    return build_draft_response()


@router.get("/api/admin/catalog/drafts", response_model=CatalogDraftResponse)
def read_catalog_drafts(account: CurrentAdmin) -> CatalogDraftResponse:
    """쌓여 있는 조작을 본다.

    Args:
        account: 관리자.

    Returns:
        초안들과 지금 세대.
    """
    return build_draft_response()


@router.post("/api/admin/catalog/draft/discard", response_model=CatalogDraftResponse)
def create_catalog_discard(
    request: CatalogDiscardRequest, account: CurrentAuthor
) -> CatalogDraftResponse:
    """초안 하나를 버린다.

    Args:
        request: 버릴 아이템.
        account: 초안을 쓸 수 있는 계정.

    Returns:
        남은 초안들.

    Raises:
        HTTPException: 그런 초안이 없는 경우.
    """
    pool = get_pool()
    if not remove_catalog_draft(pool, request.catalog_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "그런 초안이 없다")
    record_admin_action(pool, account.account_id, "catalog_draft_discard", request.catalog_id, "")
    return build_draft_response()


@router.post("/api/admin/catalog/publish", response_model=CatalogAdminResponse)
def create_catalog_publish(
    request: CatalogPublishRequest, account: CurrentOwner
) -> CatalogAdminResponse:
    """쌓인 것을 전부 반영한다 — **사람이 누른다**.

    **전부 검사한 뒤에 하나도 안 쓴 상태에서 시작한다.** 먹이면서 검사하면 절반이 들어간
    상태로 멈추고, 그때 카탈로그가 어디까지 먹었는지를 화면에서 읽을 수 없다.

    Args:
        request: 지금 세대와 사유.
        account: 발행할 수 있는 계정. **사람만 받는다.**

    Returns:
        갱신된 카탈로그.

    Raises:
        HTTPException: 세대가 어긋났거나, 쌓인 것이 없거나, 하나라도 성립하지 않는 경우.
            사유가 비어도 거절한다 — 시즌을 가르는 행위라 왜 했는지가 남아야 한다.
    """
    reason = check_reason(request.reason)
    pool = get_pool()
    generation = read_generation(pool)
    if request.generation != generation:
        # **세대를 손으로 적어야 눌린다.** 그 사이에 다른 발행이 있었다면 지금 보고 있는
        # 초안 목록이 이미 옛것이다.
        raise HTTPException(status.HTTP_409_CONFLICT, f"세대가 어긋났다 — 지금은 {generation} 이다")
    drafts = list_catalog_drafts(pool)
    if not drafts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "쌓인 것이 없다")

    # **먼저 전부 본다.** 하나라도 안 되면 아무것도 안 쓴 채로 돌려보낸다.
    for draft in drafts:
        try:
            check_draft(pool, draft)
        except ValueError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, f"{draft.catalog_id}: {error}") from error

    lines = []
    for draft in drafts:
        try:
            lines.append(apply_draft(pool, draft))
        except ValueError as error:
            # 위에서 전부 봤는데도 여기까지 온 것은, 그 사이에 다른 발행이 카탈로그를
            # 움직였다는 뜻이다. 앞의 것은 이미 들어갔으므로 **무엇까지 들어갔는지
            # 말한다** — 되돌리려면 카탈로그를 통째로 스냅숏해야 하고, 그것은 이 표의
            # 크기에서 정직하지 않다.
            apply_catalog_reload()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"{draft.catalog_id}: {error} (앞의 {len(lines)}건은 이미 들어갔다)",
            ) from error

    next_generation = apply_generation_bump(pool)
    purge_catalog_drafts(pool)
    apply_catalog_reload()
    record_admin_action(
        pool,
        account.account_id,
        "catalog_publish",
        f"세대 {next_generation}",
        f"{len(lines)}건 · {' / '.join(lines)} · {reason}",
    )
    return read_catalog_items(account)
