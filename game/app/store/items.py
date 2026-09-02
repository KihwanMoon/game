"""아이템 보관 — 인벤토리·장비·지갑 (docs/설계/4_아이템 §5·§12).

**봉인을 저장하지 않는다.** 양손무기가 보조 슬롯을 막는 것은 파생값이며, 저장하면
착용·해제 순서에 따라 상태가 갈린다 (§2.1). 여기는 착용한 것만 담고, 봉인은 읽는 쪽이
`get_effective_slots` 로 계산한다.

인벤토리는 **가장 낮은 빈 칸**에 넣는다. 자동 폐기를 두지 않는 이유는 P1 이다 — 왜
사라졌는지 설명할 수 없는 삭제는 버그와 구분되지 않는다.
"""

import json
from dataclasses import dataclass

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.store.inventory_slots import find_empty_slot
from game.schemas.item import Affix, EquipSlot

# 인벤토리 칸 수. 밸런스가 정해지기 전의 출발값이다 (docs/설계/4_아이템 §5).

EVENT_GRANT = "grant"
EVENT_EQUIP = "equip"
EVENT_UNEQUIP = "unequip"
EVENT_DISCARD = "discard"
EVENT_BREAK = "break"
EVENT_REPAIR = "repair"


@dataclass(frozen=True)
class StoredItem:
    """보관된 아이템 하나."""

    item_id: int
    catalog_id: str
    affixes: tuple[Affix, ...]
    is_broken: bool
    # 거래 후 귀속 (결정 #07). 한 번 팔린 아이템은 산 사람에게 묶여 다시 팔 수 없다.
    is_bound: bool = False
    # 남은 봉인 칸 (§17). **무엇이 들어올지는 안 담는다** — 미리 정하면 클라이언트로
    # 새어 나가고, 그 순간 "열기 전에 아는" 것이 되어 열 이유가 사라진다.
    sealed_slots: int = 0
    # 굴린 등급. 봉인 칸 수와 함께 이 아이템이 무엇인지를 말한다.
    grade: str = ""
    # 몬스터에게 빼앗겼다가 되찾은 것인가 (`설계/6_몬스터` §5). 잃은 것과 되찾은 것이
    # 가방에서 같아 보이면 World Loop 가 화면에 흔적을 남기지 않는다.
    is_recovered: bool = False


@dataclass(frozen=True)
class InventoryEntry:
    """인벤토리 한 칸. 장비이거나 소모품 스택이다."""

    slot_index: int
    item: StoredItem | None
    stack_catalog_id: str | None
    stack_count: int


def read_affixes(raw: object) -> tuple[Affix, ...]:
    """저장된 접사 절을 읽는다.

    Args:
        raw: JSONB 에서 나온 값.

    Returns:
        접사들. 형식이 아니면 빈 튜플.
    """
    items = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(items, list):
        return ()
    return tuple(
        Affix(
            stat=str(item["stat"]),
            flat=int(item.get("flat", 0)),
            percent=int(item.get("percent", 0)),
            label_ko=str(item.get("label_ko", "")),
        )
        for item in items
        if isinstance(item, dict) and "stat" in item
    )


def build_affix_payload(affixes: tuple[Affix, ...]) -> list[dict]:
    """접사를 저장 절로 되돌린다.

    Args:
        affixes: 저장할 접사들.

    Returns:
        JSONB 에 넣을 목록.
    """
    return [
        {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
        for a in affixes
    ]


def record_item_event(
    pool: ConnectionPool, entity_id: int, item_id: int | None, kind: str, detail: str = ""
) -> None:
    """아이템 이력 한 줄을 남긴다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).
        item_id: 대상 아이템. 소모품이면 None.
        kind: 사건 종류.
        detail: 부연.
    """
    with pool.connection() as connection:
        connection.execute(
            "INSERT INTO item_event (item_id, entity_id, kind, detail) VALUES (%s, %s, %s, %s)",
            (item_id, entity_id, kind, detail),
        )


def create_item(
    pool: ConnectionPool,
    entity_id: int,
    catalog_id: str,
    affixes: tuple[Affix, ...],
    origin_run_result_id: int | None = None,
    grade: str | None = None,
    sealed_slots: int = 0,
) -> int | None:
    """아이템을 발급해 인벤토리에 넣는다.

    가득 찼으면 **발급하지 않는다.** 발급만 하고 칸을 못 주면 어디에도 없는 아이템이
    생기고, 그것은 문의로 돌아온다.

    Args:
        pool: 연결 풀.
        entity_id: 받을 개체.
        catalog_id: 카탈로그 id.
        affixes: 굴린 접사.
        origin_run_result_id: 어느 검증된 런에서 나왔는가.
        grade: 굴린 등급. **카탈로그를 참조하지 않고 복사한다** — 참조로 두면 카탈로그를
            고칠 때 남의 가방에 있는 아이템의 등급이 소급해 바뀐다 (설계/4_아이템 §15.5).
        sealed_slots: 봉인된 옵션 칸 수 (§17). 등급이 정한다.

    Returns:
        만들어진 아이템 id. 인벤토리가 가득 찼으면 None.
    """
    slot = find_empty_slot(pool, entity_id)
    if slot is None:
        return None
    with pool.connection() as connection:
        row = connection.execute(
            "INSERT INTO item_instance (owner_entity_id, catalog_id, affixes,"
            " origin_run_result_id, grade, sealed_slots)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                entity_id,
                catalog_id,
                Jsonb(build_affix_payload(affixes)),
                origin_run_result_id,
                grade,
                sealed_slots,
            ),
        ).fetchone()
        if row is None:
            raise RuntimeError("아이템을 만들지 못했다")
        item_id = int(row[0])
        connection.execute(
            "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
            (entity_id, slot, item_id),
        )
    record_item_event(pool, entity_id, item_id, EVENT_GRANT, catalog_id)
    return item_id


