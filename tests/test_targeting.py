"""누가 맞는가 — 판정기 한 벌 (설계/5_스킬 §2, 2026-09-19).

**같은 규칙이 코드 두 곳에 다르게 박혀 있었다.** 즉발 범위(`apply_area_attack`)는
시전자 중심 반경 안의 **적만** 쳤고, 예고형(`_apply_blast`)은 칸에 선 것을 **진영 없이**
쳤다. 둘 다 `AREA` 인데 판정이 정반대였고 데이터만 봐서는 구별이 안 됐다 — 어제
「타겟형인지 타일에 작용하는지 구분되어 있냐」는 물음이 정확히 그 자리를 짚었다.

이제 판정기는 `simulation/targeting` 한 벌이고, **어느 것을 쓸지는 재주가 `hits` 로
적는다.** 규칙이 코드가 아니라 데이터에 있으면 관리 화면이 그것을 고칠 수 있다.
"""

import json
from pathlib import Path

import pytest

from game.app.services.run_battle import build_engine, load_balance
from game.app.simulation.plan import PlannedAction
from game.app.simulation.targeting import (
    HITS_HOSTILE_AREA,
    HITS_MODES,
    HITS_TARGET,
    HITS_TILES,
)
from game.app.skills.catalog import SkillDef, SkillShape
from game.config import BALANCE_PATH, ROOM_TEMPLATES_PATH, SKILLS_PATH
from game.schemas.room import load_room_templates

PROBE = "AREA_ATTACK"


@pytest.fixture(scope="module")
def balance():
    return load_balance(BALANCE_PATH)


@pytest.fixture(scope="module")
def templates():
    return {item.template_id: item for item in load_room_templates(ROOM_TEMPLATES_PATH)}


def build_probe(balance, templates, hits):
    """그 판정을 쓰는 범위 공격을 꽂고, 적을 시전자 옆에 붙인다.

    Args:
        balance: 밸런스 절.
        templates: 방 템플릿 표.
        hits: 판정 축.

    Returns:
        (엔진, 플레이어, 적).
    """
    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills[PROBE] = SkillDef(
        skill_id=PROBE, shape=SkillShape(kind="AREA", radius=3), coef_pct=50, hits=hits
    )
    player = engine.state.entities["player"]
    foe = next(iter(engine.state.list_hostiles(player)))
    foe.position = (player.position[0] + 1, player.position[1])
    return engine, player, foe


def test_hostile_area_spares_the_caster(balance, templates):
    """★ **적만 친다** — 즉발 범위가 지금까지 하던 판정이다."""
    engine, player, foe = build_probe(balance, templates, HITS_HOSTILE_AREA)
    before = player.hp
    engine.apply_actions((PlannedAction(entity_id="player", action_id=PROBE),))
    assert player.hp == before
    assert foe.hp < foe.hp_max


def test_tiles_hit_everyone_standing_there(balance, templates):
    """★ **칸에 선 것을 전부 친다** — 시전자도 맞는다.

    예고가 좌표에 떨어지는 것이라 아군도 맞고, 그래야 통로로 유인하는 전술이 성립한다
    (GDD §4.3). 어제 조종 무당이 제 굿에 죽은 것이 이 규칙이다.
    """
    engine, player, foe = build_probe(balance, templates, HITS_TILES)
    before = player.hp
    engine.apply_actions((PlannedAction(entity_id="player", action_id=PROBE),))
    assert player.hp < before, "칸 판정인데 시전자가 안 맞았다"
    assert foe.hp < foe.hp_max


def test_the_axis_is_what_changes_it(balance, templates):
    """★ **갈리는 것은 축 하나다.** 같은 재주·같은 배치에서 값만 바꿔 본다.

    이것이 통일의 뜻이다 — 예전에는 코드 두 곳이 갈랐으므로 데이터를 고쳐도 안 바뀌었다.
    """
    spared, _p1, _f1 = build_probe(balance, templates, HITS_HOSTILE_AREA)
    burned, _p2, _f2 = build_probe(balance, templates, HITS_TILES)
    spared.apply_actions((PlannedAction(entity_id="player", action_id=PROBE),))
    burned.apply_actions((PlannedAction(entity_id="player", action_id=PROBE),))
    assert spared.state.entities["player"].hp > burned.state.entities["player"].hp


