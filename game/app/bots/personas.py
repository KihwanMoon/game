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


@dataclass(frozen=True)
class BotPersona:
    """봇 하나를 세우는 값."""

    label: str
    ruleset_id: str
    cadence_sec: int
    skill_pct: int


# 열 명. 규칙표는 `benchmark.json`(14) 과 `g0_examples.json`(3) 에서 골랐다 — 새로 짜지
# 않은 이유는 이것들이 이미 전략 공간을 갈라 놓았기 때문이다(`test_benchmark_rulesets`).
#
# 실력 분포를 일부러 아래로 기울였다. 잘하는 셋, 보통 넷, 못하는 셋이다.
BOT_PERSONAS: tuple[BotPersona, ...] = (
    BotPersona("겨눔", "sniper", HOUR // 2, 100),
    BotPersona("문지기", "door_hold", HOUR, 100),
    BotPersona("쓸어담기", "area_sweep", HOUR * 2, 95),
    BotPersona("약한고리", "focus_lowest", HOUR, 80),
    BotPersona("위협우선", "focus_threat", HOUR + HOUR // 2, 75),
    BotPersona("사거리", "weapon_reach", HOUR * 3, 70),
    BotPersona("소환사냥", "kite_summoner", HOUR * 2, 65),
    BotPersona("맞불", "g0_pressure", HOUR // 3, 45),
    BotPersona("샘터", "spring_camp", HOUR * 4, 40),
    BotPersona("겁쟁이", "g0_kite", HOUR // 4, 30),
)
