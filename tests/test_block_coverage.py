"""팔레트가 보여 주는 블록에는 그것을 쓰는 예시가 있어야 한다.

**예시 없는 블록은 있어도 없는 것과 같다.** 카탈로그에 21/16/10 이 실려 있고 팔레트가
전부 보여 주는데, 실제로 쓰는 규칙표가 없으면 세 가지가 한꺼번에 무너진다.

1. 화면이 답을 못 준다 — 「이걸로 뭘 하지」에 답하는 예시가 하나도 없다.
2. 벤치마크가 그 경로를 한 번도 안 태운다 — 단위 검사만 남고 통합 회귀가 없다.
3. 밸런스가 눈에 안 띈다 — 아무도 안 쓰는 블록은 세도 안 세도 같다.

동결된 두 파일(`benchmark`·`g0_examples`)은 못 건드리므로, 그 뒤에 들어온 블록은
`later_blocks.json` 이 받는다. 이 검사는 **덮이지 않은 블록의 목록이 기록과 같은가**를
본다 — 새 블록을 카탈로그에 더하고 예시를 안 지으면 그날 걸린다.
"""

import json
from pathlib import Path

from game.config import (
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    LATER_BLOCKS_RULESETS_PATH,
)

# 아직 어느 규칙표도 안 쓰는 블록들. **비워 두는 것이 목표가 아니다** — 여기 있는 것은
# 「왜 아직 예시가 없는지」가 설명되는 것뿐이어야 한다.
UNCOVERED: dict[str, str] = {
    "SET_FLAG": ("플래그는 규칙의 set_flag 필드로 세운다 — 행동으로서의 SET_FLAG 는 자리가 겹친다"),
    "BOSS": "보스 방이 하나뿐이라 예시 규칙표가 그 방 전용이 된다",
    "self_has_skill": ("self_skill_ready 가 장착과 쿨타임을 함께 보므로 이쪽은 더 좁은 질문이다"),
    "self_has_status": "상태이상을 거는 적이 아직 적고, 걸린 판을 예시로 재현하기 어렵다",
    "self_cpu_headroom": (
        "예산은 편집 화면이 보여 준다 — 판 중에 그것을 읽어 행동을 바꾸는 전략이 아직 없다"
    ),
    "self_on_heal_tile": (
        "회복타일 위에서 버티는 것이 1층 실측에서 손해였다 (read_the_ground 20%)"
    ),
    "target_is_casting": "시전이 한 틱이라 조건이 참인 창이 너무 좁다",
    "CASTING": "위와 같은 이유다",
    # 아래 셋은 **지어 보고 재 본 뒤** 기록으로 넘긴 것이다. 안 쓰는 이유가 「아직 안
    # 지었다」가 아니라 「지어 보니 값을 못 한다」이며, 그 차이가 다음 사람에게 중요하다.
    "target_hp_percent": (
        "LOWEST_HP 셀렉터와 하는 일이 겹친다 — 여는 줄에 걸면 만피인 적을 못 쳐 "
        "1층 5%(폴백 6%) 였다"
    ),
    "cover_wall_distance": (
        "엄폐로 물러나는 데 쓴 틱이 때리는 틱보다 비쌌다 — read_the_ground 1층 20% (같은 뼈대 46%)"
    ),
    "self_scroll_count": (
        "주문서는 회복이 아니라 보호다. 물약 자리를 주문서로 바꾼 표는 "
        "한 번도 낫지 못해 1층 0% 였다"
    ),
}


def list_used_ids() -> set[str]:
    """규칙표 파일 전량이 쓰는 블록 id 를 모은다.

    문자열이면 무엇이든 담는다 — 블록 id 가 `action`·`lhs`·`target`·`lhs_param` 등
    여러 자리에 오므로, 자리마다 규칙을 적으면 새 자리가 생길 때 조용히 빠진다.

    Returns:
        쓰인 id 들.
    """
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key.startswith("_"):
                    continue
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str):
            found.add(node)

    for path in (
        G0_RULESETS_PATH,
        BENCHMARK_RULESETS_PATH,
        ENEMY_RULESETS_PATH,
        LATER_BLOCKS_RULESETS_PATH,
    ):
        walk(json.loads(Path(path).read_text(encoding="utf-8")))
    return found


def list_uncovered() -> set[str]:
    """어느 규칙표도 안 쓰는 블록 id 를 모은다.

    Returns:
        안 쓰이는 id 들.
    """
    catalog = json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))
    every = {
        block["id"]
        for section in ("perceptions", "actions", "selectors")
        for block in catalog[section]
    }
    return every - list_used_ids()


