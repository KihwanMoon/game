"""판이 끝난 뒤 봇이 하는 일 — 사고, 끼고, 찍고, 장전한다.

**사람도 판이 끝나면 가방과 시장을 본다.** 봇이 그것을 안 하면 번 것이 영영 안 쓰이고,
그러면 봇은 경제에 들어와 있지 않은 것이다.

그리고 **끼는 것이 지키는 것이다.** 사망 페널티는 장착·가방을 통틀어 하나를 뽑는데,
장착 중이면 파손(복구 가능)이고 가방에 있으면 삭제다 (결정 #34). 안 끼면 그 유인의
반대편만 받는다 — 실제로 봇 열이 스무 개를 그렇게 잃었다.

러너에서 갈라 둔 이유는 책임이 다르기 때문이다. 러너는 **차례**를 돌리고, 여기는 한
봇이 판 뒤에 하는 일이다 (§4 의 400줄 상한에 걸린 자리이기도 하다).
"""

from game.app.bots.shopping import (
    BagItem,
    Listing,
    build_allocation,
    find_purchase,
    list_equippable,
    list_loadable,
    list_repairable,
    parse_consumables,
)
from game.app.bots.upkeep import build_bot_upkeep, check_upkeep_matches
from game.app.store.bots import BotProfile
from game.app.store.maintenance import MaintenanceRow
from scripts.bot_client import send_request


def apply_bot_shopping(api_url: str, bot: BotProfile) -> str:
    """판이 끝난 뒤 시장을 한 번 본다.

    사람도 판이 끝나면 가방과 시장을 본다. 봇이 그것을 안 하면 번 화폐가 영영 안 쓰이고,
    그러면 봇은 경제에 들어와 있지 않은 것이다.

    **사기만 한다.** 거는 길은 여기 없다 — 봇이 물건을 걸면 「봇이 파밍해서 사람에게
    넘기는」 통로가 열린다 (T11, 결정 #02).

    Args:
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.

    Returns:
        무슨 일이 있었는지. 아무것도 안 샀으면 빈 문자열.
    """
    market = send_request(f"{api_url}/api/auction", bot.token, None)
    if market is None:
        return ""
    listings = tuple(
        Listing(
            listing_id=int(row["listing_id"]),
            price=int(row["price"]),
            is_mine=bool(row.get("is_mine")),
            expires_in_minutes=int(row.get("expires_in_minutes", 0)),
        )
        for row in market.get("listings", [])
    )
    wanted = find_purchase(listings, int(market.get("balance", 0)))
    if wanted == 0:
        return ""
    bought = send_request(f"{api_url}/api/auction/buy", bot.token, {"listing_id": wanted})
    return "" if bought is None else f"경매 #{wanted} 샀다"


def apply_bot_gear(api_url: str, bot: BotProfile) -> str:
    """가방에 있는 것을 빈 자리에 낀다.

    **끼는 것이 지키는 것이다.** 사망 페널티는 장착·가방을 통틀어 하나를 뽑는데, 뽑힌
    것이 장착 중이었으면 파손(복구 가능)이고 가방에 있었으면 삭제다 (결정 #34). 봇이
    아무것도 안 끼면 그 유인의 반대편만 받는다 — 실제로 봇 열이 스무 개를 그렇게 잃었다.

    Args:
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.

    Returns:
        무슨 일이 있었는지. 아무것도 안 꼈으면 빈 문자열.
    """
    bag = send_request(f"{api_url}/api/inventory", bot.token, None)
    if bag is None:
        return ""
    filled = frozenset(
        str(row.get("slot") or "") for row in bag.get("equipment", []) if row.get("item")
    )
    items = tuple(
        BagItem(
            item_id=int(row["item"]["item_id"]),
            slot=str(row["item"].get("slot") or ""),
            can_equip=bool(row["item"].get("can_equip")),
            is_broken=bool(row["item"].get("is_broken")),
        )
        for row in bag.get("slots", [])
        if row.get("item")
    )
    worn = []
    for item in list_equippable(items, filled):
        done = send_request(
            f"{api_url}/api/equip", bot.token, {"item_id": item.item_id, "slot": item.slot}
        )
        if done is not None:
            worn.append(item.slot)
    return "" if not worn else f"{'·'.join(worn)} 착용"


def apply_bot_repair(api_url: str, bot: BotProfile) -> str:
    """부서진 장비를 고친다.

    **안 고치면 장비가 한 방향으로만 준다.** 사망 페널티가 장착 중인 것을 부수는데
    (결정 #34), 아무도 안 고치면 봇의 장비는 죽을 때마다 줄기만 한다 — 「끼는 것이
    지키는 것이다」의 뒷부분(복구 가능)이 봇에게는 거짓이 되고, 몬스터가 뺏어 갈 것도
    사라진다.

    **끼기 전에 고친다.** 부서진 것은 낄 수 없으므로, 순서가 반대면 고친 것이 이번
    차례에는 안 끼이고 다음 판을 맨몸으로 돈다.

    Args:
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.

    Returns:
        무슨 일이 있었는지. 고칠 것이 없었으면 빈 문자열.
    """
    bag = send_request(f"{api_url}/api/inventory", bot.token, None)
    if bag is None:
        return ""
    # 장착 중인 것도 함께 본다 — 사망 페널티가 부수는 것이 주로 그쪽이다.
    rows = [row for row in bag.get("slots", []) if row.get("item")]
    rows += [row for row in bag.get("equipment", []) if row.get("item")]
    items = tuple(
        BagItem(
            item_id=int(row["item"]["item_id"]),
            slot=str(row["item"].get("slot") or ""),
            can_equip=bool(row["item"].get("can_equip")),
            is_broken=bool(row["item"].get("is_broken")),
        )
        for row in rows
    )
    fixed = []
    for item in list_repairable(items, int(bag.get("balance", 0)), int(bag.get("repair_cost", 0))):
        done = send_request(f"{api_url}/api/item/repair", bot.token, {"item_id": item.item_id})
        if done is not None:
            fixed.append(str(item.item_id))
    return "" if not fixed else f"#{'·#'.join(fixed)} 고쳤다"


