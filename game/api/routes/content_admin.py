"""콘텐츠 초안 라우트 — 편집과 검증까지만 (설계/4_아이템 §15.7 의 반대편).

**여기서 게임이 바뀌지 않는다.** 스킬·블록·밸런스·룸·적 규칙표는 두 코어가 함께 읽는
실행 자산이고, 브라우저는 빌드 시점에 번들로 인라인한다. 런타임에 DB 를 보게 만들면
서버가 없을 때 게임이 안 돈다 — 이 저장소가 지키는 전제다.

그래서 라우트는 초안을 받아 **코어가 쓰는 그 로더로 읽어 보기만** 한다. 파일을 쓰는 것은
`scripts/publish_content.py` 이고, 그것은 사람이 부른다. 자동으로 반영되면 순위표 시즌이
아무도 모르게 갈린다.
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAdmin, get_pool
from game.api.routes.admin import check_reason
from game.api.view_schemas import (
    ContentAssetResponse,
    ContentDraftRequest,
    ContentDraftResponse,
    ContentDraftRow,
)
from game.app.content.validate import check_draft
from game.app.store.admin import record_admin_action
from game.app.store.content_draft import (
    DRAFT_ASSETS,
    list_drafts,
    read_draft,
    remove_draft,
    save_draft,
)

router = APIRouter()

PUBLISH_HINT = (
    "초안은 게임에 반영되지 않는다. `scripts/publish_content.py` 로 파일을 쓰고,"
    " 커밋·배포해야 두 코어가 그것을 읽는다 — 자동으로 반영되면 시즌이 모르게 갈린다."
)


def read_current_version(asset: str) -> int:
    """그 자산 파일의 지금 세대를 읽는다.

    Args:
        asset: 자산 이름.

    Returns:
        세대. 파일이 없거나 키가 없으면 0.
    """
    path, version_key = DRAFT_ASSETS[asset]
    source = Path(path)
    if not source.exists():
        return 0
    raw = json.loads(source.read_text(encoding="utf-8"))
    return int(raw.get(version_key, 0))


def build_response(problem: str = "") -> ContentDraftResponse:
    """편집 화면 하나를 만든다.

    Args:
        problem: 방금 검증이 낸 사유. 통과면 빈 문자열.

    Returns:
        초안 목록과 안내.
    """
    return ContentDraftResponse(
        drafts=[
            ContentDraftRow(
                asset=asset,
                note=note,
                updated_at=updated_at,
                current_version=read_current_version(asset),
            )
            for asset, note, updated_at in list_drafts(get_pool())
        ],
        assets=sorted(DRAFT_ASSETS),
        problem=problem,
        publish_hint=PUBLISH_HINT,
    )


@router.get("/api/admin/content", response_model=ContentDraftResponse)
def read_content_drafts(account: CurrentAdmin) -> ContentDraftResponse:
    """초안 목록을 본다.

    Args:
        account: 관리자.

    Returns:
        초안 목록과 안내.
    """
    return build_response()


@router.post("/api/admin/content/draft", response_model=ContentDraftResponse)
def create_content_draft(
    request: ContentDraftRequest, account: CurrentAdmin
) -> ContentDraftResponse:
    """초안을 저장한다. 저장 전에 코어의 로더로 읽어 본다.

    검증을 저장 뒤로 미루면 못 읽는 절이 DB 에 남고, 그것을 발행하면 배포가 서버를
    죽인다 — 그때는 이미 파일이 커밋된 뒤다.

    Args:
        request: 자산·절·사유.
        account: 관리자.

    Returns:
        갱신된 초안 목록.

    Raises:
        HTTPException: 모르는 자산이거나, 절을 읽을 수 없거나, 버전을 안 올린 경우.
    """
    reason = check_reason(request.note)
    if request.asset not in DRAFT_ASSETS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"모르는 자산이다: {request.asset}")
    problem = check_draft(request.asset, request.payload, read_current_version(request.asset))
    if problem:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    pool = get_pool()
    save_draft(pool, request.asset, request.payload, reason, account.account_id)
    record_admin_action(pool, account.account_id, "content_draft", request.asset, reason)
    return build_response()


@router.post("/api/admin/content/discard", response_model=ContentDraftResponse)
def create_content_discard(
    request: ContentDraftRequest, account: CurrentAdmin
) -> ContentDraftResponse:
    """초안을 버린다. 파일은 안 건드린다 — 발행 전이라 게임에 없던 것이다.

    Args:
        request: 자산과 사유. `payload` 는 안 본다.
        account: 관리자.

    Returns:
        갱신된 초안 목록.
    """
    reason = check_reason(request.note)
    pool = get_pool()
    remove_draft(pool, request.asset)
    record_admin_action(pool, account.account_id, "content_discard", request.asset, reason)
    return build_response()


@router.get("/api/admin/content/{asset}", response_model=ContentAssetResponse)
def read_content_asset(asset: str, account: CurrentAdmin) -> ContentAssetResponse:
    """자산 하나의 지금 내용과 초안을 본다.

    **지금 파일을 함께 낸다.** 편집은 백지가 아니라 지금 것에서 시작해야 한다 — 화면이
    그것을 모르면 관리자가 손으로 옮겨 적게 되고, 그 순간 오타가 콘텐츠가 된다.

    Args:
        asset: 자산 이름.
        account: 관리자.

    Returns:
        지금 파일과 초안.

    Raises:
        HTTPException: 모르는 자산인 경우.
    """
    if asset not in DRAFT_ASSETS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"모르는 자산이다: {asset}")
    path, version_key = DRAFT_ASSETS[asset]
    current = json.loads(Path(path).read_text(encoding="utf-8"))
    pool = get_pool()
    notes = {name: note for name, note, _at in list_drafts(pool)}
    return ContentAssetResponse(
        asset=asset,
        current=current,
        draft=read_draft(pool, asset),
        note=notes.get(asset, ""),
        version_key=version_key,
    )
