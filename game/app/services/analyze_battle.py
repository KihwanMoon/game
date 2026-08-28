"""사후 분석 — 죽고 나서 어느 규칙이 왜 틀렸는지 특정한다 (GDD §8.3).

전량 구현(되감기 슬라이더·피해 히트맵)은 Phase 2 W8 이다. 여기서는 텍스트로 낼 수
있는 것만 한다 — **규칙별 발동 횟수**가 그중 가장 값이 크다.

`sniper` 가 "후퇴 36회 · 사격 2회" 로 진 것을 그 한 줄이 즉시 설명한다. 로그를 처음부터
읽지 않아도 고칠 곳이 특정되며, 그것이 P1(실패는 정보다)이 요구하는 것이다.
"""

from dataclasses import dataclass

from game.app.core.event_log import EventLog

WASTE_MARKERS = ("낭비", "미구현")
DEFAULT_RULE_LABEL = "DEFAULT"

# 시도의 절반 이상이 헛돌면 우연이 아니라 조건이 상황과 안 맞는 것이다.
SUSPICIOUS_WASTE_PCT = 50


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
