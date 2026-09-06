"""몬스터 스냅샷 — 지속 몬스터를 런 등식 **안에** 넣는 장치 (docs/설계/6_몬스터 §5).

이 게임의 전부는 이 등식이다.

    런 결과 = f(시드, 규칙표, 코어 버전)

리플레이·데일리 챌린지·헤드리스 밸런싱·서버 재검증이 전부 여기 얹혀 있다. 그런데 여러
플레이어가 공유하는 살아 있는 몬스터는 시드에서 나오지 않는 **세계 상태**다.

**해법: 런이 시작될 때 그 상태를 티켓에 얼려 넣는다.**

    런 결과 = f(시드, 규칙표, 코어 버전, 스냅샷)
                                     └─ 티켓에 박혀 있으므로 재현된다

등식이 유지되고, 서버는 같은 스냅샷으로 재시뮬해 검증할 수 있으며, 두 플레이어가 같은
개체를 동시에 상대해도 각자 같은 스냅샷을 본다. 오프라인 플레이도 살아남는다 — 티켓만
받아 두면 전투는 브라우저에서 돈다.

**클라이언트는 스냅샷을 되보내지 않는다.** 서버가 `ticket_id` 로 자기가 발급한 것을
조회한다 — 받으면 약한 스냅샷으로 바꿔 제출할 수 있다 (docs/설계/7_변조방지 T8).
"""

from dataclasses import dataclass

# 엔티티 id 를 만드는 규칙. 방 배치가 `{kind}_{index}` 로 붙이므로 스냅샷도 같은 이름을
# 겨냥한다 — 이름이 갈리면 스냅샷이 아무에게도 적용되지 않고, 그 사실이 조용히 넘어간다.
ENTITY_ID_SEPARATOR = "_"


@dataclass(frozen=True)
class MonsterSnapshot:
    """지속 몬스터 하나의 얼어붙은 상태.

    스탯을 직접 담는다. 레벨과 곡선만 담고 클라이언트가 계산하게 하면, 곡선을 고치는
    순간 발급된 티켓들이 다른 몬스터를 가리키게 된다.
    """

    entity_id: str
    record_id: int
    kind_id: str
    tier: str
    level: int
    hp_max: int
    attack: int
    defense: int
    rule_slots: int
    cpu_budget: int
    # 이 개체가 사는 층. **자리 이름이 층을 구분하지 않는다** — `goblin_rusher_0` 이
    # 1층부터 9층까지 따로 살고, 하강 티켓은 그 전부를 싣는다. 층이 없으면 방에 얹을 때
    # 이름만 보고 겹치게 되어 **1층 방에 9층 개체가 선다** (실측: 신규가 첫 방에서
    # 레벨 10 짜리를 만났다).
    #
    # 0 은 「모른다」다. 층을 싣기 전에 발급된 티켓이 그 값이며, 그 티켓은 예전처럼
    # 층을 안 보고 얹는다 — 발급 당시와 다르게 재시뮬하면 정상 제출이 반려된다 (R5).
    zone_floor: int = 0
    # 이 개체가 실제로 닿는 거리. **0 은 「안 실렸다」**이고 그때는 종의 값을 쓴다.
    #
    # 도플갱어 때문에 생겼다. 스탯 셋만 실으니 **장궁 든 봇의 그림자가 사거리 1 근접**으로
    # 싸웠다 — 빌드에서 가장 그 빌드다운 것이 빠진 채 숫자만 큰 몹이 됐다. 사거리는
    # 주무기가 정하고(`items/loadout.replace_range`) 그 주무기는 얼려 뒀는데, 나르는 칸이
    # 없어서 버려지고 있었다.
    attack_range: int = 0
    # 이 개체가 쓸 수 있는 스킬. **빈 튜플은 「안 실렸다」**이고 그때는 종의 규칙을 쓴다.
    #
    # `Entity.skills` 는 None 이 「전부 허용」이고 빈 튜플이 「아무것도 없음」이라 뜻이
    # 반대다 — 여기서 빈 것은 **모른다**이므로 None 으로 옮긴다. 그렇게 해야 스킬을 안
    # 싣던 옛 티켓이 예전과 똑같이 재시뮬된다 (R5).
    skills: tuple[str, ...] = ()
    # 들고 들어가는 물약 수. **-1 이 「안 실렸다」**다 — 0 은 「없다」라는 진짜 값이라
    # 구분해야 한다. 안 실렸으면 종의 기본값을 쓴다.
    potions: int = -1
    # 이 개체 **하나만의** 규칙표. None 이면 종의 표를 쓴다.
    #
    # 도플갱어의 뜻이 여기 걸린다 — 「그 규칙표가 나를 읽는다」가 이 개체의 전부인데,
    # 나르는 칸이 없어서 모든 그림자가 종의 기본표(`ai_veteran`) 하나로 싸웠다. 저장은
    # 되고 있었고(`entity_record.ruleset_json`) 관리자 화면만 그것을 읽었다.
    #
    # **개체마다 다르므로 티켓이 싣는다.** 서버가 조회해 얼려 넣는 다른 값과 같은 이유다:
    # 클라이언트가 되보내면 약한 규칙표로 바꿔 제출할 수 있다 (T8).
    ruleset: dict | None = None


