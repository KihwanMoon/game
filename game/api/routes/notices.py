"""알림함 — 읽기와 읽음 적기 (2026-09-25).

판이 끝난 결과와 없는 동안 생긴 일이 여기 쌓인다. 화면은 새로 온 것을 토스트로 띄우고,
읽을 때까지 안 읽은 수를 적는다. 적는 쪽은 각 서비스이고 여기는 얇게 둔다.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from game.api.deps import CurrentAccount, get_pool
from game.app.store.notices import (
    NOTICE_LIMIT,
    NOTICE_PAGE,
    apply_notices_read,
    count_notices,
    count_unread_notices,
    list_notices,
)

router = APIRouter()


class NoticeRow(BaseModel):
    """알림 한 건."""

    id: int
    kind: str
    title: str
    # 서버가 확정한 본문. 항목은 `·` 로 이어져 있고 화면이 그것으로 끊는다.
    body: str
    created_at: str
    is_read: bool


class NoticeBoard(BaseModel):
    """알림함."""

    unread: int
    # 전체 건수. 화면이 쪽 수를 이것으로 센다.
    total: int
    # 이 쪽이 몇 건을 건너뛰었나. 화면이 몇 쪽인지 되짚는 데 쓴다.
    offset: int
    notices: list[NoticeRow]


class NoticeReadRequest(BaseModel):
    """여기까지 읽었다. 화면이 본 가장 새 id 다."""

    up_to_id: int = Field(ge=0)


def build_board(account_id: int, offset: int = 0, limit: int = NOTICE_PAGE) -> NoticeBoard:
    """알림함 한 쪽을 만든다.

    Args:
        account_id: 대상 계정.
        offset: 건너뛸 건수.
        limit: 한 쪽의 건수.

    Returns:
        안 읽은 수·전체 수와 그 쪽의 알림.
    """
    pool = get_pool()
    return NoticeBoard(
        unread=count_unread_notices(pool, account_id),
        total=count_notices(pool, account_id),
        offset=offset,
        notices=[
            NoticeRow(
                id=one.notice_id,
                kind=one.kind,
                title=one.title,
                body=one.body,
                created_at=one.created_at.isoformat(),
                is_read=one.is_read,
            )
            for one in list_notices(pool, account_id, limit, offset)
        ],
    )


@router.get("/api/notices", response_model=NoticeBoard)
def read_notices(
    account: CurrentAccount,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=NOTICE_PAGE, ge=1, le=NOTICE_LIMIT),
) -> NoticeBoard:
    """내 알림함 한 쪽을 읽는다. **읽기만으로는 읽음이 안 된다** — 토스트를 띄울 새것을 가르려면.

    Args:
        account: 토큰으로 푼 계정.
        offset: 건너뛸 건수. 쪽 번호 × 쪽 크기다.
        limit: 한 쪽의 건수.

    Returns:
        알림함 한 쪽.
    """
    return build_board(account.account_id, offset, limit)


@router.post("/api/notices/read", response_model=NoticeBoard)
def save_notices_read(request: NoticeReadRequest, account: CurrentAccount) -> NoticeBoard:
    """그 id 까지 읽음으로 적는다.

    Args:
        request: 화면이 본 가장 새 id.
        account: 토큰으로 푼 계정.

    Returns:
        읽음을 적은 뒤의 알림함.
    """
    apply_notices_read(get_pool(), account.account_id, request.up_to_id)
    return build_board(account.account_id)