def test_the_uncovered_list_is_exact():
    """★ **안 덮인 블록의 목록이 기록과 같다.**

    새 블록을 카탈로그에 더하고 예시를 안 지으면 여기서 걸린다. 팔레트는 그것을 보여
    주는데 무엇을 보여 주는 예시가 없으면, 사람에게는 「이걸로 뭘 하지」가 남고
    벤치마크에는 한 번도 안 타는 경로가 남는다.
    """
    assert sorted(list_uncovered()) == sorted(UNCOVERED)


def test_every_uncovered_block_carries_a_reason():
    """사유 없는 예외는 기록이 아니라 알리바이다 — 다음 사람이 지을지 말지 판단해야 한다."""
    for block_id, why in UNCOVERED.items():
        assert why.strip(), f"사유가 없다: {block_id}"


def test_the_newer_action_forms_are_used():
    """★ v5·v6 형식을 실제로 쓰는 표가 있다.

    `USE_SKILL[id]`·`USE_ITEM[tag]` 는 스킬과 아이템이 늘어도 블록 목록이 안 바뀌게
    하려고 만든 형식인데(결정 #04), 쓰는 표가 없으면 그 계약이 한 번도 안 태워진다.
    """
    used = list_used_ids()
    assert "USE_SKILL" in used
    assert "USE_ITEM" in used
    assert "self_skill_ready" in used


def test_the_skill_perception_list_matches_the_catalog():
    """★ **인지 목록이 `USE_SKILL` 파라미터와 같다** (2026-09-10, 실제 신고).

    갈리면 그 스킬의 인지값이 **키째로 안 만들어진다.** 없는 값은 참도 거짓도 아니라
    화면에 「없음」으로 뜨고, 그 규칙은 영영 발동하지 않는다 — 사람이 본 것은
    `내 스킬 준비됨[CHAIN_BOLT](없음) == 참` 이었다.

    TS 쪽이 그렇게 갈려 있었다. 전투는 브라우저에서 돌고 재시뮬은 파이썬이 하므로,
    **같은 판이 두 코어에서 다르게 돌고 있었다** (G3). 골든은 이 경로를 안 덮는다 —
    골든 규칙표 중 마법 인지를 쓰는 것이 없다.
    """
    from game.app.simulation.perception import SKILL_IDS

    catalog = json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))
    params = [block for block in catalog["actions"] if block["id"] == "USE_SKILL"][0]["param"][
        "values"
    ]
    assert set(SKILL_IDS) == set(params), "인지 목록과 USE_SKILL 파라미터가 갈렸다"


def test_the_status_perception_list_matches_the_catalog():
    """★ **상태 목록도 같은 규율이다** (2026-09-11).

    스킬에서 겪은 것과 같은 자리다 — `self_has_status[GUARD]` 를 물었는데 인지가 그 키를
    안 만들면 화면에 「없음」이 뜨고 그 규칙은 영영 발동하지 않는다. 주문서 겹쳐 쓰기를
    규칙표로 피하려면 이 둘이 반드시 붙어 있어야 한다.
    """
    from game.app.simulation.perception import STATUS_NAMES

    catalog = json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))
    params = [block for block in catalog["perceptions"] if block["id"] == "self_has_status"][0][
        "param"
    ]["values"]
    assert set(STATUS_NAMES) == set(params), "인지 목록과 self_has_status 파라미터가 갈렸다"


def test_every_item_tag_the_catalog_names_can_be_used():
    """★ **블록이 가리키는 태그는 전부 실행기가 안다** (2026-09-11).

    `USE_ITEM[FLAME]` 을 고를 수 있는데 실행기가 그 태그를 모르면 「쓸 줄 모른다 — 틱
    낭비」로 떨어진다. 규칙표를 짠 사람에게 그것은 **참인데 아무 일도 안 일어나는 규칙**,
    즉 P1 을 가장 직접적으로 깨는 모양이다.
    """
    from game.app.simulation.abilities import ITEM_POTION, ITEM_SCROLL
    from game.app.simulation.support_actions import SCROLL_RESOLVERS

    catalog = json.loads(BLOCKS_PATH.read_text(encoding="utf-8"))
    params = [block for block in catalog["actions"] if block["id"] == "USE_ITEM"][0]["param"][
        "values"
    ]
    known = {ITEM_POTION, ITEM_SCROLL} | set(SCROLL_RESOLVERS)
    assert set(params) <= known, f"실행기가 모르는 태그다: {set(params) - known}"