# 도플갱어의 자리 이름 머리 (2026-09-06).
#
# **자리 이름 규약이라 스키마의 것이다.** 코어는 이 머리로 「방 배치에 없어도 더해야 하는
# 개체」를 가른다 — 그 판단을 `app/bots` 에 두면 코어가 봇 계층을 알게 된다.
#
# 더하는 것이 도플갱어뿐인 이유: 그림자만 층에 귀속이고 그 층 모든 방에 서야 한다. 여느
# 지속 몬스터는 자기 자리를 덮어쓰는 개체라, 자리가 없는 방에 더하면 그 방의 적이 늘어난다
# — 실제로 세계 몬스터(w1·w2·w3)가 모든 방에 더해져 방당 다섯이 됐다.
DOPPEL_SLOT_PREFIX = "doppel_"


def check_is_extra_slot(slot: str) -> bool:
    """방 배치에 없어도 방에 **더해야** 하는 자리인가.

    Args:
        slot: 자리 이름.

    Returns:
        더해야 하면 True.
    """
    return slot.startswith(DOPPEL_SLOT_PREFIX)


def build_entity_id(kind_id: str, index: int) -> str:
    """방 배치와 같은 규칙으로 엔티티 id 를 만든다.

    Args:
        kind_id: 적 종류 id.
        index: 배치 순번.

    Returns:
        `goblin_rusher_0` 형태의 id.
    """
    return f"{kind_id}{ENTITY_ID_SEPARATOR}{index}"


def parse_snapshot(raw: dict) -> MonsterSnapshot:
    """스냅샷 한 줄을 읽는다.

    Args:
        raw: 스냅샷 절.

    Returns:
        만들어진 스냅샷.
    """
    return MonsterSnapshot(
        entity_id=str(raw["entity_id"]),
        record_id=int(raw["record_id"]),
        kind_id=str(raw["kind_id"]),
        tier=str(raw["tier"]),
        level=int(raw["level"]),
        hp_max=int(raw["hp_max"]),
        attack=int(raw["attack"]),
        defense=int(raw["defense"]),
        rule_slots=int(raw["rule_slots"]),
        cpu_budget=int(raw["cpu_budget"]),
        zone_floor=int(raw.get("zone_floor", 0)),
        attack_range=int(raw.get("attack_range", 0)),
        # 정렬해서 담는다. 집합·딕셔너리 순회가 게임 상태로 새면 두 코어가 갈린다 (R5).
        skills=tuple(sorted(str(one) for one in raw.get("skills") or ())),
        potions=int(raw.get("potions", -1)),
        ruleset=raw.get("ruleset") or None,
    )


def build_snapshot_payload(snapshot: MonsterSnapshot) -> dict:
    """스냅샷 한 줄을 절로 되돌린다.

    Args:
        snapshot: 되돌릴 스냅샷.

    Returns:
        `parse_snapshot` 이 다시 읽을 수 있는 절.
    """
    return {
        "entity_id": snapshot.entity_id,
        "record_id": snapshot.record_id,
        "kind_id": snapshot.kind_id,
        "tier": snapshot.tier,
        "level": snapshot.level,
        "hp_max": snapshot.hp_max,
        "attack": snapshot.attack,
        "defense": snapshot.defense,
        "rule_slots": snapshot.rule_slots,
        "cpu_budget": snapshot.cpu_budget,
        "zone_floor": snapshot.zone_floor,
        "attack_range": snapshot.attack_range,
        "skills": list(snapshot.skills),
        "potions": snapshot.potions,
        "ruleset": snapshot.ruleset,
    }


def sort_snapshots(snapshots: tuple[MonsterSnapshot, ...]) -> tuple[MonsterSnapshot, ...]:
    """스냅샷을 순서대로 세운다.

    순서가 실행마다 다르면 같은 티켓이 다른 글자로 저장되고, 그 위에서 만든 검증이
    흔들린다 (R5).

    **entity_id 만으로는 순서가 정해지지 않는다.** 같은 이름이 층마다 있어서 동률이
    생기고, 동률에서는 들어온 순서가 남는다 — 그것은 DB 조회 순서이지 계약이 아니다.
    층과 레코드 id 까지 넣어 전순서로 만든다.

    Args:
        snapshots: 정렬할 스냅샷들.

    Returns:
        (entity_id, 층, 레코드 id) 순으로 정렬된 스냅샷들.
    """
    return tuple(
        sorted(snapshots, key=lambda item: (item.entity_id, item.zone_floor, item.record_id))
    )
