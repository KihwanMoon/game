"""아이템 카탈로그 로드와 조회 (docs/설계/4_아이템 §12).

카탈로그는 **DB 가 아니라 리소스**다. 코어 버전에 묶여야 하고, 서버가 재시뮬할 때
같은 값을 봐야 하기 때문이다 — 서버가 카탈로그를 따로 들면 재시뮬이 다른 아이템으로
돌아 검증이 성립하지 않는다.
"""

import json
from pathlib import Path

from game.schemas.item import EquipSlot, ItemCatalogEntry, ItemKind, parse_item


def load_item_catalog(source_path: Path) -> dict[str, ItemCatalogEntry]:
    """카탈로그 파일을 읽는다.

    Args:
        source_path: items.json 경로.

    Returns:
        catalog_id 에서 항목으로의 대응표.

    Raises:
        ValueError: 같은 id 가 두 번 나오는 경우. 뒤엣것이 앞엣것을 조용히 덮으면
            아이템 하나가 세이브에서만 존재하는 상태가 된다.
    """
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    catalog: dict[str, ItemCatalogEntry] = {}
    for item in raw["items"]:
        entry = parse_item(item)
        if entry.catalog_id in catalog:
            raise ValueError(f"카탈로그 id 가 중복이다: {entry.catalog_id}")
        catalog[entry.catalog_id] = entry
    return catalog


def find_item(catalog: dict[str, ItemCatalogEntry], catalog_id: str) -> ItemCatalogEntry:
    """카탈로그에서 항목 하나를 찾는다.

    Args:
        catalog: 카탈로그.
        catalog_id: 찾을 id.

    Returns:
        찾은 항목.

    Raises:
        KeyError: 없는 id 인 경우.
    """
    if catalog_id not in catalog:
        raise KeyError(f"카탈로그에 없는 아이템이다: {catalog_id}")
    return catalog[catalog_id]


def list_slot_items(
    catalog: dict[str, ItemCatalogEntry], slot: EquipSlot
) -> tuple[ItemCatalogEntry, ...]:
    """그 슬롯에 들어갈 수 있는 장비를 모은다.

    정렬해서 돌려준다. 딕셔너리 순회 순서가 화면 목록에 새어 나가면 같은 카탈로그가
    실행마다 다른 순서로 보인다 (R5).

    Args:
        catalog: 카탈로그.
        slot: 대상 슬롯.

    Returns:
        catalog_id 순으로 정렬된 항목들.
    """
    found = [
        entry
        for entry in catalog.values()
        if entry.kind is ItemKind.EQUIPMENT and entry.slot is slot
    ]
    return tuple(sorted(found, key=lambda entry: entry.catalog_id))
