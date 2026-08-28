"""블록 카탈로그 — 동결된 인지 변수·행동·셀렉터 목록 (GDD §3.2·§3.3·§3.4).

로드맵 Phase 0 에서 동결했고 이후 변경 금지다. 개수는 GDD §9 가 정한
인지 18 / 행동 12 / 셀렉터 7 이며, 이 모듈이 로드 시점에 그것을 검사한다.
숫자가 어긋난 채로 조용히 로드되면 규칙표가 참조하는 블록이 사라져도 알 수 없다.
"""

import json
from dataclasses import dataclass
from pathlib import Path

# GDD §9 가 정한 콘텐츠 범위. 동결 대상이므로 상수로 박아 로드 때마다 대조한다.
PERCEPTION_COUNT = 18
ACTION_COUNT = 12
SELECTOR_COUNT = 7


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


@dataclass(frozen=True)
class SelectorBlock:
    """타겟 셀렉터 하나. targeted 행동이 대상을 고르는 방식."""

    block_id: str
    label_ko: str


@dataclass(frozen=True)
class BlockCatalog:
    """동결된 블록 목록 전체."""

    version: int
    perceptions: dict[str, PerceptionBlock]
    actions: dict[str, ActionBlock]
    selectors: dict[str, SelectorBlock]


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
        )
        for item in raw["actions"]
    }
    selectors = {
        item["id"]: SelectorBlock(block_id=item["id"], label_ko=item["label_ko"])
        for item in raw["selectors"]
    }

    # dict 로 모으면 중복 id 가 조용히 덮어써진다. 원본 길이와 대조해 잡는다.
    raw_totals = len(raw["perceptions"]) + len(raw["actions"]) + len(raw["selectors"])
    if len(perceptions) + len(actions) + len(selectors) != raw_totals:
        raise ValueError("블록 id 가 중복됐다")

    catalog = BlockCatalog(
        version=raw["block_list_version"],
        perceptions=perceptions,
        actions=actions,
        selectors=selectors,
    )
    problems = _check_catalog_counts(catalog)
    if problems:
        raise ValueError("; ".join(problems))
    return catalog
