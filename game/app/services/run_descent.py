"""하강 배치 — 1층부터 보스까지 실제로 가 보는가를 잰다 (로드맵 W14, 결정 #21).

**여기가 비어 있었다.** `run_batch` 는 고정 3방을, `run_floor_batch` 는 한 층을 잰다.
그런데 실제 런은 **30방·10층 하강**이고, 그것을 끝까지 돌려 본 적이 한 번도 없었다 —
층·엘리트·보스·층별 보상·소모품 칸을 전부 붙여 놓고 재지 않은 채였다.

승률은 여기서 쓸모가 없다. 대부분의 규칙표가 0% 로 나올 것이고, 그러면 **1층에서 죽는
것과 9층에서 죽는 것이 같은 0%** 로 적힌다. 재야 하는 것은 **어디까지 갔는가**다.

방 목록은 시드에서 판다. 서버는 `secrets` 로 고르지만(시드를 아는 클라이언트가 방을
미리 알면 안 된다), 배치는 **최악 시드를 재현할 수 있어야** 그 숫자로 고칠 곳을 찾는다.
"""

from dataclasses import dataclass

from game.app.core.rng import DeterministicRng
from game.app.services.build_chain import build_descent
from game.app.services.run_chain import run_room_chain
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.schemas.blocks import BlockCatalog
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet

PERCENT = 100


@dataclass(frozen=True)
class DescentStats:
    """하강 한 묶음의 통계."""

    ruleset_id: str
    runs: int
    # 도달한 층의 평균. **100 을 곱해 소수 둘째 자리를 정수로 나른다** — 부동소수를
    # 코어 밖에서도 안 쓴다 (R5 와 같은 규율).
    average_floor_pct: int
    deepest_floor: int
    # 층마다 그 층을 **깬** 런 수. 누적이라 앞 칸이 뒤 칸보다 작을 수 없다.
    cleared_by_floor: tuple[int, ...]
    # 보스까지 깬 런 수.
    finished: int
    # 가장 얕게 끝난 런의 시드. 재현해서 어느 규칙이 왜 멈췄는지 본다 (P1).
    worst_seed: int
    worst_floor: int


def build_descent_rooms(
    rooms: dict[str, RoomTemplate],
    seed: int,
    first_room_id: str,
    rooms_per_floor: int,
    boss_room_id: str,
    boss_floor: int,
) -> tuple[str, ...]:
    """시드에서 하강 방 목록을 판다.

    **시드에서 파생하므로 재현된다.** 서버의 `secrets` 와 다른 목록이 나오지만, 재는
    것은 「이 방 조합에서 어디까지 가는가」이지 특정 목록이 아니다.

    Args:
        rooms: 방 id 에서 템플릿으로.
        seed: 이 런의 시드.
        first_room_id: 첫 층의 첫 방.
        rooms_per_floor: 층 하나에 드는 방 수.
        boss_room_id: 보스 방.
        boss_floor: 보스가 서는 층.

    Returns:
        방 id 들.
    """
    # 방 고르기를 **전투와 다른 축**에 둔다. 한 수열을 공유하면 방 하나가 바뀔 때
    # 전투의 난수까지 흔들려 무엇 때문에 결과가 달라졌는지 알 수 없다 (R5).
    stream = DeterministicRng(seed).create_stream("descent_rooms")
    return build_descent(
        rooms,
        1,
        first_room_id,
        rooms_per_floor,
        boss_room_id,
        boss_floor,
        pick=stream.get_below,
    )


def run_descent_batch(
    ruleset_id: str,
    rooms: dict[str, RoomTemplate],
    balance: dict,
    catalog: BlockCatalog,
    player_ruleset: RuleSet | None,
    enemy_rulesets: dict[str, RuleSet],
    runs: int,
    base_seed: int,
    first_room_id: str,
    rooms_per_floor: int,
    boss_room_id: str,
    boss_floor: int,
) -> DescentStats:
    """같은 규칙표로 하강을 여러 번 돌려 도달 층 분포를 낸다.

    Args:
        ruleset_id: 통계에 붙일 이름.
        rooms: 방 id 에서 템플릿으로.
        balance: 밸런스 딕셔너리.
        catalog: 동결된 블록 카탈로그.
        player_ruleset: 플레이어 규칙표. None 이면 폴백.
        enemy_rulesets: 적 규칙표들.
        runs: 반복 횟수.
        base_seed: 시작 시드. 런마다 1씩 늘린다.
        first_room_id: 첫 층의 첫 방.
        rooms_per_floor: 층 하나에 드는 방 수.
        boss_room_id: 보스 방.
        boss_floor: 보스가 서는 층.

    Returns:
        도달 층 분포. 승률 대신 **어디까지 갔는가**를 담는다.
    """
    cleared_by_floor = [0] * boss_floor
    total_floors = 0
    finished = 0
    worst_seed = base_seed
    worst_floor = boss_floor + 1
    for index in range(runs):
        seed = base_seed + index
        chain = build_descent_rooms(
            rooms, seed, first_room_id, rooms_per_floor, boss_room_id, boss_floor
        )
        result = run_room_chain(
            tuple(rooms[name] for name in chain),
            balance,
            catalog,
            player_ruleset,
            enemy_rulesets,
            seed,
            floor=1,
            rooms_per_floor=rooms_per_floor,
        )
        # **깬 층만 센다.** 층의 마지막 방에서 죽었으면 그 층은 안 깬 것이다 —
        # 층 단위 보상이 같은 셈을 쓰므로 여기서 다르게 세면 표가 거짓말을 한다.
        depth = min(boss_floor, result.cleared_rooms // rooms_per_floor)
        total_floors += depth
        for floor in range(depth):
            cleared_by_floor[floor] += 1
        if result.outcome == OUTCOME_PLAYER_WIN and depth >= boss_floor:
            finished += 1
        if depth < worst_floor:
            worst_floor = depth
            worst_seed = seed
    return DescentStats(
        ruleset_id=ruleset_id,
        runs=runs,
        average_floor_pct=total_floors * PERCENT // runs if runs else 0,
        deepest_floor=max(
            [floor + 1 for floor, count in enumerate(cleared_by_floor) if count > 0] or [0]
        ),
        cleared_by_floor=tuple(cleared_by_floor),
        finished=finished,
        worst_seed=worst_seed,
        worst_floor=worst_floor if runs else 0,
    )
