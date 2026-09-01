"""콘텐츠 팩 — 브라우저가 시작할 때 받아 가는 것 (설계/4_아이템 §18).

**관리자 전용이 아니다.** 이것이 곧 게임 데이터이고, 모든 접속자가 같은 것을 받아야
두 코어가 같은 판을 돈다.

**서버가 없어도 게임은 돈다.** 브라우저는 이것을 못 받으면 빌드에 박힌 번들로 돈다 —
그때는 코어 버전의 팩 축이 0 이고, 그 판은 제출되지 않는다(로컬 티켓).
"""

from fastapi import APIRouter

from game.api.deps import get_core_version, get_pool
from game.api.view_schemas import ContentPackResponse
from game.app.store.content_pack import build_pack, read_pack_generation

router = APIRouter()


@router.get("/api/content/pack", response_model=ContentPackResponse)
def read_content_pack() -> ContentPackResponse:
    """지금 도는 콘텐츠 전부를 낸다.

    Returns:
        자산 절들과 팩 세대, 코어 버전.
    """
    pool = get_pool()
    return ContentPackResponse(
        assets=build_pack(pool),
        generation=read_pack_generation(pool),
        core_version=get_core_version(),
    )
