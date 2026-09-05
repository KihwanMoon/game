"""정비 규칙 라우트 (설계/4_아이템 §5).

읽기·저장과 **손으로 한 번 돌리기**다.

실행 라우트를 오래 안 두었다. 「런 중에 정비를 돌려 가방을 바꾸는」 길이 생기기 때문인데,
그 조심이 정반대의 구멍을 냈다 — 정비가 **티켓이 닫힐 때만** 도는데 티켓은 죽거나 마지막
층을 깨야 닫힌다. 7층까지 이기고 그만두는 판은 영영 안 닫히고, 그런 사람에게는 정비가
한 번도 안 돌았다. 봇은 매판 죽어서 늘 닫히므로 봇에서만 도는 것처럼 보였다.

그래서 두 자리를 열었다. **다음 티켓을 받을 때** 서버가 부르고(`routes/ticket`), 여기는
사람이 지금 돌리고 싶을 때 부른다. 런 중에 눌러도 위험하지 않은 이유는 전투가 **티켓이
얼려 둔 로드아웃**으로 돌기 때문이다 — 지금 가방을 바꿔도 돌고 있는 판은 안 흔들린다.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_pool
from game.api.maintenance_service import apply_maintenance
from game.api.schemas_gear import MaintenanceRowView, MaintenanceRunView, MaintenanceView
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


@router.post("/api/maintenance/run", response_model=MaintenanceRunView)
def apply_maintenance_now(account: CurrentAccount) -> MaintenanceRunView:
    """지금 정비를 한 번 돌린다.

    **저장된 행 그대로 돈다.** 여기서 무엇을 할지 고르게 하면 규칙표가 둘이 된다 — 화면이
    보여주는 순서와 실제로 도는 순서가 갈리는 순간, 미리보기가 거짓말이 된다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        무슨 일이 있었는지 한 줄. 한 일이 없으면 빈 문자열이다 — 그것도 답이라,
        화면이 「할 일이 없었다」로 적는다.
    """
    return MaintenanceRunView(detail=apply_maintenance(account.account_id))
