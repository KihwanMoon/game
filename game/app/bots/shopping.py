"""봇의 경매 구매 (T11 대응, 결정 #07 위에 선다).

가방·성장·소모품 잡일은 `chores.py` 로 갈라 나갔다 — 저쪽은 이미 가진 것으로 무엇을
할까를 정하고, 여기는 **무엇을 살까**만 정한다.

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

**그것만으로는 부족했다.** 한 봇이 한 번에 하나만 사도, 열 봇이 시간당 다섯 판을 돌면
기회가 시간당 쉰 번이다. 매물이 서른 건이면 아무 일도 아니지만 두 건이면 여섯 시간을
넘긴 그 순간 사라진다 — 실제로 **경매 열림이 0 이었다.** 규칙 하나하나는 지켜졌는데
총량이 시장을 비웠다.

그래서 마지막 규율이 하나 더 있다: **봇은 넘치는 것만 산다.** 열린 매물이 몇 건
아래로 내려가면 아무것도 안 산다. 봇은 유동성을 더하러 온 것이지 재고를 지우러 온
것이 아니고, 「사람이 열어 봤을 때 아무것도 없다」가 이 시스템의 실패 모습이다.
"""

from dataclasses import dataclass

from game.app.bots.upgrade import (
    MAIN_SLOT,
    UPGRADE_MARGIN,
    GearItem,
    check_blocked_by_hands,
    compute_weighted_score,
)

# 등록 유효 기간(분). `auction.LISTING_TTL` 과 같은 값이어야 한다 — 남은 시간에서
# 걸린 지 얼마나 됐는지를 역산하기 때문이다.
LISTING_TTL_MINUTES = 2 * 24 * 60

# 사람에게 주는 우선권(분). 이만큼 지나도 아무도 안 사면 그때 봇이 본다.
FIRST_LOOK_MINUTES = 6 * 60

# 잔액을 이만큼은 남긴다(%). 전부 털어 사면 다음에 더 좋은 것이 떠도 못 산다.
KEEP_PERCENT = 20

# 시장에 이만큼은 남겨 둔다. 열린 매물이 이 수 이하면 봇은 아무것도 안 산다 —
# 봇은 **넘치는 것만** 사는 마지막 구매자다. 이 값이 0 이면 규칙 하나하나가 지켜져도
# 시간당 쉰 번의 기회가 시장을 비운다(실측: 경매 열림 0).
MIN_OPEN_LISTINGS = 3

PERCENT_BASE = 100


@dataclass(frozen=True)
class Listing:
    """살지 말지 판단할 매물 한 건."""

    listing_id: int
    price: int
    is_mine: bool
    expires_in_minutes: int
    # **무엇인가**를 아는 데 필요한 것들. 예전에는 값과 만료뿐이라 봇이 자기 장비와
    # 견줄 수 없었고, 그래서 **가장 싼 것**을 샀다 — 정의상 가장 값 안 나가는 물건이다.
    slot: str = ""
    affixes: tuple[tuple[str, int, int], ...] = ()
    attack_range: int = 0
    # 한 손인가 양손인가. 못 끼울 것을 사면 가방에서 버려질 뿐이다.
    hands: str = ""


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


def list_buyable(listings: tuple[Listing, ...], balance: int) -> tuple[Listing, ...]:
    """지금 살 수 있는 매물들.

    **넘치는 것만 산다.** 열린 매물이 `MIN_OPEN_LISTINGS` 이하면 아무것도 못 산다 —
    사람이 열어 봤을 때 아무것도 없는 것이 이 시스템의 실패 모습이고, 규칙 하나하나가
    지켜져도 시간당 쉰 번의 기회가 시장을 그렇게 만든다. 세는 것은 **사람이 볼 수 있는
    전량**이지 봇이 살 수 있는 것이 아니다: 봇이 못 사는 매물도 사람에게는 재고다.

    Args:
        listings: 지금 열려 있는 매물들.
        balance: 봇의 화폐.

    Returns:
        사람 우선권·시장 하한·예산을 다 통과한 매물들.
    """
    for_sale = [item for item in listings if not item.is_mine]
    if len(for_sale) <= MIN_OPEN_LISTINGS:
        return ()
    budget = resolve_budget(balance)
    return tuple(
        item for item in for_sale if check_is_open_to_bots(item) and 0 < item.price <= budget
    )


