"""1층의 옛 정예를 일반으로 내린다 (운영, 1회성).

**설계와 어긋난 옛 기록이다.** 지금 `create_monster` 는 층 몬스터를 `NORMAL` 로 심고,
정예는 e4 배치 흔들기의 승격(1층 4%)으로 나온다. 그런데 1층에 `ELITE` 네 마리가 남아
있었다 — 승격 기제가 생기기 전 시드가 심은 것이고, 등급 배수 1.5배가 **첫 방에 상시로**
걸려 있었다.

측정이 이것을 잡았다: 규칙표 17개 × 시드 8 = 136판에서 1층 돌파가 0건이었다. 신규
계정의 기본 로드아웃(HP 100 · 공 12 · 방 5)으로는 첫 방을 넘지 못한다.

**지우지 않고 내린다.** 개체를 지우면 그 개체를 만난 기록(도감·처치)이 가리키는 곳이
사라진다. 등급만 내리면 같은 개체가 그대로 살아 있고 스탯만 설계대로 돌아온다.

    GAME_DATABASE_URL=... uv run python -m scripts.demote_floor_one_elites

되돌리려면 같은 자리에 `tier = 'ELITE'` 를 다시 넣으면 된다 — 무엇을 바꿨는지 아래가
출력한다.
"""

import os
import sys

from game.app.monsters.tiers import MonsterTier
from game.app.store.connection import DATABASE_URL_ENV, create_pool

# 손대는 층. 1층만이다 — 깊은 층의 정예는 설계대로 그 자리에 있어야 한다.
TARGET_FLOOR = 1


def main() -> int:
    """1층 정예를 일반으로 내린다.

    Returns:
        종료 코드. 데이터베이스 주소가 없으면 1.
    """
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    pool = create_pool(url)
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT id, entity_slot, catalog_id, level FROM entity_record"
            " WHERE kind = 'MONSTER' AND zone_floor = %s AND tier = %s"
            " ORDER BY id",
            (TARGET_FLOOR, MonsterTier.ELITE),
        ).fetchall()
        if not rows:
            print(f"[강등] {TARGET_FLOOR}층에 정예가 없다 — 할 일이 없다")
            return 0
        for row in rows:
            print(f"[강등] #{row[0]} {row[1]} ({row[2]}, 레벨 {row[3]}) ELITE → NORMAL")
        connection.execute(
            "UPDATE entity_record SET tier = %s, updated_at = now()"
            " WHERE kind = 'MONSTER' AND zone_floor = %s AND tier = %s",
            (MonsterTier.NORMAL, TARGET_FLOOR, MonsterTier.ELITE),
        )
    print(f"[강등] {len(rows)}마리를 내렸다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
