"""도플갱어가 실제로 방에 선다 — 그리고 서도 전리품을 안 만든다.

**여기가 이 기능의 함정이었다.** 도플갱어를 기존 슬롯에 얹기만 하면 전투가 보는 종은
템플릿의 종(`goblin_rusher`)이지 `doppelganger` 가 아니다. 그러면 잡아도 「도플갱어를
잡았다」가 아니게 되고, 종 id 하나에 걸려 있던 **전리품 차단 셋이 통째로 빗나간다.**

그래서 스냅샷이 종도 정하게 했고, 그것이 실제로 그렇게 도는지를 여기서 본다.
"""

from game.app.bots.doppel import DOPPEL_KIND_ID
from game.app.services.run_battle import build_engine, load_balance
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.monster_snapshot import MonsterSnapshot, build_entity_id
from game.schemas.room import load_room_templates


def build_parts():
    """엔진을 세우는 데 필요한 것들.

    Returns:
        (방, 밸런스).
    """
    rooms = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    return rooms["corridor"], load_balance(BALANCE_PATH)


def build_doppel_snapshot(slot, kind_id=DOPPEL_KIND_ID):
    """그 자리에 앉는 도플갱어 스냅샷.

    Args:
        slot: 방 템플릿의 스폰 자리 이름.
        kind_id: 스냅샷이 이름 대는 종.

    Returns:
        스냅샷.
    """
    return MonsterSnapshot(
        entity_id=slot,
        record_id=1,
        kind_id=kind_id,
        tier="ELITE",
        level=3,
        hp_max=140,
        attack=22,
        defense=9,
        rule_slots=5,
        cpu_budget=8,
        zone_floor=1,
    )


def test_the_catalog_knows_the_doppel():
    """★ 종이 카탈로그에 있어야 방에 설 수 있다 — 없으면 조립이 그 자리에서 터진다."""
    balance = load_balance(BALANCE_PATH)
    found = [kind for kind in balance["enemies"] if kind["id"] == DOPPEL_KIND_ID]
    assert len(found) == 1
    assert found[0]["tier"] == "ELITE"


def test_a_doppel_snapshot_puts_a_doppel_in_the_room():
    """★ **스냅샷이 종도 정한다.**

    이것이 없으면 전투가 보는 종은 템플릿의 것이고, 그러면 전리품 차단이 빗나간다.
    """
    template, balance = build_parts()
    slot = build_entity_id(template.enemy_spawns[0].kind, 0)
    engine = build_engine(
        template,
        balance,
        seed=1,
        snapshots=(build_doppel_snapshot(slot),),
        is_varied=False,
    )
    stood = engine.state.entities[slot]
    assert stood.kind_id == DOPPEL_KIND_ID
    # 스탯은 스냅샷이 덮는다 — 카탈로그의 값은 스냅샷이 없을 때의 바닥이다.
    assert stood.hp_max == 140
    assert stood.attack == 22


def test_an_ordinary_snapshot_keeps_the_template_kind():
    """★ 기존 개체는 이 갈래를 안 탄다 — 심을 때 템플릿의 종으로 심으므로 값이 같다.

    이 검사가 없으면 「종을 바꿀 수 있다」가 기존 세계를 조용히 흔드는지 알 수 없다.
    """
    template, balance = build_parts()
    kind = template.enemy_spawns[0].kind
    slot = build_entity_id(kind, 0)
    engine = build_engine(
        template,
        balance,
        seed=1,
        snapshots=(
            build_doppel_snapshot(slot).__class__(
                **{**vars(build_doppel_snapshot(slot)), "kind_id": kind}
            ),
        ),
        is_varied=False,
    )
    assert engine.state.entities[slot].kind_id == kind


def test_an_unknown_kind_falls_back_to_the_template():
    """★ 카탈로그에 없는 종을 이름 대면 템플릿의 종으로 선다.

    터지지 않아야 한다 — 콘텐츠 팩이 종을 빼는 동안 발급된 티켓이 그 상태로 들어온다.
    """
    template, balance = build_parts()
    kind = template.enemy_spawns[0].kind
    slot = build_entity_id(kind, 0)
    engine = build_engine(
        template,
        balance,
        seed=1,
        snapshots=(build_doppel_snapshot(slot, "nope_not_here"),),
        is_varied=False,
    )
    assert engine.state.entities[slot].kind_id == kind
