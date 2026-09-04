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
from game.app.bots.doppel import check_is_doppel
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
from game.app.store.inventory_slots import apply_stack_grant
from game.app.store.item_catalog import read_generation
from game.app.store.items import create_item
from game.app.store.monster_snapshots import load_snapshots
from game.schemas.item import GRADE_SEALED_SLOTS, ItemKind, list_grades_downward

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


def find_grade_candidate(
    pool: ConnectionPool, source_id: int, grade: str, floor: int
) -> tuple[str, str] | None:
    """뽑힌 등급부터 **아래로 내려가며** 후보를 찾는다.

    올리지 않고 내리는 이유는 위로 올리면 그것이 공짜 승급이 되기 때문이다. 내려가는
    것은 손해이므로 남용될 수 없다.

    Args:
        pool: 연결 풀.
        source_id: 드롭 소스.
        grade: 1단계가 뽑은 등급.
        floor: 지금 층. 아직 안 열린 아이템은 후보에서 빠진다 (D1).

    Returns:
        (실제로 줄 등급, 아이템 id). 끝까지 없으면 None.
    """
    for candidate in list_grades_downward(grade):
        catalog_id = get_weighted(read_item_weights(pool, source_id, candidate, floor))
        if catalog_id is not None:
            return candidate, catalog_id
    return None


def apply_grade_misses(
    pool: ConnectionPool, account_id: int, entries: tuple[tuple[str, int], ...]
) -> None:
    """이번 굴림에서 안 나온 등급들의 천장을 한 칸씩 올린다.

    Args:
        pool: 연결 풀.
        account_id: 대상 계정.
        entries: 1단계 저울. 「안 나옴」은 등급이 아니므로 건너뛴다.
    """
    for name, _weight in entries:
        if name != GRADE_MISS:
            apply_pity(pool, account_id, name, is_hit=False)


def create_issued_item(
    pool: ConnectionPool, entity_id: int, catalog_id: str, context: dict
) -> tuple[bool, str]:
    """뽑힌 아이템을 실제로 발급한다.

    Args:
        pool: 연결 풀.
        entity_id: 받을 개체.
        catalog_id: 발급할 아이템.
        context: grade 와 submission_id 를 담은 절.

    Returns:
        (손에 들어왔는가, 화면에 적을 한 줄). 가방이 가득 차면 앞이 False 다 — 문자열을
        보고 판정하면 문구를 고치는 순간 도감이 조용히 어긋난다.
    """
    entry = get_item_catalog()[catalog_id]
    grade = str(context["grade"])
    # **소모품은 쌓는다.** 인스턴스로 넣으면 세는 쪽이 못 보고, 들고도 못 쓰는 물약이 된다.
    if entry.kind is ItemKind.CONSUMABLE:
        if not apply_stack_grant(pool, entity_id, catalog_id, max(1, entry.stack_max)):
            return False, f"{entry.label_ko} 을(를) 놓쳤다 — 가방이 가득 찼다"
        return True, f"{entry.label_ko} 획득"
    item_id = create_item(
        pool,
        entity_id,
        catalog_id,
        create_affix_rolls(entry.affixes),
        context.get("submission_id"),
        grade,
        # 등급이 봉인 칸을 준다 (§17). 최저 등급은 고정 옵션만 갖는다.
        GRADE_SEALED_SLOTS.get(grade, 0),
    )
    if item_id is None:
        return False, f"{entry.label_ko} 을(를) 놓쳤다 — 가방이 가득 찼다"
    return True, f"{entry.label_ko}({grade}) 획득"


def create_kill_drop(account_id: int, entity_id: int, context: dict) -> str:
    """처치 하나에 대해 굴리고, 나오면 발급한다.

    Args:
        account_id: 받을 계정.
        entity_id: 받을 개체.
        context: kind_id·level·floor·submission_id 를 담은 절.

    Returns:
        화면에 적을 한 줄. 아무것도 안 나왔으면 빈 문자열.
    """
    # **도플갱어는 굴리지 않는다.** 그 개체는 봇의 장비에서 나오므로, 무엇이든
    # 떨어지면 봇이 벌어 둔 것을 사람에게 건네는 통로가 된다 — 아이템이 세계에
    # 들어오는 문은 검증된 런 하나뿐이라는 결정 #02 가 그 자리에서 뚫리고, 봇을
    # 여럿 돌려 죽이는 것이 최적 파밍이 된다 (T11).
    if check_is_doppel(str(context["kind_id"])):
        return ""
    pool = get_pool()
    floor = int(context["floor"])
    level = int(context["level"])
    source_id, source_kind, source_ref = find_drop_source(pool, str(context["kind_id"]))
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
    entries = build_grade_pool(
        read_grade_weights(pool, source_id), miss_weight, level, read_pity(pool, account_id)
    )
    rolled = get_weighted(entries)
    if rolled is None or rolled == GRADE_MISS:
        apply_grade_misses(pool, account_id, entries)
        record_roll(pool, account_id, {**fields, "detail": "안 나옴"})
        return ""
    return apply_grade_roll(
        pool,
        entity_id,
        {
            "account_id": account_id,
            "rolled": rolled,
            "entries": entries,
            "source_id": source_id,
            "floor": floor,
            "fields": fields,
        },
    )


