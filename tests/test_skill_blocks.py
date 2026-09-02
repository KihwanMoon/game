"""블록 v5 — 스킬을 정체로 가리킨다 (결정 #04, docs/설계/5_스킬 §3·§4).

여기서 지키는 것은 넷이다.

1. **규칙 상태가 4종이다.** 참·발동 / 참·미발동 / 거짓 / **불가**. 불가는 거짓과 다르다 —
   조건은 참인데 실행할 수단이 없고, 플레이어가 고쳐야 할 곳이 완전히 다르다 (P1).
2. **불가가 로그에 남는다.** 조용히 넘어가면 왜 안 떴는지 알 수 없다.
3. **스킬이 늘어도 액션 종류가 고정이다.** USE_SKILL[id] 파라미터 하나로 묶었으므로
   블록 목록 버전이 오르지 않고, 따라서 랭킹 시즌이 갈리지 않는다.
4. **기존 규칙표가 그대로 돈다.** SKILL_1 과 self_cooldown_ready 를 별칭으로 남겼다.
"""

import json

import pytest

from game.app.rules.rule_vm import USE_SKILL_ACTION, build_rule_vm
from game.app.simulation.perception import build_snapshot
from game.app.simulation.plan import OUTCOME_BLOCKED
from game.config import BLOCKS_PATH
from game.schemas.blocks import ACTION_COUNT, PERCEPTION_COUNT, load_block_catalog
from game.schemas.ruleset import parse_ruleset

BLOCK_LIST_VERSION = 8  # v8: SELF 셀렉터
LEGACY_ACTIONS = ("SKILL_1", "SKILL_2", "AREA_ATTACK", "HEAL", "SUMMON")


@pytest.fixture
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture
def raw_blocks():
    return json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))


def build_skill_ruleset(skill_id: str):
    """그 스킬을 무조건 쓰는 규칙표 하나를 만든다."""
    return parse_ruleset(
        {
            "ruleset_id": "probe",
            "version": 1,
            "rules": [
                {
                    "priority": 1,
                    "cpu_cost": 1,
                    "action": USE_SKILL_ACTION,
                    "action_param": skill_id,
                    "target": "NEAREST",
                    "set_flag": None,
                    "conditions": {
                        "op": "AND",
                        "terms": [{"lhs": "self_hp_percent", "cmp": "<=", "rhs": 100}],
                    },
                }
            ],
        }
    )


# ── 카탈로그 (§4) ────────────────────────────────────────────────────────


def test_catalog_is_v8(raw_blocks):
    assert raw_blocks["block_list_version"] == BLOCK_LIST_VERSION


def test_use_skill_is_one_action_with_a_parameter(catalog):
    """★ 스킬마다 액션을 더하면 블록 버전이 계속 올라 랭킹 시즌이 갈린다."""
    action = catalog.actions[USE_SKILL_ACTION]
    assert action.param is not None
    assert action.param.name == "skill"
    assert len(action.param.values) > 1


def test_legacy_actions_survive(catalog):
    """★ 지우면 저장된 규칙표와 골든 리플레이가 전부 깨진다."""
    for action_id in LEGACY_ACTIONS:
        assert action_id in catalog.actions


def test_legacy_cooldown_perception_survives(catalog):
    assert "self_cooldown_ready" in catalog.perceptions


def test_skill_perceptions_are_parameterized(catalog):
    for block_id in ("self_skill_ready", "self_has_skill"):
        assert catalog.perceptions[block_id].param is not None


def test_counts_match_the_declared_freeze(catalog):
    """개수 동결값과 실제가 갈리면 실수로 늘어난 블록이 게이트를 통과한다."""
    assert len(catalog.perceptions) == PERCEPTION_COUNT
    assert len(catalog.actions) == ACTION_COUNT


