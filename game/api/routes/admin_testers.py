"""부른 테스터를 표시하는 라우트 (로드맵 §게이트 G1).

**G1 의 분모를 사람이 정하는 자리다.** 게이트는 「테스터 5명 중 3명」을 묻는데 이 게임은
익명으로 시작하므로, 자동으로 세면 한 판 내고 떠난 계정까지 전부 테스터가 된다 —
그것이 평균 재도전을 1.2회로 눌러 놓고 있었다. 누구를 불렀는지는 사람만 알고 있다.

**표시는 개입이라 원장에 남긴다.** 분모를 바꾸는 일이므로, 나중에 「이 숫자가 왜 이렇지」
를 물었을 때 누가 언제 누구를 넣고 뺐는지가 읽혀야 한다.

이 경로는 계정을 **표시만** 한다. 표시된 계정에 권한이 생기지 않고, 세계 상태도 안
바뀐다 — 바뀌는 것은 `report_g1.py` 가 세는 분모뿐이다.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from game.api.deps import (
    CurrentAdmin,
    CurrentOperator,
    get_pool,
)
from game.app.store.admin import record_admin_action
from game.app.store.testers import (
    MIN_TESTERS,
    TesterRow,
    apply_tester_mark,
    count_testers,
    list_candidates,
)

router = APIRouter()

# 화면에 뿌릴 최대 줄 수. 익명 계정은 접속마다 늘어나므로 상한이 없으면 화면이 못 쓰게
# 된다. 표시된 계정은 정렬에서 늘 앞에 오므로 이 상한에 밀려 사라지지 않는다.
MAX_ROWS = 200


class TesterMarkRequest(BaseModel):
    """계정 하나의 테스터 표시를 켜거나 끈다."""

    account_id: int = Field(ge=1)
    is_tester: bool


class TesterView(BaseModel):
    """표시 화면의 한 줄.

    익명 계정은 번호밖에 없으므로 **제출 수와 마지막 접속을 함께 준다** — 그것 없이는
    어느 줄이 누구인지 짐작할 단서가 화면에 하나도 없다.
    """

    account_id: int
    handle: str
    login_id: str
    is_tester: bool
    attempts: int
    last_seen: str


class TesterListResponse(BaseModel):
    """표시 화면 한 벌.

    `marked` 를 따로 주는 이유는 그것이 **G1 의 분모**이기 때문이다. 목록을 세어서 알게
    하면 상한에 잘린 화면에서 틀린 수를 읽는다.
    """

    rows: list[TesterView]
    marked: int
    # 로드맵이 전제하는 수. **화면에 박지 않고 보낸다** — 두 곳에 적으면 로드맵을 고쳤을
    # 때 한쪽만 따라가고, 그러면 같은 게이트가 두 기준으로 판정된다.
    min_testers: int


def build_tester_view(row: TesterRow) -> TesterView:
    """줄 하나를 응답 모양으로 바꾼다.

    Args:
        row: 저장소가 읽은 줄.

    Returns:
        응답 한 줄.
    """
    return TesterView(
        account_id=row.account_id,
        handle=row.handle,
        login_id=row.login_id,
        is_tester=row.is_tester,
        attempts=row.attempts,
        last_seen=row.last_seen,
    )


def build_tester_list() -> TesterListResponse:
    """지금 화면을 만든다.

    Returns:
        줄들과 표시된 계정 수.
    """
    pool = get_pool()
    # **표시 수를 목록에서 세지 않는다.** 목록은 상한에 잘리므로, 세어서 알게 하면
    # 잘린 화면에서 틀린 분모를 읽는다 — 그것이 곧 G1 의 분모다.
    return TesterListResponse(
        rows=[build_tester_view(row) for row in list_candidates(pool, MAX_ROWS)],
        marked=count_testers(pool),
        min_testers=MIN_TESTERS,
    )


@router.get("/api/admin/testers", response_model=TesterListResponse)
def read_testers(account: CurrentAdmin) -> TesterListResponse:
    """표시할 수 있는 계정을 읽는다.

    Args:
        account: 관리자. 아니면 의존성이 404 로 끊는다.

    Returns:
        줄들과 표시된 계정 수.
    """
    return build_tester_list()


@router.post("/api/admin/testers/mark", response_model=TesterListResponse)
def save_tester_mark(request: TesterMarkRequest, account: CurrentOperator) -> TesterListResponse:
    """계정 하나의 테스터 표시를 바꾼다.

    Args:
        request: 대상 계정과 켤지 끌지.
        account: 관리자.

    Returns:
        바뀐 뒤의 화면.
    """
    changed = apply_tester_mark(get_pool(), (request.account_id,), request.is_tester)
    if changed:
        record_admin_action(
            get_pool(),
            account.account_id,
            "tester_mark",
            f"account:{request.account_id}",
            "표시함" if request.is_tester else "표시 지움",
        )
    return build_tester_list()
