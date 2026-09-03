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
