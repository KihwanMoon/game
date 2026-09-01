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
from game.schemas.item import Affix, format_stat_label

# 곡선을 몇 레벨까지 보여줄 것인가. 상한이 없는 성장이라(결정: 스탯 성장 상한 없음)
# 어딘가에서 끊어야 하고, 표현력 보너스가 전부 상한에 닿는 지점이 자연스러운 끝이다.
CURVE_LEVELS = 25


def build_affix_view(affix: Affix) -> dict:
    """접사 하나를 화면이 읽는 절로 만든다.

    **한글 이름을 여기서 붙인다.** 자리마다 따로 붙이면 한 화면만 빠뜨렸을 때 거기서만
    영어 키가 보이고, 그 사실이 그 화면을 열기 전까지 안 드러난다.

    `schemas.item.build_item_payload` 와 다르다 — 저쪽은 파일로 나가는 절이라 화면용
    이름이 섞이면 다시 읽을 때 카탈로그에 눌러앉는다.

    Args:
        affix: 접사.

    Returns:
        화면용 절.
    """
    return {
        "stat": affix.stat,
        "flat": affix.flat,
        "percent": affix.percent,
        "label_ko": affix.label_ko,
        "stat_label": format_stat_label(affix.stat),
    }


def format_affix(affix: Affix) -> str:
    """접사 하나를 사람이 읽는 한 줄로 만든다.

    **무엇을 올리는지 병기한다.** 「튼튼함 +8」 만 적으면 8 이 체력인지 방어력인지 화면
    어디에도 없다 — 조건문에 각 항의 실측값을 병기하는 것과 같은 규칙이다 (GDD §8.2).

    부호를 붙이는 이유는 저주 접사가 음수이기 때문이다 — 「방어 -3」과 「방어 3」이
    같아 보이면 저주가 장점으로 읽힌다 (`설계/4_아이템` §9).

    Args:
        affix: 접사.

    Returns:
        「튼튼함 · 최대체력 +8」. 이름이 없거나 능력치 이름 그대로면 능력치만 적는다 —
        「공격력 · 공격력 +3」 은 아무것도 더 말해 주지 않고, 관리자가 이름 칸을 비웠을
        때 영어 키가 그대로 새어 나오던 자리이기도 하다.
    """
    label = format_stat_label(affix.stat)
    amount = f"{affix.flat:+d}" if affix.flat else f"{affix.percent:+d}%"
    name = affix.label_ko
    if not name or name in (affix.stat, label):
        return f"{label} {amount}"
    return f"{name} · {label} {amount}"


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
                # 사거리는 무기를 고를 때 첫 번째로 궁금한 값이다 (§2.2). 접사였을 때는
                # 「먼 사거리 +3」 처럼 보여서 무엇에 더하는 3 인지 알 수 없었다.
                "attack_range": entry.attack_range or 0,
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
