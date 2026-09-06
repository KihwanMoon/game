"""방 배치에 없는 개체를 방에 더한다 (설계/6_몬스터, 2026-09-06).

**덮어쓰기로는 모든 방에 못 선다.** 스냅샷은 방 배치의 자리(`{종류}_{순번}`)를 덮어쓰는
방식이라, 그 자리가 없는 방에는 설 자리 자체가 없다 — 실측으로 그림자가 층당 다섯 방 중
두세 방에만 섰다. 다섯 방의 적 구성이 서로 달라 모두에 있는 자리가 없었다.

**그림자는 층에 귀속이다.** 그 층에서 죽은 빌드가 그 층을 지키므로 그 층 **모든 방**에
서야 하고, 그러려면 덮어쓰는 대신 **더해야** 한다.

**무작위를 안 쓴다.** 자리를 굴려 뽑으면 흔들기 축의 호출 횟수가 바뀌어 같은 시드가 다른
판을 낸다 (R5). 규칙은 「플레이어에게서 가장 먼 빈 칸, 같으면 위·왼쪽」 하나뿐이라 두
코어가 같은 답을 낸다.

**있던 판은 안 흔들린다.** 더할 것이 없으면 아무 일도 안 일어난다 — 지금까지 발급된
티켓의 스냅샷은 전부 방 배치의 자리를 쓰므로 골든이 그대로다.
"""

from game.app.simulation.scaling import FloorScale, get_scaled_enemy_stats
from game.app.simulation.state import FACTION_ENEMY, TIER_NORMAL, Entity
from game.schemas.monster_snapshot import MonsterSnapshot, check_is_extra_slot
from game.schemas.room import WALKABLE_TILES, RoomTemplate


def compute_far_rank(spot: tuple[int, int], origin: tuple[int, int]) -> tuple[int, int, int]:
    """멀수록 앞에 오는 정렬 키.

    **체비셰프 거리**를 쓴다 — 이 격자의 이동이 여덟 방향으로 열릴 수 있고, 그때 「몇
    걸음인가」가 곧 이 값이다. 같으면 위·왼쪽이 이긴다: 순서를 못 박아야 두 코어가 같은
    칸을 고른다.

    Args:
        spot: 볼 칸.
        origin: 기준 칸. 플레이어가 선 자리다.

    Returns:
        정렬 키. 작을수록 앞이며 첫 항은 거리의 음수다.
    """
    far = max(abs(spot[0] - origin[0]), abs(spot[1] - origin[1]))
    return (-far, spot[1], spot[0])


def find_far_spot(
    template: RoomTemplate, taken: set[tuple[int, int]], origin: tuple[int, int]
) -> tuple[int, int] | None:
    """플레이어에게서 가장 먼 빈 칸.

    **가장 먼 칸이어야 한다.** 아무 빈 칸이나 주면 더해진 개체가 플레이어 코앞에 서고,
    그러면 규칙표가 손쓸 새 없이 첫 틱에 맞는다 — 더하는 것이 곧 처형이 된다.

    Args:
        template: 방 템플릿.
        taken: 이미 누가 선 칸들.
        origin: 기준 칸.

    Returns:
        설 칸. 빈 칸이 없으면 None.
    """
    free = [
        (x, y)
        for y in range(template.height)
        for x in range(template.width)
        if (x, y) not in taken and template.get_tile(x, y) in WALKABLE_TILES
    ]
    if not free:
        return None
    return min(free, key=lambda spot: compute_far_rank(spot, origin))


def list_extra_slots(overrides: dict, consumed: set[str]) -> tuple[str, ...]:
    """방 배치가 안 쓴 스냅샷 자리들 중 **더해야 하는 것**.

    **아무것이나 더하면 안 된다.** 그 층의 지속 몬스터는 자기 자리를 덮어쓰는 개체라,
    자리가 없는 방에 더하면 그 방의 적이 늘어난다 — 실제로 세계 몬스터(w1·w2·w3)가 모든
    방에 더해져 방당 둘이 다섯이 됐다 (실제 신고).

    **정렬해서 낸다.** 딕셔너리 순회 순서로 자리를 정하면 같은 티켓이 두 번 다른 판을
    낸다 (R5).

    Args:
        overrides: 이 층의 스냅샷들. 자리 이름에서 스냅샷으로.
        consumed: 방 배치가 이미 쓴 자리 이름들.

    Returns:
        더할 자리 이름들. 정렬돼 있다.
    """
    return tuple(
        sorted(slot for slot in overrides if slot not in consumed and check_is_extra_slot(slot))
    )


def build_enemy_entity(
    entity_id: str,
    kind: dict,
    found: MonsterSnapshot | None,
    scale: FloorScale,
    floor: int,
    spot: tuple[int, int],
) -> Entity:
    """적 하나를 만든다.

    **방 배치가 부르는 자리와 더해서 세우는 자리가 같은 코드를 쓴다.** 갈라 두면 얼려 둔
    상태가 한쪽에만 붙고, 그 사실이 조용히 넘어간다.

    지속 몬스터가 이 자리에 있으면 얼려 둔 상태가 층 스케일을 **대체한다.** 얹으면 같은
    개체가 층마다 다른 값을 갖게 되어 스냅샷의 뜻이 사라진다.

    **키트도 얼려 둔 것을 쓴다.** 스탯 셋만 대체하던 때는 장궁 든 봇의 그림자가 사거리 1
    근접으로 싸웠다 — 빌드에서 가장 그 빌드다운 것이 빠졌다. 안 실린 값은 종의 것을
    그대로 쓰므로 옛 티켓은 예전과 똑같이 재시뮬된다 (R5).

    Args:
        entity_id: 자리 이름.
        kind: 종의 밸런스 절.
        found: 이 자리의 스냅샷. 없으면 None.
        scale: 층 스케일.
        floor: 이 방의 층.
        spot: 설 칸.

    Returns:
        만들어진 개체.
    """
    hp_max, attack = get_scaled_enemy_stats(kind, scale, floor)
    defense = kind["defense"]
    cpu_budget = kind.get("cpu_budget", 0)
    attack_range = kind["attack_range"]
    potions = int(kind.get("potions", 0))
    # None 은 「장착 개념이 안 배선됨 = 전부 허용」이다. 빈 튜플(아무것도 없음)과 뜻이
    # 반대라, 스냅샷의 빈 것은 **모른다**로 읽어 None 으로 둔다.
    skills: tuple[str, ...] | None = None
    if found is not None:
        hp_max, attack, defense, cpu_budget = (
            found.hp_max,
            found.attack,
            found.defense,
            found.cpu_budget,
        )
        attack_range = found.attack_range or attack_range
        potions = found.potions if found.potions >= 0 else potions
        skills = found.skills or None
    return Entity(
        entity_id=entity_id,
        kind_id=kind["id"],
        faction=FACTION_ENEMY,
        position=spot,
        hp=hp_max,
        hp_max=hp_max,
        attack=attack,
        defense=defense,
        attack_range=attack_range,
        initiative=kind["initiative"],
        regen_base=kind["regen_base"],
        cpu_budget=cpu_budget,
        consumables={"POTION": potions},
        skills=skills,
        tier=str(kind.get("tier", TIER_NORMAL)),
    )
