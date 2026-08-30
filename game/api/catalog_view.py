"""콘텐츠 카탈로그 조회 — 관리자가 **무엇이 들어 있는지** 보는 창.

**읽기 전용이다.** 아이템·적·레벨 곡선은 `resources/*.json` 과 코어 상수이고, 그것은
`core_version` 에 묶여 있다 — 런타임에 바꾸면 이미 발급된 티켓이 다른 게임을 가리키고,
브라우저(빌드에 박힌 JSON)와 서버가 다른 값을 본다 (결정 #06, R5). 고치는 길은 파일을
고쳐 배포하는 것뿐이며, 이 모듈은 그 파일을 **게임이 읽는 그대로** 보여 준다.

같은 소스를 읽는 것이 중요하다. 별도 표를 만들어 두면 화면에 적힌 값과 전투가 쓰는 값이
갈라지고, 그때 이 뷰어는 도움이 아니라 오해의 근원이 된다.
"""

from game.app.progression.attributes import build_attribute_bonus
from game.app.progression.levels import (
    MAX_BONUS_CPU,
    MAX_BONUS_FLAGS,
    MAX_BONUS_RULE_SLOTS,
    build_growth,
    compute_required_xp,
)
from game.schemas.item import Affix

# 곡선을 몇 레벨까지 보여줄 것인가. 상한이 없는 성장이라(결정: 스탯 성장 상한 없음)
# 어딘가에서 끊어야 하고, 표현력 보너스가 전부 상한에 닿는 지점이 자연스러운 끝이다.
CURVE_LEVELS = 25


def format_affix(affix: Affix) -> str:
    """접사 하나를 사람이 읽는 한 줄로 만든다.

    부호를 붙이는 이유는 저주 접사가 음수이기 때문이다 — 「방어 -3」과 「방어 3」이
    같아 보이면 저주가 장점으로 읽힌다 (`설계/4_아이템` §9).

    Args:
        affix: 접사.

    Returns:
        화면에 적을 문자열.
    """
    name = affix.label_ko or affix.stat
    return f"{name} {affix.flat:+d}" if affix.flat else f"{name} {affix.percent:+d}%"


def build_item_rows(catalog: dict) -> list[dict]:
    """아이템 카탈로그를 화면용 줄로 만든다.

    Args:
        catalog: catalog_id 에서 항목으로의 대응표.

    Returns:
        catalog_id 순으로 정렬된 줄들.
    """
    rows = []
    for catalog_id in sorted(catalog):
        entry = catalog[catalog_id]
        rows.append(
            {
                "catalog_id": entry.catalog_id,
                "label_ko": entry.label_ko,
                "kind": str(entry.kind),
                "slot": str(entry.slot) if entry.slot else "",
                "hands": str(entry.hands) if entry.hands else "",
                "grants_skill": entry.grants_skill or "",
                "affixes": [format_affix(a) for a in entry.affixes],
                "requirements": [f"{c.stat} >= {c.minimum}" for c in entry.requirements],
            }
        )
    return rows


def build_enemy_rows(balance: dict) -> list[dict]:
    """적 카탈로그를 화면용 줄로 만든다.

    Args:
        balance: balance.json 을 읽은 딕셔너리.

    Returns:
        id 순으로 정렬된 줄들.
    """
    rows = []
    for kind in sorted(balance["enemies"], key=lambda item: item["id"]):
        rows.append(
            {
                "kind_id": kind["id"],
                "label_ko": kind.get("label_ko", kind["id"]),
                "type": kind["type"],
                "ruleset_id": kind["ruleset_id"],
                "hp_max": int(kind["hp_max"]),
                "attack": int(kind["attack"]),
                "defense": int(kind["defense"]),
                "attack_range": int(kind["attack_range"]),
            }
        )
    return rows


def build_level_curve(counts: tuple[tuple[int, int], ...]) -> list[dict]:
    """레벨 곡선을 실제 분포와 겹쳐서 만든다.

    **겹치는 것이 요점이다.** 곡선만 보면 튜닝할 수 없다 — 사람들이 실제로 어디서
    멈추는지가 보여야 "이 구간이 너무 긴가" 를 물을 수 있다.

    Args:
        counts: (레벨, 인원) 쌍들.

    Returns:
        레벨 오름차순 줄들. 필요 경험치·누적·표현력 보너스·능력치 포인트·인원.
    """
    people = dict(counts)
    rows = []
    total = 0
    for level in range(1, CURVE_LEVELS + 1):
        growth = build_growth(level)
        rows.append(
            {
                "level": level,
                "required_xp": compute_required_xp(level),
                "total_xp": total,
                "bonus_rule_slots": growth.bonus_rule_slots,
                "bonus_cpu": growth.bonus_cpu,
                "bonus_flags": growth.bonus_flags,
                "stat_points": growth.stat_points,
                # 그 포인트를 한 축에 몰았을 때의 공격력. 능력치가 표현력과 달리 상한이
                # 없으므로, 후반에 무엇이 벌어지는지는 이 값이 말해 준다 (#53).
                "attack_if_all_str": build_attribute_bonus({"str": growth.stat_points}).attack,
                "players": people.get(level, 0),
            }
        )
        total += compute_required_xp(level)
    return rows


def build_curve_caps() -> dict:
    """표현력 상한을 함께 보낸다.

    상한 없이 곡선만 보면 그 값이 계속 오르는지 알 수 없다.

    Returns:
        상한 값들.
    """
    return {
        "max_bonus_rule_slots": MAX_BONUS_RULE_SLOTS,
        "max_bonus_cpu": MAX_BONUS_CPU,
        "max_bonus_flags": MAX_BONUS_FLAGS,
    }
