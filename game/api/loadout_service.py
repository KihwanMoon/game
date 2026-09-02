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
from game.app.items.stats import get_effective_slots
from game.app.store.accounts import find_player_entity
from game.app.store.consumables import (
    ConsumableSlot,
    count_slot_charges,
    list_consumable_slots,
)
from game.app.store.items import list_equipment
from game.app.store.progress import read_progress
from game.schemas.consumable import SLOT_STATS, list_slot_tags
from game.schemas.item import EquipSlot, ItemCatalogEntry
from game.schemas.loadout import build_loadout_payload


def build_equipped_entries(
    pool: ConnectionPool, entity_id: int, catalog: dict
) -> dict[EquipSlot, ItemCatalogEntry]:
    """지금 몸에 걸친 것들을 슬롯별로 모은다.

    **파손된 장비는 뺀다.** 파손은 "그 자리가 비어 있는 것" 과 같다 — 복구하기 전까지는
    효과가 없어야 복구비용이 뜻을 갖는다 (결정 #34).

    Args:
        pool: 연결 풀.
        entity_id: 대상 개체.
        catalog: 아이템 카탈로그.

    Returns:
        슬롯에서 항목으로. 인스턴스가 굴린 접사가 입혀져 있다.
    """
    equipped: dict[EquipSlot, ItemCatalogEntry] = {}
    for slot, item in list_equipment(pool, entity_id).items():
        if item.is_broken:
            continue
        entry = find_catalog_item(catalog, item.catalog_id)
        # **인스턴스가 가진 것만 쓴다.** 카탈로그를 안 보므로 카탈로그를 고쳐도 이미
        # 나온 장비의 성능이 안 바뀐다 — 그것이 §15.11 이 연 것이다.
        equipped[slot] = _build_rolled_entry(entry, item.affixes)
    return equipped


def count_slot_bonus(equipped: dict[EquipSlot, ItemCatalogEntry]) -> dict[str, int]:
    """장비 접사가 소모품 칸을 몇 개 늘리는지 센다 (§5).

    **`get_effective_slots` 를 거친다.** 양손무기가 봉인한 보조 슬롯의 장비는 효과가
    없어야 하고, 칸도 그 예외가 아니다 — 안 거치면 봉인된 장비의 「물약 주머니」가 그대로
    산다.

    Args:
        equipped: 착용 중인 항목들.

    Returns:
        쓰임새에서 늘어난 칸 수로. 늘어난 것이 없으면 0 이 담긴다.
    """
    totals: dict[str, int] = {tag: 0 for tag in list_slot_tags()}
    for _slot, entry in get_effective_slots(equipped):
        if entry is None:
            continue
        for affix in entry.affixes:
            for tag, stat in sorted(SLOT_STATS.items()):
                if affix.stat == stat:
                    totals[tag] = totals.get(tag, 0) + affix.flat
    return totals


def list_loaded_consumables(
    slots: tuple[ConsumableSlot, ...], catalog: dict
) -> tuple[ItemCatalogEntry, ...]:
    """칸에 끼운 소모품 중 **충전이 남은 것**들을 칸 순서대로 모은다.

    다 쓴 물약은 파손된 장비와 같다 — 효과가 남으면 보충비가 뜻을 잃는다.

    Args:
        slots: 읽어 온 소모품 칸들.
        catalog: 아이템 카탈로그.

    Returns:
        카탈로그 항목들. 칸 순서 그대로다 (R5).
    """
    loaded: list[ItemCatalogEntry] = []
    for slot in slots:
        if slot.catalog_id is None or slot.charges <= 0:
            continue
        entry = catalog.get(slot.catalog_id)
        if entry is not None:
            loaded.append(entry)
    return tuple(loaded)


def build_ticket_loadout(account_id: int) -> dict:
    """이 계정의 지금 장비·레벨·소모품 칸으로 전투 입력을 만든다.

    Args:
        account_id: 대상 계정.

    Returns:
        티켓에 실을 절.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    catalog = get_item_catalog()
    equipped = build_equipped_entries(pool, entity_id, catalog)
    slots = list_consumable_slots(pool, entity_id, count_slot_bonus(equipped))
    player = get_context().balance["player"]
    progress = read_progress(pool, entity_id)
    loadout = build_player_loadout(
        {key: int(value) for key, value in player.items() if isinstance(value, int)},
        equipped,
        progress.level,
        int(player["rule_slots"]),
        progress.stats,
        count_slot_charges(slots),
        list_loaded_consumables(slots, catalog),
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