def list_inventory(pool: ConnectionPool, entity_id: int) -> tuple[InventoryEntry, ...]:
    """인벤토리를 칸 번호 순으로 읽는다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).

    Returns:
        칸 번호 순으로 정렬된 항목들. 빈 칸은 담지 않는다.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT s.slot_index, s.item_id, s.stack_catalog_id, s.stack_count,"
            " i.catalog_id, i.affixes, i.is_broken, i.is_bound, i.taken_from, i.sealed_slots,"
            # **등급을 읽는다.** 안 읽으면 모든 줄이 빈 등급으로 나가고, 화면은 색도
            # 이름표도 못 붙인다 — 봉인 칸은 뜨는데 등급만 안 뜨던 것이 이 자리다.
            " i.grade"
            " FROM inventory_slot s LEFT JOIN item_instance i ON i.id = s.item_id"
            " WHERE s.entity_id = %s ORDER BY s.slot_index",
            (entity_id,),
        ).fetchall()
    return tuple(
        InventoryEntry(
            slot_index=int(row[0]),
            item=None
            if row[1] is None
            else StoredItem(
                item_id=int(row[1]),
                catalog_id=str(row[4]),
                affixes=read_affixes(row[5]),
                is_broken=bool(row[6]),
                is_bound=bool(row[7]),
                # `taken_from` 이 채워진 채 내 가방에 있다는 것은 되찾았다는 뜻이다 —
                # 몬스터가 들고 있는 동안에는 그 개체가 소유자다.
                is_recovered=row[8] is not None,
                sealed_slots=int(row[9] or 0),
                grade=str(row[10] or ""),
            ),
            stack_catalog_id=None if row[2] is None else str(row[2]),
            stack_count=int(row[3] or 0),
        )
        for row in rows
    )


def list_equipment(pool: ConnectionPool, entity_id: int) -> dict[EquipSlot, StoredItem]:
    """착용 중인 장비를 읽는다. **봉인은 반영하지 않는다** — 읽는 쪽이 계산한다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).

    Returns:
        슬롯에서 아이템으로의 대응표.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT e.slot, i.id, i.catalog_id, i.affixes, i.is_broken, i.is_bound,"
            " i.taken_from, i.sealed_slots, i.grade"
            " FROM equipment_slot e JOIN item_instance i ON i.id = e.item_id"
            " WHERE e.entity_id = %s ORDER BY e.slot",
            (entity_id,),
        ).fetchall()
    return {
        EquipSlot(str(row[0])): StoredItem(
            item_id=int(row[1]),
            catalog_id=str(row[2]),
            affixes=read_affixes(row[3]),
            is_broken=bool(row[4]),
            is_bound=bool(row[5]),
            is_recovered=row[6] is not None,
            sealed_slots=int(row[7] or 0),
            grade=str(row[8] or ""),
        )
        for row in rows
    }


