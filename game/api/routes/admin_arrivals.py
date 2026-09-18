"""새로 들어온 계정을 보는 관리자 라우트 (U1).

**볼 자리가 없어서 DB 를 직접 열어야 했다.** 관리 화면 탭 열하나 중 계정을 보는 곳은
테스터 탭 하나뿐이고, 그것은 G1 의 분모를 정하려고 사람이 손으로 고르는 자리다.
「어제 몇 명이 들어왔고 그중 누가 가입했나」를 볼 자리가 없으면 아무도 안 본다 —
봇 탭과 지킴이 탭을 만든 것과 같은 이유다.

**읽기만 한다.** 이 문으로는 아무것도 안 바뀐다.
"""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from game.api.deps import CurrentAdmin, get_pool
from game.app.store.arrivals import (
    DEFAULT_ARRIVAL_DAYS,
    MAX_ARRIVALS,
    list_arrivals,
    read_arrival_summary,
)

router = APIRouter()


class ArrivalView(BaseModel):
    """새로 들어온 계정 한 줄."""

    account_id: int = 0
    name: str = ""
    is_joined: bool = False
    is_bot: bool = False
    created_at: str = ""
    runs: int = 0
    best_floor: int = 0


class ArrivalListResponse(BaseModel):
    """유입 목록과 요약.

    **둘을 함께 낸다.** 스무 줄을 눈으로 세는 것과 「어제 스물, 그중 둘이 가입」을 읽는
    것은 다르다.
    """

    days: int = DEFAULT_ARRIVAL_DAYS
    arrived: int = 0
    joined: int = 0
    played: int = 0
    rows: list[ArrivalView] = Field(default_factory=list)


@router.get("/api/admin/arrivals", response_model=ArrivalListResponse)
def read_admin_arrivals(
    account: CurrentAdmin,
    days: int = Query(default=DEFAULT_ARRIVAL_DAYS, ge=1, le=90),
) -> ArrivalListResponse:
    """최근에 들어온 계정을 새것부터 낸다.

    Args:
        account: 관리자 계정. 문지기가 이미 검증했다.
        days: 며칠치를 볼 것인가.

    Returns:
        목록과 요약.
    """
    # `account` 는 문지기가 채운다 — 여기서 다시 보지 않는다.
    _ = account
    pool = get_pool()
    summary = read_arrival_summary(pool, days)
    rows = [
        ArrivalView(
            account_id=row.account_id,
            name=row.name,
            is_joined=row.is_joined,
            is_bot=row.is_bot,
            created_at=row.created_at,
            runs=row.runs,
            best_floor=row.best_floor,
        )
        for row in list_arrivals(pool, days, MAX_ARRIVALS)
    ]
    return ArrivalListResponse(
        days=summary.days,
        arrived=summary.arrived,
        joined=summary.joined,
        played=summary.played,
        rows=rows,
    )
