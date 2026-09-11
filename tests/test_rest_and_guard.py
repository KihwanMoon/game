"""둔화와 방벽 — 한 틱의 값을 정한 두 결정 (2026-09-10).

둘은 같은 축이다. **한 틱이 무엇만큼 값어치가 있는가.**

- 둔화는 이동만 늦춰서 안 움직여도 때리는 사격형에게 아무 효과가 없었다. 이제 행동
  전체를 늦춘다 — 두 틱에 한 번만 행동한다.
- 방벽은 켜는 데 한 틱을 내는데, 그 틱에 때렸으면 들어갔을 공격이 2틱 50%로 아끼는
  피해보다 컸다. 이제 **틱을 안 쓴다** — 규칙표에서 한 줄은 여전히 차지한다.

`test_player_telegraph.py` 에서 갈라 나왔다. 저쪽은 **예고가 어떻게 서는가**이고
여기는 **한 틱을 무엇에 쓰는가**다. 파일이 400줄 상한을 넘은 것이 계기였을 뿐,
가르는 선은 책임이다 (§4).
"""

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.app.skills.catalog import SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

METEOR = "METEOR"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_casting(balance, templates, **switches):
    """예고를 건 상태의 엔진을 만든다."""
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[METEOR] = SkillDef(
        skill_id=METEOR,
        shape=SkillShape(kind="AREA", radius=2),
        coef_pct=200,
        telegraph=3,
        **switches,
    )
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="USE_SKILL", skill_id=METEOR),)
    )
    assert len(engine.telegraphs.list_active()) == 1
    return engine, engine.state.entities["player"]


# ── 둔화가 행동을 늦춘다 (2026-09-10 결정) ──────────────────────────────


def test_a_slowed_entity_does_not_act_at_all(balance, templates):
    """★ **이동만이 아니다.** 사격형에게 효과가 없던 것이 이 한 줄이었다.

    `SLOW` 가 이동 경로에서만 걸릴 때는 안 움직여도 때리는 적에게 아무 일도 안 났고,
    이미 붙은 돌진형에게도 없었다. 서리 장판이 피해 0 으로는 어느 표에서도 값을 못 한
    원인이 그것이다 (설계/5_스킬 §10.10).
    """
    engine = build_engine(templates["corridor"], balance, seed=3)
    player = engine.state.entities["player"]
    target = next(one for one in engine.state.list_hostiles(player))
    target.position = (player.position[0] + 1, player.position[1])
    player.statuses["SLOW"] = 4

    before = target.hp
    engine.state.tick = 1  # 홀수 틱이 쉬는 틱이다
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="ATTACK", target_id=target.entity_id),)
    )
    assert target.hp == before, "쉬는 틱에 때렸다"

    engine.state.tick = 2
    engine.apply_actions(
        (PlannedAction(entity_id="player", action_id="ATTACK", target_id=target.entity_id),)
    )
    assert target.hp < before, "쉬지 않는 틱에도 못 때렸다"


def test_resting_does_not_cancel_a_cast(balance, templates):
    """★ **쉬는 틱은 「다른 행동」이 아니다.**

    예고를 끊는 것은 다른 행동을 했다는 사실인데(§10.3), 둔화로 쉰 틱은 아무 행동도
    안 한 틱이다. 여기서 끊으면 둔화 한 번이 마법을 통째로 지운다.
    """
    engine, player = build_casting(balance, templates, cancel_on_act=True)
    player.statuses["SLOW"] = 4
    engine.state.tick = 1
    engine.apply_actions((PlannedAction(entity_id=player.entity_id, action_id="APPROACH"),))
    assert len(engine.telegraphs.list_active()) == 1


# ── 방벽은 자리를 안 먹는다 (2026-09-10 결정) ────────────────────────────


