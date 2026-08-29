"""프리셋 슬롯·공유 코드·세이브 파일 테스트 (로드맵 W5, GDD §2.3, TDD §9).

`test_meta.py` 에서 갈라 나왔다 — 앞쪽은 "런을 넘어 무엇이 쌓이는가", 여기는 "쌓인 것을
어떻게 담고 옮기는가" 다. 공유 코드가 왕복해도 같은 규칙표인가, 세이브 파일이 같은
상태에서 바이트까지 같은가를 본다 (R5).
"""

import json

import pytest

from game.app.services.manage_meta import (
    RunSummary,
    add_preset,
    apply_run_result,
    filter_preset_rules,
    find_preset,
    load_meta_save,
    remove_preset,
    save_meta_save,
)
from game.config import BLOCKS_PATH, ENEMY_RULESETS_PATH
from game.schemas.blocks import load_block_catalog
from game.schemas.meta_save import (
    MAX_PRESET_SLOTS,
    META_FORMAT_TAG,
    MetaSave,
    RulePreset,
    build_meta_payload,
    parse_meta_save,
)
from game.schemas.preset_code import (
    PRESET_CODE_PREFIX,
    PRESET_CODE_VERSION,
    export_preset_code,
    get_code_version,
    parse_preset_code,
)
from game.schemas.ruleset import load_rulesets

SUMMONER_KIND = "goblin_summoner"
ARCHER_KIND = "goblin_archer"


@pytest.fixture(scope="module")
def enemy_rulesets():
    return load_rulesets(ENEMY_RULESETS_PATH)


@pytest.fixture(scope="module")
def catalog():
    return load_block_catalog(BLOCKS_PATH)


@pytest.fixture
def sample_preset(enemy_rulesets):
    return RulePreset(name="카이팅 v3", ruleset=enemy_rulesets["ai_longbow"])


# --- 프리셋 8슬롯 ----------------------------------------------------------


def test_preset_slots_stop_at_eight(sample_preset):
    meta = MetaSave()
    for index in range(MAX_PRESET_SLOTS):
        meta = add_preset(meta, RulePreset(f"슬롯{index}", sample_preset.ruleset))
    assert len(meta.presets) == MAX_PRESET_SLOTS
    with pytest.raises(ValueError, match="가득"):
        add_preset(meta, RulePreset("하나 더", sample_preset.ruleset))


def test_same_name_replaces_the_slot(sample_preset, enemy_rulesets):
    meta = add_preset(MetaSave(), sample_preset)
    replaced = RulePreset(sample_preset.name, enemy_rulesets["ai_rusher"])
    meta = add_preset(meta, replaced)
    assert len(meta.presets) == 1
    assert find_preset(meta, sample_preset.name).ruleset.ruleset_id == "ai_rusher"


def test_removed_preset_is_gone(sample_preset):
    meta = remove_preset(add_preset(MetaSave(), sample_preset), sample_preset.name)
    assert meta.presets == ()
    assert find_preset(meta, sample_preset.name) is None


def test_locked_rules_are_dropped_on_load(sample_preset):
    meta = MetaSave(
        unlocked_perceptions=("target_distance",), unlocked_actions=("ATTACK", "RETREAT")
    )
    loaded = filter_preset_rules(sample_preset, meta)
    actions = tuple(rule.action for rule in loaded.ruleset.rules)
    # SKILL_1 은 미해금이라 그 줄만 빠지고 나머지는 순서대로 남는다.
    assert actions == ("RETREAT", "ATTACK")
    assert loaded.name == sample_preset.name


# --- 공유 코드 -------------------------------------------------------------


def test_preset_code_round_trip(enemy_rulesets):
    for ruleset_id, ruleset in sorted(enemy_rulesets.items()):
        preset = RulePreset(name=f"복제 {ruleset_id}", ruleset=ruleset)
        restored = parse_preset_code(export_preset_code(preset))
        assert restored == preset


def test_preset_code_has_version_prefix(sample_preset):
    code = export_preset_code(sample_preset)
    assert code.startswith(PRESET_CODE_PREFIX)
    assert get_code_version(code) == PRESET_CODE_VERSION


