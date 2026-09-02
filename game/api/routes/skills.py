"""스킬 세팅 라우트 (결정 #13 확장).

**빼기만 한다.** 스킬은 장비가 열고, 여기서는 연 것 중 이번 런에 안 들고 갈 것을 끈다.
"""

from fastapi import APIRouter

from game.api.deps import CurrentAccount, get_item_catalog, get_pool
from game.api.loadout_service import build_equipped_entries
from game.api.schemas_gear import SkillPrefView, SkillRowView
from game.app.store.accounts import find_player_entity
from game.app.store.skill_prefs import (
    LOCKED_SKILLS,
    read_disabled_skills,
    save_disabled_skills,
)
from game.schemas.loadout import BASE_SKILLS

router = APIRouter()


def build_skill_rows(account_id: int) -> SkillPrefView:
    """지금 장비가 여는 스킬들과 끔 상태를 모은다.

    Args:
        account_id: 대상 계정.

    Returns:
        스킬 세팅 화면 값.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    opened = set(BASE_SKILLS)
    for _slot, entry in sorted(
        build_equipped_entries(pool, entity_id, get_item_catalog()).items(),
        key=lambda pair: str(pair[0]),
    ):
        if entry.grants_skill:
            opened.add(entry.grants_skill)
    disabled = set(read_disabled_skills(pool, account_id))
    return SkillPrefView(
        rows=[
            SkillRowView(
                skill_id=skill,
                is_on=skill not in disabled,
                is_locked=skill in LOCKED_SKILLS,
            )
            for skill in sorted(opened)
        ]
    )


@router.get("/api/skills", response_model=SkillPrefView)
def read_skill_prefs(account: CurrentAccount) -> SkillPrefView:
    """장비가 연 스킬들과 끔 상태를 읽는다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        스킬 줄들. 켬이 기본이다.
    """
    return build_skill_rows(account.account_id)


@router.put("/api/skills", response_model=SkillPrefView)
def save_skill_prefs(request: SkillPrefView, account: CurrentAccount) -> SkillPrefView:
    """끔 상태를 저장한다. 다음 티켓부터 실린다 — 이번 런의 로드아웃은 얼려져 있다.

    Args:
        request: 스킬 줄들. `is_on` 이 거짓인 것만 저장된다.
        account: 토큰으로 푼 계정.

    Returns:
        저장 뒤의 스킬 줄들.
    """
    disabled = tuple(row.skill_id for row in request.rows if not row.is_on)
    save_disabled_skills(get_pool(), account.account_id, disabled)
    return build_skill_rows(account.account_id)
