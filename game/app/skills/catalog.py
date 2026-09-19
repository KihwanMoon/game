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
# **적을 타고 튄다** (2026-09-17 요청). `LINE` 이 「누가 뒤에 서 있는가」를 물었다면
# 이것은 「누가 서로 가까이 있는가」를 묻는다 — 줄을 세울 필요가 없어 1층 배치에서도
# 성립한다. `radius` 가 한 번에 튀는 거리, `hops` 가 몇 번 튀는가다.
SHAPE_CHAIN = "CHAIN"

# 효과의 갈래. 지금은 상태 부여 하나다 — 피해·회복은 평면 필드가 이미 든다.
EFFECT_STATUS = "STATUS"

# 형태를 안 적은 스킬의 기본. 예전 스킬 절에는 `shape` 가 없을 수 있고, 그때 한 명을
# 때리는 것이 가장 덜 놀라운 해석이다.
DEFAULT_SHAPE_KIND = SHAPE_SINGLE

# 계수를 안 적은 스킬의 기본. 100 이 「계수 그대로」다.
DEFAULT_COEF_PCT = 100


@dataclass(frozen=True)
class SkillShape:
    """이 스킬이 무엇을 덮는가.

    `radius` 와 `length` 를 함께 두는 이유는 형태마다 쓰는 것이 다르기 때문이다 —
    `AREA` 는 반경을, `LINE` 은 길이를, `CHAIN` 은 반경과 `hops` 를 함께 본다. 갈래마다
    클래스를 나누면 읽는 쪽이 isinstance 로 갈라야 하고, 그것은 데이터로 형태를 늘린다는
    이 설계의 반대다.
    """

    kind: str = DEFAULT_SHAPE_KIND
    # 맨해튼 반경. `AREA` 가 덮는 범위, `CHAIN` 이 한 번에 튀는 거리다. 0 이면 중심
    # 한 칸이다.
    radius: int = 0
    # 직선 길이. `LINE` 만 쓴다.
    length: int = 0
    # 첫 대상 뒤로 몇 번 더 튀는가. `CHAIN` 만 쓴다. 0 이면 한 명만 맞는다.
    hops: int = 0


# 시전 중 행동 규율 (§10.3). **기본은 잠금이다** — 스킬이 안 적으면 시전 틱 동안
# 규칙표가 안 돈다. 모르는 채로 취소되는 것보다 모르는 채로 버티는 쪽이 낫다:
# 취소는 그 스킬을 **영영 못 쓰게** 만들지만 잠금은 한 번 쓰게 한다.
#
# 넷인 이유는 지금 콘텐츠가 이미 둘을 쓰고 있어서다. 적의 굿은 전부 `FREE`(물러서면서도
# 계속 시전)이고, 셋만 두면 그 행동이 통째로 바뀐다.
CAST_LOCK = "LOCK"  # 규칙표가 안 돈다. 다른 행동 불가, 시전 유지
CAST_HOLD = "HOLD"  # 규칙표는 돌되 끊는 행동이 「불가」가 된다. 왜 못 했는지가 로그에 남는다
CAST_CANCEL = "CANCEL"  # 다른 행동을 고르면 취소된다 (예전 `cancel_on_act: true`)
CAST_FREE = "FREE"  # 다른 행동을 해도 시전이 유지된다 (예전 `cancel_on_act: false`)

# 아는 값 전부. 모르는 값이 데이터로 들어오면 조용히 자유가 되므로 부르는 쪽이 본다.
CAST_ACT_MODES: frozenset[str] = frozenset({CAST_LOCK, CAST_HOLD, CAST_CANCEL, CAST_FREE})


@dataclass(frozen=True)
class SkillEffect:
    """스킬이 맞은 대상에게 얹는 것 하나 (설계/5_스킬 §1).

    **평면 필드를 대신하지 않는다.** `coef_pct`·`heal_pct`·`guard_pct` 는 뜻이 그대로다 —
    거기서 파생시키려던 설계가 반증에서 세 번 깨졌다: `coef_pct: 0` 의 뜻이 단계마다
    바뀌고(피해 0 / 효과 없음 / 기본 100), `find_skill` 의 「모르는 id 에도 레코드」
    폴백이 뒤집히고, 전제 검사가 early return 이라 `[GUARD, DAMAGE]` 가 적이 없을 때
    보호막까지 안 걸렸다. **덧붙이기만 하면 셋 다 성립하지 않는다.**

    **붙는 시점은 예고 발동이다.** 그때는 누가 그 칸에 섰는지 이미 정해져 있어
    「대상이 없어서 못 걸었다」가 생기지 않는다 — early return 문제가 사라지는 자리다.
    """

    kind: str
    # `STATUS` 가 거는 상태 이름 (POISON·SLOW·STUN).
    status: str = ""
    # 몇 틱 유지되는가. UPKEEP 이 매 틱 1씩 깎는다.
    duration: int = 0


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
    # 시전 중 다른 행동을 어떻게 할 것인가 (§10.3, 2026-09-19).
    #
    # **불리언 하나로는 모자랐다.** 예전에는 `cancel_on_act` 였고 뜻이 「다른 행동을 하면
    # 취소」 하나뿐이라 **잠그는 길이 없었다.** 실측으로 예고 3틱인 메테오는 보호 줄이
    # 없으면 60판 중 60판이 취소됐고, 예고 1틱인 연쇄 번개는 끼어들 틱이 0 이라 같은
    # 플래그가 한 번도 안 닿았다 — 한 값이 스킬마다 다른 뜻이 되고 있었다.
    cast_act: str = CAST_FREE
    # 시전 중 **맞으면** 취소되는가. 「안전한 자리에서 쏘는가」를 규칙표에 묻는다.
    cancel_on_hit: bool = False
    # 대상 최대 HP 의 정수 퍼센트. 고정값이 아닌 이유는 회복이 덩치에 비례해야 해서다.
    heal_pct: int = 0
    # 받는 피해를 몇 퍼센트 줄이고 몇 틱 유지하는가 (GUARD 계열).
    guard_pct: int = 0
    guard_ticks: int = 0
    tags: tuple[str, ...] = ()
    # 맞은 대상에게 얹는 것들. **평면 필드에 더해진다** — 대신하지 않는다.
    effects: tuple[SkillEffect, ...] = ()


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
        hops=int(raw.get("hops", 0)),
    )


def build_effect(raw: dict) -> SkillEffect:
    """효과 절 하나를 레코드로 바꾼다.

    Args:
        raw: `effects` 배열의 한 항목.

    Returns:
        읽어 낸 효과.
    """
    return SkillEffect(
        kind=str(raw.get("kind") or ""),
        status=str(raw.get("status") or ""),
        duration=int(raw.get("duration", 0)),
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
        cast_act=str(raw.get("cast_act", CAST_LOCK)),
        cancel_on_hit=bool(raw.get("cancel_on_hit", False)),
        heal_pct=int(raw.get("heal_pct", 0)),
        guard_pct=int(raw.get("guard_pct", 0)),
        guard_ticks=int(raw.get("guard_ticks", 0)),
        tags=tuple(str(tag) for tag in raw.get("tags", ())),
        effects=tuple(build_effect(one) for one in raw.get("effects", ())),
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
