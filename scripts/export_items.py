"""아이템 카탈로그를 DB 에서 파일로 내보낸다 (설계/4_아이템 §15.7).

**정본은 DB 이고 이 파일은 파생물이다.** 그런데도 파일을 두는 이유가 있다 — 헤드리스
러너와 골든 테스트가 DB 없이 돌아야 하기 때문이다. 골든 재현이 DB 상태에 묶이면 어제의
리플레이가 오늘 DB 를 고쳤다는 이유로 깨진다.

`item_list_version` 에는 **DB 의 카탈로그 세대**가 들어간다. 그 값이 코어 버전의 `i` 축이다.

    uv run python -m scripts.export_items
"""

import json

from game.app.store.connection import create_pool
from game.app.store.item_catalog import list_catalog, read_generation
from game.config import ITEMS_PATH
from game.schemas.item import build_item_payload

COMMENT = (
    "아이템 카탈로그 스냅샷. **손으로 고치지 않는다** — 정본은 DB 의 item_catalog 이고"
    " 이 파일은 scripts/export_items.py 가 내보낸 파생물이다 (설계/4_아이템 §15.7)."
    " 헤드리스 러너와 골든이 DB 없이 돌기 위한 사본이며, item_list_version 은 DB 의"
    " 카탈로그 세대다."
)


def export_items() -> int:
    """DB 의 카탈로그를 items.json 으로 쓴다.

    Returns:
        쓴 항목 수.

    Raises:
        RuntimeError: 카탈로그가 비어 있는 경우. **빈 파일을 쓰지 않는다** — 이 파일은
            빈 DB 를 채우는 씨앗이기도 해서, 한 번 비우면 되살릴 곳이 없어진다.
            실제로 시딩 전 DB 에 대고 돌려 파일을 0개로 덮은 적이 있다.
    """
    pool = create_pool()
    try:
        catalog = list_catalog(pool)
        generation = read_generation(pool)
    finally:
        pool.close()
    if not catalog:
        raise RuntimeError("카탈로그가 비어 있다 — 시딩을 먼저 돌린다 (apply_catalog_seed)")
    payload = {
        "_comment": COMMENT,
        "item_list_version": generation,
        "items": [build_item_payload(catalog[key]) for key in sorted(catalog)],
    }
    ITEMS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return len(catalog)


def main() -> None:
    """스크립트 진입점."""
    print(f"wrote {ITEMS_PATH} ({export_items()} items)")


if __name__ == "__main__":
    main()