def find_item(pool: ConnectionPool, entity_id: int, item_id: int) -> StoredItem | None:
    """계정이 가진 아이템 하나를 찾는다.

    Args:
        pool: 연결 풀.
        entity_id: 개체 id (entity_record).
        item_id: 아이템 id.

    Returns:
        찾은 아이템. 없거나 남의 것이면 None.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT id, catalog_id, affixes, is_broken, is_bound, taken_from, sealed_slots,"
            " grade FROM item_instance"
            " WHERE id = %s AND owner_entity_id = %s",
            (item_id, entity_id),
        ).fetchone()
    if row is None:
        return None
    return StoredItem(
        item_id=int(row[0]),
        catalog_id=str(row[1]),
        affixes=read_affixes(row[2]),
        is_broken=bool(row[3]),
        is_bound=bool(row[4]),
        is_recovered=row[5] is not None,
        sealed_slots=int(row[6] or 0),
        grade=str(row[7] or ""),
    )


# 봉인 옵션 풀의 기본값. **서버만 읽는다** — 굴림이 코어 밖이라 리플레이가 안 흔들린다.
# 사거리와 CPU 는 가중치를 낮게 뒀다. 둘은 값이 아니라 **전술을 바꾸는** 옵션이라,
# 흔하게 나오면 규칙표를 다시 짜는 일이 파밍의 부작용이 된다.
DEFAULT_AFFIX_POOL: tuple[tuple[str, str, int, int, int, int, int], ...] = (
    ("attack", "날카로움", 1, 4, 0, 0, 30),
    ("defense", "단단함", 1, 3, 0, 0, 30),
    ("hp_max", "튼튼함", 3, 10, 0, 0, 30),
    ("initiative", "재빠름", 2, 8, 0, 0, 20),
    ("attack_range", "먼 사거리", 1, 1, 0, 0, 5),
    ("cpu_budget", "여유 회로", 1, 1, 0, 0, 5),
    # 소모품 칸을 늘린다 (§5). **사거리·CPU 와 같은 무게다** — 한 칸이 곧 물약 하나가
    # 아니라 「그 칸에 무엇을 끼울지」를 하나 더 고르는 것이라, 흔하면 한도가 흐려진다.
    ("potion_slots", "물약 주머니", 1, 1, 0, 0, 5),
    ("scroll_slots", "주문서 통", 1, 1, 0, 0, 5),
)


def apply_affix_pool_seed(pool: ConnectionPool) -> int:
    """파일에 있는데 풀에 없는 옵션만 심는다.

    **한 번 채우고 끝내지 않는다.** 예전에는 표가 비어 있을 때만 돌아서, 옵션을 하나
    더해도 이미 돌고 있는 서버에는 영영 안 들어갔다 — 카탈로그와 드롭 표에서 이미 두 번
    겪은 구멍이고, 세 번째가 소모품 칸 옵션이었다.

    **있는 줄은 안 고친다.** 관리자가 무게를 조정한 것이 배포 한 번에 되돌아가면
    정본이 DB 라는 말이 거짓이 된다.

    Args:
        pool: 연결 풀.

    Returns:
        새로 심은 줄 수. 심을 것이 없었으면 0.
    """
    with pool.connection() as connection:
        rows = connection.execute("SELECT stat FROM affix_pool").fetchall()
        known = {str(row[0]) for row in rows}
        fresh = [entry for entry in DEFAULT_AFFIX_POOL if entry[0] not in known]
        for entry in fresh:
            connection.execute(
                "INSERT INTO affix_pool (stat, label_ko, flat_min, flat_max,"
                " percent_min, percent_max, weight) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                entry,
            )
    return len(fresh)


def list_affix_pool(pool: ConnectionPool) -> tuple[tuple[str, str, int, int, int, int, int], ...]:
    """옵션 풀을 읽는다. 폐기된 줄은 빠진다.

    Args:
        pool: 연결 풀.

    Returns:
        (stat, label_ko, flat_min, flat_max, percent_min, percent_max, weight) 들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT stat, label_ko, flat_min, flat_max, percent_min, percent_max, weight"
            " FROM affix_pool WHERE NOT is_retired ORDER BY id"
        ).fetchall()
    return tuple(
        (str(r[0]), str(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]), int(r[6])) for r in rows
    )


def apply_unseal(pool: ConnectionPool, item_id: int, affix: Affix) -> bool:
    """봉인 한 칸을 열고 옵션을 붙인다.

    **조건부 갱신이다.** 남은 칸이 있을 때만 바뀌므로, 같은 요청이 두 번 와도 한 번만
    열린다 — 화폐는 부르는 쪽이 이미 뺐다.

    Args:
        pool: 연결 풀.
        item_id: 대상 아이템.
        affix: 붙일 옵션.

    Returns:
        실제로 열렸으면 True.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT affixes FROM item_instance WHERE id = %s AND sealed_slots > 0", (item_id,)
        ).fetchone()
        if row is None:
            return False
        merged = list(row[0] or []) + build_affix_payload((affix,))
        cursor = connection.execute(
            "UPDATE item_instance SET affixes = %s, sealed_slots = sealed_slots - 1"
            " WHERE id = %s AND sealed_slots > 0",
            (Jsonb(merged), item_id),
        )
    return cursor.rowcount == 1
