"""전리품 이전 — 몬스터가 플레이어의 장비를 가져간다 (결정 #34, `설계/6_몬스터` §5).

**사본을 만든다.** 원본을 옮기면 플레이어가 그것을 되찾기 전까지 잃은 것이 되고, 사망
대가(장비 하나)와 이중으로 물린다. 사본이라 되찾는 것은 "덤" 이고, 그것이 되찾으러 갈
동기를 만들되 강제하지 않는 방식이다.

몬스터 성장(`store/monsters.py`)과 갈라 둔 이유는 책임이 다르기 때문이다 — 저쪽은 개체가
얼마나 컸는가이고, 이쪽은 무엇을 들고 있는가다.
"""

import json

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.store.items import find_empty_slot, record_item_event

# 되찾기. `grant` 와 가르는 이유는 원장에서 World Loop 를 셀 수 있어야 하기 때문이다 —
# 발급된 아이템과 돌려받은 아이템은 경제에서 뜻이 다르다.
EVENT_RECOVER = "recover"

# 한 개체가 들 수 있는 전리품 수 (2026-09-06).
#
# **상한이 없어서 무한히 쌓였다.** 패배마다 하나씩 들어오는데 봇이 쉼 없이 죽으므로,
# 1층 고블린 하나가 **696개**를 들고 있었다 — 도감이 못 읽을 화면이 되고, 「저 놈이 내
# 걸 들고 있다」가 목록에 묻힌다.
#
# 다섯인 이유는 그것이 **보여 주기에 충분한 수**이기 때문이다. 이 사본의 목적은 도감이
# 그 한 줄을 말하는 것이지 몬스터를 키우는 것이 아니다.
MAX_TROPHIES = 5


def compute_affix_score(raw: object) -> int:
    """이 절이 개체를 얼마나 세게 만드는가.

    **거친 척도다.** 스탯마다 값어치가 다르지만(공격 1 과 체력 1 은 같지 않다), 여기서
    필요한 것은 순위지 균형이 아니다 — 「더 강해지는가」만 가르면 된다. 정교한 값어치는
    밸런스의 몫이고 그것을 여기 두면 두 곳이 어긋난다.

    퍼센트를 그대로 더하는 이유도 같다. 기준값을 모르면 환산할 수 없고, 그것을 알려면
    개체 스탯을 여기까지 끌고 와야 한다.

    Args:
        raw: 접사 절. 문자열이거나 이미 풀린 목록이다.

    Returns:
        합. 절이 아니면 0.
    """
    if isinstance(raw, str):
        # **터지면 그 판의 결산이 통째로 죽는다.** 절이 아닌 값이 어디서 오든(옛 행,
        # 손으로 고친 데이터), 값어치를 못 매기는 것과 판이 안 끝나는 것은 다른 일이다.
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return 0
    if not isinstance(raw, list):
        return 0
    return sum(
        int(one.get("flat", 0)) + int(one.get("percent", 0)) for one in raw if isinstance(one, dict)
    )


