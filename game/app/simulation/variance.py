"""판마다 달라지는 것 — 배치 흔들기와 정예 승격 (GDD §11 전략 공간).

**같은 방이 늘 같은 판이었다.** 방 배치가 템플릿에 고정이라, 같은 방·같은 시드면 적이
늘 같은 칸에 같은 종으로 섰다 — 규칙표를 한 번 맞추면 그 방은 영원히 풀린 문제가 된다.

여기서 두 가지를 흔든다.

* **배치**: 적이 제 자리 둘레의 걸을 수 있는 칸으로 옮겨 설 수 있다. 방의 뜻(통로·엄폐)은
  유지되고 거리만 갈린다.
* **정예 승격**: 일반 적이 같은 유형의 정예로 바뀔 수 있다. 확률은 층에 비례한다 —
  깊이 내려갈수록 「이번엔 뭐가 나올까」가 커진다.

**전부 시드에서 나온다** (R5). `create_stream("variance")` 로 축을 갈라, 흔들기 호출
횟수가 바뀌어도 전투 난수가 안 흔들린다. 두 코어가 같은 순서로 같은 수를 뽑아야 하므로
순회 순서를 절대 바꾸지 않는다 (G3).
"""

from game.app.core.rng import DeterministicRng
from game.schemas.room import WALKABLE_TILES, RoomTemplate

# 배치를 흔들 때 볼 이웃 칸. **순서가 계약이다** — 두 코어가 같은 순서로 봐야 같은 칸을
# 고른다. 제자리를 맨 앞에 두어 「안 움직임」도 후보에 넣는다.
JITTER_OFFSETS: tuple[tuple[int, int], ...] = (
    (0, 0),
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
)

# 층 1 의 정예 승격 확률(퍼센트)과 층마다 더할 몫. 10층이면 4 + 3*9 = 31% 다 —
# 깊은 층에서도 절반을 넘지 않아야 「정예를 만났다」가 사건으로 남는다.
ELITE_BASE_PCT = 4
ELITE_PCT_PER_FLOOR = 3
PERCENT_BASE = 100

# 일반 종에서 같은 유형의 정예로. **닫힌 표다** — 데이터에서 유추하면 종을 더할 때마다
# 엉뚱한 짝이 생기고, 그것이 조용히 밸런스를 바꾼다.
ELITE_BY_KIND: dict[str, str] = {
    "goblin_rusher": "veteran_rusher",
    "goblin_archer": "longbow_archer",
    "goblin_summoner": "arch_summoner",
    "mender_acolyte": "plague_mender",
    "dire_wolf": "veteran_rusher",
}


def resolve_elite_pct(floor: int) -> int:
    """이 층의 정예 승격 확률.

    Args:
        floor: 현재 층. 1 이 첫 층이다.

    Returns:
        퍼센트. 절반을 넘지 않는다 — 정예가 기본이 되면 사건이 아니게 된다.
    """
    return min(50, ELITE_BASE_PCT + ELITE_PCT_PER_FLOOR * max(0, floor - 1))


def resolve_elite_kind(kind_id: str, floor: int, rng: DeterministicRng) -> str:
    """이 적을 정예로 올릴지 정한다.

    **정수 비교다** (R5). 부동소수를 쓰면 두 코어가 경계에서 갈린다.

    Args:
        kind_id: 원래 종.
        floor: 현재 층.
        rng: 변수 축 난수원.

    Returns:
        바뀐 종. 짝이 없거나 굴림에서 떨어지면 원래 종 그대로다.

    """
    elite = ELITE_BY_KIND.get(kind_id)
    if elite is None:
        return kind_id
    return elite if rng.get_below(PERCENT_BASE) < resolve_elite_pct(floor) else kind_id


def resolve_spawn_spot(
    template: RoomTemplate,
    spot: tuple[int, int],
    taken: set[tuple[int, int]],
    rng: DeterministicRng,
) -> tuple[int, int]:
    """적이 설 칸을 제 자리 둘레에서 고른다.

    **한 칸만 흔든다.** 멀리 옮기면 방이 설계한 통로·엄폐의 뜻이 사라진다 — 흔드는 것은
    거리와 각도이지 방의 구조가 아니다.

    Args:
        template: 방 템플릿.
        spot: 템플릿이 정한 자리.
        taken: 이미 누가 선 칸들.
        rng: 변수 축 난수원.

    Returns:
        설 칸. 후보가 없으면 제 자리 그대로다.
    """
    options = [
        (spot[0] + dx, spot[1] + dy)
        for dx, dy in JITTER_OFFSETS
        if (spot[0] + dx, spot[1] + dy) not in taken
        and template.get_tile(spot[0] + dx, spot[1] + dy) in WALKABLE_TILES
    ]
    if not options:
        return spot
    return options[rng.get_below(len(options))]
