"""이벤트 로그 — 코어가 발행하고 UI 가 구독만 하는 단방향 스트림 (TDD §2).

레코드의 필드는 디자인 시스템의 LogRow 계약에서 왔다 — `tick·rule·expr·outcome·
delta·fired`. UI 가 그 여섯을 표시하므로 코어가 그 여섯을 내야 한다.

`expr` 이 조건문 문자열인 것이 핵심이다. GDD §8.2 는 매 틱 **평가된 조건의 실제 값**을
노출하라고 요구하고, 디자인의 규칙 행은 `적거리(2) <= 사거리(3)` 처럼 항마다 실측값을
괄호로 병기한다. 참/거짓만 남기면 죽고 나서 어느 규칙이 왜 틀렸는지 특정할 수 없다 —
그것이 P1(실패는 정보다)의 실현 수단이다.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LogEntry:
    """로그 한 줄. UI 의 LogRow 하나에 대응한다."""

    tick: int
    entity_id: str
    phase: str
    expr: str
    outcome: str
    rule: int | None = None
    delta: int | None = None
    fired: bool = False
    # 피해를 **받은** 쪽. entity_id 는 행위자라 지형 피해가 아닌 한 둘이 다르다.
    # 피해 히트맵(GDD §8.3)이 "어느 칸에서 맞았는가"를 세려면 피격자를 알아야 하는데,
    # outcome 문자열에서 되뽑으면 표시 문구를 고칠 때마다 집계가 조용히 틀린다.
    target_id: str | None = None


@dataclass
class EventLog:
    """틱 진행 중 쌓이는 이벤트. 코어만 쓰고 UI 는 읽기만 한다."""

    entries: list[LogEntry] = field(default_factory=list)

    def record(self, entry: LogEntry) -> None:
        """이벤트 한 건을 남긴다.

        Args:
            entry: 남길 레코드.
        """
        self.entries.append(entry)

    def count(self) -> int:
        """쌓인 이벤트 수."""
        return len(self.entries)

    def filter_by_tick(self, tick: int) -> tuple[LogEntry, ...]:
        """한 틱의 이벤트만 골라낸다.

        Args:
            tick: 고를 틱 번호.

        Returns:
            그 틱에 남은 레코드들. 남긴 순서를 유지한다.
        """
        return tuple(entry for entry in self.entries if entry.tick == tick)

    def format_lines(self) -> tuple[str, ...]:
        """터미널 출력용 문자열로 편다 (Phase 1 은 UI 가 없다).

        Returns:
            "T027 | [3] 조건 → 결과" 형식의 줄들.
        """
        lines = []
        for entry in self.entries:
            slot = f"[{entry.rule}]" if entry.rule is not None else "   "
            delta = f" ({entry.delta:+d})" if entry.delta is not None else ""
            lines.append(
                f"T{entry.tick:03d} | {entry.entity_id:<18s} {slot} {entry.expr} → "
                f"{entry.outcome}{delta}"
            )
        return tuple(lines)
