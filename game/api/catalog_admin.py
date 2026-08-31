"""카탈로그 편집 정책 (설계/4_아이템 §15.7).

**수정과 신설을 가른다.** 이미 나온 아이템이 소급해 바뀌는 것을 막는 것이 이 모듈의
전부다.

인스턴스가 굴린 접사가 없으면 카탈로그 기본값을 쓴다. 그래서 접사를 고치면 **남의
가방에 있는 아이템의 성능이 바뀐다.** 등급·분류·슬롯도 같다. 그런 수정은 "새 id 등록 +
옛 id 폐기" 로만 해야 하며, 그 규율을 사람의 기억이 아니라 여기서 지킨다.

바꿔도 되는 것은 **이미 나온 것에 소급하지 않는 것**뿐이다 — 이름과 최소 층. 이름은
표시이고, 최소 층은 앞으로의 굴림에만 걸린다.
"""

from dataclasses import replace

from game.schemas.item import ItemCatalogEntry, parse_item

# 이미 나온 아이템에 소급하지 않는 필드. 이것만 제자리에서 고칠 수 있다.
MUTABLE_FIELDS = ("label_ko", "min_floor")


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
