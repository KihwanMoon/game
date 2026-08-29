"""사후 분석 — 죽고 나서 어느 규칙이 왜 틀렸는지 특정한다 (GDD §8.3).

두 가지를 낸다. **규칙별 발동 횟수**는 "어느 규칙이 틀렸는가"를, **피해 히트맵**은
"어디에 서 있었던 것이 틀렸는가"를 답한다. `sniper` 가 "후퇴 36회 · 사격 2회" 로 진 것,
피해의 절반을 같은 통로 칸에서 받은 것 — 그 두 줄이면 로그를 처음부터 읽지 않아도
고칠 곳이 특정된다. 그것이 P1(실패는 정보다)이 요구하는 것이다.

집계는 데이터를 돌려주고 문자열 포맷은 별도 함수로 둔다. Phase 3 의 웹 UI 가 같은
집계를 그대로 소비하며, 그때 필요 없는 것은 터미널용 문자열뿐이다 (design/README.md).
"""

from dataclasses import dataclass

from game.app.core.event_log import EventLog, LogEntry
from game.app.simulation.phases import PHASE_TELEGRAPH, PHASE_UPKEEP

WASTE_MARKERS = ("낭비", "미구현")
DEFAULT_RULE_LABEL = "DEFAULT"

# 시도의 절반 이상이 헛돌면 우연이 아니라 조건이 상황과 안 맞는 것이다.
SUSPICIOUS_WASTE_PCT = 50

# 이동(ACT)보다 앞에서 나는 피해다. 그 틱의 **시작** 좌표에서 맞은 것이므로
# 끝 좌표로 세면 용암 위를 지나친 칸이 아니라 도착한 칸이 붉어진다.
PRE_MOVE_PHASES = (PHASE_UPKEEP, PHASE_TELEGRAPH)

# 히트맵 한 칸의 표시 폭. 세 자리부터는 자리를 넓히는 대신 상한 표기로 줄인다 —
# 격자 모양이 무너지면 어느 칸인지 세는 일이 더 어려워진다.
HEATMAP_CELL_WIDTH = 2
HEATMAP_CELL_MAX = 99
HEATMAP_EMPTY = "."
HEATMAP_OVERFLOW = "++"


@dataclass(frozen=True)
class RuleStat:
    """규칙 하나의 성적."""

    label: str
    fired: int
    acted: int
    wasted: int

    @property
    def waste_pct(self) -> int:
        """시도 중 헛돈 비율. 정수 퍼센트다."""
        attempts = self.acted + self.wasted
        return self.wasted * 100 // attempts if attempts else 0


def build_rule_stats(log: EventLog, entity_id: str) -> tuple[RuleStat, ...]:
    """한 엔티티의 규칙별 발동·성공·낭비를 센다.

    Args:
        log: 전투 이벤트 로그.
        entity_id: 대상 엔티티 id.

    Returns:
        우선순위 순으로 정렬된 성적표. DEFAULT 는 맨 뒤에 온다.
    """
    fired: dict[int | None, int] = {}
    acted: dict[int | None, int] = {}
    wasted: dict[int | None, int] = {}

    for entry in log.entries:
        if entry.entity_id != entity_id:
            continue
        if entry.phase == "DECIDE":
            fired[entry.rule] = fired.get(entry.rule, 0) + 1
        elif entry.phase == "ACT":
            bucket = wasted if any(m in entry.outcome for m in WASTE_MARKERS) else acted
            bucket[entry.rule] = bucket.get(entry.rule, 0) + 1

    keys = sorted(set(fired) | set(acted) | set(wasted), key=lambda k: (k is None, k or 0))
    return tuple(
        RuleStat(
            label=DEFAULT_RULE_LABEL if key is None else f"[{key}]",
            fired=fired.get(key, 0),
            acted=acted.get(key, 0),
            wasted=wasted.get(key, 0),
        )
        for key in keys
    )


