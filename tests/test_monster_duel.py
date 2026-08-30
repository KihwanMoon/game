"""몬스터끼리의 전투 (결정 #38, docs/설계/6_몬스터 §6).

예전에는 레벨 차이에 확률을 얹은 판정이었다. 지금은 **실제로 규칙표대로 붙는다** —
그래서 세계 틱이 만드는 레벨 변화가 운이 아니라 규칙표의 결과다.

여기서 지키는 것은 넷이다.

1. 같은 시드면 같은 결과다 (R5). 세계 틱은 조사에 쓰려면 재현돼야 한다.
2. 규칙표가 결과를 바꾼다. 안 바꾸면 확률 굴림과 구별되지 않는다.
3. 스탯이 결과를 바꾼다. 레벨이 오른 개체가 유리해야 성장이 뜻을 갖는다.
4. 시간 초과도 승부를 낸다. 무승부로 두면 그 쌍은 영원히 그대로다.
"""

import pytest

from game.app.services.run_battle import load_balance
from game.app.services.run_duel import LEFT_ID, RIGHT_ID, run_monster_duel
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.monster_snapshot import MonsterSnapshot
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets

ARENA = "open_field"

# 서로 접근해 때리는 규칙표. 스탯을 재려면 실제로 붙어야 한다.
AGGRESSIVE = "ai_rusher"


@pytest.fixture(scope="module")
def parts():
    templates = {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)}
    return {
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "rulesets": load_rulesets(ENEMY_RULESETS_PATH),
        "arena": templates[ARENA],
    }


def build_snapshot(record_id, kind_id="goblin_rusher", level=1, hp=60, attack=10, defense=3):
    return MonsterSnapshot(
        entity_id=f"slot{record_id}",
        record_id=record_id,
        kind_id=kind_id,
        tier="NORMAL",
        level=level,
        hp_max=hp,
        attack=attack,
        defense=defense,
        rule_slots=4,
        cpu_budget=6,
    )


def fight(parts, left, right, left_rules, right_rules, seed=4242):
    return run_monster_duel(
        left,
        right,
        (parts["rulesets"][left_rules], parts["rulesets"][right_rules]),
        parts["arena"],
        parts["balance"],
        parts["catalog"],
        seed,
    )


def list_ruleset_ids(parts):
    return sorted(parts["rulesets"])


def test_the_same_seed_gives_the_same_duel(parts):
    """★ 세계 틱은 조사에 쓰려면 재현돼야 한다 (R5)."""
    ids = list_ruleset_ids(parts)
    args = (build_snapshot(1), build_snapshot(2), ids[0], ids[1])
    assert fight(parts, *args) == fight(parts, *args)


def test_a_duel_always_names_a_winner(parts):
    """★ 무승부를 두면 그 쌍은 영원히 같은 레벨에 머문다."""
    ids = list_ruleset_ids(parts)
    result = fight(parts, build_snapshot(1), build_snapshot(2), ids[0], ids[1])
    assert result.winner_record_id in {1, 2}
    assert result.loser_record_id in {1, 2}
    assert result.winner_record_id != result.loser_record_id


def test_stats_decide_the_duel(parts):
    """★ 레벨이 오른 개체가 유리해야 성장이 뜻을 갖는다.

    **붙는 규칙표로 잰다.** 서로 접근하지 않는 규칙표 둘을 붙이면 스탯이 결과를 정할
    기회가 없고, 그러면 이 검사는 스탯이 아니라 그 규칙표를 재게 된다.
    """
    strong = build_snapshot(1, level=9, hp=400, attack=40, defense=20)
    weak = build_snapshot(2, level=1, hp=30, attack=4, defense=0)
    assert fight(parts, strong, weak, AGGRESSIVE, AGGRESSIVE).winner_record_id == 1
    # 자리를 바꿔도 같아야 한다 — 왼쪽이 유리한 자리면 결투가 자리 뽑기가 된다.
    assert fight(parts, weak, strong, AGGRESSIVE, AGGRESSIVE).winner_record_id == 1


def test_the_ruleset_changes_the_duel(parts):
    """★ **이것이 없으면 확률 굴림과 구별되지 않는다.**

    같은 스탯 둘을 붙였을 때, 한쪽의 규칙표만 바꿔 결과나 길이가 달라져야 한다.
    """
    ids = list_ruleset_ids(parts)
    base = fight(parts, build_snapshot(1), build_snapshot(2), ids[0], ids[0])
    swapped = [
        fight(parts, build_snapshot(1), build_snapshot(2), ids[0], other) for other in ids[1:]
    ]
    assert any(
        item.winner_record_id != base.winner_record_id or item.ticks != base.ticks
        for item in swapped
    ), "어느 규칙표로 바꿔도 같은 결과다 — 규칙표가 반영되지 않는다"


