"""튜토리얼 — 각 단계가 실제로 무언가를 가르치는가 (로드맵 W20, 결정 #17).

**이 검사가 튜토리얼의 전부다.** 단계 하나가 가르치는 것은 설명문이 아니라 **시작
규칙표로는 지고 해답 규칙표로는 이긴다**는 대비이며, 그 대비가 깨지면 설명문이 아무리
좋아도 그 단계는 거짓말을 한다.

밸런스를 고치면 여기가 함께 빨개지는 것이 정상이다 — 적이 약해지면 "지던 것" 이 이기고,
그 순간 그 단계는 아무것도 보여주지 못한다.
"""

import pytest

from game.app.rules.rule_vm import build_rule_vm
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import (
    assign_enemy_policies,
    build_engine,
    load_balance,
    run_battle,
)
from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
    TUTORIAL_STAGES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets, parse_ruleset
from game.schemas.tutorial import load_tutorial_stages

STAGES = load_tutorial_stages(TUTORIAL_STAGES_PATH)
PLAYER_ID = "player"


@pytest.fixture(scope="module")
def parts():
    balance = load_balance(BALANCE_PATH)
    return {
        "balance": balance,
        "catalog": load_block_catalog(BLOCKS_PATH),
        "rooms": {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)},
        "enemies": load_rulesets(ENEMY_RULESETS_PATH),
    }


def run_stage(parts, stage, rules):
    """그 단계를 이 규칙표로 한 번 돌린다."""
    ruleset = parse_ruleset(stage.build_ruleset(rules))
    # 가르치는 판은 배치가 고정이다 — 같은 자리에서 같은 교훈이 나와야 한다.
    engine = build_engine(
        parts["rooms"][stage.room_id], parts["balance"], seed=stage.seed, is_varied=False
    )
    engine.policies[PLAYER_ID] = build_rule_vm(ruleset, parts["catalog"], engine.config.kind_types)
    assign_enemy_policies(engine, parts["balance"], parts["catalog"], parts["enemies"])
    return run_battle(engine)


def test_stages_exist():
    """★ 비어 있으면 아래 검사가 전부 통과해도 뜻이 없다."""
    assert len(STAGES) >= 5


def test_stage_ids_are_unique():
    """진행 상태를 id 로 저장하므로 겹치면 한 단계가 다른 단계를 덮는다."""
    ids = [stage.stage_id for stage in STAGES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.stage_id)
def test_the_solution_actually_wins(parts, stage):
    """★ 해답이 이기지 못하면 그 단계는 통과할 수 없다."""
    result = run_stage(parts, stage, stage.solution_rules)
    assert result.outcome == stage.goal.outcome, f"{stage.stage_id}: {result.outcome}"
    if stage.goal.min_player_hp is not None:
        assert result.player_hp >= stage.goal.min_player_hp


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.stage_id)
def test_the_start_actually_fails(parts, stage):
    """★ **여기가 튜토리얼의 핵심이다.**

    시작 규칙표로도 이겨 버리면 고칠 이유가 없고, 그 단계는 아무것도 가르치지 못한다.
    설명문은 그대로인 채 대비만 조용히 사라지는 것이 가장 나쁜 실패다.

    CPU 예산 단계만 예외다 — 거기서는 애초에 출격이 막히는 것이 배울 내용이다.
    """
    problems = validate_ruleset(
        parse_ruleset(stage.build_ruleset(stage.start_rules)),
        parts["catalog"],
        parts["balance"]["player"]["cpu_budget"],
        parts["balance"]["player"]["rule_slots"],
    )
    if problems:
        return
    result = run_stage(parts, stage, stage.start_rules)
    assert result.outcome != stage.goal.outcome, f"{stage.stage_id} 는 고치지 않아도 이긴다"


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.stage_id)
def test_the_solution_fits_the_budget(parts, stage):
    """★ 해답이 예산을 넘으면 화면에서 출격 버튼이 막힌다."""
    budget = stage.goal.max_cpu or parts["balance"]["player"]["cpu_budget"]
    problems = validate_ruleset(
        parse_ruleset(stage.build_ruleset(stage.solution_rules)),
        parts["catalog"],
        budget,
        parts["balance"]["player"]["rule_slots"],
    )
    assert problems == [], f"{stage.stage_id}: {problems}"


def test_the_cpu_stage_starts_over_budget(parts):
    """★ CPU 단계의 시작 규칙표는 **예산을 넘어야 한다.**

    넘지 않으면 "예산을 넘으면 출격할 수 없다" 를 보여줄 수 없다.
    """
    stage = next(s for s in STAGES if s.stage_id == "cpu_budget")
    problems = validate_ruleset(
        parse_ruleset(stage.build_ruleset(stage.start_rules)),
        parts["catalog"],
        parts["balance"]["player"]["cpu_budget"],
        parts["balance"]["player"]["rule_slots"],
    )
    assert problems != []


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.stage_id)
def test_every_stage_says_what_it_teaches(stage):
    """설명이 비면 스테이지가 퀴즈가 된다 — 초보자는 무엇을 배웠는지 모른다."""
    assert stage.teaches_ko.strip()
    assert stage.brief_ko.strip()
    assert stage.hint_ko.strip()


@pytest.mark.parametrize("stage", STAGES, ids=lambda s: s.stage_id)
def test_stages_stay_small(stage):
    """로드맵 W20 이 정한 「규칙 3개짜리」다. 넘으면 첫 화면이 벽이 된다."""
    assert len(stage.solution_rules) <= 3
