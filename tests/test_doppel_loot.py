"""도플갱어는 전리품을 만들지 않는다 (결정 #02·#34, T11).

**이것이 뚫리면 봇이 파밍 도구가 된다.** 도플갱어는 봇의 빌드에서 나오므로, 잡았을 때
무엇이든 떨어지면 봇이 벌어 둔 것을 사람에게 건네는 통로가 된다 — 아이템이 세계에
들어오는 문은 검증된 런 하나뿐이라는 결정이 그 자리에서 뚫리고, 봇을 여럿 돌려 죽이는
것이 최적 전략이 된다.

아이템이 도플갱어를 거쳐 사람에게 갈 수 있는 길은 셋이다. 셋 다 여기서 막혀 있는지 본다.
"""

import contextlib

from game.app.bots.doppel import DOPPEL_KIND_ID, build_doppel_slot, check_is_doppel


def test_the_doppel_kind_is_recognised():
    """종 판정이 이름 하나에 걸려 있다 — 그것이 세 길목 전부의 열쇠다."""
    assert check_is_doppel(DOPPEL_KIND_ID)
    assert not check_is_doppel("goblin_rusher")
    assert not check_is_doppel("")


def test_the_doppel_slot_does_not_collide_with_room_slots():
    """자리 이름이 방 템플릿의 슬롯과 겹치면 그 자리의 몬스터가 조용히 덮인다."""
    from game.config import ROOM_TEMPLATES_PATH
    from game.schemas.monster_snapshot import build_entity_id
    from game.schemas.room import load_room_templates

    taken = {
        build_entity_id(spawn.kind, index)
        for template in load_room_templates(ROOM_TEMPLATES_PATH)
        for index, spawn in enumerate(template.enemy_spawns)
    }
    assert build_doppel_slot(12) not in taken


def test_a_doppel_kill_rolls_no_drop(monkeypatch):
    """★ 길 1 — 처치 드롭. 굴리지 않는다.

    빈 드롭 표로 대신하지 않는다. 비어 있는 표는 나중에 누가 채울 수 있는 **데이터**이고,
    이것은 채울 수 없는 **코드**다.
    """
    from game.api import loot_service

    def fail_on_roll(*_args, **_kwargs):
        raise AssertionError("도플갱어에서 드롭을 굴렸다")

    # 굴림 아래의 전부를 터지게 해 둔다 — 통과했다면 반드시 여기에 닿는다.
    monkeypatch.setattr(loot_service, "get_pool", fail_on_roll)
    context = {"kind_id": DOPPEL_KIND_ID, "level": 9, "floor": 5, "submission_id": 1}
    assert loot_service.create_kill_drop(1, 1, context) == ""


def test_a_normal_kill_still_reaches_the_roll(monkeypatch):
    """★ 반대쪽도 본다 — 일반 몬스터는 굴림에 닿는다.

    이것이 없으면 위 검사는 「드롭이 아예 안 돈다」와 구별되지 않는다.
    """
    from game.api import loot_service

    reached = []

    def note_reach(*_args, **_kwargs):
        reached.append(True)
        raise RuntimeError("여기까지면 충분하다")

    monkeypatch.setattr(loot_service, "get_pool", note_reach)
    context = {"kind_id": "goblin_rusher", "level": 3, "floor": 1, "submission_id": 1}
    with contextlib.suppress(RuntimeError):
        loot_service.create_kill_drop(1, 1, context)
    assert reached == [True]
