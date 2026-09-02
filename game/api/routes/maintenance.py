"""정비 규칙 라우트 (설계/4_아이템 §5).

읽기와 저장뿐이다. **실행은 여기 없다** — 티켓이 닫힐 때 제출 경로가 부른다. 실행
라우트를 열면 「런 중에 정비를 돌려 가방을 바꾸는」 길이 생긴다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas import MaintenanceRowView, MaintenanceView
from game.app.store.maintenance import (
    MaintenanceRow,
    check_rows,
    read_maintenance,
    save_maintenance,
)

router = APIRouter()


@router.get("/api/maintenance", response_model=MaintenanceView)
def read_maintenance_rule(account: CurrentAccount) -> MaintenanceView:
    """정비 행들을 읽는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        지금 행들. 저장한 적이 없으면 빈 목록이다.
    """
    rows = read_maintenance(get_pool(), account.account_id)
    return MaintenanceView(
        rows=[MaintenanceRowView(action=row.action, grade=row.grade) for row in rows]
    )


@router.put("/api/maintenance", response_model=MaintenanceView)
def save_maintenance_rule(request: MaintenanceView, account: CurrentAccount) -> MaintenanceView:
    """정비 행들을 저장한다. 순서 그대로다.

    Args:
        request: 새 행들.
        account: 토큰으로 푼 계정.

    Returns:
        저장된 행들.

    Raises:
        HTTPException: 닫힌 어휘 밖의 행이 있는 경우 — 오타가 조용히 「안 함」이 되면
            켰다고 믿은 정비가 안 돈다.
    """
    rows = tuple(MaintenanceRow(action=row.action, grade=row.grade) for row in request.rows)
    problem = check_rows(rows)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)
    save_maintenance(get_pool(), account.account_id, rows)
    return request