def test_every_shipped_skill_declares_a_known_mode():
    """★ **모르는 값은 조용히 대상 하나가 된다** — 오타 하나가 광역을 단일로 만든다."""
    raw = json.loads(Path(SKILLS_PATH).read_text(encoding="utf-8"))
    bad = [one["id"] for one in raw["skills"] if one.get("hits") not in HITS_MODES]
    assert bad == [], f"모르는 판정: {bad}"


def test_the_shipped_modes_match_what_the_code_used_to_do():
    """★ **축을 열면서 동작을 안 바꿨다.** 예고형은 칸, 즉발 범위는 적, 나머지는 대상.

    축을 여는 것과 값을 바꾸는 것은 다른 일이다. 섞으면 뒤에 달라진 것이 어느 쪽 탓인지
    못 가른다 — 골든이 안 움직인 것이 그 증거이고, 이 검사가 그 사실을 글로 남긴다.
    """
    raw = json.loads(Path(SKILLS_PATH).read_text(encoding="utf-8"))
    for one in raw["skills"]:
        if int(one.get("telegraph", 0)) > 0:
            wanted = HITS_TILES
        elif one["shape"]["kind"] == "AREA":
            wanted = HITS_HOSTILE_AREA
        else:
            wanted = HITS_TARGET
        assert one["hits"] == wanted, f"{one['id']}: {one['hits']} ≠ {wanted}"


def test_an_instant_skill_applies_its_effects(balance, templates):
    """★ **즉발도 상태를 얹는다** (2026-09-19).

    예전에는 상태를 얹는 절이 **예고 레코드에 묶여** 있었다. 그래서 즉발 재주에
    `effects` 를 달면 파싱도 저장도 되고 관리 화면에도 뜨는데 **아무 일도 안 났다** —
    `SLOW`·`POISON`·`cast_cooldown_add` 에 이어 네 번째 「조용히 무효」였다.

    「피해를 주면서 둔화도 건다」는 `SkillEffect` 머리말이 이미 약속한 것인데, 반쪽만
    지켜지고 있었다.
    """
    from game.app.skills.catalog import SkillEffect

    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills["SKILL_1"] = SkillDef(
        skill_id="SKILL_1",
        shape=SkillShape(kind="SINGLE"),
        coef_pct=100,
        hits=HITS_TARGET,
        effects=(SkillEffect(kind="STATUS", status="POISON", duration=5),),
    )
    player = engine.state.entities["player"]
    foe = next(iter(engine.state.list_hostiles(player)))
    foe.position = (player.position[0] + 1, player.position[1])
    engine.apply_actions(
        (
            PlannedAction(
                entity_id="player",
                action_id="USE_SKILL",
                skill_id="SKILL_1",
                target_id=foe.entity_id,
            ),
        )
    )
    assert foe.statuses.get("POISON") == 5, "즉발 재주의 effects 가 안 걸렸다"
    assert foe.hp < foe.hp_max, "피해도 함께 들어가야 한다"


def test_the_effect_is_written_down(balance, templates):
    """★ 조용히 걸리면 「왜 중독됐지」가 된다 — 얹은 것도 로그에 남는다 (P1)."""
    from game.app.skills.catalog import SkillEffect

    engine = build_engine(templates["open_field"], balance, seed=3)
    engine.config.skills["SKILL_1"] = SkillDef(
        skill_id="SKILL_1",
        shape=SkillShape(kind="SINGLE"),
        coef_pct=100,
        hits=HITS_TARGET,
        effects=(SkillEffect(kind="STATUS", status="SLOW", duration=3),),
    )
    player = engine.state.entities["player"]
    foe = next(iter(engine.state.list_hostiles(player)))
    foe.position = (player.position[0] + 1, player.position[1])
    engine.apply_actions(
        (
            PlannedAction(
                entity_id="player",
                action_id="USE_SKILL",
                skill_id="SKILL_1",
                target_id=foe.entity_id,
            ),
        )
    )
    assert any("SLOW" in str(one.expr) for one in engine.log.entries)
