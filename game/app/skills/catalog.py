"""스킬 한 줄을 레코드로 읽는다 (설계/5_스킬 §1).

**평행한 딕셔너리를 하나로 모은다.** 예전에는 `EngineConfig` 가 스킬 속성마다 표를
따로 들었다 — 계수·사거리·쿨타임·회복률·감쇠율·감쇠틱 여섯이다. 속성을 하나 더하면
표가 하나 늘고 그것을 만드는 자리·넘기는 자리·읽는 자리가 함께 늘었으며, 무엇보다
**표끼리 어긋날 수 있었다**: 어떤 스킬이 계수 표에는 있고 쿨타임 표에는 없으면
「쿨타임 0」으로 조용히 돈다.

`shape` 가 이 모듈이 생긴 직접적인 이유다. `skills.json` 은 처음부터 `shape` 를 적고
있었는데 **읽는 코드가 없었고**, 실제 반경은 `actions.AREA_ATTACK_RADIUS = 2` 라는
상수였다 — 같은 개념이 데이터와 코드 두 곳에 있었고 데이터 쪽이 거짓이었다.

여기는 **읽기만 한다.** 무엇을 맞히는지는 `shapes.py` 가, 무엇을 하는지는 실행기가
정한다 (설계/5_스킬 §9 4단계).
"""

from dataclasses import dataclass, field

# 형태의 갈래 (설계/5_스킬 §2). `CONE` 은 아직 안 쓴다 — 쓰는 스킬이 생길 때 더한다.
SHAPE_SINGLE = "SINGLE"
SHAPE_AREA = "AREA"
SHAPE_LINE = "LINE"
SHAPE_SELF = "SELF"

# 형태를 안 적은 스킬의 기본. 예전 스킬 절에는 `shape` 가 없을 수 있고, 그때 한 명을
# 때리는 것이 가장 덜 놀라운 해석이다.
DEFAULT_SHAPE_KIND = SHAPE_SINGLE

# 계수를 안 적은 스킬의 기본. 100 이 「계수 그대로」다.
DEFAULT_COEF_PCT = 100


@dataclass(frozen=True)
class SkillShape:
    """이 스킬이 무엇을 덮는가.

    `radius` 와 `length` 를 함께 두는 이유는 형태마다 쓰는 것이 다르기 때문이다 —
    `AREA` 는 반경을, `LINE` 은 길이를 본다. 갈래마다 클래스를 나누면 읽는 쪽이
    isinstance 로 갈라야 하고, 그것은 데이터로 형태를 늘린다는 이 설계의 반대다.
    """

    kind: str = DEFAULT_SHAPE_KIND
    # 맨해튼 반경. `AREA` 만 쓴다. 0 이면 중심 한 칸이다.
    radius: int = 0
    # 직선 길이. `LINE` 만 쓴다.
    length: int = 0


@dataclass(frozen=True)
class SkillDef:
    """스킬 하나. `skills.json` 의 한 줄이 이것이 된다."""

    skill_id: str
    family: str = ""
    shape: SkillShape = field(default_factory=SkillShape)
    target_faction: str = ""
    coef_pct: int = DEFAULT_COEF_PCT
    cooldown: int = 0
    # 스킬이 자체 사거리를 가지면 그 값. None 이면 엔티티의 `attack_range` 를 쓴다 —
    # 없다고 0 으로 두면 원거리 스킬이 매 틱 「사거리 밖」으로 헛돈다.
    reach: int | None = None
    # 0 이면 즉시. >0 이면 그 틱만큼 예고를 띄운다 (설계/5_스킬 §10).
    telegraph: int = 0
    # 시전 중 **다른 행동을 하면** 취소되는가 (§10.3). 취소가 벌이 아니라 선택이 되는
    # 자리다 — 잠그면 그 틱 동안 규칙표가 안 돈다.
    cancel_on_act: bool = False
    # 시전 중 **맞으면** 취소되는가. 「안전한 자리에서 쏘는가」를 규칙표에 묻는다.
    cancel_on_hit: bool = False
    # 대상 최대 HP 의 정수 퍼센트. 고정값이 아닌 이유는 회복이 덩치에 비례해야 해서다.
    heal_pct: int = 0
    # 받는 피해를 몇 퍼센트 줄이고 몇 틱 유지하는가 (GUARD 계열).
    guard_pct: int = 0
    guard_ticks: int = 0
    tags: tuple[str, ...] = ()


def build_shape(raw: dict | None) -> SkillShape:
    """`shape` 절을 읽는다.

    Args:
        raw: 절. 없으면 기본 형태다.

    Returns:
        읽어 낸 형태.
    """
    if not raw:
        return SkillShape()
    return SkillShape(
        kind=str(raw.get("kind") or DEFAULT_SHAPE_KIND),
        radius=int(raw.get("radius", 0)),
        length=int(raw.get("length", 0)),
    )


def build_skill_def(raw: dict) -> SkillDef:
    """스킬 절 하나를 레코드로 바꾼다.

    **없는 값은 기본값으로 둔다.** 필수로 막으면 스킬 절에 필드를 하나 더할 때마다
    옛 콘텐츠 팩이 통째로 안 읽힌다 — 발행된 팩은 되돌릴 수 없다 (설계/4_아이템 §18).

    Args:
        raw: `skills.json` 의 한 줄.

    Returns:
        읽어 낸 스킬.
    """
    return SkillDef(
        skill_id=str(raw["id"]),
        family=str(raw.get("family") or ""),
        shape=build_shape(raw.get("shape")),
        target_faction=str(raw.get("target_faction") or ""),
        coef_pct=int(raw.get("coef_pct", DEFAULT_COEF_PCT)),
        cooldown=int(raw.get("cooldown", 0)),
        reach=None if raw.get("range") is None else int(raw["range"]),
        telegraph=int(raw.get("telegraph", 0)),
        cancel_on_act=bool(raw.get("cancel_on_act", False)),
        cancel_on_hit=bool(raw.get("cancel_on_hit", False)),
        heal_pct=int(raw.get("heal_pct", 0)),
        guard_pct=int(raw.get("guard_pct", 0)),
        guard_ticks=int(raw.get("guard_ticks", 0)),
        tags=tuple(str(tag) for tag in raw.get("tags", ())),
    )


def load_skill_defs(rows: list[dict]) -> dict[str, SkillDef]:
    """스킬 절 전부를 id 로 찾을 수 있게 담는다.

    Args:
        rows: `skills.json` 의 `skills` 배열.

    Returns:
        id 에서 스킬로의 대응표.
    """
    return {row["id"]: build_skill_def(row) for row in rows}


def find_skill(defs: dict[str, SkillDef], skill_id: str) -> SkillDef:
    """스킬 하나를 찾는다.

    **모르는 id 도 레코드를 돌려준다.** None 을 돌려주면 부르는 쪽마다 없음 처리가
    생기고, 그중 하나가 빠지면 거기서 터진다 — 기본값 레코드는 「아무 특성도 없는
    스킬」이라 뜻이 분명하다.

    Args:
        defs: 스킬 표.
        skill_id: 찾을 id.

    Returns:
        찾은 스킬. 없으면 기본값만 담긴 레코드.
    """
    return defs.get(skill_id) or SkillDef(skill_id=skill_id)
