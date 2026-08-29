"""규칙 DSL 의 직렬화 형식 (TDD §3.3, GDD §3.1).

`[우선순위 N] IF <조건식> THEN <행동> [TARGET <셀렉터>] [SET <플래그>]`

인자를 받는 인지 변수(쿨타임[스킬]·플래그[A~D]·적유형존재[유형])를 담을 자리가
TDD §3.3 의 term 형식에 없어 `lhs_param` 을 더했다. Phase 0 F-6 으로 보고된 확장이다.

우변(`rhs`)은 리터럴이거나 자기 스탯 참조다 (F-2). 스탯 참조의 표현은
`{"rhs": {"stat": "attack_range"}}` 이며, 객체 한 겹으로 감싼 이유는 언어 중립성이다 —
Phase 3 의 TypeScript 코어가 `typeof rhs === "object"` 만으로 분기할 수 있고,
문자열 우변("attack_range")과 달리 뒷날 문자열 리터럴을 더해도 뜻이 겹치지 않는다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

OP_SINGLE = "SINGLE"
OP_AND = "AND"
OP_OR = "OR"
CONDITION_OPS = frozenset({OP_SINGLE, OP_AND, OP_OR})

COMPARISONS = frozenset({"<", "<=", ">", ">=", "==", "!="})

# GDD §3.1 — 조건식은 최대 3항이다. §3.6 의 CPU 비용표도 3항까지만 값을 갖는다.
MAX_TERMS = 3

# 스탯 참조 우변을 알아보는 키. 허용 스탯의 닫힌 목록은 blocks.json 의 rhs_stats 이며,
# 여기서는 형식만 정한다 — 목록은 데이터, 형식은 계약이다.
RHS_STAT_KEY = "stat"


@dataclass(frozen=True)
class StatRef:
    """조건 우변이 가리키는 자기 스탯 (F-2). `사거리` 처럼 값이 런타임에 정해진다."""

    stat: str


@dataclass(frozen=True)
class Term:
    """조건 한 항. `적거리 <= 3` 하나에 해당한다."""

    lhs: str
    comparison: str
    rhs: int | bool | StatRef
    lhs_param: str | None = None

    @property
    def key(self) -> str:
        """스냅샷에서 값을 찾을 키."""
        return self.lhs if self.lhs_param is None else f"{self.lhs}[{self.lhs_param}]"


@dataclass(frozen=True)
class Condition:
    """조건식. 항 여러 개를 AND/OR 로 묶는다."""

    op: str
    terms: tuple[Term, ...]


@dataclass(frozen=True)
class Rule:
    """규칙 한 줄."""

    priority: int
    conditions: Condition
    action: str
    target: str | None = None
    set_flag: str | None = None
    cpu_cost: int = 1


@dataclass(frozen=True)
class RuleSet:
    """한 엔티티의 규칙표 전체."""

    ruleset_id: str
    version: int
    rules: tuple[Rule, ...]


def parse_rhs(raw: object) -> int | bool | StatRef:
    """조건 항의 우변을 읽는다. 리터럴이거나 스탯 참조다 (F-2).

    Args:
        raw: term 의 rhs 절. 정수·불리언 리터럴이거나 `{"stat": ...}` 객체.

    Returns:
        리터럴 그대로, 또는 스탯 참조.

    Raises:
        ValueError: 객체 우변에 stat 문자열이 없거나 우변 형식을 알 수 없는 경우.
    """
    if isinstance(raw, dict):
        stat = raw.get(RHS_STAT_KEY)
        if not isinstance(stat, str):
            raise ValueError(f"우변 객체에는 {RHS_STAT_KEY} 문자열이 있어야 한다: {raw}")
        return StatRef(stat=stat)
    # bool 은 int 의 하위형이라 이 검사 하나로 둘 다 걸린다.
    if isinstance(raw, int):
        return raw
    raise ValueError(f"우변은 정수·불리언이거나 스탯 참조여야 한다: {raw}")


def parse_term(raw: dict) -> Term:
    """원시 딕셔너리에서 조건 항을 만든다.

    Args:
        raw: term 절.

    Returns:
        만들어진 항.
    """
    return Term(
        lhs=raw["lhs"],
        comparison=raw["cmp"],
        rhs=parse_rhs(raw["rhs"]),
        lhs_param=raw.get("lhs_param"),
    )


def parse_ruleset(raw: dict) -> RuleSet:
    """원시 딕셔너리에서 규칙표를 만든다.

    우선순위 오름차순으로 정렬해 둔다. 실행이 위에서부터 평가하는 것을 전제하므로
    (TDD §5.2) 정렬을 로드 시점에 끝내면 매 틱 다시 정렬할 필요가 없다.

    Args:
        raw: ruleset 절.

    Returns:
        우선순위 순으로 정렬된 규칙표.
    """
    rules = tuple(
        sorted(
            (
                Rule(
                    priority=item["priority"],
                    conditions=Condition(
                        op=item["conditions"]["op"],
                        terms=tuple(parse_term(t) for t in item["conditions"]["terms"]),
                    ),
                    action=item["action"],
                    target=item.get("target"),
                    set_flag=item.get("set_flag"),
                    cpu_cost=item["cpu_cost"],
                )
                for item in raw["rules"]
            ),
            key=lambda rule: rule.priority,
        )
    )
    return RuleSet(ruleset_id=raw["ruleset_id"], version=raw["version"], rules=rules)


def load_rulesets(source_path: Path) -> dict[str, RuleSet]:
    """규칙표 묶음 JSON 을 읽는다.

    Args:
        source_path: rulesets 배열을 담은 JSON 경로.

    Returns:
        ruleset_id 에서 규칙표로의 대응표.
    """
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    parsed = [parse_ruleset(item) for item in raw["rulesets"]]
    return {ruleset.ruleset_id: ruleset for ruleset in parsed}
