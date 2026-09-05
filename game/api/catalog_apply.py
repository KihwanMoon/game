"""카탈로그 초안을 검사하고 반영한다 (설계/9_에이전트_운영 §3.2).

**같은 검사가 두 번 돈다.** 초안을 올릴 때와 발행할 때다. 두 번인 이유는 그 사이에
카탈로그가 움직이기 때문이다 — 다른 초안이 먼저 발행돼 같은 id 가 이미 생겼을 수 있고,
그때는 발행이 조용히 덮는 대신 멈춰야 한다.

올릴 때도 하는 이유는 **올린 사람이 그 자리에서 알아야 하기 때문이다.** 발행할 때만
검사하면 잘못된 초안이 며칠 쌓여 있다가 사람이 발행을 누른 순간 터진다.

그래서 `check_*` 와 `apply_*` 를 갈랐다. 앞엣것은 아무것도 안 쓰고 무엇을 쓸지만 만든다.
"""

from dataclasses import replace

from psycopg_pool import ConnectionPool

from game.api.catalog_admin import build_entry_from_request, list_locked_changes
from game.app.store.catalog_draft import (
    ACTION_EDIT,
    ACTION_ITEM,
    ACTION_RESTORE,
    ACTION_RETIRE,
    CatalogDraft,
)
from game.app.store.drops import SOURCE_ANY, save_source
from game.app.store.item_catalog import apply_retire, list_catalog, save_catalog_entry
from game.schemas.item import (
    ItemCatalogEntry,
    list_grades_above,
    list_unknown_stats,
    parse_affix,
)


class CatalogConflictError(ValueError):
    """이미 있는 id 로 등록하려 했다.

    `ValueError` 와 갈라 두는 이유는 **답이 다르기 때문이다** — 절이 규격을 어긴 것은
    400 이고 이것은 409 다. 하나로 묶으면 "고치려던 것" 이 "잘못 썼다" 로 읽힌다.
    """


class CatalogMissingError(ValueError):
    """없는 아이템을 고치거나 폐기하려 했다 — 404 다."""


def check_item(pool: ConnectionPool, payload: dict) -> ItemCatalogEntry:
    """아이템 등록이 성립하는지 본다. 아무것도 안 쓴다.

    Args:
        pool: 연결 풀.
        payload: 아이템 절.

    Returns:
        등록할 항목.

    Raises:
        ValueError: 절이 규격을 어긴 경우.
        CatalogConflictError: 이미 있는 id 인 경우.
    """
    entry = build_entry_from_request(payload)
    before = list_catalog(pool).get(entry.catalog_id)
    if before is not None:
        # **고치기는 `edit` 이 한다.** 있는 id 로 등록하려는 것은 십중팔구 "고치려던
        # 것" 이므로, 무엇이 다른지를 사유에 적어 돌려준다.
        locked = list_locked_changes(before, entry)
        detail = (
            "이미 있는 id 다 — 이름·최소 층은 고치기로,"
            " 나머지는 새 id 로 등록하고 옛 id 를 폐기한다"
        )
        raise CatalogConflictError(
            f"{detail} ({', '.join(locked)} 이(가) 다르다)" if locked else detail
        )
    return entry


def check_edit(pool: ConnectionPool, payload: dict) -> ItemCatalogEntry:
    """아이템 수정이 성립하는지 본다. 아무것도 안 쓴다.

    **안 보낸 것은 지금 것을 그대로 둔다.** 빈 접사 목록을 "접사를 지운다" 로 읽으면
    이름만 고치려던 요청이 아이템을 맹탕으로 만든다.

    Args:
        pool: 연결 풀.
        payload: 대상 id 와 고칠 값들.

    Returns:
        저장할 항목.

    Raises:
        ValueError: 정본에 없는 스탯에 접사를 붙인 경우.
        CatalogMissingError: 없는 아이템인 경우.
    """
    catalog_id = str(payload.get("catalog_id", ""))
    before = list_catalog(pool).get(catalog_id)
    if before is None:
        raise CatalogMissingError("없는 아이템이다")
    raw_affixes = payload.get("affixes") or []
    affixes = before.affixes if not raw_affixes else tuple(parse_affix(a) for a in raw_affixes)
    # 등록과 같은 문지기를 둔다. 여기만 비면 **실제로 쓰는 경로**가 검사를 안 받는다 —
    # 수치를 고치는 일은 등록보다 훨씬 자주 일어난다.
    unknown = list_unknown_stats(affixes)
    if unknown:
        raise ValueError(f"모르는 스탯이다: {', '.join(unknown)}")
    attack_range = payload.get("attack_range")
    use_tag = payload.get("use_tag")
    return replace(
        before,
        label_ko=str(payload.get("label_ko", before.label_ko)),
        min_floor=int(payload.get("min_floor", before.min_floor)),
        grade=str(payload.get("grade") or before.grade),
        affixes=affixes,
        attack_range=before.attack_range if attack_range is None else int(attack_range),
        use_tag=before.use_tag if use_tag is None else (str(use_tag) or None),
    )


