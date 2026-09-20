"""같은 것을 두 이름으로 부르지 않는가.

2026-09-19 에 같은 재주가 화면 셋에서 세 이름이었다 — 발행한 「돌려치기」가 편집기에서는
「광역 공격」, 전투 쿨타임 줄에서는 「광역」이었다. 화면 쪽은 폴백을 정본 아래로 내려
고쳤지만, **정본이 둘이면 언젠가 또 갈린다.**

행동 블록과 재주는 별도 파일에 각자 ``label_ko`` 를 들고 있고, 그 둘이 같은 것을 가리키는
자리가 일곱 있다(``USE_SKILL[X]`` 의 별칭들). 그 자리에서 두 이름이 어긋나지 않는지 본다 —
어긋나면 어느 쪽을 믿어야 하는지 아무도 모른다.
"""

import json
import re

import pytest

from game.config import BALANCE_PATH, BLOCKS_PATH, SKILLS_PATH


@pytest.fixture(name="blocks")
def fixture_blocks() -> dict:
    """블록 목록 원문.

    Returns:
        blocks.json 내용.
    """
    return json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(name="skills")
def fixture_skills() -> dict:
    """재주 목록 원문.

    Returns:
        skills.json 내용.
    """
    return json.loads(SKILLS_PATH.read_text(encoding="utf-8"))


def test_action_and_skill_agree_on_names(blocks: dict, skills: dict) -> None:
    """같은 id 를 든 행동과 재주가 같은 이름을 쓴다."""
    names = {one["id"]: one.get("label_ko") for one in skills["skills"]}
    clashed = {
        one["id"]: (one["label_ko"], names[one["id"]])
        for one in blocks["actions"]
        if one["id"] in names and names[one["id"]] is not None
        if names[one["id"]] != one["label_ko"]
    }
    assert clashed == {}


def test_skill_param_values_have_definitions(blocks: dict, skills: dict) -> None:
    """USE_SKILL 이 고르게 하는 재주는 **전부** 정의가 있다.

    2026-09-19 까지 ``SUMMON`` 하나가 빠져 있었다 — 인자 목록에만 있고 행이 없어 이름을
    화면이 손으로 들었다. 행을 채웠으므로 이제 예외가 없고, 예외 자리를 남겨 두지
    않는다: 하나를 허용해 두면 다음 것이 그 자리에 조용히 들어온다.
    """
    defined = {one["id"] for one in skills["skills"]}
    values = next(one for one in blocks["actions"] if one["id"] == "USE_SKILL")["param"]["values"]
    assert sorted(set(values) - defined) == []


def test_aliases_are_declared(blocks: dict) -> None:
    """별칭은 자기가 어느 길의 별칭인지 적어 둔다.

    팔레트가 이것을 읽어 같은 것을 두 번 세우지 않는다. 손으로 목록을 들면 재주가 늘
    때 또 갈린다.
    """
    by_param = {
        value for one in blocks["actions"] for value in (one.get("param") or {}).get("values", [])
    }
    for action in blocks["actions"]:
        if action["id"] in by_param:
            continue
        # 인자로 안 닿는 것은 스스로 적어야 한다. USE_POTION 이 그 하나다.
        assert action["id"] not in {"USE_POTION"} or action.get("_alias_of")


# 설명문에 나오면 안 되는 것 둘. 코드에서만 뜻이 있는 이름들이다.
FIELD_NAME = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
FILE_NAME = re.compile(r"\b[a-z_]+\.(?:py|ts|tsx|json|sh)\b")


def list_public_notes(blocks: dict, skills: dict) -> list[tuple[str, str]]:
    """공개 페이지로 나가는 설명문 전부.

    Args:
        blocks: 블록 목록 원문. 쓰지 않지만 픽스처를 맞춘다.
        skills: 재주 목록 원문.

    Returns:
        (어디, 글) 쌍들.
    """
    balance = json.loads(BALANCE_PATH.read_text(encoding="utf-8"))
    rows = [(f"몬스터 {one['id']}", one.get("_note", "")) for one in balance["enemies"]]
    rows += [(f"재주 {one['id']}", one.get("_note", "")) for one in skills["skills"]]
    return [(name, text) for name, text in rows if text]


def test_notes_do_not_name_fields(blocks: dict, skills: dict) -> None:
    """★ 설명문이 필드 이름과 파일 이름을 안 쓴다 (2026-09-20).

    이 글은 **공개 도감 페이지로 그대로 나간다**(`/codex/`). 읽는 사람은 ``guard_ticks``
    가 얼마인지 모르고 ``apply_damage`` 가 무엇인지도 모른다 — 실제로 「다음 guard_ticks
    동안 받는 피해를 guard_pct 만큼 줄인다」가 나가고 있었다.

    한글 이름은 **관리 표가 정한 것**을 쓴다(`admin/skillFields`). 화면과 설명이 다른
    말을 쓰면 고치는 사람이 어느 칸을 만져야 하는지 못 찾는다.
    """
    bad: dict[str, list[str]] = {}
    for name, text in list_public_notes(blocks, skills):
        found = sorted(set(FIELD_NAME.findall(text)) | set(FILE_NAME.findall(text)))
        if found:
            bad[name] = found
    assert bad == {}
