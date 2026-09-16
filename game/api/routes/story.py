"""장 카드를 본 기록 (2026-09-16).

**계정에 붙는다.** 세션 안에서만 기억하던 때는 새로고침하거나 다른 기기로 옮기면 1장
카드가 다시 떴다 — 이야기는 한 번 읽는 것이라 두 번째부터는 방해다.

**카드 id 는 화면이 정한다.** 서버가 이야기의 목록을 들고 있지 않기 때문이다 — 장 카드도
그림자 카드도 `frontend/src/content/story.ts` 가 정본이고, 여기는 「봤다」는 사실만 담는다.
서버가 목록까지 알면 이야기를 하나 더할 때마다 양쪽을 고쳐야 한다.
"""

from fastapi import APIRouter

from game.api.deps import CurrentAccount, get_pool
from game.api.schemas import StorySeenRequest, StorySeenResponse
from game.app.store.story_seen import apply_seen_card, list_seen_cards

router = APIRouter()


@router.get("/api/story/seen", response_model=StorySeenResponse)
def read_story_seen(account: CurrentAccount) -> StorySeenResponse:
    """이 계정이 이미 본 카드들.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        카드 id 들.
    """
    return StorySeenResponse(seen=list(list_seen_cards(get_pool(), account.account_id)))


@router.post("/api/story/seen", response_model=StorySeenResponse)
def create_story_seen(request: StorySeenRequest, account: CurrentAccount) -> StorySeenResponse:
    """카드 하나를 봤다고 남긴다.

    **거절하지 않는다.** 모르는 카드 id 가 와도 그대로 담는다 — 이야기 목록은 화면이 들고
    있고, 서버가 그것을 검사하면 이야기를 하나 더할 때마다 양쪽을 고쳐야 한다. 담기는 것은
    판정에 아무 영향이 없는 문자열 하나다.

    Args:
        request: 본 카드.
        account: 토큰으로 푼 계정.

    Returns:
        남긴 뒤의 카드 id 들.
    """
    pool = get_pool()
    apply_seen_card(pool, account.account_id, request.card_id)
    return StorySeenResponse(seen=list(list_seen_cards(pool, account.account_id)))
