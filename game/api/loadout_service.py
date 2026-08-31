"""티켓에 실을 로드아웃을 만든다 (결정 #13).

장비는 서버가 알고 전투는 브라우저가 돈다. **런이 시작될 때 확정해 티켓에 얼려 넣는
것**이 그 간극을 메우는 유일한 방법이며, 몬스터 스냅샷과 같은 이유다.

**파손된 장비는 빼고 합산한다.** 파손은 "그 자리가 비어 있는 것" 과 같다 — 복구하기
전까지는 효과가 없어야 복구비용이 뜻을 갖는다 (결정 #34).
"""

from dataclasses import replace

from psycopg_pool import ConnectionPool

from game.api.deps import get_context, get_item_catalog, get_pool
from game.app.items.catalog import find_item as find_catalog_item
from game.app.items.loadout import build_player_loadout
from game.app.store.accounts import find_player_entity
from game.app.store.items import list_equipment, list_inventory
from game.app.store.progress import read_progress
from game.schemas.item import EquipSlot, ItemCatalogEntry
from game.schemas.loadout import build_loadout_payload


def build_ticket_loadout(account_id: int) -> dict:
    """이 계정의 지금 장비·레벨로 전투 입력을 만든다.

    Args:
        account_id: 대상 계정.

    Returns:
        티켓에 실을 절.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    catalog = get_item_catalog()
    equipped: dict[EquipSlot, ItemCatalogEntry] = {}
    for slot, item in list_equipment(pool, entity_id).items():
        # 파손된 장비는 그 자리가 비어 있는 것과 같다. 효과가 남으면 복구비용이
        # 뜻을 잃는다 (결정 #34).
        if item.is_broken:
            continue
        entry = find_catalog_item(catalog, item.catalog_id)
        # 인스턴스가 굴린 접사가 카탈로그 기본값을 **대체한다** — 같은 이름의 아이템이
        # 조금씩 다르게 나와야 파밍이 성립한다.
        equipped[slot] = entry if not item.affixes else _build_rolled_entry(entry, item.affixes)
    player = get_context().balance["player"]
    progress = read_progress(pool, entity_id)
    loadout = build_player_loadout(
        {key: int(value) for key, value in player.items() if isinstance(value, int)},
        equipped,
        progress.level,
        int(player["rule_slots"]),
        progress.stats,
        count_consumables(pool, entity_id, catalog),
    )
    return build_loadout_payload(loadout)


def _build_rolled_entry(entry: ItemCatalogEntry, affixes: tuple) -> ItemCatalogEntry:
    """인스턴스가 굴린 접사를 입힌 카탈로그 항목을 만든다.

    Args:
        entry: 카탈로그 항목.
        affixes: 그 인스턴스의 접사.

    Returns:
        접사만 바뀐 항목.
    """
    return replace(entry, affixes=affixes)


def count_consumables(pool: ConnectionPool, entity_id: int, catalog: dict) -> dict[str, int]:
    """가방에 든 소모품을 **태그별로** 센다 (#54).

    태그로 세는 이유는 규칙표가 카탈로그 id 가 아니라 태그를 가리키기 때문이다 — 회복
    물약을 여러 등급으로 늘려도 `USE_ITEM[POTION]` 이 그대로 도는 것이 그 설계다.

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        catalog: 아이템 카탈로그.

    Returns:
        태그에서 개수로. 소모품이 없으면 빈 딕셔너리.
    """
    counts: dict[str, int] = {}
    for entry in list_inventory(pool, entity_id):
        if entry.stack_catalog_id is None or entry.stack_count <= 0:
            continue
        item = catalog.get(entry.stack_catalog_id)
        for tag in getattr(item, "tags", ()) or ():
            counts[tag] = counts.get(tag, 0) + entry.stack_count
    return counts
