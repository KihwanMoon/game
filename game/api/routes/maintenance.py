"""정비 규칙 라우트 (설계/4_아이템 §5).

읽기와 저장뿐이다. **실행은 여기 없다** — 티켓이 닫힐 때 제출 경로가 부른다. 실행
라우트를 열면 「런 중에 정비를 돌려 가방을 바꾸는」 길이 생긴다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas import MaintenanceView
from game.app.store.maintenance import (
    DISCARD_CHOICES,
    MaintenanceRule,
    read_maintenance,
    save_maintenance,
)

router = APIRouter()


@router.get("/api/maintenance", response_model=MaintenanceView)
def read_maintenance_rule(account: CurrentAccount) -> MaintenanceView:
    """정비 규칙을 읽는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        지금 규칙. 저장한 적이 없으면 전부 꺼짐이다.
    """
    rule = read_maintenance(get_pool(), account.account_id)
    return MaintenanceView(
        is_refill_on=rule.is_refill_on,
        is_repair_on=rule.is_repair_on,
        discard_grade=rule.discard_grade,
    )


@router.put("/api/maintenance", response_model=MaintenanceView)
def save_maintenance_rule(request: MaintenanceView, account: CurrentAccount) -> MaintenanceView:
    """정비 규칙을 저장한다.

    Args:
        request: 새 규칙.
        account: 토큰으로 푼 계정.

    Returns:
        저장된 규칙.

    Raises:
        HTTPException: 버리기 등급이 닫힌 목록 밖인 경우 — 오타가 조용히 「안 버림」이
            되면 켰다고 믿은 사람의 가방이 안 비워진다.
    """
    if request.discard_grade not in DISCARD_CHOICES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "버릴 수 없는 등급이다")
    save_maintenance(
        get_pool(),
        account.account_id,
        MaintenanceRule(
            is_refill_on=request.is_refill_on,
            is_repair_on=request.is_repair_on,
            discard_grade=request.discard_grade,
        ),
    )
    return request