def test_same_preset_gives_the_same_code(sample_preset, enemy_rulesets):
    twin = RulePreset(name=sample_preset.name, ruleset=enemy_rulesets["ai_longbow"])
    assert export_preset_code(sample_preset) == export_preset_code(twin)


def test_code_survives_copy_paste_damage(sample_preset):
    code = export_preset_code(sample_preset)
    mangled = f"  {code.rstrip('=')}\n"
    assert parse_preset_code(mangled) == sample_preset


@pytest.mark.parametrize("code", ["", "hello", "v2", "9:abc", "vx:abc"])
def test_codes_without_a_version_are_rejected(code):
    with pytest.raises(ValueError, match="시작해야"):
        parse_preset_code(code)


def test_other_generation_code_is_rejected(sample_preset):
    body = export_preset_code(sample_preset)[len(PRESET_CODE_PREFIX) :]
    with pytest.raises(ValueError, match="세대"):
        parse_preset_code(f"v1:{body}")


@pytest.mark.parametrize("body", ["!!!!", "AAAA"])
def test_broken_code_body_is_rejected(body):
    with pytest.raises(ValueError, match="풀 수 없다"):
        parse_preset_code(PRESET_CODE_PREFIX + body)


def test_truncated_code_is_rejected(sample_preset):
    code = export_preset_code(sample_preset)
    with pytest.raises(ValueError, match="풀 수 없다"):
        parse_preset_code(code[: len(code) // 2])


# --- 파일 저장 -------------------------------------------------------------


def test_missing_file_gives_an_empty_save(tmp_path):
    assert load_meta_save(tmp_path / "없다.json") == MetaSave()


def test_file_round_trip_keeps_everything(tmp_path, sample_preset, catalog):
    meta = apply_run_result(
        MetaSave(),
        RunSummary(
            floor_reached=3,
            seen_perceptions=("target_distance", "self_hp_percent"),
            seen_actions=("ATTACK", "RETREAT"),
            encountered_kinds=(SUMMONER_KIND, ARCHER_KIND),
            defeated_kinds=(ARCHER_KIND,),
        ),
        catalog,
    )
    meta = add_preset(meta, sample_preset)
    target = tmp_path / "meta_save.json"
    save_meta_save(meta, target)
    assert load_meta_save(target) == meta


def test_saved_file_is_byte_identical_for_the_same_save(tmp_path, sample_preset):
    target = tmp_path / "meta_save.json"
    meta = add_preset(MetaSave(best_floor=2), sample_preset)
    save_meta_save(meta, target)
    first = target.read_bytes()
    save_meta_save(meta, target)
    assert target.read_bytes() == first


def test_save_creates_the_directory(tmp_path):
    target = tmp_path / "volume" / "meta_save.json"
    save_meta_save(MetaSave(), target)
    assert json.loads(target.read_text(encoding="utf-8"))["format"] == META_FORMAT_TAG


def test_save_leaves_no_temp_file(tmp_path):
    save_meta_save(MetaSave(), tmp_path / "meta_save.json")
    assert [path.name for path in sorted(tmp_path.iterdir())] == ["meta_save.json"]


def test_newer_format_is_rejected():
    payload = build_meta_payload(MetaSave())
    payload["format"] = "v99"
    with pytest.raises(ValueError, match="새 세이브"):
        parse_meta_save(payload)


@pytest.mark.parametrize("tag", [None, "", "1", "vx"])
def test_bad_format_tag_is_rejected(tag):
    payload = build_meta_payload(MetaSave())
    if tag is None:
        del payload["format"]
    else:
        payload["format"] = tag
    with pytest.raises(ValueError):
        parse_meta_save(payload)


def test_hand_edited_save_is_normalized():
    payload = build_meta_payload(MetaSave())
    payload["unlocked_actions"] = ["RETREAT", "ATTACK"]
    payload["bestiary"] = [
        {"kind_id": SUMMONER_KIND, "encounters": 1, "defeats": 0},
        {"kind_id": ARCHER_KIND, "encounters": 2, "defeats": 1},
    ]
    meta = parse_meta_save(payload)
    assert meta.unlocked_actions == ("ATTACK", "RETREAT")
    assert tuple(record.kind_id for record in meta.bestiary) == (ARCHER_KIND, SUMMONER_KIND)
