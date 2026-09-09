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
    # 낀 주무기의 카탈로그 id. **코어는 이것을 읽지 않는다.**
    #
    # 스탯은 이미 위에 녹아 있으므로(결정 #13) 판정에 쓸 자리가 없다. 싣는 이유는
    # **재생이 그 판을 그대로 보여 주려면 무엇을 들고 있었는지 알아야** 하기 때문이다 —
    # 로드아웃이 스탯뿐이라 지나간 판의 무기를 서버도 복원할 수 없었고, 그래서 재생의
    # 칼자국이 사거리로만 갈렸다(도신검과 도끼가 같은 그림이었다).
    #
    # 겉모습이 아니라 **그 판의 사실**이다. 겉모습 표(`item_looks`)는 이 id 를 열쇠로
    # 쓰지만 여전히 화면 쪽에 있고 `core_version` 에 안 낀다 (계약 C1·C2).
    #
    # **서버가 쓰고 클라이언트는 읽기만 한다.** 제출에는 받을 자리가 없다 (설계/7 §4).
    main_weapon: str = ""
    # 시전 축 셋 (설계/5_스킬 §10.7). 유물이 마법의 **제약을 바꾸는** 자리다 —
    # 예고를 줄이고, 이동해도 안 끊기게 하고, 반경을 넓힌다.
    cast_lead_cut: int = 0
    steady_cast: int = 0
    blast_radius: int = 0
    cast_cooldown_add: int = 0


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
        cast_lead_cut=int(raw.get("cast_lead_cut", 0)),
        steady_cast=int(raw.get("steady_cast", 0)),
        blast_radius=int(raw.get("blast_radius", 0)),
        cast_cooldown_add=int(raw.get("cast_cooldown_add", 0)),
        # 정렬해서 담는다 (R5). 없으면 빈손이다 — 구버전 티켓이 그 경우다.
        consumables=tuple(sorted((str(k), int(v)) for k, v in raw.get("consumables", {}).items())),
        # 정렬해서 담는다. 순서가 실행마다 다르면 같은 티켓이 다른 글자로 저장된다 (R5).
        skills=tuple(sorted(raw.get("skills", []))),
        # 없으면 빈 문자열이다 — 싣기 전에 발급된 티켓이 그 경우이고, 그때 화면은
        # 실측 거리로 근사한다.
        main_weapon=str(raw.get("main_weapon", "")),
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
        "cast_lead_cut": loadout.cast_lead_cut,
        "steady_cast": loadout.steady_cast,
        "blast_radius": loadout.blast_radius,
        "cast_cooldown_add": loadout.cast_cooldown_add,
        "consumables": dict(loadout.consumables),
        "skills": list(loadout.skills),
        "main_weapon": loadout.main_weapon,
    }
