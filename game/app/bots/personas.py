"""봇 열의 성격 (T11 대응).

**스펙을 손으로 박지 않는다.** 규칙표·리듬·실력 셋만 다르게 주면 나머지는 굴러가면서
갈린다 — 장비는 주운 것에서 나오고, 도달 층은 서버가 `reached_floor` 로 물리며, 도감은
만난 것이 채운다. 손으로 박은 스펙은 첫날만 다양하고 그 뒤로는 굳는다.

**못하는 봇이 있어야 한다.** 전부 잘하면 지속 몬스터가 감쇠만 하고 층 난이도가 한쪽으로
흐른다. 1층에서 죽는 쪽이 몬스터를 먹이고, 그것이 다음 사람이 만날 난이도를 만든다.

리듬도 갈라 둔다. 열이 같은 박자로 나가면 세계가 한꺼번에 움직였다 한꺼번에 멈춘다.
"""

from dataclasses import dataclass

# 한 시간. 리듬을 초로 적으면 읽을 때마다 나눠야 한다.
HOUR = 3600

# 시간당 최대 출격 수. **상한이지 목표가 아니다** — 이보다 자주 나가는 봇은 없다.
#
# 세우는 이유가 둘이다. 하나는 부하다: 이 API 에 런 단위 레이트 리밋이 없어(로그인만
# `throttle` 이 센다) 봇이 첫 대량 클라이언트가 된다. 다른 하나는 경제다 — 봇이 사람보다
# 빨리 돌면 전리품과 화폐가 봇 쪽에서 나오고, 그러면 시장을 채우려던 것이 시장을 봇의
# 것으로 만든다.
#
# 「한 판」은 티켓 하나다. 하강 한 번이 층마다 청구를 여러 번 올리지만 그것은 한 판이며,
# 사람도 그렇게 논다.
MAX_RUNS_PER_HOUR = 5

# 판 사이의 최소 간격(초). `next_run_at` 이 이만큼은 미뤄지므로 상한이 실제로 걸린다.
MIN_CADENCE_SEC = HOUR // MAX_RUNS_PER_HOUR


@dataclass(frozen=True)
class BotPersona:
    """봇 하나를 세우는 값."""

    label: str
    ruleset_id: str
    cadence_sec: int
    skill_pct: int


# 열 명. **전부 상한으로 돈다** — 봇마다 시간당 다섯 판이고 합쳐서 50판이다. 리듬을
# 갈라 두면 세계가 고르게 움직이지만, 지금은 세계가 너무 조용한 것이 더 큰 문제다.
# 규칙표는 `benchmark.json`(14) 과 `g0_examples.json`(3) 에서 골랐다 — 새로 짜지
# 않은 이유는 이것들이 이미 전략 공간을 갈라 놓았기 때문이다(`test_benchmark_rulesets`).
#
# 실력 분포를 일부러 아래로 기울였다. 잘하는 셋, 보통 넷, 못하는 셋이다.
BOT_PERSONAS: tuple[BotPersona, ...] = (
    BotPersona("겨눔", "sniper", MIN_CADENCE_SEC, 100),
    BotPersona("문지기", "door_hold", MIN_CADENCE_SEC, 100),
    BotPersona("쓸어담기", "area_sweep", MIN_CADENCE_SEC, 95),
    BotPersona("약한고리", "focus_lowest", MIN_CADENCE_SEC, 80),
    BotPersona("위협우선", "focus_threat", MIN_CADENCE_SEC, 75),
    BotPersona("사거리", "weapon_reach", MIN_CADENCE_SEC, 70),
    BotPersona("소환사냥", "kite_summoner", MIN_CADENCE_SEC, 65),
    BotPersona("맞불", "g0_pressure", MIN_CADENCE_SEC, 45),
    BotPersona("샘터", "spring_camp", MIN_CADENCE_SEC, 40),
    BotPersona("겁쟁이", "g0_kite", MIN_CADENCE_SEC, 30),
)


def resolve_cadence(seconds: int) -> int:
    """리듬을 상한 안으로 물린다.

    **성격 정의에만 적지 않는다.** 거기 적힌 값은 데이터라 다음 사람이 더 빠른 수를 넣을
    수 있고, 그러면 상한이 있었다는 사실만 남는다. `next_run_at` 을 쓰는 자리마다 이것을
    거치게 해서, 상한을 넘기려면 이 함수를 고쳐야 하게 둔다.

    Args:
        seconds: 바라는 간격(초).

    Returns:
        `MIN_CADENCE_SEC` 이상의 간격.
    """
    return max(MIN_CADENCE_SEC, seconds)
