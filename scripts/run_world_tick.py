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
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.app.monsters.growth import get_level_cap
from game.app.services.run_battle import load_balance
from game.app.services.run_duel import run_monster_duel
from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.monsters import (
    MonsterRecord,
    add_monster_xp,
    apply_monster_defeat,
    build_monster_snapshot,
    list_monsters,
)
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import BlockCatalog, load_block_catalog
from game.schemas.room import RoomTemplate, load_room_templates
from game.schemas.ruleset import RuleSet, load_rulesets, parse_ruleset

# 훑을 층 범위. 층 사슬이 붙으면 여기가 늘어난다.
MIN_FLOOR = 1
MAX_FLOOR = 5

# 몬스터끼리의 싸움이 주는 경험치. 플레이어를 잡는 것(60)보다 적다 — 서로 잡아 주는 것이
# 플레이어를 사냥하는 것보다 이득이면 세계가 플레이어를 무시하게 된다.
XP_PER_MONSTER = 25

# 한 판에 필요한 개체 수. 하나뿐이면 붙일 상대가 없다.
PAIR_SIZE = 2

# 결투장으로 쓸 방. 엄폐가 없어 규칙표의 차이가 지형에 가려지지 않는다.
ARENA_ROOM_ID = "open_field"

# 시드를 층·쌍마다 가르는 간격. 한 수열을 공유하면 앞 쌍의 전투 길이가 뒤 쌍을 흔든다.
FLOOR_STRIDE = 1000
PAIR_STRIDE = 100000


@dataclass(frozen=True)
class WorldParts:
    """결투에 필요한 자원 묶음. 층마다 다시 읽지 않으려고 한 번만 만든다."""

    balance: dict
    catalog: BlockCatalog
    rulesets: dict[str, RuleSet]
    arena: RoomTemplate


def build_world_parts() -> WorldParts:
    """결투에 필요한 자원을 읽는다.

    Returns:
        자원 묶음.

    Raises:
        KeyError: 결투장 방이 템플릿에 없는 경우. 설정이 잘못된 것이라 조용히 넘기지 않는다.
    """
    templates = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    return WorldParts(
        balance=load_balance(BALANCE_PATH),
        catalog=load_block_catalog(BLOCKS_PATH),
        rulesets=dict(load_rulesets(ENEMY_RULESETS_PATH)),
        arena=templates[ARENA_ROOM_ID],
    )


def build_duel_seed(base_seed: int, floor: int, left_id: int, right_id: int) -> int:
    """이 쌍의 결투 시드를 만든다.

    쌍마다 갈라 두는 이유는 R5 다. 한 수열을 층 전체가 공유하면 앞 쌍의 전투 길이가
    바뀔 때 뒤 쌍의 결과까지 흔들려, 개체 하나를 고쳤을 뿐인데 층 전체가 달라진다.

    Args:
        base_seed: 이번 세계 틱의 시드.
        floor: 층.
        left_id: 한쪽 record_id.
        right_id: 다른 쪽 record_id.

    Returns:
        이 쌍만의 시드.
    """
    return (base_seed * FLOOR_STRIDE + floor) * PAIR_STRIDE + left_id * PAIR_SIZE + right_id


def find_monster_ruleset(
    record: MonsterRecord, base: dict, rulesets: dict[str, RuleSet]
) -> RuleSet:
    """이 개체가 쓸 규칙표를 고른다.

    개체 전용 규칙표가 있으면 그것을 쓴다 (레벨별 규칙표 #36 의 자리). 없으면 카탈로그
    기본표다.

    Args:
        record: 몬스터 레코드.
        base: balance.json 의 그 적 절.
        rulesets: ruleset_id 에서 규칙표로의 대응표.

    Returns:
        쓸 규칙표.
    """
    if record.ruleset_json:
        return parse_ruleset(record.ruleset_json)
    return rulesets[base["ruleset_id"]]


def run_floor(pool: ConnectionPool, floor: int, world: WorldParts, base_seed: int) -> list[str]:
    """한 층의 몬스터끼리 한 번 붙인다.

    Args:
        pool: 연결 풀.
        floor: 대상 층.
        world: 결투에 필요한 자원 묶음.
        base_seed: 이번 세계 틱의 시드.

    Returns:
        무슨 일이 있었는지 적은 줄들.
    """
    records = list_monsters(pool, floor)
    if len(records) < PAIR_SIZE:
        return []
    notes: list[str] = []
    by_id = {kind["id"]: kind for kind in world.balance["enemies"]}
    # 정렬된 목록을 둘씩 짝짓는다. 순서가 실행마다 다르면 같은 시드가 다른 결과를 낸다.
    for index in range(0, len(records) - 1, PAIR_SIZE):
        left, right = records[index], records[index + 1]
        duel = run_monster_duel(
            build_monster_snapshot(left, by_id[left.catalog_id]),
            build_monster_snapshot(right, by_id[right.catalog_id]),
            (
                find_monster_ruleset(left, by_id[left.catalog_id], world.rulesets),
                find_monster_ruleset(right, by_id[right.catalog_id], world.rulesets),
            ),
            world.arena,
            world.balance,
            world.catalog,
            build_duel_seed(base_seed, floor, left.record_id, right.record_id),
        )
        winner = left if duel.winner_record_id == left.record_id else right
        loser = right if duel.winner_record_id == left.record_id else left
        level = add_monster_xp(pool, winner.record_id, floor, "MONSTER", None, XP_PER_MONSTER)
        dropped = apply_monster_defeat(pool, loser.record_id, floor)
        verdict = "시간 초과로" if duel.is_timeout else f"{duel.ticks}틱에"
        notes.append(
            f"층{floor} {winner.catalog_id}(→lv{level}/{get_level_cap(floor)})"
            f" 이 {loser.catalog_id}(→lv{dropped}) 를 {verdict} 눌렀다"
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
    world = build_world_parts()
    lines: list[str] = []
    for floor in range(MIN_FLOOR, MAX_FLOOR + 1):
        lines.extend(run_floor(pool, floor, world, seed))
    print("\n".join(lines) if lines else "붙일 몬스터가 없다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
