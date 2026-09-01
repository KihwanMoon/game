"""경매장 라우트 (결정 #20).

**거래는 재현으로 풀리지 않는 유일한 축이다.** 아이템의 진위는 서버 발급이 보증하지만
소유권은 계산할 수 없다 — 원장이 정한다.

수수료가 화폐를 태우고, 만료가 시세를 흐르게 하고, 원장이 자전거래 흔적을 남긴다.
자세한 이유는 `app/store/auction.py` 의 머리말.
"""

from fastapi import APIRouter, HTTPException, status

from game.api.deps import CurrentAccount, get_item_catalog, get_pool
from game.api.discovery_service import record_item_discovery
from game.api.schemas import (
    AuctionListRequest,
    AuctionResponse,
    ListingAction,
    ListingView,
)
from game.app.items.catalog import find_item as find_catalog_item
from game.app.store.accounts import find_player_entity
from game.app.store.auction import (
    LISTING_FEE_PERCENT,
    Listing,
    apply_cancel,
    apply_purchase,
    compute_fee,
    create_listing,
    list_open,
)
from game.app.store.equipment import read_balance
from game.app.store.items import find_item

router = APIRouter()


def build_affix_rows(listing: Listing) -> list[dict]:
    """이 매물이 실제로 지닌 접사를 낸다.

    **인스턴스가 가진 것만 낸다.** 예전에는 비어 있으면 카탈로그 기본값으로 메웠는데,
    그것이 곧 "카탈로그를 고치면 남의 가방이 바뀐다" 였다 (설계/4_아이템 §15.11).

    Args:
        listing: 매물 한 건.

    Returns:
        접사 절들. 굴린 것이 없으면 빈 목록.
    """
    return [dict(affix) for affix in listing.affixes]


def build_listing_view(listing: Listing, catalog: dict) -> ListingView:
    """매물 한 건을 화면이 읽을 절로 바꾼다.

    수수료를 여기서 계산해 실어 보내는 이유는, 화면이 다시 계산하면 두 곳이 갈리기
    때문이다.

    Args:
        listing: 저장 층이 읽어 온 매물.
        catalog: 아이템 카탈로그.

    Returns:
        매물 절.
    """
    return ListingView(
        listing_id=listing.listing_id,
        item_id=listing.item_id,
        catalog_id=listing.catalog_id,
        label_ko=find_catalog_item(catalog, listing.catalog_id).label_ko,
        price=listing.price,
        is_mine=listing.is_mine,
        affixes=build_affix_rows(listing),
        expires_in_minutes=listing.expires_in_minutes,
        fee=compute_fee(listing.price),
    )


def build_auction_response(account_id: int) -> AuctionResponse:
    """지금 매물과 내 잔액을 모아 응답을 만든다.

    Args:
        account_id: 보는 계정.

    Returns:
        매물 목록과 잔액·수수료율.
    """
    pool = get_pool()
    catalog = get_item_catalog()
    return AuctionResponse(
        listings=[build_listing_view(row, catalog) for row in list_open(pool, account_id)],
        balance=read_balance(pool, account_id),
        fee_percent=LISTING_FEE_PERCENT,
    )


@router.get("/api/auction", response_model=AuctionResponse)
def read_auction(account: CurrentAccount) -> AuctionResponse:
    """열려 있는 매물을 싼 것부터 본다.

    Args:
        account: 토큰으로 푼 계정.

    Returns:
        매물 목록. 만료된 것은 조회할 때 정리된다.
    """
    return build_auction_response(account.account_id)


@router.post("/api/auction/list", response_model=AuctionResponse)
def create_auction_listing(request: AuctionListRequest, account: CurrentAccount) -> AuctionResponse:
    """아이템을 경매에 건다. 수수료를 먼저 낸다.

    Args:
        request: 아이템 id 와 호가.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 매물 목록.

    Raises:
        HTTPException: 가진 아이템이 아니거나, 파손됐거나, 호가·잔액이 맞지 않는 경우.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account.account_id)
    stored = find_item(pool, entity_id, request.item_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "가진 아이템이 아니다")
    if stored.is_broken:
        # 파손품을 팔 수 있으면 복구비용을 남에게 떠넘기는 것이 최적이 된다.
        raise HTTPException(status.HTTP_409_CONFLICT, "파손된 장비는 걸 수 없다")
    try:
        create_listing(pool, account.account_id, entity_id, request.item_id, request.price)
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return build_auction_response(account.account_id)


@router.post("/api/auction/buy", response_model=AuctionResponse)
def create_auction_purchase(request: ListingAction, account: CurrentAccount) -> AuctionResponse:
    """매물을 산다.

    Args:
        request: 매물 id.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 매물 목록.

    Raises:
        HTTPException: 살 수 없는 매물이거나 잔액·칸이 모자란 경우.
    """
    pool = get_pool()
    try:
        sold = apply_purchase(
            pool,
            request.listing_id,
            account.account_id,
            find_player_entity(pool, account.account_id),
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    # 산 것도 얻은 것이다. 발급만 도감에 남기면 "경매로만 구할 수 있는 것" 이 영영
    # 안 열린다.
    record_item_discovery(account.account_id, sold.catalog_id)
    return build_auction_response(account.account_id)


@router.post("/api/auction/cancel", response_model=AuctionResponse)
def create_auction_cancel(request: ListingAction, account: CurrentAccount) -> AuctionResponse:
    """내 매물을 내린다. 수수료는 돌려주지 않는다.

    돌려주면 무료로 시세를 떠볼 수 있고, 그러면 수수료가 배출구 역할을 못 한다.

    Args:
        request: 매물 id.
        account: 토큰으로 푼 계정.

    Returns:
        갱신된 매물 목록.

    Raises:
        HTTPException: 내 매물이 아니거나 받을 칸이 없는 경우.
    """
    pool = get_pool()
    try:
        apply_cancel(
            pool,
            request.listing_id,
            account.account_id,
            find_player_entity(pool, account.account_id),
        )
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    return build_auction_response(account.account_id)


@router.get("/api/auction/fee", response_model=dict)
def read_auction_fee(price: int) -> dict:
    """그 호가에 붙는 수수료를 미리 본다.

    Args:
        price: 호가.

    Returns:
        수수료와 비율.
    """
    return {"price": price, "fee": compute_fee(price), "fee_percent": LISTING_FEE_PERCENT}
