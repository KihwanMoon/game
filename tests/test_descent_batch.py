"""하강 배치 — 1층부터 보스까지 가 보는가를 잰다 (결정 #21).

**여기가 비어 있었다.** 배치는 고정 3방과 한 층만 쟀고, 실제 런인 30방·10층 하강은 한
번도 끝까지 돌려 본 적이 없었다 — 층·엘리트·보스·층별 보상·소모품 칸을 전부 붙여 놓고서다.

승률로는 안 보인다. 대부분 0% 이고, 그러면 **1층에서 죽은 것과 9층에서 죽은 것이 같은
0%** 로 적힌다. 재는 것은 어디까지 갔는가다.

여기서 지키는 것은 셋이다.

1. **같은 시드가 같은 하강을 만든다.** 최악 시드를 적어 놓고 재현 못 하면 그 숫자로
   고칠 곳을 못 찾는다 (P1).
2. **방 고르기가 전투 난수를 안 흔든다.** 한 축이 바뀔 때 다른 축이 따라 움직이면
   회귀 검증이 불가능하다 (R5).
3. **깬 층만 센다.** 층의 마지막 방에서 죽었으면 그 층은 안 깬 것이다 — 층 단위 보상이
   같은 셈을 쓰므로 여기서 다르게 세면 표가 거짓말을 한다.
"""

from game.app.services.run_battle import load_balance
from game.app.services.run_descent import build_descent_rooms, run_descent_batch
from game.config import BALANCE_PATH, BLOCKS_PATH, ENEMY_RULESETS_PATH, ROOM_TEMPLATES_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

ROOMS = {template.template_id: template for template in load_room_templates(ROOM_TEMPLATES_PATH)}
BOSS_FLOOR = 10
PER_FLOOR = 3


def build_chain(seed):
    """검사용 하강 하나.

    Args:
        seed: 시드.

    Returns:
        방 id 들.
    """
    return build_descent_rooms(ROOMS, seed, "open_field", PER_FLOOR, "boss_hall", BOSS_FLOOR)


def test_the_same_seed_builds_the_same_descent():
    """★ 재현이 안 되면 최악 시드를 적어 놔도 그 판을 다시 볼 수 없다 (P1)."""
    assert build_chain(7) == build_chain(7)


def test_a_different_seed_builds_a_different_descent():
    """★ 시드가 안 갈리면 배치가 같은 판을 N번 도는 것이 된다."""
    assert any(build_chain(seed) != build_chain(1) for seed in range(2, 12))


def test_the_descent_reaches_the_boss():
    """★ 보스 방이 끝에 안 오면 「10층에 보스」가 이 표에서 거짓이 된다."""
    chain = build_chain(3)
    assert len(chain) == PER_FLOOR * BOSS_FLOOR
    assert chain[-1] == "boss_hall"


def test_a_deep_room_never_opens_the_descent():
    """★ 층 게이팅이 배치에서만 새면, 표가 실제 런보다 어려운(또는 쉬운) 판을 잰다.

    `min_floor` 가 층 게이팅의 전부다. 배치가 그것을 안 지키면 「1층에서 멈춘다」는
    숫자가 1층 방 때문인지 섞여 든 9층 방 때문인지 알 수 없다.
    """
    for seed in range(1, 12):
        first_floor = build_chain(seed)[:PER_FLOOR]
        assert all(ROOMS[name].min_floor <= 1 for name in first_floor), first_floor


def run_probe(runs=2, ruleset=None):
    """하강을 조금 돌린다.

    Args:
        runs: 반복 횟수.
        ruleset: 플레이어 규칙표. None 이면 폴백.

    Returns:
        통계.
    """
    return run_descent_batch(
        "probe",
        ROOMS,
        load_balance(BALANCE_PATH),
        load_block_catalog(BLOCKS_PATH),
        ruleset,
        load_rulesets(ENEMY_RULESETS_PATH),
        runs,
        1,
        "open_field",
        PER_FLOOR,
        "boss_hall",
        BOSS_FLOOR,
    )


def test_the_floor_histogram_never_grows_downward():
    """★ 누적이라 깊은 층이 얕은 층보다 많이 깨질 수 없다 — 그러면 표가 거짓말이다."""
    counts = run_probe().cleared_by_floor
    assert len(counts) == BOSS_FLOOR
    assert all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1)), counts


def test_a_run_that_dies_mid_floor_does_not_clear_it():
    """★ **층의 마지막 방에서 죽었는데 그 층을 깬 것으로 세면, 보상이 나가는 셈과 어긋난다.**

    층 단위 보상은 `cleared_rooms // rooms_per_floor` 로 층을 판다 (`floor_service`).
    표가 올림으로 세면 실제로는 안 나간 보상을 나간 것처럼 그린다.

    **방을 조금 깨는 규칙표로 잰다.** 폴백은 0방에서 끝나 올림과 내림이 같은 답을 내고,
    그래서 이 검사가 한 번 헛돌았다.
    """
    from game.config import BENCHMARK_RULESETS_PATH

    partial = load_rulesets(BENCHMARK_RULESETS_PATH)["kite_summoner"]
    stats = run_probe(runs=3, ruleset=partial)
    # 실측: 시드 1~3 은 2~4방에서 끝난다. 4방이면 1층만 깬 것이다 — 2층으로 세면 틀렸다.
    assert stats.deepest_floor == 1, stats
    assert stats.finished == 0