def test_the_arena_is_cleared_of_bystanders(parts):
    """★ 방의 원래 스폰이 남으면 제삼자가 끼어들어 결과가 방마다 달라진다."""
    from game.app.rules.rule_vm import build_rule_vm
    from game.app.services.run_battle import build_engine
    from game.app.services.run_duel import build_duel_entity
    from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER

    engine = build_engine(parts["arena"], parts["balance"], seed=1)
    engine.state.entities.clear()
    by_id = {kind["id"]: kind for kind in parts["balance"]["enemies"]}
    left = build_snapshot(1)
    engine.state.entities[LEFT_ID] = build_duel_entity(
        LEFT_ID, left, FACTION_PLAYER, parts["arena"].player_spawn, by_id[left.kind_id]
    )
    right = build_snapshot(2)
    engine.state.entities[RIGHT_ID] = build_duel_entity(
        RIGHT_ID,
        right,
        FACTION_ENEMY,
        parts["arena"].enemy_spawns[0].position,
        by_id[right.kind_id],
    )
    ids = list_ruleset_ids(parts)
    engine.policies[LEFT_ID] = build_rule_vm(
        parts["rulesets"][ids[0]], parts["catalog"], engine.config.kind_types
    )
    assert sorted(engine.state.entities) == sorted([LEFT_ID, RIGHT_ID])


def test_the_duel_uses_snapshot_stats_not_catalog(parts):
    """★ 스냅샷이 스탯을 정한다.

    카탈로그 값을 쓰면 레벨이 오른 개체와 갓 나온 개체가 같은 힘으로 싸운다.
    """
    fat = build_snapshot(1, hp=500)
    thin = build_snapshot(2, hp=20)
    assert fight(parts, fat, thin, AGGRESSIVE, AGGRESSIVE).winner_record_id == 1


def test_hunters_never_join_a_duel(parts):
    """★ **추격자는 결투에 끼면 안 된다.**

    추격자는 플레이어의 지연을 벌하는 장치라 언제나 적 진영에 붙는다 (GDD §7). 결투장에
    들어오면 오른쪽 편만 드는 것이 되어, 왼쪽 자리에 선 개체가 긴 싸움에서 반드시 진다 —
    실제로 이 자리를 처음 만들었을 때 **강한 개체가 늘 지는 현상**으로 드러났다.

    **결투 경로를 그대로 지난다.** 엔진을 따로 조립해 재면 `run_monster_duel` 이
    추격자를 끄는지는 확인되지 않는다.
    """
    # 서로 닿지 못하는 규칙표라 상한까지 간다 — 추격자가 나올 시간을 준다.
    passive = "ai_arch_summoner"
    result = fight(parts, build_snapshot(1, hp=300), build_snapshot(2, hp=300), passive, passive)
    assert result.is_timeout
    assert not [name for name in result.entity_ids if "_h" in name], result.entity_ids


def test_a_duel_has_no_bystanders(parts):
    """★ 결투장에는 둘만 있어야 한다.

    방의 원래 스폰이 남으면 제삼자가 끼어들어, 같은 두 개체를 붙여도 방마다 다른 결과가
    나온다. 소환물은 예외다 — 그것은 규칙표가 부른 것이라 결투의 일부다.
    """
    result = fight(parts, build_snapshot(1), build_snapshot(2), AGGRESSIVE, AGGRESSIVE)
    template_ids = {f"goblin_rusher_{index}" for index in range(4)}
    assert not (set(result.entity_ids) & template_ids), result.entity_ids


def test_the_timeout_verdict_matches_the_hp_view(parts):
    """★ 시간 초과 판정이 «가한 피해» 로 적혀 있지만 «남은 체력» 과 같은 답을 낸다.

    남은 비율은 받은 피해 비율의 뒤집힘이라 두 식은 동치다. 이 검사가 있는 이유는 언젠가
    한쪽만 고쳤을 때 그 사실이 드러나게 하려는 것이다 — 처음 이 자리를 쓸 때 "체력으로
    재면 도망만 다닌 쪽이 이긴다" 고 적었는데, 그것은 **틀린 설명**이었다.
    """
    from game.app.services.run_duel import build_duel_entity, build_duel_result
    from game.app.simulation.state import FACTION_ENEMY, FACTION_PLAYER

    by_id = {kind["id"]: kind for kind in parts["balance"]["enemies"]}
    # **양쪽 다 살아 있어야 시간 초과다.** 한쪽이 0 이면 그냥 승부가 난 것이라 이
    # 판정식을 타지 않는다 — 처음 쓴 사례 하나가 그것이었고, 검사가 잡아 줬다.
    cases = ((100, 60, 100, 50), (100, 90, 400, 100), (50, 5, 300, 299), (80, 80, 80, 1))
    for left_max, left_hp, right_max, right_hp in cases:
        left = build_snapshot(1, hp=left_max)
        right = build_snapshot(2, hp=right_max)
        entities = {
            LEFT_ID: build_duel_entity(LEFT_ID, left, FACTION_PLAYER, (1, 1), by_id[left.kind_id]),
            RIGHT_ID: build_duel_entity(
                RIGHT_ID, right, FACTION_ENEMY, (2, 2), by_id[right.kind_id]
            ),
        }
        entities[LEFT_ID].hp = left_hp
        entities[RIGHT_ID].hp = right_hp
        result = build_duel_result("TIMEOUT", 200, entities, left, right)
        assert result.is_timeout, (left_max, left_hp, right_max, right_hp)
        verdict = result.winner_record_id
        by_hp = 1 if left_hp * right_max >= right_hp * left_max else 2
        assert verdict == by_hp, (left_max, left_hp, right_max, right_hp)