def test_no_equipment_shape_blocks(catalog):
    """★ 장비 전용 블록을 만들지 않기로 했다 (결정 #13).

    장비는 전투 전에 캐릭터 능력치·스킬로 녹고 규칙표는 캐릭터만 읽는다. 사거리가 이미
    스탯 참조로 읽히므로 활로 바꾸면 같은 규칙표가 저절로 다르게 돈다.
    """
    for block_id in ("self_weapon_hands", "self_has_shield", "self_equipped_item"):
        assert block_id not in catalog.perceptions


# ── 규칙 상태 4종 (§3) ───────────────────────────────────────────────────


def test_equipped_skill_fires(catalog, monkeypatch, probe_world):
    world, entity = probe_world(skills=("SKILL_2",))
    vm = build_rule_vm(build_skill_ruleset("SKILL_2"), catalog, {})
    snapshot = build_snapshot(world, entity, {})
    plan = vm.plan_action(entity, snapshot, world)
    assert plan.action_id == USE_SKILL_ACTION
    assert plan.skill_id == "SKILL_2"
    assert plan.blocked == ()


def test_missing_skill_is_blocked_not_false(catalog, probe_world):
    """★ 불가는 거짓이 아니다. 조건은 참인데 수단이 없다."""
    world, entity = probe_world(skills=("SKILL_1",))
    vm = build_rule_vm(build_skill_ruleset("SKILL_2"), catalog, {})
    plan = vm.plan_action(entity, build_snapshot(world, entity, {}), world)
    # 그 규칙은 발동하지 않았지만 **왜 안 됐는지가 계획에 실려 나온다.**
    assert plan.action_id != USE_SKILL_ACTION
    assert [item.rule_index for item in plan.blocked] == [1]
    assert "SKILL_2" in plan.blocked[0].reason


def test_unwired_entity_allows_every_skill(catalog, probe_world):
    """장착 개념이 배선되기 전(skills=None)에는 전부 허용한다.

    빈 튜플(아무것도 장착 안 함)과 구분해야 한다 — 구분하지 않으면 아이템이 붙기 전까지
    모든 스킬 규칙이 불가가 된다.
    """
    world, entity = probe_world(skills=None)
    vm = build_rule_vm(build_skill_ruleset("SKILL_2"), catalog, {})
    plan = vm.plan_action(entity, build_snapshot(world, entity, {}), world)
    assert plan.skill_id == "SKILL_2"


def test_blocked_outcome_label_is_distinct():
    """거짓과 같은 글자를 쓰면 화면이 둘을 구분할 수 없다."""
    assert OUTCOME_BLOCKED == "불가"


# ── 인지값 (§4) ──────────────────────────────────────────────────────────


def test_skill_ready_needs_both_equipped_and_off_cooldown(probe_world):
    """★ self_cooldown_ready 는 쿨타임만 본다 — 미장착 스킬에도 참을 낸다.

    그 값으로 규칙을 짜면 실행되지 않는 규칙이 화면에서 참으로 보인다.
    self_skill_ready 가 장착과 쿨타임을 함께 보는 이유다.
    """
    world, entity = probe_world(skills=("SKILL_1",))
    values = build_snapshot(world, entity, {}).values
    assert values["self_cooldown_ready[SKILL_2]"] is True
    assert values["self_has_skill[SKILL_2]"] is False
    assert values["self_skill_ready[SKILL_2]"] is False
    assert values["self_skill_ready[SKILL_1]"] is True


def test_cooldown_makes_an_equipped_skill_not_ready(probe_world):
    world, entity = probe_world(skills=("SKILL_1",))
    entity.cooldowns["SKILL_1"] = 2
    values = build_snapshot(world, entity, {}).values
    assert values["self_has_skill[SKILL_1]"] is True
    assert values["self_skill_ready[SKILL_1]"] is False


def test_snapshot_covers_every_catalog_skill(catalog, probe_world):
    """카탈로그와 인지 목록이 갈리면 그 스킬 규칙이 언제나 거짓이 된다."""
    world, entity = probe_world()
    values = build_snapshot(world, entity, {}).values
    for skill in catalog.actions[USE_SKILL_ACTION].param.values:
        assert f"self_skill_ready[{skill}]" in values
