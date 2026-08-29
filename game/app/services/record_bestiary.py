"""몬스터 도감 — 적의 규칙표를 **그대로** 공개한다 (GDD §2.3·§5).

몬스터가 플레이어와 동일한 DSL 로 기술돼 있으므로 도감은 요약이 아니라 원문을 낸다.
이것이 실패한 런조차 자산을 남기게 하는 장치다 — 진 뒤에 상대의 규칙을 읽고 카운터를
설계하면, 그 규칙은 다음 런으로 넘어간다 (P1).

**규칙표 밖에서 처리되는 것도 함께 낸다.** 소환의 주기·소환물·동시 상한은 밸런스
데이터에 있고, 자폭의 예고 틱·반경·고정 피해도 그렇다. 규칙표만 보여 주면 플레이어는
`SUMMON` 한 줄을 읽고 "한 마리씩 부르겠지" 라고 카운터를 세우며, 그 카운터가 통하지
않는 이유를 어디에서도 찾을 수 없다. 도감이 거짓말을 하면 P1 이 뒤집힌다.

아직 구현되지 않은 행동(actions.DEFERRED_ACTIONS)도 같은 이유로 표시한다. 목록이
줄어들면 이 경고도 저절로 사라지므로, 도감이 코드보다 뒤처지지 않는다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from game.app.simulation.actions import DEFERRED_ACTIONS
from game.config import ENEMY_RULESETS_PATH
from game.schemas.meta_save import MetaSave
from game.schemas.ruleset import Rule, RuleSet, StatRef, Term

# 도감이 싣는 스탯과 그 표기. 순서를 튜플로 박아 둔 이유는 R5 다 — 딕셔너리 순회로
# 만들면 같은 적의 도감이 실행마다 다른 순서로 나온다.
STAT_LABELS: tuple[tuple[str, str], ...] = (
    ("hp_max", "HP"),
    ("attack", "공격"),
    ("defense", "방어"),
    ("attack_range", "사거리"),
    ("initiative", "이니셔티브"),
    ("regen_base", "재생"),
    ("potions", "포션"),
    ("cpu_budget", "CPU"),
    ("rule_slots", "규칙 슬롯"),
)

SUMMON_ACTION = "SUMMON"
SUMMON_REASON = (
    "규칙표의 SUMMON 은 '언제' 만 정한다. 무엇을 몇 마리까지 부르는지는 "
    "밸런스 데이터에 있어 규칙표를 아무리 읽어도 나오지 않는다."
)
TELEGRAPH_REASON = (
    "예고 공격의 반경·피해·예고 틱은 규칙표에 없다. 피해가 방어력 감쇠를 받지 "
    "않는 고정값이라, 스탯으로 버티는 카운터가 통하지 않는다."
)
DEFERRED_LABEL = "미구현 행동"
DEFERRED_REASON_HEAD = "규칙표에 있지만 이대로 실행되지는 않는다:"

# 우변이 스탯 참조임을 눈으로 구분하기 위한 표기. 리터럴 3 과 사거리 3 은 다르다.
STAT_REF_OPEN = "<"
STAT_REF_CLOSE = ">"

# 규칙표 JSON 의 표기와 맞춘다.
BOOL_LABELS = {True: "true", False: "false"}


@dataclass(frozen=True)
class DetailLine:
    """도감의 값 한 줄. 스탯이거나 능력의 세부값이다."""

    key: str
    label_ko: str
    value: int | str


@dataclass(frozen=True)
class AbilityNote:
    """규칙표 밖에서 처리되는 능력 하나."""

    ability_id: str
    label_ko: str
    reason_ko: str
    details: tuple[DetailLine, ...] = ()


@dataclass(frozen=True)
class BestiaryPage:
    """도감 한 페이지. 적 하나에 대해 아는 전부다."""

    kind_id: str
    label_ko: str
    strategy_ko: str
    stats: tuple[DetailLine, ...]
    ruleset: RuleSet
    notes: tuple[AbilityNote, ...]


def find_enemy_entry(kind_id: str, balance: dict) -> dict:
    """밸런스 데이터에서 적 종류 절을 찾는다.

    Args:
        kind_id: 적 종류 id.
        balance: balance.json 딕셔너리.

    Returns:
        찾은 적 절.

    Raises:
        KeyError: 그런 적이 없는 경우.
    """
    for entry in balance["enemies"]:
        if entry["id"] == kind_id:
            return entry
    raise KeyError(f"밸런스에 없는 적이다: {kind_id}")


def get_enemy_ruleset(kind_id: str, balance: dict, enemy_rulesets: dict[str, RuleSet]) -> RuleSet:
    """적의 규칙표를 그대로 돌려준다. 도감의 본체다.

    가공하지 않는다. 요약하거나 순서를 바꾸면 플레이어가 읽은 것과 엔진이 실행하는
    것이 달라지고, 그 순간 도감은 카운터의 근거가 되지 못한다.

    Args:
        kind_id: 적 종류 id.
        balance: balance.json 딕셔너리.
        enemy_rulesets: ruleset_id 에서 규칙표로의 대응표.

    Returns:
        그 적이 실제로 쓰는 규칙표.

    Raises:
        KeyError: 적이 없거나 그 적의 규칙표가 로드되지 않은 경우.
    """
    entry = find_enemy_entry(kind_id, balance)
    ruleset_id = entry.get("ruleset_id")
    if ruleset_id not in enemy_rulesets:
        raise KeyError(f"규칙표가 로드되지 않았다: {kind_id} -> {ruleset_id}")
    return enemy_rulesets[ruleset_id]


def build_stat_lines(entry: dict) -> tuple[DetailLine, ...]:
    """적 절에서 도감이 싣는 스탯 줄을 만든다.

    Args:
        entry: 밸런스의 적 절.

    Returns:
        STAT_LABELS 순서의 스탯 줄. 그 적에게 없는 스탯은 빠진다.
    """
    return tuple(
        DetailLine(key=key, label_ko=label, value=entry[key])
        for key, label in STAT_LABELS
        if key in entry
    )


def build_summon_note(entry: dict) -> AbilityNote | None:
    """소환 능력을 규칙표 밖 항목으로 만든다.

    Args:
        entry: 밸런스의 적 절.

    Returns:
        소환 항목. 소환하지 않는 적이면 None.
    """
    summon = entry.get("summon")
    if summon is None:
        return None
    return AbilityNote(
        ability_id=SUMMON_ACTION,
        label_ko="소환",
        reason_ko=SUMMON_REASON,
        details=(
            DetailLine(key="spawns", label_ko="소환물", value=summon["spawns"]),
            DetailLine(key="every_ticks", label_ko="주기(틱)", value=summon["every_ticks"]),
            DetailLine(key="max_alive", label_ko="동시 상한", value=summon["max_alive"]),
        ),
    )


def build_telegraph_note(entry: dict) -> AbilityNote | None:
    """예고 공격을 규칙표 밖 항목으로 만든다.

    Args:
        entry: 밸런스의 적 절.

    Returns:
        예고 공격 항목. 예고가 없는 적이면 None.
    """
    telegraph = entry.get("telegraph")
    if telegraph is None:
        return None
    details = [
        DetailLine(key="lead_ticks", label_ko="예고(틱)", value=telegraph["lead_ticks"]),
        DetailLine(key="radius", label_ko="반경", value=telegraph["radius"]),
        DetailLine(key="damage", label_ko="고정 피해", value=telegraph["damage"]),
    ]
    if telegraph.get("self_destruct"):
        details.append(DetailLine(key="self_destruct", label_ko="자폭", value="예"))
    if telegraph.get("cancel_on_death"):
        # 두 번째 정답('사거리 밖에서 먼저 끊는다')이 성립하는 근거라 반드시 싣는다.
        details.append(
            DetailLine(key="cancel_on_death", label_ko="시전자 사망 시 취소", value="예")
        )
    return AbilityNote(
        ability_id=telegraph["skill"],
        label_ko="예고 공격",
        reason_ko=TELEGRAPH_REASON,
        details=tuple(details),
    )


def list_deferred_notes(ruleset: RuleSet) -> tuple[AbilityNote, ...]:
    """규칙표에 있지만 아직 그대로 실행되지 않는 행동을 모은다.

    Args:
        ruleset: 훑을 규칙표.

    Returns:
        우선순위 순, 행동별 한 번씩의 경고 항목.
    """
    notes: list[AbilityNote] = []
    seen: list[str] = []
    for rule in ruleset.rules:
        reason = DEFERRED_ACTIONS.get(rule.action)
        if reason is None or rule.action in seen:
            continue
        seen.append(rule.action)
        notes.append(
            AbilityNote(
                ability_id=rule.action,
                label_ko=DEFERRED_LABEL,
                reason_ko=f"{DEFERRED_REASON_HEAD} {reason}",
            )
        )
    return tuple(notes)


def load_strategy_notes(source_path: Path = ENEMY_RULESETS_PATH) -> dict[str, str]:
    """규칙표 JSON 에서 전략 한 줄 설명을 읽는다.

    `strategy_ko` 는 도감에 실으려고 데이터에 넣은 필드인데 RuleSet 데이터클래스에
    자리가 없어 parse_ruleset 이 버린다. 통합에서 RuleSet 에 필드가 생기면 이 함수는
    사라진다.

    Args:
        source_path: rulesets 배열을 담은 JSON 경로.

    Returns:
        ruleset_id 에서 전략 설명으로의 대응표.
    """
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    return {item["ruleset_id"]: item.get("strategy_ko", "") for item in raw["rulesets"]}


def build_bestiary_page(
    kind_id: str,
    balance: dict,
    enemy_rulesets: dict[str, RuleSet],
    strategies: dict[str, str] | None = None,
) -> BestiaryPage:
    """적 하나의 도감 페이지를 만든다.

    Args:
        kind_id: 적 종류 id.
        balance: balance.json 딕셔너리.
        enemy_rulesets: ruleset_id 에서 규칙표로의 대응표.
        strategies: load_strategy_notes 결과. 주면 전략 한 줄로 쓴다. 없으면
            밸런스 쪽 설계 노트를 쓴다.

    Returns:
        규칙표 원문과 규칙표 밖 항목을 함께 담은 페이지.
    """
    entry = find_enemy_entry(kind_id, balance)
    ruleset = get_enemy_ruleset(kind_id, balance, enemy_rulesets)
    notes = [note for note in (build_summon_note(entry), build_telegraph_note(entry)) if note]
    notes.extend(list_deferred_notes(ruleset))
    strategy = (strategies or {}).get(ruleset.ruleset_id) or entry.get("_note", "")
    return BestiaryPage(
        kind_id=kind_id,
        label_ko=entry.get("label_ko", kind_id),
        strategy_ko=strategy,
        stats=build_stat_lines(entry),
        ruleset=ruleset,
        notes=tuple(notes),
    )


def list_bestiary_pages(
    meta: MetaSave,
    balance: dict,
    enemy_rulesets: dict[str, RuleSet],
    strategies: dict[str, str] | None = None,
) -> tuple[BestiaryPage, ...]:
    """세이브에 기록된 적들의 도감을 kind_id 순으로 만든다.

    만나지 않은 적은 나오지 않는다. 도감이 처음부터 다 열려 있으면 조우가 보상이
    되지 못한다.

    Args:
        meta: 도감 기록을 가진 메타 세이브.
        balance: balance.json 딕셔너리.
        enemy_rulesets: ruleset_id 에서 규칙표로의 대응표.
        strategies: load_strategy_notes 결과. 페이지마다 그대로 넘긴다.

    Returns:
        기록 순(kind_id 오름차순)의 페이지들.
    """
    return tuple(
        build_bestiary_page(record.kind_id, balance, enemy_rulesets, strategies)
        for record in meta.bestiary
    )


def format_term(term: Term) -> str:
    """조건 항 하나를 사람이 읽는 한 줄로 편다.

    Args:
        term: 펼 항.

    Returns:
        `적거리[NEAREST] <= <attack_range>` 형태의 문자열.
    """
    if isinstance(term.rhs, StatRef):
        rhs = f"{STAT_REF_OPEN}{term.rhs.stat}{STAT_REF_CLOSE}"
    elif isinstance(term.rhs, bool):
        # 파이썬 표기(True)가 아니라 DSL 표기(true)로 낸다. 도감이 보여준 문장을
        # 그대로 규칙표에 옮겨 적을 수 있어야 원문 공개라고 할 수 있다.
        rhs = BOOL_LABELS[term.rhs]
    else:
        rhs = str(term.rhs)
    return f"{term.key} {term.comparison} {rhs}"


def format_rule(rule: Rule) -> str:
    """규칙 한 줄을 DSL 표기로 편다.

    Args:
        rule: 펼 규칙.

    Returns:
        `[1] IF ... THEN ... TARGET ...` 형태의 문자열.
    """
    joiner = " AND " if rule.conditions.op == "AND" else " OR "
    condition = joiner.join(format_term(term) for term in rule.conditions.terms)
    line = f"[{rule.priority}] IF {condition} THEN {rule.action}"
    if rule.target:
        line += f" TARGET {rule.target}"
    if rule.set_flag:
        line += f" SET {rule.set_flag}"
    return f"{line}  (cpu {rule.cpu_cost})"


def format_bestiary_page(page: BestiaryPage) -> str:
    """도감 한 페이지를 터미널 출력용 문자열로 만든다.

    Args:
        page: 펼 페이지.

    Returns:
        여러 줄 문자열.
    """
    stats = " · ".join(f"{line.label_ko} {line.value}" for line in page.stats)
    lines = [f"[{page.label_ko}] {page.kind_id}", f"  스탯: {stats}"]
    if page.strategy_ko:
        lines.append(f"  전략: {page.strategy_ko}")
    lines.append(f"  규칙표 ({page.ruleset.ruleset_id} v{page.ruleset.version})")
    lines.extend(f"    {format_rule(rule)}" for rule in page.ruleset.rules)
    if page.notes:
        lines.append("  규칙표 밖 — 이것을 모르면 카운터가 빗나간다")
    for note in page.notes:
        lines.append(f"    · {note.ability_id} {note.label_ko} — {note.reason_ko}")
        if note.details:
            detail = " / ".join(f"{item.label_ko} {item.value}" for item in note.details)
            lines.append(f"      {detail}")
    return "\n".join(lines)