def apply_bot_upkeep(api_url: str, bot: BotProfile) -> str:
    """이 봇의 정비 규칙을 표준 배치로 세운다.

    **한 번 세우면 서버가 판마다 돌린다.** 러너가 매번 손으로 하는 것보다 낫다 — 러너가
    죽어 있는 동안에도 세계는 돌기 때문이다.

    예전에는 여기서 `REFILL` 한 줄만 세웠다. 그래서 봇의 봉인은 안 열리고 가방은 잡템으로
    찼다 — 사람이 쓰는 규칙 일곱이 이미 있는데 봇만 그것을 안 썼다. 배치와 그 순서의
    근거는 `bots/upkeep.py` 에 있다.

    **다를 때만 쓴다.** 매 판 같은 값을 다시 저장하면 사람이 손으로 고친 배치가 매번
    되돌아간다.

    Args:
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.

    Returns:
        무슨 일이 있었는지. 이미 같으면 빈 문자열.
    """
    upkeep = send_request(f"{api_url}/api/maintenance", bot.token, None)
    if upkeep is None:
        return ""
    now = tuple(
        MaintenanceRow(str(row.get("action", "")), str(row.get("grade", "")))
        for row in upkeep.get("rows", [])
    )
    if check_upkeep_matches(now, bot.ruleset_id):
        return ""
    rows = build_bot_upkeep(bot.ruleset_id)
    done = send_request(
        f"{api_url}/api/maintenance",
        bot.token,
        {"rows": [{"action": row.action, "grade": row.grade} for row in rows]},
        method="PUT",
    )
    return "" if done is None else f"정비 규칙 {len(rows)}줄 세움"


def apply_bot_supplies(api_url: str, bot: BotProfile) -> str:
    """빈 소모품 칸을 채운다.

    **끼워야 보충이 돈다.** 정비의 REFILL 은 이미 끼운 것을 채우기만 한다 — 칸이 비어
    있으면 채울 대상이 없어서 아무 일도 안 일어난다. 그래서 봇이 소모품을 주워도 가방에
    쌓이기만 하고, 죽을 때 사망 페널티가 그것을 지운다. 장비와 같은 이유다.

    **끼우는 것은 여기 남는다.** 정비의 소모품 교체는 이미 낀 것을 더 나은 것으로 바꾸는
    일이고, 빈 칸을 처음 채우는 것은 그것과 다른 일이다 (`maintenance_upgrade` 주석).

    Args:
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.

    Returns:
        무슨 일이 있었는지. 할 일이 없었으면 빈 문자열.
    """
    stock = send_request(f"{api_url}/api/consumables", bot.token, None)
    if stock is None:
        return ""
    slots, options = parse_consumables(stock)
    loaded = []
    for slot, catalog_id in list_loadable(slots, options):
        done = send_request(
            f"{api_url}/api/consumable/load",
            bot.token,
            {
                "use_tag": slot.use_tag,
                "slot_index": slot.slot_index,
                "catalog_id": catalog_id,
            },
        )
        if done is not None:
            loaded.append(catalog_id)
    return "" if not loaded else f"소모품 {'·'.join(loaded)} 장전"


def apply_bot_growth(api_url: str, bot: BotProfile) -> str:
    """레벨이 준 능력치 포인트를 쓴다.

    **안 쓰면 없는 것과 같다.** 포인트는 레벨과 함께 쌓이기만 하고 배분해야 몸에 붙는다 —
    실제로 열 봇 전부 레벨 4 에 배분표가 비어 있었고, 9점씩 놀고 있었다. 사람은 레벨이
    오르면 찍는다.

    Args:
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.

    Returns:
        무슨 일이 있었는지. 쓸 것이 없었으면 빈 문자열.
    """
    progress = send_request(f"{api_url}/api/progress", bot.token, None)
    if progress is None:
        return ""
    spent = {key: int(value) for key, value in (progress.get("stats") or {}).items()}
    wanted = build_allocation(int(progress.get("level", 1)), bot.ruleset_id, spent)
    if wanted == spent:
        return ""
    done = send_request(f"{api_url}/api/progress/stats", bot.token, {"stats": wanted}, method="PUT")
    return (
        ""
        if done is None
        else "능력치 " + " ".join(f"{key}{wanted[key]}" for key in sorted(wanted) if wanted[key])
    )