def check_retire(pool: ConnectionPool, catalog_id: str) -> str:
    """폐기·복구가 성립하는지 본다. 아무것도 안 쓴다.

    Args:
        pool: 연결 풀.
        catalog_id: 대상 아이템.

    Returns:
        대상 id.

    Raises:
        CatalogMissingError: 없는 아이템인 경우.
    """
    if catalog_id not in list_catalog(pool):
        raise CatalogMissingError("없는 아이템이다")
    return catalog_id


def check_draft(pool: ConnectionPool, draft: CatalogDraft) -> None:
    """초안 하나가 지금 카탈로그에 대해 성립하는지 본다.

    Args:
        pool: 연결 풀.
        draft: 볼 초안.

    Raises:
        ValueError: 성립하지 않는 경우.
    """
    if draft.action == ACTION_ITEM:
        check_item(pool, draft.payload)
    elif draft.action == ACTION_EDIT:
        check_edit(pool, draft.payload)
    else:
        check_retire(pool, draft.catalog_id)


def apply_drop_seed(pool: ConnectionPool, catalog_id: str, grade: str) -> None:
    """새 아이템을 드롭 표에 올린다. 가중치는 1 로 시작한다.

    올리지 않으면 등록해도 **굴려서 나오지 않는다.** 등록과 드롭 표를 따로 두면 "왜 안
    나오지" 가 되고, 그 답은 화면 어디에도 없다.

    **등급마다 한 줄씩 올린다.** 카탈로그의 `grade` 는 「이 등급부터」라는 뜻이므로, 한
    칸에만 올리면 상위 등급을 뽑았을 때 후보가 없어 굴림이 증발한다 (§15.4).

    Args:
        pool: 연결 풀.
        catalog_id: 새 아이템.
        grade: 그 아이템의 최저 등급.
    """
    source_id = save_source(pool, SOURCE_ANY)
    with pool.connection() as connection:
        for code in list_grades_above(grade):
            connection.execute(
                "INSERT INTO drop_item_weight (source_id, grade, catalog_id, weight)"
                " VALUES (%s, %s, %s, 1) ON CONFLICT DO NOTHING",
                (source_id, code, catalog_id),
            )


def apply_draft(pool: ConnectionPool, draft: CatalogDraft) -> str:
    """초안 하나를 카탈로그에 반영한다.

    **세대를 여기서 안 올린다.** 발행 한 번이 경계 한 번이므로, 부르는 쪽이 전부 먹인 뒤
    한 번만 올린다 (§15.8).

    Args:
        pool: 연결 풀.
        draft: 반영할 초안.

    Returns:
        무슨 일이 있었는지 적은 한 줄. 원장에 실린다.

    Raises:
        ValueError: 지금 카탈로그에 대해 성립하지 않는 경우.
    """
    if draft.action == ACTION_ITEM:
        entry = check_item(pool, draft.payload)
        save_catalog_entry(pool, entry)
        apply_drop_seed(pool, entry.catalog_id, entry.grade)
        return f"등록 {entry.catalog_id}"
    if draft.action == ACTION_EDIT:
        entry = check_edit(pool, draft.payload)
        save_catalog_entry(pool, entry)
        return f"수정 {entry.catalog_id}"
    is_retired = draft.action == ACTION_RETIRE
    apply_retire(pool, check_retire(pool, draft.catalog_id), is_retired)
    return f"{'폐기' if is_retired else '복구'} {draft.catalog_id}"


__all__ = [
    "ACTION_RESTORE",
    "CatalogConflictError",
    "CatalogMissingError",
    "apply_draft",
    "apply_drop_seed",
    "check_draft",
    "check_edit",
    "check_item",
    "check_retire",
]