def find_upgrade_buy(
    buyable: tuple[Listing, ...],
    worn: dict[str, GearItem],
    weights: dict[str, int],
    base_stats: dict[str, int],
) -> int:
    """지금 낀 것보다 나은 매물 중 **가장 많이 나은** 것.

    **끼는 것과 같은 저울이다** (`bots/upkeep.PERSONA_PRIORITY`). 사는 저울과 끼는 저울이
    다르면 봇이 산 것을 안 끼는 일이 생긴다 — 돈만 나가고 몸은 그대로다.

    **여유폭을 요구한다.** 갈아 끼우기와 같은 값이다: 근소하게 나은 것을 사면 그 돈으로
    다음에 뜰 확실한 것을 못 산다.

    Args:
        buyable: 살 수 있는 매물들.
        worn: 자리에서 지금 낀 것으로.
        weights: 이 봇의 저울.
        base_stats: 퍼센트를 값으로 바꾸는 기준.

    Returns:
        살 매물 id. 나은 것이 없으면 0.
    """
    scored: list[tuple[int, int, int]] = []
    for item in buyable:
        if not item.slot:
            continue
        offered_hands = GearItem(
            item_id=0,
            slot=item.slot,
            can_equip=True,
            is_broken=False,
            hands=item.hands,
            affixes=(),
            attack_range=0,
        )
        # 못 끼울 것은 안 산다 — 사도 가방에서 버려질 뿐이고, 그때 돈만 나간다.
        if check_blocked_by_hands(offered_hands, (worn or {}).get(MAIN_SLOT)):
            continue
        current = worn.get(item.slot)
        if current is None:
            # 빈 자리는 견줄 상대가 없다. 그 자리를 채우는 것은 러너의 몫이다
            # (`apply_bot_gear`) — 여기서 사면 두 곳이 같은 자리를 두고 다툰다.
            continue
        offered = GearItem(
            item_id=0,
            slot=item.slot,
            can_equip=True,
            is_broken=False,
            hands=item.hands,
            affixes=item.affixes,
            attack_range=item.attack_range,
        )
        gain = compute_weighted_score(offered, weights, base_stats) - compute_weighted_score(
            current, weights, base_stats
        )
        if gain >= UPGRADE_MARGIN:
            scored.append((gain, item.price, item.listing_id))
    if not scored:
        return 0
    # 많이 나은 것 먼저, 같으면 싼 쪽, 그래도 같으면 id 가 작은 쪽 — 순서가 흔들리면
    # 같은 상황에서 다른 일이 벌어진다 (R5 와 같은 결의 규율).
    return min(scored, key=lambda one: (-one[0], one[1], one[2]))[2]


def find_purchase(
    listings: tuple[Listing, ...],
    balance: int,
    worn: dict[str, GearItem] | None = None,
    weights: dict[str, int] | None = None,
    base_stats: dict[str, int] | None = None,
) -> int:
    """이번에 살 매물을 고른다.

    **나은 것이 먼저, 없으면 싼 것.** 예전에는 싼 것만 샀다 — 6시간 넘게 안 팔린 것 중
    제일 싼 것이라 정의상 가장 값 안 나가는 물건이고, 봇의 가방에 쌓였다가 정비의
    버리기나 사망 페널티가 지웠다. 사실상 화폐 소각기였다.

    싼 것 사기를 **없애지는 않았다.** 봇이 시장에서 사 주는 것 자체가 사람이 드롭을 팔
    곳이고, 나은 것만 사면 그 자리가 크게 준다. 그래서 둘을 순서로 둔다: 쓸모를 먼저
    보고, 없으면 유동성을 낸다.

    **싼 것부터 하나만 산다.** 한 번에 여럿 사면 열 봇이 시장을 한 바퀴에 비우고, 그것은
    유동성이 아니라 청소다.

    Args:
        listings: 지금 열려 있는 매물들.
        balance: 봇의 화폐.
        worn: 자리에서 지금 낀 것으로. 없으면 견줌을 건너뛴다.
        weights: 이 봇의 저울. 없으면 견줌을 건너뛴다.
        base_stats: 퍼센트를 값으로 바꾸는 기준.

    Returns:
        살 매물 id. 살 것이 없으면 0.
    """
    buyable = list_buyable(listings, balance)
    if not buyable:
        return 0
    if worn is not None and weights is not None and base_stats is not None:
        upgrade = find_upgrade_buy(buyable, worn, weights, base_stats)
        if upgrade != 0:
            return upgrade
    return min(buyable, key=lambda item: (item.price, item.listing_id)).listing_id
