"""메타 세이브 직렬화 형식 (TDD §9, GDD §2.3).

**사망해도 남는 것만** 담는다 — 해금 블록, 층 도달 기록(규칙 슬롯 상한의 근거),
몬스터 도감, 코드 라이브러리(프리셋 8슬롯). 장비·임시 모듈·층 진행도·포션은 런
스냅샷 쪽이고 여기 들어오면 안 된다. 들어오는 순간 사망의 대가가 사라진다.

첫 필드가 형식 태그(`v1`)인 이유는 마이그레이션 판정이다 (TDD §9). 태그를 먼저 읽어
처리 방법을 정하므로 본문 구조가 바뀌어도 읽기 시작하는 지점은 그대로다.

순서를 정규화해 보관하는 것은 R5 때문이다. 해금 목록과 도감은 정렬된 튜플로만 둔다 —
집합을 그대로 직렬화하면 같은 세이브가 실행마다 다른 파일이 되고, 그 위에서 만든
리플레이 검증이 흔들린다. 프리셋만은 슬롯 번호가 뜻을 가지므로 넣은 순서를 지킨다.
"""

from dataclasses import dataclass

from game.schemas.ruleset import Rule, RuleSet, StatRef, Term, parse_ruleset

# 형식 태그. 값이 아니라 접두어를 먼저 보는 것이 마이그레이션 판정의 방식이다.
META_FORMAT_PREFIX = "v"
META_FORMAT_VERSION = 1
META_FORMAT_TAG = f"{META_FORMAT_PREFIX}{META_FORMAT_VERSION}"

# GDD §2.3 — 코드 라이브러리는 8슬롯, 시작 슬롯 보너스는 최대 +4 다.
MAX_PRESET_SLOTS = 8
MAX_SLOT_BONUS = 4

# 층 1 도달은 시작 조건이라 보너스가 아니다. 보너스는 층 2부터 붙는다.
FIRST_FLOOR = 1


@dataclass(frozen=True)
class BestiaryRecord:
    """도감 한 줄. 이 적을 몇 번 만났고 몇 번 잡았는가.

    조우만으로도 규칙표가 열린다 (GDD §2.3). 잡은 횟수를 따로 세는 것은 도감을
    "읽었다" 와 "통했다" 를 구분하기 위해서다.
    """

    kind_id: str
    encounters: int = 0
    defeats: int = 0


@dataclass(frozen=True)
class RulePreset:
    """코드 라이브러리 한 슬롯. 이름 붙인 규칙표 하나다."""

    name: str
    ruleset: RuleSet


@dataclass(frozen=True)
class MetaSave:
    """사망해도 남는 것 전부."""

    format_version: int = META_FORMAT_VERSION
    best_floor: int = 0
    unlocked_perceptions: tuple[str, ...] = ()
    unlocked_actions: tuple[str, ...] = ()
    bestiary: tuple[BestiaryRecord, ...] = ()
    presets: tuple[RulePreset, ...] = ()


def get_format_version(tag: str) -> int:
    """형식 태그에서 버전 정수를 읽는다.

    Args:
        tag: `v1` 형태의 태그.

    Returns:
        태그가 가리키는 버전 정수.

    Raises:
        ValueError: 접두어가 없거나 뒤가 정수가 아닌 경우.
    """
    if not tag.startswith(META_FORMAT_PREFIX):
        raise ValueError(f"형식 태그는 {META_FORMAT_PREFIX} 로 시작해야 한다: {tag!r}")
    body = tag[len(META_FORMAT_PREFIX) :]
    if not body.isdigit():
        raise ValueError(f"형식 태그의 버전이 정수가 아니다: {tag!r}")
    return int(body)


def build_rhs_payload(rhs: int | bool | StatRef) -> int | bool | dict:
    """조건 우변을 JSON 값으로 되돌린다.

    Args:
        rhs: 리터럴이거나 스탯 참조인 우변.

    Returns:
        JSON 에 그대로 넣을 수 있는 값.
    """
    if isinstance(rhs, StatRef):
        return {"stat": rhs.stat}
    return rhs


def build_term_payload(term: Term) -> dict:
    """조건 항 하나를 JSON 딕셔너리로 되돌린다.

    Args:
        term: 되돌릴 항.

    Returns:
        parse_term 이 다시 읽을 수 있는 딕셔너리. lhs_param 이 없으면 그 키도 없다.
    """
    payload: dict = {"lhs": term.lhs, "cmp": term.comparison, "rhs": build_rhs_payload(term.rhs)}
    if term.lhs_param is not None:
        payload["lhs_param"] = term.lhs_param
    return payload


