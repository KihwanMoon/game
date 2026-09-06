"""한 방에 그림자 하나 (설계/6_몬스터, 2026-09-06).

**DB 없이 돈다.** 고르는 규칙이 맞는지가 여기서 볼 것이고, 그것은 저장소와 무관하다.

밀집이 난이도를 통째로 올렸다 — 빈 스폰 자리가 있는 만큼 섰고, 자리 이름이 방을 안 담아
한 방의 `bomb_slime_0·_1·_2` 가 모두 차면 셋이 같은 방에 섰다. 실측으로 4층에 열한 마리.
"""

from game.api.doppel_pick import (
    build_room_doppels,
    list_floor_rooms,
    list_room_slots,
)
from game.app.store.monsters import MonsterRecord
from game.schemas.room import EnemySpawn, RoomTemplate


def build_record(record_id, catalog_id="goblin_rusher", floor=4, slot="goblin_rusher_0"):
    return MonsterRecord(
        record_id=record_id,
        catalog_id=catalog_id,
        tier="NORMAL",
        zone_floor=floor,
        entity_slot=slot,
        total_xp=0,
        level=1,
        alive=True,
    )


def build_room(kinds):
    return RoomTemplate(
        template_id="probe",
        purpose="fight",
        tiles=((0, 0), (0, 0)),
        player_spawn=(0, 0),
        enemy_spawns=tuple(
            EnemySpawn(kind=kind, position=(index + 1, 1)) for index, kind in enumerate(kinds)
        ),
    )


ROOMS = {
    "a": build_room(["bomb_slime", "bomb_slime", "bomb_slime"]),
    "b": build_room(["goblin_archer"]),
    "c": build_room(["dire_wolf", "dire_wolf"]),
}
ROOM_IDS = ("a", "b", "c")

# 이 층의 모든 자리. 여느 개체가 다 차지하면 그림자가 앉을 데가 없다.
ROOM_SLOTS = sorted(
    {
        slot
        for room_id in ROOM_IDS
        for slot in (
            f"{spawn.kind}_{index}" for index, spawn in enumerate(ROOMS[room_id].enemy_spawns)
        )
    }
)


def pick(records, roll=lambda _n: 0):
    return build_room_doppels(records, ROOMS, ROOM_IDS, 3, 4, roll)


def count_shadows(found):
    return len([one for one in found if one.catalog_id == "doppelganger"])


def test_a_floor_gets_exactly_one_shadow():
    """★ **그림자는 층에 귀속이다.** 그 층에서 죽은 빌드가 그 층을 지킨다.

    방에 매어 두면 「이 층의 주인」이 아니라 「저 방의 몹」이 된다. 방마다 따로 고르던
    때는 4층에 다섯이 섰고 둘이 한 방에 보였다 (실제 신고).
    """
    shadows = [build_record(i, "doppelganger") for i in range(1, 12)]
    assert count_shadows(pick(shadows)) == 1


def test_the_shadow_stands_in_every_room_of_the_floor():
    """★ **모든 방에 선다.** 자리 이름이 곧 그 배정이다.

    공통 자리가 있으면 그것을 골라야 다섯 방 어디서 만나도 같은 그림자다.
    """
    common = {
        "a": build_room(["bomb_slime", "goblin_archer"]),
        "b": build_room(["goblin_archer", "dire_wolf"]),
        "c": build_room(["goblin_archer"]),
    }
    found = build_room_doppels(
        [build_record(1, "doppelganger")], common, ("a", "b", "c"), 3, 4, lambda _n: 0
    )
    shadow = next(one for one in found if one.catalog_id == "doppelganger")
    # goblin_archer_0 만 세 방에 다 있다.
    assert shadow.entity_slot == "goblin_archer_0"


