"""처치마다 전리품을 굴린다 (설계/4_아이템 §15.3).

**굴림의 단위가 런이 아니라 처치다.** "몬스터 레벨에 따라 달라진다" 를 성립시키려면
누구를 잡았는가가 입력이어야 하고, 재시뮬은 이미 그것을 안다 —
`RunSummary.defeated_kinds` 가 처치 하나당 한 항목이다.

레벨은 티켓 스냅샷에서 찾고, 없으면 층에서 파생한다. 방이 그때 낳은 잡몹에는 개체
레벨이 없기 때문이다.

**안 나온 굴림도 원장에 남긴다** (D4). 안 나온 것이 데이터다 — 결과만 남기면 확률이
맞는지 사후에 증명할 수 없다.
"""

from psycopg_pool import ConnectionPool

from game.api.deps import get_item_catalog, get_pool
from game.api.discovery_service import record_item_discovery
from game.app.items.drops import GRADE_MISS, build_grade_pool, create_affix_rolls, get_weighted
from game.app.store.accounts import find_player_entity
from game.app.store.drops import (
    DEFAULT_GRADE_WEIGHTS,
    SOURCE_ANY,
    SOURCE_MONSTER,
    apply_pity,
    find_source,
    read_grade_weights,
    read_item_weights,
    read_pity,
    record_roll,
)
from game.app.store.item_catalog import read_generation
from game.app.store.items import create_item
from game.app.store.monsters import load_snapshots

# 스냅샷에 없는 종의 기준 레벨. 방이 그때 낳은 잡몹은 개체 레벨이 없다.
FLOOR_LEVEL_STEP = 1


def find_monster_level(kind_id: str, snapshots: tuple, floor: int) -> int:
    """그 종을 잡았을 때 쓸 레벨을 정한다.

    Args:
        kind_id: 잡은 종.
        snapshots: 티켓이 얼려 둔 지속 몬스터들.
        floor: 이 런의 층.

    Returns:
        레벨. 스냅샷에 없으면 층에서 파생한 값.
    """
    found = [item.level for item in snapshots if item.kind_id == kind_id]
    return max(found) if found else max(1, floor * FLOOR_LEVEL_STEP)


def find_drop_source(pool: ConnectionPool, kind_id: str) -> tuple[int | None, str, str]:
    """이 종의 드롭 표를 찾는다. 없으면 `ANY` 로 떨어진다.

    Args:
        pool: 연결 풀.
        kind_id: 잡은 종.

    Returns:
        (소스 id, 소스 갈래, 소스 식별자). 표가 아예 없으면 id 가 None.
    """
    source_id = find_source(pool, SOURCE_MONSTER, kind_id)
    if source_id is not None:
        return source_id, SOURCE_MONSTER, kind_id
    return find_source(pool, SOURCE_ANY), SOURCE_ANY, ""


def create_kill_drop(account_id: int, entity_id: int, context: dict) -> str:
    """처치 하나에 대해 굴리고, 나오면 발급한다.

    Args:
        account_id: 받을 계정.
        entity_id: 받을 개체.
        context: kind_id·level·floor·submission_id 를 담은 절.

    Returns:
        화면에 적을 한 줄. 아무것도 안 나왔으면 빈 문자열.
    """
    pool = get_pool()
    kind_id = str(context["kind_id"])
    floor = int(context["floor"])
    level = int(context["level"])
    source_id, source_kind, source_ref = find_drop_source(pool, kind_id)
    fields = {
        "submission_id": context.get("submission_id"),
        "source_kind": source_kind,
        "source_ref": source_ref,
        "monster_level": level,
        "floor": floor,
        "generation": read_generation(pool),
    }
    if source_id is None:
        record_roll(pool, account_id, {**fields, "detail": "드롭 표가 없다"})
        return ""

    miss_weight = next(weight for grade, weight, _s in DEFAULT_GRADE_WEIGHTS if grade == GRADE_MISS)
    pool_entries = build_grade_pool(
        read_grade_weights(pool, source_id), miss_weight, level, read_pity(pool, account_id)
    )
    grade = get_weighted(pool_entries)
    if grade is None or grade == GRADE_MISS:
        for name, _weight in pool_entries:
            if name != GRADE_MISS:
                apply_pity(pool, account_id, name, is_hit=False)
        record_roll(pool, account_id, {**fields, "detail": "안 나옴"})
        return ""

    apply_pity(pool, account_id, grade, is_hit=True)
    catalog_id = get_weighted(read_item_weights(pool, source_id, grade, floor))
    if catalog_id is None:
        record_roll(pool, account_id, {**fields, "grade": grade, "detail": "그 등급에 후보가 없다"})
        return ""

    entry = get_item_catalog()[catalog_id]
    item_id = create_item(
        pool,
        entity_id,
        catalog_id,
        create_affix_rolls(entry.affixes, grade),
        context.get("submission_id"),
        grade,
    )
    detail = "가방이 가득 차 놓쳤다" if item_id is None else ""
    record_roll(
        pool,
        account_id,
        {**fields, "grade": grade, "catalog_id": catalog_id, "detail": detail},
    )
    if item_id is None:
        return f"{entry.label_ko} 을(를) 놓쳤다 — 가방이 가득 찼다"
    # 손에 들어온 것만 밝힌다. 놓친 것을 밝히면 도감이 "가진 적 없는 것" 을 연다.
    record_item_discovery(account_id, catalog_id)
    return f"{entry.label_ko}({grade}) 획득"


def create_run_drops(
    account_id: int, submission_id: int, verified: object, floor: int, ticket_id: str
) -> list[str]:
    """이 런의 처치를 하나씩 굴린다.

    **재시뮬이 확정한 처치 목록만 쓴다.** 클라이언트 보고로 굴리면 "많이 잡았다" 고 적어
    보내는 것이 곧 파밍이 된다 (T9 와 같은 자리).

    Args:
        account_id: 받을 계정.
        submission_id: 이 결과의 제출 id.
        verified: 서버가 확정한 결과. `summary.defeated_kinds` 를 읽는다.
        floor: 이 런의 층.
        ticket_id: 이 런의 티켓. 스냅샷에서 개체 레벨을 찾는다.

    Returns:
        화면에 적을 줄들. 아무것도 안 나왔으면 빈 목록.
    """
    summary = getattr(verified, "summary", None)
    defeated = tuple(getattr(summary, "defeated_kinds", ()) or ())
    if not defeated:
        return []
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    snapshots = load_snapshots(pool, ticket_id)
    notes: list[str] = []
    for kind_id in defeated:
        note = create_kill_drop(
            account_id,
            entity_id,
            {
                "kind_id": kind_id,
                "level": find_monster_level(kind_id, snapshots, floor),
                "floor": floor,
                "submission_id": submission_id,
            },
        )
        if note:
            notes.append(note)
    return notes