def create_trophy(
    pool: ConnectionPool,
    record_id: int,
    catalog_id: str,
    affixes: list[dict],
    taken_from: int,
) -> bool:
    """몬스터가 플레이어의 장비 사본을 가져간다 (결정 #34).

    **다섯까지만 들고, 더 강해질 때만 받는다** (2026-09-06). 상한이 없던 때는 패배마다
    하나씩 영원히 쌓여 한 마리가 696개를 들고 있었다.

    **별도 표가 아니라 그 개체가 소유한 아이템으로 넣는다.** 표를 가르면 "몬스터가 내
    장비를 들고 있다" 가 다시 특수 케이스가 되고, 나중에 몬스터가 그것을 장착하거나
    되찾기가 거래를 타야 할 때 양쪽을 합쳐야 한다.

    Args:
        pool: 연결 풀.
        record_id: 가져간 몬스터의 개체 id.
        catalog_id: 아이템 카탈로그 id.
        affixes: 접사 절.
        taken_from: 누구에게서 가져왔는가.

    Returns:
        실제로 가져갔으면 True. 상한에 걸렸고 더 강해지지도 않으면 False.
    """
    score = compute_affix_score(affixes)
    with pool.connection() as connection:
        held = connection.execute(
            "SELECT id, affixes FROM item_instance WHERE owner_entity_id = %s ORDER BY id",
            (record_id,),
        ).fetchall()
        if len(held) >= MAX_TROPHIES:
            # **더 강해질 때만 받는다.** 가장 약한 것과 견주어 못 이기면 안 가져간다 —
            # 그러면 개체가 「지금까지 본 것 중 가장 좋은 다섯」으로 수렴한다.
            weakest = min(held, key=lambda row: compute_affix_score(row[1]))
            if score <= compute_affix_score(weakest[1]):
                return False
            connection.execute("DELETE FROM item_instance WHERE id = %s", (weakest[0],))
        connection.execute(
            "INSERT INTO item_instance (owner_entity_id, catalog_id, affixes, taken_from)"
            " VALUES (%s, %s, %s, %s)",
            (record_id, catalog_id, Jsonb(affixes), taken_from),
        )
    return True


def list_trophies(pool: ConnectionPool, record_id: int) -> tuple[dict, ...]:
    """그 몬스터가 들고 있는 전리품을 읽는다. 도감이 이것을 보여준다.

    Args:
        pool: 연결 풀.
        record_id: 몬스터 id.

    Returns:
        전리품 절들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT catalog_id, taken_from FROM item_instance"
            " WHERE owner_entity_id = %s AND taken_from IS NOT NULL"
            " ORDER BY created_at DESC",
            (record_id,),
        ).fetchall()
    return tuple({"catalog_id": str(row[0]), "taken_from": row[1]} for row in rows)


def apply_recovery(
    pool: ConnectionPool, record_id: int, account_id: int, entity_id: int
) -> tuple[str, ...]:
    """그 몬스터가 들고 있던 것 중 **내 것만** 되찾는다 (`설계/6_몬스터` §5, M1).

    처치 보상을 "아이템" 이 아니라 "그 몬스터가 들고 있던 것 중 자기 것" 으로 한정하는
    것이 동시 처치의 보상 복제를 막는 방식이다 — 두 사람이 같은 개체를 잡아도 각자
    자기 것만 가져간다.

    **되찾은 것은 귀속된다.** 사본이라 아이템 총량이 이미 한 번 늘었고, 그것이 경매에
    흘러들면 사망이 화폐 발행이 된다. 귀속은 그 통로를 막되 쓰는 것은 막지 않는다
    (결정 #07·#34).

    가방이 가득 차면 **거기서 멈춘다.** 소유만 옮기고 칸을 못 주면 어디에도 없는
    아이템이 생긴다 — `create_item` 과 같은 이유다.

    Args:
        pool: 연결 풀.
        record_id: 처치한 몬스터.
        account_id: 되찾는 계정. `taken_from` 과 대조한다.
        entity_id: 그 계정의 개체 id (아이템이 옮겨 갈 자리).

    Returns:
        되찾은 아이템의 카탈로그 id 들. 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, catalog_id FROM item_instance"
            " WHERE owner_entity_id = %s AND taken_from = %s ORDER BY created_at",
            (record_id, account_id),
        ).fetchall()
    taken: list[str] = []
    for row in rows:
        slot = find_empty_slot(pool, entity_id)
        if slot is None:
            break
        with pool.connection() as connection:
            connection.execute(
                "UPDATE item_instance SET owner_entity_id = %s, is_bound = TRUE WHERE id = %s",
                (entity_id, int(row[0])),
            )
            connection.execute(
                "INSERT INTO inventory_slot (entity_id, slot_index, item_id) VALUES (%s, %s, %s)",
                (entity_id, slot, int(row[0])),
            )
        record_item_event(pool, entity_id, int(row[0]), EVENT_RECOVER, str(row[1]))
        taken.append(str(row[1]))
    return tuple(taken)
