"""플레이어 로드아웃 — 장비·레벨이 확정한 전투 입력 (결정 #13).

**장비는 전투 전에 캐릭터로 녹는다.** 규칙표는 캐릭터만 읽고 장비를 직접 보지 않는다
(결정 #13) — 그래서 장비 전용 DSL 블록이 없고, 사거리가 바뀌면 같은 규칙표가 저절로
다르게 돈다.

문제는 **장비를 서버가 알고 전투를 브라우저가 돈다**는 것이다. 몬스터 스냅샷과 같은
상황이며 같은 방법으로 푼다 — 런이 시작될 때 확정해 티켓에 얼려 넣는다.

    런 결과 = f(시드, 규칙표, 코어 버전, 몬스터 스냅샷, **로드아웃**)

넣지 않으면 화면은 맨몸으로 싸우고 서버는 장비를 낀 채로 재시뮬한다. 그러면 검증이
언제나 어긋나거나, 더 나쁘게는 서버 결과가 조용히 정본이 된다.

**최종 스탯을 담는다.** 장비 목록과 합산 규칙을 담고 클라이언트가 계산하게 하면,
합산을 고치는 순간 이미 발급된 티켓들이 다른 캐릭터를 가리키게 된다.
"""

from dataclasses import dataclass

# 아무것도 안 껴도 언제나 쓸 수 있는 스킬. 기본 공격과 두 스킬은 캐릭터의 것이지
# 장비의 것이 아니다 — 여기서 빼면 맨몸 플레이어가 아무 행동도 못 한다.
BASE_SKILLS: tuple[str, ...] = ("ATTACK", "SKILL_1", "SKILL_2")

# 스킬위력의 기준값. 100 이 "계수 그대로" 다.
BASE_SKILL_POWER_PCT = 100


@dataclass(frozen=True)
class PlayerLoadout:
    """런 하나의 플레이어 전투 입력. 티켓이 얼려 둔 값이다."""

    hp_max: int
    attack: int
    defense: int
    attack_range: int
    initiative: int
    cpu_budget: int
    rule_slots: int
    # 이 캐릭터가 내는 스킬의 위력. 정수 퍼센트로 100 이 "계수 그대로" 다 (결정 #51).
    # 지능이 여기를 올린다.
    skill_power_pct: int
    skills: tuple[str, ...]
    # 이 런에 들고 들어가는 소모품. 종류에서 개수로 (#54).
    #
    # **장비와 같은 이유로 티켓이 싣는다.** 인벤토리는 서버가 알고 전투는 브라우저가
    # 도므로, 얼려 두지 않으면 화면은 빈손으로 싸우고 서버는 주머니를 채운 채 재시뮬한다.
    # 정렬된 쌍으로 담는 이유는 딕셔너리 순회 순서가 티켓에 새어 나가면 안 되기 때문이다 (R5).
    consumables: tuple[tuple[str, int], ...] = ()


def parse_loadout(raw: dict) -> PlayerLoadout:
    """로드아웃 절을 읽는다.

    Args:
        raw: 로드아웃 절.

    Returns:
        만들어진 로드아웃.
    """
    return PlayerLoadout(
        hp_max=int(raw["hp_max"]),
        attack=int(raw["attack"]),
        defense=int(raw["defense"]),
        attack_range=int(raw["attack_range"]),
        initiative=int(raw["initiative"]),
        cpu_budget=int(raw["cpu_budget"]),
        rule_slots=int(raw["rule_slots"]),
        # 없으면 기준값이다. 구버전 티켓이 남아 있어도 그것이 "위력 0" 이 되면
        # 그 티켓으로 돌린 판이 전부 최소피해로 끝난다.
        skill_power_pct=int(raw.get("skill_power_pct", BASE_SKILL_POWER_PCT)),
        # 정렬해서 담는다 (R5). 없으면 빈손이다 — 구버전 티켓이 그 경우다.
        consumables=tuple(sorted((str(k), int(v)) for k, v in raw.get("consumables", {}).items())),
        # 정렬해서 담는다. 순서가 실행마다 다르면 같은 티켓이 다른 글자로 저장된다 (R5).
        skills=tuple(sorted(raw.get("skills", []))),
    )


def build_loadout_payload(loadout: PlayerLoadout) -> dict:
    """로드아웃을 절로 되돌린다.

    Args:
        loadout: 되돌릴 로드아웃.

    Returns:
        `parse_loadout` 이 다시 읽을 수 있는 절.
    """
    return {
        "hp_max": loadout.hp_max,
        "attack": loadout.attack,
        "defense": loadout.defense,
        "attack_range": loadout.attack_range,
        "initiative": loadout.initiative,
        "cpu_budget": loadout.cpu_budget,
        "rule_slots": loadout.rule_slots,
        "skill_power_pct": loadout.skill_power_pct,
        "consumables": dict(loadout.consumables),
        "skills": list(loadout.skills),
    }