def build_guard_ruleset(guard_terms=None):
    """방벽을 1번에 두고 그 아래 공격을 둔 규칙표.

    Args:
        guard_terms: 방벽 규칙의 조건. 없으면 「준비됨」으로 묻는다.

    Returns:
        검증을 거친 규칙표.
    """
    from game.schemas.ruleset import parse_ruleset

    def rule(priority, cost, action, terms, param=None, target=None):
        row = {"priority": priority, "cpu_cost": cost, "action": action, "set_flag": None}
        if param is not None:
            row["action_param"] = param
        row["target"] = target
        row["conditions"] = {"op": "SINGLE", "terms": terms}
        return row

    return parse_ruleset(
        {
            "ruleset_id": "probe_guard",
            "version": 1,
            "strategy_ko": "방벽을 켜고 그대로 때린다",
            "rules": [
                rule(
                    1,
                    1,
                    "USE_SKILL",
                    guard_terms
                    or [
                        {
                            "lhs": "self_skill_ready",
                            "cmp": "==",
                            "rhs": True,
                            "lhs_param": "GUARD_BRACE",
                        }
                    ],
                    param="GUARD_BRACE",
                    target="SELF",
                ),
                rule(
                    2,
                    1,
                    "ATTACK",
                    [{"lhs": "target_distance", "cmp": "<=", "rhs": 1, "lhs_param": "NEAREST"}],
                    target="NEAREST",
                ),
            ],
        }
    )


def test_guarding_does_not_spend_the_tick(balance, templates):
    """★ **방벽은 켜고, 그 틱에 때리기도 한다** (2026-09-10 결정).

    켜는 데 한 틱을 내던 것이 방벽이 어느 구간에서도 값을 못 하던 이유였다 — 2틱 50%로
    아끼는 피해보다 그 틱에 때렸으면 들어갔을 공격이 컸다 (설계/5_스킬 §2.1).

    규칙표에서 **한 줄은 여전히 차지한다.** 자리값이 아니라 틱값을 없앤 것이다.
    """
    from game.app.rules.rule_vm import build_rule_vm
    from game.config import BLOCKS_PATH
    from game.schemas.blocks import load_block_catalog

    engine = build_engine(templates["corridor"], balance, seed=3)
    player = engine.state.entities["player"]
    target = next(one for one in engine.state.list_hostiles(player))
    target.position = (player.position[0] + 1, player.position[1])
    engine.policies["player"] = build_rule_vm(
        build_guard_ruleset(), load_block_catalog(BLOCKS_PATH), engine.config.kind_types
    )

    before = target.hp
    engine.state.tick = 2
    engine.apply_actions(engine.plan_actions(engine.build_perceptions()))
    assert player.statuses.get("GUARD", 0) > 0, "방벽이 안 켜졌다"
    assert target.hp < before, "방벽을 켜느라 때리지 못했다"


def test_an_unopened_guard_is_still_blocked(balance, templates):
    """★ **안 열린 스킬을 조용히 켜면 안 된다** (결정 #04).

    자리를 안 먹는다고 미장착 검사를 건너뛰면 「불가」가 안 잡히고, 그러면 방패를 안
    낀 것이 화면 어디에도 안 보인다.
    """
    from game.app.rules.rule_vm import build_rule_vm
    from game.config import BLOCKS_PATH
    from game.schemas.blocks import load_block_catalog

    engine = build_engine(templates["corridor"], balance, seed=3)
    player = engine.state.entities["player"]
    player.skills = ["ATTACK"]  # 방벽을 안 열었다
    # **조건이 참이어야 「불가」가 성립한다.** `self_skill_ready` 로 물으면 미장착일 때
    # 그냥 거짓이라 다음 규칙으로 가고, 그것은 「불가」가 아니라 「거짓」이다.
    ruleset = build_guard_ruleset([{"lhs": "self_hp_percent", "cmp": "<=", "rhs": 100}])
    engine.policies["player"] = build_rule_vm(
        ruleset, load_block_catalog(BLOCKS_PATH), engine.config.kind_types
    )
    # **순서로 집지 않는다.** `list_actors` 가 플레이어를 먼저 준다는 보장이 없다.
    plans = {one.entity_id: one for one in engine.plan_actions(engine.build_perceptions())}
    plan = plans["player"]
    assert plan.free_skills == (), "안 열린 스킬을 켰다"
    assert any("GUARD_BRACE" in one.reason for one in plan.blocked), "「불가」로 안 잡혔다"
