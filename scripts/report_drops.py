"""드롭 곡선을 잰다 — 숫자를 정하기 전에 숫자를 본다.

**밸런스 목표(결정 #21)가 아직 미결이다.** 그래서 이 스크립트는 값을 정하지 않고, 지금
표가 만들어 내는 곡선을 보여 준다. 고를 근거가 없는 채로 숫자를 바꾸면 그것은 밸런스가
아니라 취향이다.

재는 것은 넷이다.

    굴림당 드롭률      한 번 잡을 때 무언가 나올 확률
    런당 기대 개수     처치 수를 곱한 값. **이것이 사람이 느끼는 값이다**
    등급 분포          보통·상급·유물이 각각 얼마나
    첫 유물까지 런 수  "언젠가 나온다" 가 몇 판인지

한 런의 처치 수는 방 배치의 적 수가 아니다 — 소환사가 계속 부르므로 실측이 필요하고,
`item_roll_log` 가 그 값을 안다.

    docker compose run --rm ops uv run python -m scripts.report_drops
"""

import argparse
from collections import Counter

from psycopg_pool import ConnectionPool

from game.app.items.drops import GRADE_MISS, build_grade_pool, get_weighted
from game.app.store.connection import create_pool
from game.app.store.drops import DEFAULT_GRADE_WEIGHTS, SOURCE_ANY, find_source, read_grade_weights

# 표본 수. 유물이 만분의 5 라 작은 표본으로는 그 칸이 통째로 비어 보인다.
SAMPLES = 200_000

# 실측이 없을 때 쓸 처치 수. 프로덕션 로그에서 잰 값이다 (2026-08-31, corridor 1층).
FALLBACK_KILLS = 16

PERCENT_BASE = 100


def read_kills_per_run(pool: ConnectionPool) -> float:
    """원장에서 런당 처치 수를 잰다.

    Args:
        pool: 연결 풀.

    Returns:
        평균 처치 수. 기록이 없으면 실측 기본값.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT avg(count) FROM ("
            " SELECT count(*) AS count FROM item_roll_log"
            " WHERE submission_id IS NOT NULL GROUP BY submission_id) AS runs"
        ).fetchone()
    return FALLBACK_KILLS if row is None or row[0] is None else float(row[0])


def build_weights(pool: ConnectionPool) -> tuple[tuple[tuple[str, int, int], ...], int]:
    """지금 쓰이는 등급 가중치를 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        (등급 가중치들, 안 나옴 몫).
    """
    source_id = find_source(pool, SOURCE_ANY)
    rows = read_grade_weights(pool, source_id) if source_id is not None else ()
    if not rows:
        rows = tuple((g, w, s) for g, w, s in DEFAULT_GRADE_WEIGHTS if g != GRADE_MISS)
    miss = next(w for g, w, _s in DEFAULT_GRADE_WEIGHTS if g == GRADE_MISS)
    return rows, miss


def count_grades(weights: tuple, miss: int, level: int) -> Counter:
    """표본을 돌려 등급 분포를 센다.

    Args:
        weights: 등급 가중치들.
        miss: 안 나옴 몫.
        level: 잡은 개체의 레벨.

    Returns:
        등급별 횟수.
    """
    return Counter(get_weighted(build_grade_pool(weights, miss, level, {})) for _ in range(SAMPLES))


def format_row(counts: Counter, level: int, kills: float) -> str:
    """한 레벨의 곡선을 한 줄로 적는다.

    Args:
        counts: 등급별 횟수.
        level: 레벨.
        kills: 런당 처치 수.

    Returns:
        사람이 읽을 한 줄.
    """
    total = sum(counts.values())
    drop = PERCENT_BASE - counts[GRADE_MISS] * PERCENT_BASE / total
    per_run = drop * kills / PERCENT_BASE
    relic = counts.get("RELIC", 0) / total
    runs_to_relic = "—" if relic <= 0 else f"{1 / (relic * kills):.0f}판"
    parts = " ".join(
        f"{name} {counts[name] * PERCENT_BASE / total:6.3f}%"
        for name in sorted(counts)
        if name != GRADE_MISS
    )
    return (
        f"레벨 {level:2d}  굴림 {drop:5.2f}%  런당 {per_run:4.2f}개"
        f"  {parts}  첫 유물 {runs_to_relic}"
    )


def run_player_trial(weights: tuple, miss: int, level: int, kills: int, runs: int) -> int:
    """한 사람이 첫 유물을 볼 때까지 몇 판인지 센다.

    **천장을 이어서 센다.** 천장을 빼고 재면 "언젠가 나온다" 가 실제보다 훨씬 멀어 보이고,
    그 숫자로 확률을 고치면 두 번 고치게 된다 — 앞의 측정이 틀렸기 때문이다.

    Args:
        weights: 등급 가중치들.
        miss: 안 나옴 몫.
        level: 잡는 개체의 레벨.
        kills: 런당 처치 수.
        runs: 최대 몇 판까지 볼지.

    Returns:
        첫 유물이 나온 판 번호. 끝까지 안 나오면 runs 를 넘는 값.
    """
    pity: dict[str, int] = {}
    for run in range(1, runs + 1):
        for _kill in range(kills):
            grade = get_weighted(build_grade_pool(weights, miss, level, pity))
            for name, _weight, _scale in weights:
                pity[name] = 0 if name == grade else pity.get(name, 0) + 1
            if grade == "RELIC":
                return run
    return runs + 1


def format_first_relic(weights: tuple, miss: int, level: int, kills: int) -> str:
    """천장을 포함한 첫 유물까지의 판 수를 잰다.

    Args:
        weights: 등급 가중치들.
        miss: 안 나옴 몫.
        level: 잡는 개체의 레벨.
        kills: 런당 처치 수.

    Returns:
        사람이 읽을 한 줄.
    """
    players = 200
    limit = 400
    found = sorted(
        run_player_trial(weights, miss, level, kills, limit) for _player in range(players)
    )
    middle = found[len(found) // 2]
    worst = found[int(len(found) * 0.9)]
    tail = f"{limit}판 안에 못 봄" if worst > limit else f"{worst}판"
    return f"레벨 {level:2d}  첫 유물 중앙값 {middle}판 · 열에 아홉은 {tail} 안에 (천장 포함)"


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="드롭 곡선을 잰다")
    parser.add_argument("--levels", default="1,5,10,20", help="잴 레벨들")
    args = parser.parse_args()

    pool = create_pool()
    try:
        kills = read_kills_per_run(pool)
        weights, miss = build_weights(pool)
    finally:
        pool.close()
    print(f"런당 처치 {kills:.1f}회 (원장 실측) · 표본 {SAMPLES:,}")
    print("가중치: " + ", ".join(f"{g}={w}(+{s}%/레벨)" for g, w, s in weights) + f", MISS={miss}")
    print()
    for text in args.levels.split(","):
        level = int(text)
        print(format_row(count_grades(weights, miss, level), level, kills))
    print()
    # 천장을 이어서 재면 값이 크게 달라진다. 위의 "첫 유물" 은 천장이 없는 경우다.
    for text in args.levels.split(","):
        print(format_first_relic(weights, miss, int(text), round(kills)))
    print()
    print("**이 값은 밸런스가 아니라 자리다** — 결정 #21(밸런스 목표)이 정해져야 고를 수 있다.")


if __name__ == "__main__":
    main()
