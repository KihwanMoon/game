"""봇이 더 좋은 것으로 갈아 끼운다.

**빈 자리만 채우고 있었다.** 봇은 주운 것을 빈 칸에 넣기만 하고, 나중에 더 좋은 것이
들어와도 벗지 않았다. 그래서 봇의 장비는 첫 몇 판에 굳고, 그 뒤로 경매에서 사 온 유물이
가방에서 사망 페널티에 녹았다.

안 하고 있던 이유가 있었다. **값을 매기는 기준이 틀리면 봇이 좋은 것을 벗고 나쁜 것을
낀다.** 그래서 기준을 새로 지어내지 않고 이미 있는 것 둘을 쓴다.

* **성격**은 `personas.resolve_persona` 가 정한다 — 능력치 배분이 쓰는 것과 같은 표다.
  두 벌이면 봇이 스탯은 사수처럼, 장비는 전사처럼 고르게 된다.
* **퍼센트를 값으로 바꾸는 기준**은 `balance.json` 의 플레이어 기본값이다. 환산 상수를
  지어내지 않는다 — 실제 합산식이 쓰는 바로 그 값이다 (`(기본 + 고정) × (1 + %)`).

**근소한 차이로는 안 바꾼다.** 벗은 것은 가방으로 가고, 가방에 있는 것은 죽을 때
**삭제**된다 (결정 #34). 1점 이득을 보려고 바꾸면 그 1점보다 큰 것을 잃을 수 있다.

**양손 자리는 건드리지 않는다.** 양손무기가 보조 칸을 봉인하므로(`items/stats.py`) 그
자리의 교체는 두 칸을 동시에 보는 판단이고, 한 칸씩 보는 이 규칙으로는 틀린다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from game.app.bots.personas import resolve_persona

PERCENT_BASE = 100

# 성격이 장비에서 무엇을 보는가. 능력치 배분(str/dex/int)과 축이 다른 이유는 접사가
# 전투 수치에 붙기 때문이다 — 같은 성격을 두 축으로 옮긴 표이지 새 성격이 아니다.
#
# **여기 없는 스탯은 0 이다.** 소모품 칸처럼 판단이 갈리는 것을 빼 두면, 「물약 칸 +1」
# 하나로 무기를 바꾸는 일이 안 생긴다.
STAT_WEIGHTS: dict[str, dict[str, int]] = {
    # 사거리 한 칸이 무겁다. 기본 사거리가 1 이라 +1 은 **닿는 거리를 두 배로**
    # 만들고, 그것이 곧 「맞지 않고 때린다」의 성립 여부다 — 공격 +4 와 맞바꿀 값이다.
    "ranged": {"attack_range": 8, "attack": 2, "initiative": 2, "hp_max": 1, "defense": 1},
    "caster": {"cpu_budget": 4, "initiative": 2, "hp_max": 2, "attack": 1, "defense": 1},
    "melee": {"attack": 3, "hp_max": 2, "defense": 2, "initiative": 1},
}

# **사람이 고르는 우선순위 — 값은 파일에 있다.**
#
# `game/resources/balance/gear_priority.json` 하나를 파이썬과 브라우저가 **직접** 읽는다.
# 여기 상수로 박아 두면 미리보기가 「2개 교체」라 적고 서버는 3개를 바꾸는 일이 생기고,
# 그때 어느 쪽이 맞는지 물으면 답할 사람이 없다 — 사본을 두지 않는 것이 이 저장소의
# 규율이다 (CLAUDE.md 의 `@resources`).
#
# 봉인된 자산이 아니다. 전투 시뮬레이션에 안 들어가므로 고쳐도 지나간 판의 재현성이
# 깨지지 않고, core_version 도 안 움직인다.
_PRIORITY_PATH = (
    Path(__file__).resolve().parents[2] / "resources" / "balance" / "gear_priority.json"
)
_PRIORITY_FILE = json.loads(_PRIORITY_PATH.read_text(encoding="utf-8"))

GEAR_PRIORITY_WEIGHTS: dict[str, dict[str, int]] = {
    name: {stat: value for stat, value in table.items() if isinstance(value, int)}
    for name, table in _PRIORITY_FILE["priorities"].items()
}

# 이만큼은 이겨야 바꾼다. 벗은 것이 가방에서 삭제될 수 있으므로 근소한 차이는 손해다.
# 이 값도 파일에서 온다 — 미리보기가 같은 여유폭으로 세야 같은 답을 낸다.
UPGRADE_MARGIN: int = int(_PRIORITY_FILE["margin"])

# 교체 판단에서 빼는 자리. 양손무기가 보조 칸을 봉인해 두 칸을 함께 봐야 한다.
TWO_HANDED_SLOTS = frozenset(_PRIORITY_FILE["two_handed_slots"])


@dataclass(frozen=True)
class GearItem:
    """값을 매길 장비 하나."""

    item_id: int
    slot: str
    can_equip: bool
    is_broken: bool
    hands: str
    affixes: tuple[tuple[str, int, int], ...]
    attack_range: int


def compute_item_score(item: GearItem, persona: str, base_stats: dict[str, int]) -> int:
    """이 봇에게 이 장비가 얼마나 값하는가.

    **퍼센트를 실제 합산식과 같은 방식으로 값으로 바꾼다** — `기본값 × % / 100`. 환산
    상수를 지어내면 그 상수가 곧 아무도 안 정한 밸런스 결정 하나가 된다.

    정수만 쓴다. 곱한 뒤에 나눈다 (R5).

    Args:
        item: 값을 매길 장비.
        persona: 이 봇의 성격.
        base_stats: 플레이어 기본 스탯. 퍼센트를 값으로 바꾸는 기준이다.

    Returns:
        점수. 클수록 이 봇에게 좋다. 저주 접사가 있으면 음수일 수 있다.
    """
    return compute_weighted_score(
        item, STAT_WEIGHTS.get(persona, STAT_WEIGHTS["melee"]), base_stats
    )


def compute_weighted_score(
    item: GearItem, weights: dict[str, int], base_stats: dict[str, int]
) -> int:
    """저울을 직접 받아 값을 매긴다.

    **성격표에서 갈라 나왔다.** 봇은 성격으로 저울을 고르고 사람은 우선순위로 고르는데,
    저울을 고르는 방식이 다를 뿐 **재는 방식은 같아야 한다** — 두 벌로 두면 같은 장비가
    봇 화면과 정비 미리보기에서 다른 값을 갖는다.

    Args:
        item: 값을 매길 장비.
        weights: 스탯에서 무게로. 여기 없는 스탯은 0 이다.
        base_stats: 플레이어 기본 스탯. 퍼센트를 값으로 바꾸는 기준이다.

    Returns:
        점수. 클수록 좋다. 저주 접사가 있으면 음수일 수 있다.
    """
    total = 0
    for stat, flat, percent in item.affixes:
        weight = weights.get(stat, 0)
        if weight == 0:
            continue
        total += weight * (flat + base_stats.get(stat, 0) * percent // PERCENT_BASE)
    # 무기가 정하는 사거리는 접사가 아니라 필드다 (§2.2). 안 세면 활과 단검이 같아진다.
    total += weights.get("attack_range", 0) * item.attack_range
    return total


def find_upgrades(
    bag: tuple[GearItem, ...],
    worn: tuple[GearItem, ...],
    ruleset_id: str,
    base_stats: dict[str, int],
) -> tuple[tuple[GearItem, GearItem], ...]:
    """자리마다 갈아 낄 짝을 고른다.

    **찬 자리만 본다.** 빈 자리는 `list_equippable` 이 채운다 — 두 곳이 같은 자리를
    노리면 한 번에 두 번 끼우려다 하나가 거절당한다.

    Args:
        bag: 가방 속 장비들.
        worn: 지금 입고 있는 것들.
        ruleset_id: 이 봇의 규칙표. 성격을 여기서 읽는다.
        base_stats: 플레이어 기본 스탯.

    Returns:
        (벗을 것, 낄 것) 짝들. 자리 이름 순이다.
    """
    persona = resolve_persona(ruleset_id)
    return find_upgrades_by_weights(
        bag, worn, STAT_WEIGHTS.get(persona, STAT_WEIGHTS["melee"]), base_stats
    )


def find_upgrades_by_weights(
    bag: tuple[GearItem, ...],
    worn: tuple[GearItem, ...],
    weights: dict[str, int],
    base_stats: dict[str, int],
) -> tuple[tuple[GearItem, GearItem], ...]:
    """저울을 직접 받아 갈아 낄 짝을 고른다.

    Args:
        bag: 가방 속 장비들.
        worn: 지금 입고 있는 것들.
        weights: 스탯에서 무게로.
        base_stats: 플레이어 기본 스탯.

    Returns:
        (벗을 것, 낄 것) 짝들. 자리 이름 순이다.
    """
    wearing = {item.slot: item for item in worn if item.slot}
    # 자리에서 (벗을 것, 낄 것, 낄 것의 점수) 로. 점수를 들고 다니는 이유는 같은 값을
    # 후보마다 세 번 다시 재지 않기 위해서다.
    best: dict[str, tuple[GearItem, GearItem, int]] = {}
    for candidate in bag:
        if not candidate.can_equip or candidate.is_broken or not candidate.slot:
            continue
        if candidate.slot in TWO_HANDED_SLOTS or candidate.hands == "TWO":
            continue
        current = wearing.get(candidate.slot)
        if current is None or current.is_broken:
            continue
        score = compute_weighted_score(candidate, weights, base_stats)
        if score - compute_weighted_score(current, weights, base_stats) < UPGRADE_MARGIN:
            continue
        # 같은 자리에 후보가 여럿이면 제일 나은 것 하나. 동점이면 먼저 본 쪽이 남는다 —
        # 가방 순서가 곧 id 순이라, 순서가 흔들리면 같은 가방에서 다른 몸이 나간다.
        found = best.get(candidate.slot)
        if found is None or score > found[2]:
            best[candidate.slot] = (current, candidate, score)
    return tuple((best[slot][0], best[slot][1]) for slot in sorted(best))
