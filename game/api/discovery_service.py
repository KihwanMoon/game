"""도감 해금을 기록한다 — 아이템 하나를 얻으면 무엇이 함께 열리는가.

**아이템이 여는 스킬도 함께 연다.** 장비가 스킬을 여는 구조(결정 #13)에서 아이템만
밝히면, 도감이 "이 검이 무엇을 열어 주는지" 를 못 말한다 — 그것이 그 검을 찾는 이유인데.

기록 지점을 한 함수로 모은 이유는 셋이기 때문이다(보상 발급·되찾기·경매 구매). 흩어
두면 한 곳을 빠뜨렸을 때 "왜 저건 도감에 안 뜨지" 가 되고, 그 답을 찾기가 어렵다.
"""

from game.api.deps import get_item_catalog, get_pool
from game.app.items.catalog import find_item as find_catalog_item
from game.app.store.discovery import KIND_ITEM, KIND_SKILL, record_discovery


def record_item_discovery(account_id: int, catalog_id: str) -> None:
    """아이템 하나를 얻은 것을 도감에 남긴다.

    카탈로그에 없는 id 는 조용히 넘긴다 — 폐기된 아이템을 되찾는 경우가 있고, 그때
    도감 기록 때문에 되찾기가 실패하면 안 된다.

    Args:
        account_id: 얻은 계정.
        catalog_id: 얻은 아이템의 카탈로그 id.
    """
    pool = get_pool()
    record_discovery(pool, account_id, KIND_ITEM, catalog_id)
    try:
        entry = find_catalog_item(get_item_catalog(), catalog_id)
    except KeyError:
        return
    if entry.grants_skill:
        record_discovery(pool, account_id, KIND_SKILL, entry.grants_skill)