def apply_grade_roll(pool: ConnectionPool, entity_id: int, context: dict) -> str:
    """뽑힌 등급으로 아이템을 정하고 천장을 갱신한다.

    **후보가 없으면 천장을 안 태운다.** 예전에는 후보를 찾기 전에 `is_hit=True` 를 눌러,
    표가 빈 등급을 뽑을 때마다 천장이 0 으로 돌아가고 손에는 아무것도 안 남았다 —
    프로덕션에서 상급·유물 굴림 26건이 그렇게 사라졌다. 오래 못 받은 사람일수록 그
    경로를 자주 밟는다.

    Args:
        pool: 연결 풀.
        entity_id: 받을 개체.
        context: account_id·rolled·entries·source_id·floor·fields 를 담은 절.

    Returns:
        화면에 적을 한 줄. 아무것도 안 나왔으면 빈 문자열.
    """
    account_id = int(context["account_id"])
    rolled = str(context["rolled"])
    fields = dict(context["fields"])
    found = find_grade_candidate(pool, int(context["source_id"]), rolled, int(context["floor"]))
    if found is None:
        apply_grade_misses(pool, account_id, context["entries"])
        record_roll(
            pool, account_id, {**fields, "grade": rolled, "detail": "그 등급에 후보가 없다"}
        )
        return ""
    issued, catalog_id = found
    apply_pity(pool, account_id, issued, is_hit=True)
    if issued != rolled:
        # 강등해서 준 것은 뽑힌 등급을 **받은 것이 아니다.** 천장은 그대로 쌓여야 한다.
        apply_pity(pool, account_id, rolled, is_hit=False)
    is_kept, note = create_issued_item(
        pool, entity_id, catalog_id, {"grade": issued, "submission_id": fields["submission_id"]}
    )
    record_roll(
        pool,
        account_id,
        {
            **fields,
            "grade": issued,
            "catalog_id": catalog_id,
            "detail": build_roll_detail(rolled, issued, is_kept),
        },
    )
    if is_kept:
        # 손에 들어온 것만 밝힌다. 놓친 것을 밝히면 도감이 "가진 적 없는 것" 을 연다.
        record_item_discovery(account_id, catalog_id)
    return note


def build_roll_detail(rolled: str, issued: str, is_kept: bool) -> str:
    """원장에 남길 사유 한 줄을 만든다.

    **강등을 원장에 남긴다.** 안 남기면 나중에 분포를 재 볼 때 상급이 실제보다 많이
    나온 것처럼 보인다.

    Args:
        rolled: 1단계가 뽑은 등급.
        issued: 실제로 준 등급.
        is_kept: 손에 들어왔는가.

    Returns:
        사유. 특별할 것이 없으면 빈 문자열.
    """
    parts = []
    if issued != rolled:
        parts.append(f"{rolled} → {issued} 강등")
    if not is_kept:
        parts.append("가방이 가득 차 놓쳤다")
    return ". ".join(parts)


def list_floor_defeats(
    room_kinds: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
    start_floor: int,
    floor: int,
    rooms_per_floor: int,
) -> tuple[str, ...]:
    """그 층의 방들에서 잡은 것만 고른다.

    **전체를 주면 층을 깰 때마다 지나온 층의 전리품이 다시 나온다.** 서버는 층 단위
    보상을 줄 때마다 처음부터 그 층까지 다시 돌므로(T9), 앞 층의 처치가 결과에 늘 섞여
    있다 — 여기서 잘라야 한 번 준 것을 또 주지 않는다.

    Args:
        room_kinds: 방마다 (만난 종, 잡은 종).
        start_floor: 하강이 시작한 층.
        floor: 보상을 줄 층.
        rooms_per_floor: 층 하나에 드는 방 수. 0 이면 전체가 한 층이다.

    Returns:
        잡은 종들. 방 순서대로이며 중복이 그대로 남는다 — 같은 종을 둘 잡았으면 둘이다.
    """
    if rooms_per_floor <= 0:
        return tuple(kind for _seen, killed in room_kinds for kind in killed)
    begin = max(0, floor - start_floor) * rooms_per_floor
    return tuple(
        kind for _seen, killed in room_kinds[begin : begin + rooms_per_floor] for kind in killed
    )


def create_run_drops(
    account_id: int, submission_id: int, defeated: tuple[str, ...], floor: int, ticket_id: str
) -> list[str]:
    """이 층의 처치를 하나씩 굴린다.

    **재시뮬이 확정한 처치 목록만 쓴다.** 클라이언트 보고로 굴리면 "많이 잡았다" 고 적어
    보내는 것이 곧 파밍이 된다 (T9 와 같은 자리).

    Args:
        account_id: 받을 계정.
        submission_id: 이 결과의 제출 id.
        defeated: 이 층에서 잡은 종들. 부르는 쪽이 층으로 잘라서 넘긴다.
        floor: 이 층.
        ticket_id: 이 런의 티켓. 스냅샷에서 개체 레벨을 찾는다.

    Returns:
        화면에 적을 줄들. 아무것도 안 나왔으면 빈 목록.
    """
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