def build_rule_payload(rule: Rule) -> dict:
    """규칙 한 줄을 JSON 딕셔너리로 되돌린다.

    Args:
        rule: 되돌릴 규칙.

    Returns:
        parse_ruleset 이 다시 읽을 수 있는 딕셔너리.
    """
    return {
        "priority": rule.priority,
        "cpu_cost": rule.cpu_cost,
        "action": rule.action,
        "target": rule.target,
        "set_flag": rule.set_flag,
        "conditions": {
            "op": rule.conditions.op,
            "terms": [build_term_payload(term) for term in rule.conditions.terms],
        },
    }


def build_ruleset_payload(ruleset: RuleSet) -> dict:
    """규칙표를 JSON 딕셔너리로 되돌린다. parse_ruleset 의 역방향이다.

    제자리는 parse_ruleset 옆(schemas/ruleset.py)이다. W5 가 기존 파일을 건드리지
    않기로 해 여기 둔 것이며, 통합에서 옮긴다.

    Args:
        ruleset: 되돌릴 규칙표.

    Returns:
        parse_ruleset 에 그대로 넣을 수 있는 딕셔너리.
    """
    return {
        "ruleset_id": ruleset.ruleset_id,
        "version": ruleset.version,
        "rules": [build_rule_payload(rule) for rule in ruleset.rules],
    }


def parse_preset(raw: dict) -> RulePreset:
    """프리셋 한 슬롯을 읽는다.

    Args:
        raw: name 과 ruleset 을 가진 절.

    Returns:
        만들어진 프리셋.
    """
    return RulePreset(name=raw["name"], ruleset=parse_ruleset(raw["ruleset"]))


def build_preset_payload(preset: RulePreset) -> dict:
    """프리셋 한 슬롯을 JSON 딕셔너리로 되돌린다.

    Args:
        preset: 되돌릴 프리셋.

    Returns:
        parse_preset 이 다시 읽을 수 있는 딕셔너리.
    """
    return {"name": preset.name, "ruleset": build_ruleset_payload(preset.ruleset)}


def parse_bestiary_record(raw: dict) -> BestiaryRecord:
    """도감 한 줄을 읽는다.

    Args:
        raw: kind_id·encounters·defeats 를 가진 절.

    Returns:
        만들어진 도감 기록.
    """
    return BestiaryRecord(
        kind_id=raw["kind_id"],
        encounters=raw.get("encounters", 0),
        defeats=raw.get("defeats", 0),
    )


def build_bestiary_payload(record: BestiaryRecord) -> dict:
    """도감 한 줄을 JSON 딕셔너리로 되돌린다.

    Args:
        record: 되돌릴 도감 기록.

    Returns:
        parse_bestiary_record 가 다시 읽을 수 있는 딕셔너리.
    """
    return {
        "kind_id": record.kind_id,
        "encounters": record.encounters,
        "defeats": record.defeats,
    }


def parse_meta_save(raw: dict) -> MetaSave:
    """메타 세이브 전체를 읽는다.

    태그를 먼저 보고 판정한다. 앞선 버전은 여기서 변환하고, 이 코어보다 새 버전은
    거부한다 — 모르는 필드를 무시하고 저장하면 그 필드가 다음 저장에서 사라진다.

    Args:
        raw: 세이브 파일 전체 딕셔너리.

    Returns:
        정렬 정규화까지 끝난 메타 세이브.

    Raises:
        ValueError: 형식 태그가 없거나 이 코어보다 새 버전인 경우.
    """
    tag = raw.get("format")
    if not isinstance(tag, str):
        raise ValueError("세이브에 형식 태그(format)가 없다")
    version = get_format_version(tag)
    if version > META_FORMAT_VERSION:
        raise ValueError(f"이 코어보다 새 세이브다: {tag} > {META_FORMAT_TAG}")

    records = tuple(parse_bestiary_record(item) for item in raw.get("bestiary", []))
    return MetaSave(
        format_version=version,
        best_floor=raw.get("best_floor", 0),
        unlocked_perceptions=tuple(sorted(raw.get("unlocked_perceptions", []))),
        unlocked_actions=tuple(sorted(raw.get("unlocked_actions", []))),
        bestiary=tuple(sorted(records, key=lambda record: record.kind_id)),
        presets=tuple(parse_preset(item) for item in raw.get("presets", [])),
    )


def build_meta_payload(meta: MetaSave) -> dict:
    """메타 세이브 전체를 JSON 딕셔너리로 되돌린다.

    Args:
        meta: 되돌릴 메타 세이브.

    Returns:
        parse_meta_save 가 다시 읽을 수 있는 딕셔너리. 형식 태그는 항상 현재 값이다.
    """
    return {
        "format": META_FORMAT_TAG,
        "best_floor": meta.best_floor,
        "unlocked_perceptions": list(meta.unlocked_perceptions),
        "unlocked_actions": list(meta.unlocked_actions),
        "bestiary": [build_bestiary_payload(record) for record in meta.bestiary],
        "presets": [build_preset_payload(preset) for preset in meta.presets],
    }
