"""인자 없는 `소모품 사용` 은 물약이다 (e2).

`USE_POTION` 별칭과 같은 규약이고 실행부(`apply_item`)도 그렇게 떨어진다. 그런데
**문지기만 빈 문자열의 개수를 셌다** — 늘 0 이라, 인자 고르개가 생기기 전에 지은 소모품
규칙 전부가 영원히 「불가」였다. 「소모품 사용이 안돼」가 그것이다.
"""


def test_a_paramless_use_item_drinks_a_potion():
    """★ 문지기가 빈 문자열을 세면 인자 없는 규칙이 영원히 「불가」다."""
    from game.app.rules.rule_vm import build_rule_vm
    from game.app.services.run_battle import build_engine, load_balance, run_battle
    from game.config import BALANCE_PATH, BLOCKS_PATH, ROOM_TEMPLATES_PATH
    from game.schemas.blocks import load_block_catalog
    from game.schemas.loadout import PlayerLoadout
    from game.schemas.room import load_room_templates
    from game.schemas.ruleset import parse_ruleset

    catalog = load_block_catalog(BLOCKS_PATH)
    balance = load_balance(BALANCE_PATH)
    rooms = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    rs = parse_ruleset(
        {
            "ruleset_id": "p",
            "version": 1,
            "rules": [
                {
                    "priority": 1,
                    "cpu_cost": 2,
                    "action": "USE_ITEM",
                    "action_param": None,
                    "target": None,
                    "set_flag": None,
                    "conditions": {
                        "op": "AND",
                        "terms": [{"lhs": "self_hp_percent", "cmp": "<", "rhs": 60}],
                    },
                },
                {
                    "priority": 2,
                    "cpu_cost": 1,
                    "action": "ATTACK",
                    "action_param": None,
                    "target": "NEAREST_ENEMY",
                    "set_flag": None,
                    "conditions": {
                        "op": "AND",
                        "terms": [{"lhs": "enemy_distance", "cmp": "<", "rhs": 9}],
                    },
                },
            ],
        }
    )
    loadout = PlayerLoadout(
        hp_max=100,
        attack=12,
        defense=5,
        attack_range=1,
        initiative=50,
        cpu_budget=10,
        rule_slots=8,
        skill_power_pct=100,
        skills=("ATTACK", "SKILL_1", "SKILL_2"),
        consumables=(("POTION", 2),),
    )
    engine = build_engine(rooms["open_field"], balance, seed=7, loadout=loadout)
    engine.policies["player"] = build_rule_vm(rs, catalog, engine.config.kind_types)
    run_battle(engine)
    assert any("USE_ITEM" in e.expr and "HP" in e.outcome for e in engine.log.entries), (
        "인자 없는 소모품 규칙이 발동하지 않았다"
    )
