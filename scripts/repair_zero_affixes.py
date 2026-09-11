"""굴림이 지워 버린 접사를 되살린다 (2026-09-11, 실제 신고).

「소모품 칸을 늘려 주는 장비가 이름만 있고 옵션이 적용되지 않는다」가 신고였고, 원인은
`loot.convert_affix_roll` 이 값에 80~120% 를 곱하고 내림한 것이다 — 값이 1 인 접사는
굴림 폭의 절반(80~99)에서 **0 이 됐다.** 이름은 남고 효과만 사라진다.

굴림은 고쳤지만(`resolve_rolled_value`) **이미 발급된 인스턴스는 그대로다.** 여기서
그것들을 되살린다.

**되살리는 값은 1 이다.** 카탈로그 값이 아니라, 고친 굴림이 **최악의 굴림에서 내놓았을
값**이다 — 나쁘게 굴린 아이템을 좋게 만들어 주는 것이 아니라 사라진 것만 되돌린다.

**0 → 0 인 접사는 안 건드린다.** 카탈로그가 애초에 0 으로 적어 둔 항목까지 1 로 만들면
없던 옵션이 생긴다.

    GAME_DATABASE_URL=... uv run python -m scripts.repair_zero_affixes           # 미리보기
    GAME_DATABASE_URL=... uv run python -m scripts.repair_zero_affixes --apply
"""

import argparse
import os
import sys

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool

# 되살릴 최소 크기. 고친 굴림이 보장하는 값과 같아야 한다 — 다르면 스크립트가 굴림보다
# 후하거나 박해지고, 그 차이를 나중에 설명할 수 없다.
MIN_VALUE = 1


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="굴림이 지운 접사를 되살린다")
    parser.add_argument("--apply", action="store_true", help="실제로 쓴다. 없으면 미리보기")
    return parser.parse_args(argv)


def list_catalog_bases(pool: ConnectionPool) -> dict[tuple[str, str], tuple[int, int]]:
    """카탈로그가 적어 둔 접사의 기준값.

    Args:
        pool: 연결 풀.

    Returns:
        (catalog_id, 접사 이름) 에서 (flat, percent) 로.
    """
    with pool.connection() as connection:
        rows = connection.execute("SELECT catalog_id, affixes FROM item_catalog").fetchall()
    bases: dict[tuple[str, str], tuple[int, int]] = {}
    for catalog_id, affixes in rows:
        for affix in affixes or []:
            key = (str(catalog_id), str(affix.get("label_ko", "")))
            bases[key] = (int(affix.get("flat", 0)), int(affix.get("percent", 0)))
    return bases


def build_repaired_affixes(
    catalog_id: str, affixes: list, bases: dict[tuple[str, str], tuple[int, int]]
) -> tuple[list, tuple[str, ...]]:
    """인스턴스 하나의 접사 목록을 고친다.

    Args:
        catalog_id: 이 인스턴스의 카탈로그 id.
        affixes: 저장된 접사 절들.
        bases: 카탈로그 기준값 표.

    Returns:
        (고친 절들, 고친 접사 이름들). 고칠 것이 없으면 이름이 빈 튜플이다.
    """
    fixed: list = []
    touched: list[str] = []
    for affix in affixes:
        label = str(affix.get("label_ko", ""))
        flat = int(affix.get("flat", 0))
        percent = int(affix.get("percent", 0))
        base_flat, base_percent = bases.get((catalog_id, label), (0, 0))
        if flat == 0 and percent == 0 and (base_flat > 0 or base_percent > 0):
            # 기준이 어느 쪽에 적혀 있었는지를 그대로 따른다 — 평값을 백분율로 되살리면
            # 같은 이름이 아이템마다 다른 축을 만진다.
            key = "flat" if base_flat > 0 else "percent"
            fixed.append({**affix, key: MIN_VALUE})
            touched.append(label)
            continue
        fixed.append(affix)
    return fixed, tuple(touched)


def apply_repair(pool: ConnectionPool, *, is_dry_run: bool) -> int:
    """지워진 접사를 전부 되살린다.

    Args:
        pool: 연결 풀.
        is_dry_run: True 면 읽기만 하고 무엇을 고칠지 적는다.

    Returns:
        고친(또는 고칠) 인스턴스 수.
    """
    bases = list_catalog_bases(pool)
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, catalog_id, affixes FROM item_instance ORDER BY id"
        ).fetchall()
    changed = 0
    for instance_id, catalog_id, affixes in rows:
        fixed, touched = build_repaired_affixes(str(catalog_id), list(affixes or []), bases)
        if not touched:
            continue
        changed += 1
        print(f"  #{instance_id} {catalog_id} — {', '.join(touched)}")
        if is_dry_run:
            continue
        with pool.connection() as connection:
            connection.execute(
                "UPDATE item_instance SET affixes = %s WHERE id = %s",
                (Jsonb(fixed), instance_id),
            )
    return changed


def main(argv: list[str]) -> int:
    """스크립트 진입점.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        종료 코드. 0 이면 성공.
    """
    arguments = parse_arguments(argv)
    url = os.environ.get(DATABASE_URL_ENV, "")
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    pool = create_pool(url)
    try:
        changed = apply_repair(pool, is_dry_run=not arguments.apply)
    finally:
        pool.close()
    if not changed:
        print("지워진 접사가 없다")
        return 0
    verb = "고칠 수 있다 (--apply 로 쓴다)" if not arguments.apply else "고쳤다"
    print(f"인스턴스 {changed}개를 {verb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
