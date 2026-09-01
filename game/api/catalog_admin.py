"""카탈로그 편집 정책 (설계/4_아이템 §15.7).

**이미 나온 아이템이 소급해 바뀌는 것을 막는 것이 이 모듈의 전부다.**

예전에는 그 목록이 훨씬 길었다. 인스턴스의 접사가 비어 있으면 읽는 쪽이 카탈로그
기본값으로 메웠고, 그래서 접사를 고치면 남의 가방에 있는 아이템의 성능이 바뀌었다 —
접사·등급까지 전부 잠가야 했다.

**§15.11 이 그 고리를 끊었다.** 인스턴스가 발급 시점에 자기 접사를 갖고, 읽는 쪽이
카탈로그를 안 본다. 등급도 인스턴스가 복사해 간다(§15.5). 그래서 이제 접사·등급·요구조건·
태그를 제자리에서 고칠 수 있고, 그 변경은 **앞으로 나올 것에만** 걸린다.

남은 잠금은 셋뿐이고 이유가 다르다 — `kind`·`slot`·`hands` 는 **이미 착용된 자리**를
가리킨다. 투구를 갑옷으로 바꾸면 누군가의 머리 칸에 갑옷이 들어 있게 되고, 그 상태를
어느 화면도 설명하지 못한다.
"""

from dataclasses import replace

from game.schemas.item import ItemCatalogEntry, parse_item

# 제자리에서 고칠 수 있는 것. 인스턴스가 자기 접사·등급을 갖게 된 뒤로(§15.11) 목록이
# 늘었다 — 이 값들은 앞으로 나올 것에만 걸린다.
MUTABLE_FIELDS = (
    "label_ko",
    "min_floor",
    "affixes",
    "grade",
    "requirements",
    "tags",
    "grants_skill",
    "stack_max",
    "is_retired",
)


def list_locked_changes(before: ItemCatalogEntry, after: ItemCatalogEntry) -> tuple[str, ...]:
    """제자리에서 고칠 수 없는 것이 바뀌었는지 본다.

    Args:
        before: 지금 카탈로그의 항목.
        after: 고치려는 항목.

    Returns:
        바뀐 잠긴 필드들. 없으면 빈 튜플.
    """
    frozen = replace(before, **{name: getattr(after, name) for name in MUTABLE_FIELDS})
    if frozen == after:
        return ()
    changed = [
        name
        for name in vars(before)
        if name not in MUTABLE_FIELDS and getattr(before, name) != getattr(after, name)
    ]
    return tuple(sorted(changed))


def build_entry_from_request(payload: dict) -> ItemCatalogEntry:
    """관리자가 보낸 절을 카탈로그 항목으로 만든다.

    파일 파서를 그대로 쓴다 — 파서가 둘이면 규칙이 둘이 되고, 관리자가 만든 아이템만
    다른 규칙으로 검사되는 날이 온다.

    Args:
        payload: 아이템 절.

    Returns:
        카탈로그 항목.

    Raises:
        ValueError: 장비인데 슬롯이 없는 등 절이 규격을 어긴 경우.
    """
    return parse_item(payload)
