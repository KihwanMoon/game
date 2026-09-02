"""블록 카탈로그 — 인지 변수·행동·셀렉터 목록 (GDD §3.2·§3.3·§3.4).

개수는 인지 18 / 행동 14 / 셀렉터 9 이며, 이 모듈이 로드 시점에 그것을 검사한다.
숫자가 어긋난 채로 조용히 로드되면 규칙표가 참조하는 블록이 사라져도 알 수 없다.

행동이 12 에서 13 이 된 것은 v3 의 SUMMON 추가다. GDD §5 가 "몬스터도 플레이어와
완전히 동일한 DSL 로 기술한다" 고 못박았는데 소환만 밸런스 속성으로 빠져 있어,
도감이 소환 주기를 규칙표 밖에서 따로 보여줘야 하는 모순이 있었다.

v4 는 치유형에 같은 일을 했다 (docs/04 H-1~H-3). 행동 HEAL 과 셀렉터 두 개
(ALLY_WOUNDED · TYPE_HEALER)가 늘었고, 인지 변수는 인자값만 늘어 18 그대로다.

**셀렉터에 진영이 붙었다.** targeted 행동은 자기가 요구하는 진영(target_faction)을
선언하고, 검증기가 `HEAL @NEAREST` 처럼 어긋난 조합을 거부한다. 진영을 인자로 두지
않은 이유는 docs/04 H-2 에 있다.

rhs_stats 는 조건 우변에 둘 수 있는 자기 스탯의 닫힌 목록이다 (F-2). 열어 두면
오타 난 스탯 이름이 조용히 거짓이 되어 규칙이 영영 발동하지 않는다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

# 콘텐츠 범위. 동결 대상이므로 상수로 박아 로드 때마다 대조한다.
PERCEPTION_COUNT = 21  # v7 에서 self_scroll_count 가 들어왔다 (§5 소모품 칸)
ACTION_COUNT = 16  # v6 에서 USE_ITEM 이 들어왔다 (#54)
SELECTOR_COUNT = 9
RHS_STAT_COUNT = 7  # v7 에서 scrolls 가 들어왔다 — potions 와 짝

# 셀렉터가 고르는 진영. 행동의 target_faction 도 이 둘 중 하나다.
FACTION_ENEMY = "enemy"
FACTION_ALLY = "ally"


@dataclass(frozen=True)
class BlockParam:
    """블록이 받는 인자. 예: 쿨타임[스킬], 플래그[A~D]."""

    name: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class PerceptionBlock:
    """인지 변수 하나. 규칙 조건의 좌변이 될 수 있는 것."""

    block_id: str
    category: str
    returns: str
    label_ko: str
    param: BlockParam | None = None
    value_range: tuple[int, int] | None = None


@dataclass(frozen=True)
class ActionBlock:
    """행동 하나. 규칙이 실행하는 것."""

    block_id: str
    category: str
    targeted: bool
    label_ko: str
    # 이 행동이 요구하는 대상 진영. 대상을 받지 않는 행동은 None 이다.
    target_faction: str | None = None
    # 이 행동이 받는 인자 (v5). USE_SKILL[skill] 이 이것을 쓴다 — 스킬마다 액션을
    # 더하면 블록 목록 버전이 계속 올라 랭킹 시즌이 갈린다 (docs/설계/5_스킬 §4).
    param: BlockParam | None = None


@dataclass(frozen=True)
class SelectorBlock:
    """타겟 셀렉터 하나. targeted 행동이 대상을 고르는 방식."""

    block_id: str
    label_ko: str
    # 이 셀렉터가 고르는 진영. 기본은 적대다 — v3 까지는 전부 적대였다.
    faction: str = FACTION_ENEMY


@dataclass(frozen=True)
class StatBlock:
    """조건 우변에 둘 수 있는 자기 스탯 하나 (F-2)."""

    block_id: str
    label_ko: str


@dataclass(frozen=True)
class BlockCatalog:
    """블록 목록 전체."""

    version: int
    perceptions: dict[str, PerceptionBlock]
    actions: dict[str, ActionBlock]
    selectors: dict[str, SelectorBlock]
    rhs_stats: dict[str, StatBlock]


def _build_param(raw: dict | None) -> BlockParam | None:
    """원시 딕셔너리에서 블록 인자를 만든다.

    Args:
        raw: JSON 의 param 절. 인자가 없는 블록이면 None.

    Returns:
        만들어진 인자, 또는 None.
    """
    if raw is None:
        return None
    return BlockParam(name=raw["name"], values=tuple(raw["values"]))


def _check_catalog_counts(catalog: BlockCatalog) -> list[str]:
    """동결된 개수와 실제 개수를 대조한다.

    Args:
        catalog: 검사할 카탈로그.

    Returns:
        불일치 메시지 목록. 전부 맞으면 빈 리스트.
    """
    expected = (
        ("perceptions", len(catalog.perceptions), PERCEPTION_COUNT),
        ("actions", len(catalog.actions), ACTION_COUNT),
        ("selectors", len(catalog.selectors), SELECTOR_COUNT),
        ("rhs_stats", len(catalog.rhs_stats), RHS_STAT_COUNT),
    )
    return [
        f"{name} 개수가 동결값과 다르다: {got} != {want}"
        for name, got, want in expected
        if got != want
    ]


def load_block_catalog(source_path: Path) -> BlockCatalog:
    """블록 목록 JSON 을 읽어 카탈로그를 만든다.

    Args:
        source_path: blocks.json 경로.

    Returns:
        동결 개수 검사를 통과한 카탈로그.

    Raises:
        ValueError: 개수가 동결값과 다르거나 id 가 중복된 경우.
    """
    raw = json.loads(source_path.read_text(encoding="utf-8"))

    perceptions = {
        item["id"]: PerceptionBlock(
            block_id=item["id"],
            category=item["category"],
            returns=item["returns"],
            label_ko=item["label_ko"],
            param=_build_param(item.get("param")),
            value_range=tuple(item["range"]) if "range" in item else None,
        )
        for item in raw["perceptions"]
    }
    actions = {
        item["id"]: ActionBlock(
            block_id=item["id"],
            category=item["category"],
            targeted=item["targeted"],
            label_ko=item["label_ko"],
            target_faction=item.get("target_faction"),
            param=_build_param(item.get("param")),
        )
        for item in raw["actions"]
    }
    selectors = {
        item["id"]: SelectorBlock(
            block_id=item["id"],
            label_ko=item["label_ko"],
            faction=item.get("faction", FACTION_ENEMY),
        )
        for item in raw["selectors"]
    }
    rhs_stats = {
        item["id"]: StatBlock(block_id=item["id"], label_ko=item["label_ko"])
        for item in raw["rhs_stats"]
    }

    # dict 로 모으면 중복 id 가 조용히 덮어써진다. 원본 길이와 대조해 잡는다.
    sections = ("perceptions", "actions", "selectors", "rhs_stats")
    raw_totals = sum(len(raw[section]) for section in sections)
    if len(perceptions) + len(actions) + len(selectors) + len(rhs_stats) != raw_totals:
        raise ValueError("블록 id 가 중복됐다")

    catalog = BlockCatalog(
        version=raw["block_list_version"],
        perceptions=perceptions,
        actions=actions,
        selectors=selectors,
        rhs_stats=rhs_stats,
    )
    problems = _check_catalog_counts(catalog)
    if problems:
        raise ValueError("; ".join(problems))
    return catalog
