"""봇의 경매 구매 (T11 대응, 결정 #07 위에 선다).

**봇은 사기만 한다.** 걸지 않는 것이 이 모듈의 첫 번째 규율이다 — 봇이 물건을 걸면
「봇이 파밍해서 사람에게 넘기는」 길이 열리고, 그것이 T11 이자 아이템이 세계에 들어오는
문을 검증된 런 하나로 묶은 결정 #02 가 막으려던 것이다. 도플갱어에서 막은 세 길과 같은
이유이며, 여기가 네 번째 길목이다.

**반대 방향은 안전하다.** 사람이 걸고 봇이 사면 아이템이 사람 경제에서 나가고, 경매는
살 때 `is_bound = TRUE` 를 박으므로 그 물건은 다시 걸리지 않는다 — 결정 #07 이
자전거래를 막으려고 만든 규칙이 여기서 그대로 「한 방향」 보장이 된다. 새 통로를 뚫을
필요가 없었다.

**봇은 마지막 구매자다.** 열리자마자 채가면 열 봇이 초당 한 번 훑는 시장에서 사람은
아무것도 못 산다 — 시장을 채우려던 것이 시장을 봇의 것으로 만든다. 그래서 **오래
걸려 있던 것만** 산다: 사람이 먼저 볼 시간을 주고, 아무도 안 가져간 것에 값을 매긴다.
"""

from dataclasses import dataclass

# 등록 유효 기간(분). `auction.LISTING_TTL` 과 같은 값이어야 한다 — 남은 시간에서
# 걸린 지 얼마나 됐는지를 역산하기 때문이다.
LISTING_TTL_MINUTES = 2 * 24 * 60

# 사람에게 주는 우선권(분). 이만큼 지나도 아무도 안 사면 그때 봇이 본다.
FIRST_LOOK_MINUTES = 6 * 60

# 잔액을 이만큼은 남긴다(%). 전부 털어 사면 다음에 더 좋은 것이 떠도 못 산다.
KEEP_PERCENT = 20

PERCENT_BASE = 100


@dataclass(frozen=True)
class Listing:
    """살지 말지 판단할 매물 한 건."""

    listing_id: int
    price: int
    is_mine: bool
    expires_in_minutes: int


def check_is_open_to_bots(listing: Listing) -> bool:
    """봇이 손대도 되는 매물인가.

    Args:
        listing: 볼 매물.

    Returns:
        사람에게 우선권을 주고도 남아 있으면 참.
    """
    if listing.is_mine:
        return False
    age_minutes = LISTING_TTL_MINUTES - listing.expires_in_minutes
    return age_minutes >= FIRST_LOOK_MINUTES


def resolve_budget(balance: int) -> int:
    """이번에 쓸 수 있는 최대 금액.

    Args:
        balance: 가진 화폐.

    Returns:
        쓸 수 있는 금액. 잔액의 일부는 남긴다.
    """
    return balance * (PERCENT_BASE - KEEP_PERCENT) // PERCENT_BASE


def find_purchase(listings: tuple[Listing, ...], balance: int) -> int:
    """이번에 살 매물을 고른다.

    **싼 것부터 하나만 산다.** 한 번에 여럿 사면 열 봇이 시장을 한 바퀴에 비우고, 그것은
    유동성이 아니라 청소다. 값이 같으면 id 가 작은 쪽 — 순서가 실행마다 흔들리면 같은
    상황에서 다른 일이 벌어진다 (R5 와 같은 결의 규율).

    Args:
        listings: 지금 열려 있는 매물들.
        balance: 봇의 화폐.

    Returns:
        살 매물 id. 살 것이 없으면 0.
    """
    budget = resolve_budget(balance)
    affordable = [
        item for item in listings if check_is_open_to_bots(item) and 0 < item.price <= budget
    ]
    if not affordable:
        return 0
    return min(affordable, key=lambda item: (item.price, item.listing_id)).listing_id
