"""봇 하나를 **사람 화면과 같은 눈으로** 본다 (T11).

`admin_bots` 에서 갈라 나왔다. 저쪽은 봇 **떼**를 다룬다 — 몇 마리가 돌고, 무엇을 벌었고,
누구를 멈출까. 여기는 봇 **하나**를 연다: 규칙표 둘, 캐릭터, 가방, 스킬, 지나간 판들.

**사람 화면과 같은 절을 쓴다.** `build_inventory_response`·`build_skill_rows` 를 그대로
부르는 이유는, 여기서 따로 만들면 두 화면이 다른 것을 그리게 되고 「봇에게 뭐가 있지」를
답하려던 화면이 답을 틀리게 하기 때문이다 — 봇 가방이 한 번 그렇게 갈렸었다.

**읽기 전용이다.** 성격을 고치는 길은 `admin_bots` 에 이미 있고(규칙표 id·실력·주기),
아이템을 넘기는 길도 거기 있다. 여기에 **입히는 길은 두지 않는다** — 관리자가 봇에게
직접 장비를 채워 넣기 시작하면 그 봇이 만든 순위·경매 기록이 무엇을 뜻하는지 알 수 없게
된다. 봇은 준 것을 **제 규칙으로** 입어야 한다 (`bots/upgrade`).
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from game.api.deps import CurrentAdmin, get_context, get_pool
from game.api.routes.skills import build_skill_rows
from game.api.schemas import ProgressResponse
from game.api.schemas_gear import MaintenanceRowView, MaintenanceView, SkillPrefView
from game.app.progression.floors import read_floor_cap
from game.app.progression.levels import STAT_KEYS
from game.app.store.accounts import find_player_entity
from game.app.store.bots import check_is_bot
from game.app.store.maintenance import read_maintenance
from game.app.store.progress import read_progress, read_reached_floor
from game.app.store.runs import list_recent_runs

router = APIRouter()

# 리플레이가 보여 주는 판 수. **최근 것만 본다** — 봇은 시간당 다섯 판을 돌므로 전부
# 내면 목록이 곧 로그가 되고, 로그는 화면이 아니라 파일이 읽을 것이다.
RECENT_RUN_LIMIT = 10


class BotRunView(BaseModel):
    """지나간 판 한 줄."""

    submission_id: int
    room_id: str
    floor: int
    # 시드를 함께 낸다. **같은 판을 다시 돌려 보려면 이것이 있어야 한다** — 코어가
    # 결정론이라 시드와 규칙표가 있으면 그 판이 그대로 재현된다 (R5·G3).
    seed: int
    outcome: str
    ticks: int
    player_hp: int
    # 서버가 재시뮬해 확정했는가. 빈 문자열이면 아직 안 봤다는 뜻이고, 그것은 「없다」와
    # 다르다 — 서버가 밀렸을 때 화면이 「안 돌았다」로 읽히면 안 된다.
    verdict: str
    submitted_at: str


class BotDetailResponse(BaseModel):
    """봇 하나를 사람 화면과 같은 눈으로 본 것."""

    account_id: int
    handle: str
    # 봇이 쓰는 전투 규칙표의 id. **절이 아니라 id 다** — 봇의 규칙표는 우리가 고른
    # 프리셋이고, 그 내용은 사람 화면의 견본 목록에 이미 있다.
    ruleset_id: str
    maintenance: MaintenanceView
    progress: ProgressResponse
    skills: SkillPrefView
    runs: list[BotRunView] = Field(default_factory=list)


@router.get("/api/admin/bot/detail", response_model=BotDetailResponse)
def read_bot_detail(account_id: int, account: CurrentAdmin) -> BotDetailResponse:
    """봇 하나의 규칙표·캐릭터·스킬·지나간 판을 한 번에 읽는다.

    **한 번에 읽는 이유**는 탭마다 따로 부르면 탭을 옮길 때마다 화면이 비었다가 차기
    때문이다 — 다섯 번 부를 것을 한 번 부른다. 가방만 따로인 것은 그것이 이미 사람
    화면과 같은 라우트를 쓰고 있어서다 (`/api/admin/bot/bag`).

    **봇만 본다.** 아무 계정이나 볼 수 있으면 이것은 관리자가 남의 계정을 들여다보는
    길이 된다 — 봇을 관리하려고 연 창이 그것이어서는 안 된다.

    Args:
        account_id: 볼 봇의 계정.
        account: 관리자 계정.

    Returns:
        그 봇의 규칙표 id·정비 규칙·성장·스킬·최근 판들.

    Raises:
        HTTPException: 봇이 아닌 계정이면 404.
    """
    pool = get_pool()
    row = check_bot_row(account_id)
    entity_id = find_player_entity(pool, account_id)
    progress = read_progress(pool, entity_id)
    return BotDetailResponse(
        account_id=account_id,
        handle=row[0],
        ruleset_id=row[1],
        maintenance=MaintenanceView(
            rows=[
                MaintenanceRowView(action=one.action, grade=one.grade)
                for one in read_maintenance(pool, account_id)
            ]
        ),
        progress=ProgressResponse(
            **vars(progress),
            stat_keys=list(STAT_KEYS),
            reached_floor=read_reached_floor(pool, progress.entity_id),
            floor_cap=read_floor_cap(get_context().balance),
            loadout=None,
        ),
        skills=build_skill_rows(account_id),
        runs=[
            BotRunView(**vars(one)) for one in list_recent_runs(pool, account_id, RECENT_RUN_LIMIT)
        ],
    )


def check_bot_row(account_id: int) -> tuple[str, str]:
    """봇인지 보고 이름과 규칙표 id 를 준다.

    Args:
        account_id: 볼 계정.

    Returns:
        (핸들, 규칙표 id).

    Raises:
        HTTPException: 봇이 아니면 404.
    """
    pool = get_pool()
    if not check_is_bot(pool, account_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 봇이다: {account_id}")
    with pool.connection() as connection:
        found = connection.execute(
            "SELECT a.handle, COALESCE(b.ruleset_id, '')"
            " FROM account a LEFT JOIN bot_profile b ON b.account_id = a.id"
            " WHERE a.id = %s",
            (account_id,),
        ).fetchone()
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"없는 봇이다: {account_id}")
    return str(found[0] or ""), str(found[1] or "")
