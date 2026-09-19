"""예고 피해가 건너뛰는 것 다섯 (설계/5_스킬, 2026-09-19).

**이것은 「아직 안 한 일」이 아니라 정해진 규칙이다.** 즉발은 `calculate_damage` →
`apply_damage` 를 거치는데 예고 피해는 시전 시점에 `공격력 × 계수` 로 얼어붙고 발동 때
HP 에서 바로 빠진다 (`_apply_blast`). 그래서 다섯이 안 걸린다.

앞의 둘(방어력·포위도)은 `telegraph.py` 머리말이 사유를 적어 둔다 — *「예고의 유일한
정답이 회피여야 `위험 예고 타일 위에 있는가` 가 전술이 된다」*. 뒤의 셋(스킬위력·방벽·
피격 시전취소)은 `apply_damage` 를 안 거친 결과이고 문서에 사유가 없었다.

**2026-09-19 에 재고 지금대로 두기로 정했다.** 회피가 유일한 답이라는 규칙을 끝까지
미는 쪽이, 예외를 셋 두는 것보다 설명하기 쉽다.

**그래서 이 검사가 있다.** 문서만 두면 다음 사람이 「빠뜨린 것」으로 보고 고친다 —
고치는 것 자체가 나쁜 게 아니라, **모르고 고치는 것**이 나쁘다. 여기가 빨개지면 그때
이 머리말을 읽고 정하면 된다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import STATUS_GUARD, PlannedAction
from game.app.skills.catalog import SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

PROBE = "SKILL_1"
COEF = 200


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def measure(balance, templates, telegraph, *, defense=0, guard=False, power=100):
    """같은 계수로 실제로 깎인 HP 를 잰다.

    Args:
        balance: 밸런스 절.
        templates: 방 템플릿 표.
        telegraph: 예고 틱. 0 이면 즉발.
        defense: 맞는 쪽 방어력.
        guard: 맞는 쪽이 방벽을 켰는가.
        power: 때리는 쪽 스킬위력 퍼센트.

    Returns:
        깎인 HP.
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[PROBE] = SkillDef(
        skill_id=PROBE,
        shape=SkillShape(kind="AREA" if telegraph else "SINGLE", radius=1),
        coef_pct=COEF,
        telegraph=telegraph,
        hits="TILES" if telegraph else "TARGET",
    )
    player = engine.state.entities["player"]
    player.skill_power_pct = power
    foe = next(iter(engine.state.list_hostiles(player)))
    foe.position = (player.position[0] + 1, player.position[1])
    foe.defense = defense
    if guard:
        foe.statuses[STATUS_GUARD] = 3
    before = foe.hp
    engine.apply_actions(
        (
            PlannedAction(
                entity_id="player", action_id="USE_SKILL", skill_id=PROBE, target_id=foe.entity_id
            ),
        )
    )
    for _step in range(telegraph + 1):
        engine.run_tick()
    return before - foe.hp


def test_the_blast_ignores_defense(balance, templates):
    """★ 1. **방어력을 안 본다** — 예고의 유일한 답이 회피여야 하기 때문이다."""
    assert measure(balance, templates, 1, defense=0) == measure(balance, templates, 1, defense=10)
    # 즉발은 본다. 둘이 같아지면 이 규칙이 사라진 것이다.
    assert measure(balance, templates, 0, defense=10) < measure(balance, templates, 0, defense=0)


def test_the_blast_ignores_guard(balance, templates):
    """★ 4. **방벽이 거의 안 듣는다** — `apply_damage` 를 안 거치기 때문이다.

    즉발은 절반으로 줄고 예고형은 거의 그대로다. 「방패를 들면 예고도 견딘다」를 열면
    회피가 유일한 답이 아니게 된다.
    """
    bare = measure(balance, templates, 1, guard=False)
    shielded = measure(balance, templates, 1, guard=True)
    assert shielded >= bare * 8 // 10, "예고 피해가 방벽에 반으로 깎였다면 규칙이 바뀐 것이다"
    # 즉발은 확실히 줄어든다.
    assert measure(balance, templates, 0, guard=True) < measure(balance, templates, 0) // 2 + 1


def test_the_blast_ignores_skill_power(balance, templates):
    """★ 3. **스킬위력을 안 받는다** — 시전 시점에 공격력 × 계수로 얼어붙는다."""
    assert measure(balance, templates, 1, power=100) == measure(balance, templates, 1, power=200)
    assert measure(balance, templates, 0, power=200) > measure(balance, templates, 0, power=100)


def test_the_blast_does_not_cancel_the_victim_cast(balance, templates):
    """★ 5. **예고 피해로는 남의 시전이 안 끊긴다.**

    `cancel_on_hit` 이 켜진 굿도 「그 굿이 끊기는 쪽」이지 「그 굿이 남을 끊는 쪽」이
    아니다 — 끊는 일은 `apply_damage` 안에 있고 예고 발동은 그것을 안 거친다.

    **예고 피해만 넣어야 한다.** 처음에는 재주를 써서 재려 했는데, 같은 틱에 규칙표가
    평타를 한 대 더 넣어서 그쪽이 끊었다 — 로그에는 똑같이 `취소 ← 피격` 으로 찍혀
    「예고가 끊었다」로 잘못 읽혔다. 카운트다운만 돌려 그 둘을 가른다.
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    player = engine.state.entities["player"]
    foe = next(iter(engine.state.list_hostiles(player)))
    # 맞는 쪽이 끊기는 예고를 걸어 둔다.
    engine.telegraphs.register(
        caster_id=foe.entity_id,
        skill_id="적의 굿",
        tiles=((0, 0),),
        damage=1,
        lead_ticks=5,
        visible_ticks=5,
        cancel_on_hit=True,
    )
    # 적이 선 칸을 때리는 예고. 살아남을 만큼만 아프게 둔다 — 죽으면 `cancel_on_death`
    # 가 지우고, 그것은 피격 취소와 다른 사유다.
    engine.telegraphs.register(
        caster_id=player.entity_id,
        skill_id="내 굿",
        tiles=(foe.position,),
        damage=5,
        lead_ticks=1,
        visible_ticks=1,
    )
    engine.telegraphs.run_countdown(engine.state, engine.log)
    assert foe.is_alive and foe.hp < foe.hp_max, "예고가 안 맞았으면 이 검사는 아무것도 안 본다"
    standing = [one for one in engine.telegraphs.list_active() if one.caster_id == foe.entity_id]
    assert standing, "예고 피해가 남의 시전을 끊었다면 규칙이 바뀐 것이다"