def format_rule_stats(stats: tuple[RuleStat, ...]) -> str:
    """성적표를 표로 편다.

    Args:
        stats: build_rule_stats 결과.

    Returns:
        출력할 문자열.
    """
    lines = [f"  {'규칙':<8} {'발동':>5} {'성공':>5} {'헛돔':>5}  진단", "  " + "-" * 46]
    for stat in stats:
        note = ""
        if stat.fired and not stat.acted and not stat.wasted:
            note = "발동했지만 실행 단계에 도달하지 않음"
        elif stat.waste_pct >= SUSPICIOUS_WASTE_PCT:
            note = f"시도의 {stat.waste_pct}% 가 헛돎 — 조건을 의심할 것"
        elif stat.fired == 0:
            note = "한 번도 발동하지 않음 — 조건이 너무 좁다"
        lines.append(f"  {stat.label:<8} {stat.fired:>5} {stat.acted:>5} {stat.wasted:>5}  {note}")
    return "\n".join(lines)


@dataclass(frozen=True)
class DamageHit:
    """피해 한 건. 어느 틱에 누가 어느 칸에서 얼마를 맞았는가."""

    tick: int
    target_id: str
    position: tuple[int, int]
    amount: int


def extract_damage_hits(
    entries: tuple[LogEntry, ...],
    start_positions: dict[str, tuple[int, int]],
    end_positions: dict[str, tuple[int, int]],
) -> tuple[DamageHit, ...]:
    """한 틱의 로그에서 피격 좌표를 뽑는다.

    좌표는 로그에 없다. 로그가 남기는 것은 "누가 얼마를 맞았는가" 이고 "어디에서"는
    그 틱의 세계 상태에만 있으므로, 호출자가 틱 전후의 좌표표를 함께 넘긴다.

    Args:
        entries: 그 한 틱에 쌓인 로그.
        start_positions: 틱 시작 시점의 entity_id → 좌표.
        end_positions: 틱 종료 시점의 entity_id → 좌표. 그 틱에 등장한
            개체는 시작 시점 표에 없으므로 이쪽으로 대신한다.

    Returns:
        로그에 남은 순서대로의 피격 기록. 피해가 아닌 줄은 빠진다.
    """
    hits: list[DamageHit] = []
    for entry in entries:
        if entry.target_id is None or entry.delta is None or entry.delta >= 0:
            continue
        source = start_positions if entry.phase in PRE_MOVE_PHASES else end_positions
        position = source.get(entry.target_id, end_positions.get(entry.target_id))
        if position is None:
            continue
        hits.append(
            DamageHit(
                tick=entry.tick,
                target_id=entry.target_id,
                position=position,
                amount=-entry.delta,
            )
        )
    return tuple(hits)


def build_damage_heatmap(
    hits: tuple[DamageHit, ...], width: int, height: int, target_id: str | None = None
) -> tuple[tuple[int, ...], ...]:
    """피격 기록을 격자 합계로 접는다 (GDD §8.3).

    Args:
        hits: 피격 기록들.
        width: 방의 가로 칸 수.
        height: 방의 세로 칸 수.
        target_id: 이 엔티티가 맞은 것만 센다. None 이면 전원을 센다.

    Returns:
        [y][x] 순서의 피해 합계 격자. 방 밖 좌표는 버린다.
    """
    grid = [[0] * width for _ in range(height)]
    for hit in hits:
        if target_id is not None and hit.target_id != target_id:
            continue
        x, y = hit.position
        if 0 <= x < width and 0 <= y < height:
            grid[y][x] += hit.amount
    return tuple(tuple(row) for row in grid)


def format_damage_heatmap(grid: tuple[tuple[int, ...], ...]) -> str:
    """히트맵 격자를 텍스트로 편다.

    Args:
        grid: build_damage_heatmap 결과.

    Returns:
        열 머리글이 붙은 격자 문자열. 격자가 비어 있으면 빈 문자열.
    """
    if not grid:
        return ""
    header = "   " + "".join(f"{x:>{HEATMAP_CELL_WIDTH}d}" for x in range(len(grid[0])))
    lines = [header]
    for y, row in enumerate(grid):
        cells = "".join(f"{_format_cell(value):>{HEATMAP_CELL_WIDTH}s}" for value in row)
        lines.append(f"{y:>2d} {cells}")
    return "\n".join(lines)


def _format_cell(value: int) -> str:
    """히트맵 한 칸의 표시 문자열.

    Args:
        value: 그 칸의 피해 합계.

    Returns:
        폭 안에 들어가는 표기. 0 은 점, 상한 초과는 생략 표기다.
    """
    if value <= 0:
        return HEATMAP_EMPTY
    if value > HEATMAP_CELL_MAX:
        return HEATMAP_OVERFLOW
    return str(value)