def test_it_falls_back_to_the_widest_slot():
    """공통 자리가 없으면 **가장 많이 걸친 것**을 고른다 — 방 하나에 가두지 않는다."""
    # 자리 이름은 `{종류}_{방 안 순번}` 이다 — 같은 종이라도 순번이 다르면 다른 이름이다.
    spread = {
        "a": build_room(["goblin_archer", "bomb_slime"]),
        "b": build_room(["goblin_archer"]),
        "c": build_room(["dire_wolf"]),
    }
    found = build_room_doppels(
        [build_record(1, "doppelganger")], spread, ("a", "b", "c"), 3, 4, lambda _n: 0
    )
    shadow = next(one for one in found if one.catalog_id == "doppelganger")
    assert shadow.entity_slot == "goblin_archer_0"


def test_a_room_gets_at_most_one_shadow():
    """★ 층당 하나이므로 방당 하나가 저절로 성립한다."""
    shadows = [build_record(i, "doppelganger") for i in range(1, 12)]
    slots = [one.entity_slot for one in pick(shadows) if one.catalog_id == "doppelganger"]
    assert len(slots) == len(set(slots)) == 1


def test_shadows_sit_in_the_room_they_appear_in():
    """★ 저장된 자리는 다른 방의 것일 수 있다.

    스냅샷이 아무에게도 안 붙으면 개체는 있는데 아무도 못 만난다.
    """
    found = pick([build_record(1, "doppelganger", slot="누구의_자리도_아님")])
    assert found[0].entity_slot in list_room_slots(ROOMS, "a")


def test_the_same_shadow_never_appears_twice():
    """★ 두 번 나오면 목숨을 두 번 깎는다 — 「세 번 만나되 약해진다」와 어긋난다."""
    shadows = [build_record(i, "doppelganger") for i in (1, 2, 3)]
    ids = [one.record_id for one in pick(shadows)]
    assert len(ids) == len(set(ids))


def test_fewer_shadows_than_rooms_is_fine():
    found = pick([build_record(1, "doppelganger")])
    assert count_shadows(found) == 1


def test_ordinary_monsters_pass_through():
    """★ 여느 몬스터는 안 건드린다 — 층당 셋 상한은 이미 심을 때 지켜진다."""
    plain = [build_record(i) for i in (1, 2, 3)]
    found = pick(plain)
    assert len(found) == 3
    assert count_shadows(found) == 0


def test_no_shadows_changes_nothing():
    plain = [build_record(1), build_record(2)]
    assert pick(plain) == plain


def test_a_shadow_on_another_floor_is_left_alone():
    """다른 층의 그림자는 그 층의 방에서 고른다 — 여기 방들과 섞이면 안 된다."""
    found = pick([build_record(1, "doppelganger", floor=9)])
    assert count_shadows(found) == 0


def test_the_roll_actually_chooses():
    """★ 굴림이 다르면 다른 그림자가 나온다 — 늘 첫 번째면 자리가 굳는다."""
    shadows = [build_record(i, "doppelganger") for i in (1, 2, 3, 4, 5)]
    first = [
        one.record_id for one in pick(shadows, lambda _n: 0) if one.catalog_id == "doppelganger"
    ]
    last = [
        one.record_id for one in pick(shadows, lambda n: n - 1) if one.catalog_id == "doppelganger"
    ]
    assert first != last


def test_floor_rooms_are_split_by_the_chain():
    assert list_floor_rooms(ROOM_IDS, 3, 0) == ROOM_IDS
    assert list_floor_rooms(("a", "b", "c", "d"), 2, 1) == ("c", "d")
    # 0 이면 전체가 한 층이다.
    assert list_floor_rooms(ROOM_IDS, 0, 0) == ROOM_IDS
    assert list_floor_rooms(ROOM_IDS, 0, 1) == ()


def test_an_unknown_room_has_no_slots():
    """방 목록에 없는 id 로 터지면 티켓 발급이 통째로 죽는다."""
    assert list_room_slots(ROOMS, "없는방") == ()
