"""스텝 실행 — 전투를 정해진 틱 수만큼 끊어 돌린다 (GDD §2.1 의 배속).

오토배틀은 플레이어 입력이 없는 시간이 길다. 그 시간을 관찰과 진단으로 채우려면
화면이 진행을 붙잡을 수 있어야 하고(GDD §8), 그 단위가 여기 있는 '구간'이다.
일시정지 / 1x / 2x / 4x / 즉시 실행이 전부 "한 번에 몇 틱을 돌리는가" 하나로 환산된다.

**틱 자체는 나누지 않는다.** 7페이즈 한 바퀴가 원자 단위이며, 그 중간에서 멈추면
DECIDE 가 고정한 스냅샷과 ACT 가 보는 세계가 갈려 동시성 공정성이 깨진다 (TDD §4.1).
그래서 가장 느린 배속도 1틱이고, 일시정지는 0틱 — 즉 아무것도 돌리지 않는 것이다.
"""

from dataclasses import dataclass

from game.app.core.event_log import LogEntry
from game.app.simulation.engine import TickEngine
from game.app.simulation.phases import OUTCOME_ONGOING
from game.config import DEFAULT_MAX_TICKS

# GDD §2.1 의 배속. Phase 1 은 터미널이므로 "한 번에 몇 틱" 으로 환산한다.
SPEED_PAUSE = "pause"
SPEED_INSTANT = "instant"
SPEED_STEP_TICKS = {SPEED_PAUSE: 0, "1x": 1, "2x": 2, "4x": 4}
SPEED_LABELS = (SPEED_PAUSE, "1x", "2x", "4x", SPEED_INSTANT)


@dataclass(frozen=True)
class TickBatch:
    """한 번에 돌린 구간과 그 사이에 쌓인 로그."""

    start_tick: int
    end_tick: int
    outcome: str
    entries: tuple[LogEntry, ...]


def get_step_ticks(speed_label: str, max_ticks: int = DEFAULT_MAX_TICKS) -> int:
    """배속 표기를 한 번에 돌릴 틱 수로 바꾼다 (GDD §2.1).

    Args:
        speed_label: pause·1x·2x·4x·instant 중 하나.
        max_ticks: 즉시 실행이 한 번에 돌릴 상한.

    Returns:
        한 번에 돌릴 틱 수. 일시정지는 0 이다.

    Raises:
        ValueError: 모르는 배속 표기인 경우.
    """
    if speed_label == SPEED_INSTANT:
        return max_ticks
    if speed_label not in SPEED_STEP_TICKS:
        raise ValueError(f"모르는 배속이다: {speed_label!r} (가능: {', '.join(SPEED_LABELS)})")
    return SPEED_STEP_TICKS[speed_label]


def run_tick_batch(engine: TickEngine, ticks: int) -> TickBatch:
    """틱을 정해진 수만큼만 돌리고 멈춘다. 스텝 실행의 기본 단위다.

    승패가 먼저 갈리면 남은 틱을 돌리지 않는다.

    Args:
        engine: 조립된 엔진.
        ticks: 이번에 돌릴 틱 수. 0 이하면 아무것도 돌리지 않는다.

    Returns:
        돌린 구간과 그 사이에 쌓인 로그. 한 틱도 돌리지 않았으면
        start_tick 이 end_tick 보다 크고 entries 는 비어 있다.
    """
    first_tick = engine.state.tick + 1
    seen = engine.log.count()
    outcome = OUTCOME_ONGOING
    for _ in range(max(0, ticks)):
        outcome = engine.run_tick()
        if outcome != OUTCOME_ONGOING:
            break
    return TickBatch(
        start_tick=first_tick,
        end_tick=engine.state.tick,
        outcome=outcome,
        entries=tuple(engine.log.entries[seen:]),
    )


def iter_tick_batches(engine: TickEngine, ticks: int) -> tuple[TickBatch, ...]:
    """승패가 갈릴 때까지 정해진 틱 수로 끊어 돌린다.

    화면이 버튼 하나에 한 구간씩 돌릴 때는 run_tick_batch 를 직접 부른다. 이 함수는
    끝까지 돌리되 구간 경계를 남겨 "몇 틱째에 무엇이 있었는가" 를 잃지 않으려는 쪽,
    즉 터미널 출력과 회귀 검사를 위한 것이다.

    Args:
        engine: 조립된 엔진.
        ticks: 한 번에 돌릴 틱 수.

    Returns:
        구간들. 일시정지(0틱)면 빈 튜플이다 — 0틱을 계속 돌리면 전투가 끝나지 않아
        호출자가 멈추지 못한다.
    """
    if ticks <= 0:
        return ()
    batches = []
    outcome = OUTCOME_ONGOING
    while outcome == OUTCOME_ONGOING:
        batch = run_tick_batch(engine, ticks)
        outcome = batch.outcome
        batches.append(batch)
    return tuple(batches)
