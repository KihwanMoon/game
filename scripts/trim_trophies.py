"""쌓인 전리품을 상한까지 줄인다 (결정 #34, 2026-09-06 개정).

**코드만 고치면 옛 것이 그대로 남는다.** 상한이 없던 동안 패배마다 사본이 하나씩 들어왔고,
봇이 쉼 없이 죽으므로 1층 고블린 하나가 696개를 들고 있었다 — 새 규칙은 앞으로 들어오는
것만 막는다.

**가장 강한 다섯을 남긴다.** 새 규칙이 수렴하는 자리와 같은 곳으로 옮겨 놓는 것이다 —
오래된 것부터 자르면 규칙이 바뀐 날 이전과 이후가 다른 세계가 된다.

    GAME_DATABASE_URL=... uv run python -m scripts.trim_trophies --dry-run
    GAME_DATABASE_URL=... uv run python -m scripts.trim_trophies
"""

import argparse
import os
import sys

from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.trophies import MAX_TROPHIES, compute_affix_score


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="쌓인 전리품을 상한까지 줄인다")
    parser.add_argument("--dry-run", action="store_true", help="세기만 하고 안 지운다")
    return parser.parse_args(argv)


def main() -> int:
    """스크립트 진입점.

    Returns:
        종료 코드. 연결이 없으면 1.
    """
    arguments = parse_arguments(sys.argv[1:])
    if not os.environ.get(DATABASE_URL_ENV, "").strip():
        print(f"{DATABASE_URL_ENV} 가 없다")
        return 1
    pool = create_pool()
    with pool.connection() as connection:
        crowded = connection.execute(
            "SELECT owner_entity_id, count(*) FROM item_instance i"
            " JOIN entity_record e ON e.id = i.owner_entity_id AND e.kind = 'MONSTER'"
            " GROUP BY 1 HAVING count(*) > %s ORDER BY 2 DESC",
            (MAX_TROPHIES,),
        ).fetchall()
        if not crowded:
            print(f"상한({MAX_TROPHIES})을 넘는 개체가 없다")
            return 0
        total = 0
        for record_id, held in crowded:
            rows = connection.execute(
                "SELECT id, affixes FROM item_instance WHERE owner_entity_id = %s",
                (record_id,),
            ).fetchall()
            # 강한 순으로 세우고 앞의 다섯만 남긴다. 같은 값이면 최근 것(큰 id)이 이긴다.
            ranked = sorted(
                rows, key=lambda row: (compute_affix_score(row[1]), row[0]), reverse=True
            )
            doomed = [row[0] for row in ranked[MAX_TROPHIES:]]
            print(f"  개체 {record_id}: {held}개 → {MAX_TROPHIES}개 ({len(doomed)}개 정리)")
            total += len(doomed)
            if not arguments.dry_run:
                connection.execute("DELETE FROM item_instance WHERE id = ANY(%s)", (doomed,))
        head = "정리했을 것" if arguments.dry_run else "정리했다"
        print(f"{head}: 개체 {len(crowded)}마리 · 아이템 {total}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
