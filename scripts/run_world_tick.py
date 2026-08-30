"""세계 한 틱 — 몬스터끼리의 전투를 서버가 돌린다 (결정 #38, docs/설계/6_몬스터 §6).

**플레이어가 없어도 세계가 움직인다.** 다시 들어갔을 때 지형이 바뀌어 있는 것이 지속
세계의 핵심이고, 그것이 없으면 몬스터는 플레이어를 기다리는 장식이 된다.

라우트가 아니라 스크립트인 이유는 이것이 **운영이 부르는 것**이기 때문이다. 엔드포인트로
두면 누구나 세계를 앞으로 밀 수 있고, 그러면 자기 몬스터를 키우려고 반복 호출하는 것이
최적이 된다.

    GAME_DATABASE_URL=... uv run python -m scripts.run_world_tick

같은 층의 지속 몬스터 둘을 붙인다. 이긴 쪽이 경험치를 얻고 진 쪽이 감쇠한다 — 처치와
같은 규칙이라 폭주 방지(결정 #35)가 그대로 적용된다.
"""

import os
import sys

from psycopg_pool import ConnectionPool

from game.app.core.rng import DeterministicRng
from game.app.monsters.growth import get_level_cap
from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.monsters import (
    MonsterRecord,
    add_monster_xp,
    apply_monster_defeat,
    list_monsters,
)

# 훑을 층 범위. 층 사슬이 붙으면 여기가 늘어난다.
MIN_FLOOR = 1
MAX_FLOOR = 5

# 몬스터끼리의 싸움이 주는 경험치. 플레이어를 잡는 것(60)보다 적다 — 서로 잡아 주는 것이
# 플레이어를 사냥하는 것보다 이득이면 세계가 플레이어를 무시하게 된다.
XP_PER_MONSTER = 25

# 한 판에 필요한 개체 수. 하나뿐이면 붙일 상대가 없다.
PAIR_SIZE = 2


def check_winner(left: MonsterRecord, right: MonsterRecord, rng: DeterministicRng) -> int:
    """둘 중 누가 이기는지 정한다.

    전면 시뮬레이션을 돌리지 않는다. 규칙표 대 규칙표를 제대로 돌리려면 방과 배치가
    필요한데, 몬스터끼리는 그것이 정의돼 있지 않다 — **지금은 레벨 차이에 확률을 얹은
    판정이고, 그 사실을 숨기지 않는다.** 방이 정의되면 여기를 전투로 바꾼다.

    확률은 정수 비교다 (R5).

    Args:
        left: 한쪽.
        right: 다른 쪽.
        rng: 난수원.

    Returns:
        이긴 쪽의 record_id.
    """
    # 레벨이 높을수록 유리하되 확정은 아니다. 확정이면 상위 개체가 영원히 이겨
    # 하위가 존재할 이유가 사라진다.
    total = max(1, left.level + right.level)
    return left.record_id if rng.get_below(total) < left.level else right.record_id


def run_floor(pool: ConnectionPool, floor: int, rng: DeterministicRng) -> list[str]:
    """한 층의 몬스터끼리 한 번 붙인다.

    Args:
        pool: 연결 풀.
        floor: 대상 층.
        rng: 난수원.

    Returns:
        무슨 일이 있었는지 적은 줄들.
    """
    records = list_monsters(pool, floor)
    if len(records) < PAIR_SIZE:
        return []
    notes: list[str] = []
    # 정렬된 목록을 둘씩 짝짓는다. 순서가 실행마다 다르면 같은 시드가 다른 결과를 낸다.
    for index in range(0, len(records) - 1, PAIR_SIZE):
        left, right = records[index], records[index + 1]
        winner_id = check_winner(left, right, rng)
        loser = right if winner_id == left.record_id else left
        winner = left if winner_id == left.record_id else right
        level = add_monster_xp(pool, winner.record_id, floor, "MONSTER", None, XP_PER_MONSTER)
        dropped = apply_monster_defeat(pool, loser.record_id, floor)
        notes.append(
            f"층{floor} {winner.catalog_id}(→lv{level}/{get_level_cap(floor)})"
            f" 이 {loser.catalog_id}(→lv{dropped}) 를 눌렀다"
        )
    return notes


def main() -> int:
    """스크립트 진입점.

    Returns:
        종료 코드. 연결이 없으면 1.
    """
    if not os.environ.get(DATABASE_URL_ENV, "").strip():
        print(f"{DATABASE_URL_ENV} 가 없다")
        return 1
    pool = create_pool()
    # 시드를 인자로 받는다. 같은 시드로 다시 돌리면 같은 결과가 나와야 조사에 쓸 수 있다.
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rng = DeterministicRng(seed)
    lines: list[str] = []
    for floor in range(MIN_FLOOR, MAX_FLOOR + 1):
        lines.extend(run_floor(pool, floor, rng))
    print("\n".join(lines) if lines else "붙일 몬스터가 없다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
