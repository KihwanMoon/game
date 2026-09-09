"""유물이 마법의 **제약**을 바꾼다 (설계/5_스킬 §10.7, 도입 순서 H7).

**여기서 보는 것은 「더 세졌는가」가 아니다.** 유물이 더 센 마법을 열면 규칙표는
`USE_SKILL[METEOR]` 를 `USE_SKILL[GREAT_METEOR]` 로 바꾸고 끝이라, 장비 교체가 규칙
재설계를 안 부른다 — P3 를 만족하지 않는다. 그래서 축 넷이 전부 **제약**을 만진다.

| 축 | 바꾸는 제약 | 규칙표가 어떻게 달라지나 |
|:--|:--|:--|
| `cast_lead_cut` | 예고 3 → 1틱 | 「뭉쳤을 때」가 아니라 「다가올 때」 쏜다 |
| `steady_cast` | 시전 중 이동해도 안 끊긴다 | 쏘고 바로 후퇴 — 카이팅과 결합한다 |
| `blast_radius` | 반경 3 → 5 | 한 방에 한 번 — 「보스전에만」 |
| `cast_cooldown_add` | 쿨 16 → 24 | 위 반경의 **대가**다 |

넷째가 없으면 셋째가 상위 호환이 되고, 그것이 §10.7 이 금지한 바로 그 모양이다.
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.app.simulation.telegraph import MIN_LEAD_TICKS
from game.app.skills.catalog import SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

METEOR = "METEOR"
BASE_TELEGRAPH = 3
BASE_RADIUS = 3
BASE_COOLDOWN = 16


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_probe(balance, templates, **axes):
    """유물 축을 끼운 플레이어와 엔진을 만든다.

    Args:
        balance: 밸런스 절.
        templates: 방 템플릿 표.
        **axes: 엔티티에 얹을 시전 축들.

    Returns:
        (엔진, 플레이어).
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=BASE_RADIUS),
        coef_pct=200,
        telegraph=BASE_TELEGRAPH,
        cooldown=BASE_COOLDOWN,
        cancel_on_act=True,
        cancel_on_hit=True,
    )
    player = engine.state.entities["player"]
    for name, value in axes.items():
        setattr(player, name, value)
    return engine, player


def build_plan():
    return PlannedAction(entity_id="player", action_id="USE_SKILL", skill_id=METEOR)


def test_the_scepter_shortens_the_telegraph(balance, templates):
    """★ 예고 3 → 1틱. **이것이 규칙표를 다시 짜게 만드는 지점이다** (§10.7).

    3틱짜리는 「적이 뭉쳤을 때」 쏘는 것이고, 1틱이면 「다가올 때」 쏜다.
    """
    engine, _player = build_probe(balance, templates, cast_lead_cut=2)
    engine.apply_actions((build_plan(),))
    assert engine.telegraphs.list_active()[0].remaining_ticks == 1


def test_the_telegraph_never_reaches_zero(balance, templates):
    """★ **0 이면 예고가 아니라 즉발이다.** 회피할 틈이 한 틱은 남아야 한다.

    예고의 유일한 정답이 회피이므로(피해가 방어를 안 거친다), 하한이 없으면 유물 하나가
    「피할 수 없는 광역기」를 만든다.
    """
    engine, _player = build_probe(balance, templates, cast_lead_cut=99)
    engine.apply_actions((build_plan(),))
    assert engine.telegraphs.list_active()[0].remaining_ticks == MIN_LEAD_TICKS


def test_the_core_widens_the_blast(balance, templates):
    """★ 반경 3 → 5. 데이터가 아니라 **낀 사람**이 넓힌다."""
    engine, player = build_probe(balance, templates, blast_radius=2)
    engine.apply_actions((build_plan(),))
    tiles = engine.telegraphs.list_active()[0].tiles
    reach = max(abs(x - player.position[0]) + abs(y - player.position[1]) for x, y in tiles)
    assert reach == BASE_RADIUS + 2


def test_the_core_pays_for_the_width_in_cooldown(balance, templates):
    """★ **대가가 없으면 상위 호환이다** (§10.7 이 금지한 것).

    끼기만 하면 되는 유물은 규칙표를 안 바꾼다. 쿨 24 는 한 방에 한 번이라 「보스전에만」
    쪽으로 규칙표가 기운다 — 그것이 이 유물이 파는 것이다.
    """
    engine, player = build_probe(balance, templates, blast_radius=2, cast_cooldown_add=8)
    engine.apply_actions((build_plan(),))
    assert player.cooldowns[METEOR] == BASE_COOLDOWN + 8


def test_the_cooldown_cost_does_not_touch_ordinary_actions(balance, templates):
    """★ **마법의 대가가 캐릭터의 벌이 되면 안 된다.**

    쿨타임 0 인 평타에 8 이 붙으면 그 유물을 낀 사람은 8틱에 한 번만 때린다. 대가는
    예고를 쓰는 스킬에만 붙는다.
    """
    engine, player = build_probe(balance, templates, cast_cooldown_add=8)
    engine.apply_actions((PlannedAction(entity_id="player", action_id="ATTACK"),))
    assert player.cooldowns.get("ATTACK", 0) == 0


def test_the_signet_keeps_the_cast_through_a_move(balance, templates):
    """★ 쏘고 바로 후퇴. **카이팅과 결합하는 자리다** (§10.7)."""
    engine, player = build_probe(balance, templates, steady_cast=1)
    engine.apply_actions((build_plan(),))
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="HOLD"),))
    assert len(engine.telegraphs.list_active()) == 1


def test_the_signet_does_not_also_buy_immunity_to_being_hit(balance, templates):
    """★ **둘 다 끄면 상위 호환이 된다.**

    피격 취소가 남아야 「안전한 자리에서 쏘는가」가 규칙표의 질문으로 남는다. 그것까지
    사라지면 이 유물은 제약을 바꾸는 것이 아니라 제약을 없애는 것이 된다.
    """
    engine, player = build_probe(balance, templates, steady_cast=1)
    engine.apply_actions((build_plan(),))
    engine.actions.apply_damage(player, 5, "ACT", "시험", "e1")
    assert engine.telegraphs.list_active() == ()


def test_nothing_changes_without_a_relic(balance, templates):
    """★ **유물 없이도 마법은 쓴다.** 전략 축이 만분의 5 뒤에 갇히면 안 된다 (§10.7)."""
    engine, player = build_probe(balance, templates)
    engine.apply_actions((build_plan(),))
    telegraph = engine.telegraphs.list_active()[0]
    assert telegraph.remaining_ticks == BASE_TELEGRAPH
    assert player.cooldowns[METEOR] == BASE_COOLDOWN
