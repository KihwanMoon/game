"""디자인 시스템 정본과 저장소 구현이 어긋나면 그날 잡는다.

**드리프트가 조사가 되면 이미 늦다.** 토큰이 그랬다 — 열한 개가 어긋난 것을 몇 주 뒤에
전수 조사로 알았다. 컴포넌트는 그보다 더 조용하다: 이름이 같고 타입만 갈린 자리는
화면이 멀쩡히 그려지기 때문이다(배속이 문자열 대 숫자였다).

**구현을 복사하지 않는다.** 저장소에는 이미 구현이 있고(`frontend/src/ds`), 필요한 것은
「정본이 무엇을 약속하는가」뿐이다. `.jsx` 를 떠 오면 그 사본이 또 썩고, 그것이 지금
고치려는 문제다.

그래서 여기서 재는 것은 **차이의 목록이 기록과 같은가** 하나다. 새 차이가 생기면
정본을 고치거나 `design/components.contract.json` 에 사유와 함께 적어야 통과한다.
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTRACT_PATH = REPO_ROOT / "design" / "components.contract.json"

DS_DIR = REPO_ROOT / "frontend" / "src" / "ds"

# 컴포넌트가 아닌 파일. 갤러리와 검사는 화면 부품이 아니다.
NOT_COMPONENTS = frozenset({"ds.test", "gallery", "galleryMain", "index"})

# `readonly name?: Type` 한 줄에서 이름만 집는다.
PROP_PATTERN = re.compile(r"^\s*readonly\s+([A-Za-z0-9_]+)\??\s*:")


def read_contract() -> dict:
    """기록해 둔 정본 계약을 읽는다.

    Returns:
        계약 문서.
    """
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def list_repo_props(name: str) -> tuple[str, ...] | None:
    """저장소 컴포넌트의 props 이름을 뽑는다.

    Args:
        name: 컴포넌트 이름.

    Returns:
        props 이름들. 그 파일이 없으면 None.
    """
    path = DS_DIR / f"{name}.tsx"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    block = re.search(rf"export interface {name}Props \{{(.*?)\n\}}", text, re.S)
    if block is None:
        return ()
    return tuple(
        found.group(1)
        for line in block.group(1).splitlines()
        if (found := PROP_PATTERN.match(line)) is not None
    )


def list_repo_components() -> tuple[str, ...]:
    """저장소가 가진 컴포넌트 이름들.

    Returns:
        이름 순의 컴포넌트들.
    """
    return tuple(
        sorted(
            path.stem
            for path in DS_DIR.glob("*.tsx")
            if path.stem not in NOT_COMPONENTS and not path.stem.endswith(".test")
        )
    )


def build_difference(name: str, design_props: list[str]) -> dict[str, list[str]]:
    """정본과 저장소의 props 차이를 낸다.

    Args:
        name: 컴포넌트 이름.
        design_props: 정본이 약속한 props.

    Returns:
        `repo_only`·`design_only` 절. 같으면 빈 절이다.
    """
    repo_props = list_repo_props(name)
    if repo_props is None:
        return {"design_only": sorted(design_props)}
    found: dict[str, list[str]] = {}
    repo_only = sorted(set(repo_props) - set(design_props))
    design_only = sorted(set(design_props) - set(repo_props))
    if repo_only:
        found["repo_only"] = repo_only
    if design_only:
        found["design_only"] = design_only
    return found


def test_every_recorded_component_exists():
    """★ 정본에 있는 것은 저장소에도 있어야 한다.

    없으면 그 컴포넌트를 쓰는 시트가 저장소 어디에도 대응이 없다는 뜻이다.
    """
    contract = read_contract()
    for name in contract["components"]:
        assert list_repo_props(name) is not None, f"저장소에 없다: {name}"


def test_the_missing_list_is_exact():
    """★ 저장소에만 있는 컴포넌트 목록이 기록과 같다.

    새로 만든 컴포넌트를 정본에 안 올리면 여기서 걸린다 — 지금 셋이 그 상태이고,
    셋 다 등급·연결선 토큰을 쓰는 쪽이라 그 토큰이 정본에서 아무 데도 안 쓰인다.
    """
    contract = read_contract()
    extra = sorted(set(list_repo_components()) - set(contract["components"]))
    assert extra == sorted(contract["missing_in_design"]), (
        f"정본에 없는 컴포넌트가 바뀌었다: {extra}"
    )


def test_no_unrecorded_divergence():
    """★ **어긋난 자리는 전부 사유와 함께 적혀 있어야 한다.**

    이것이 이 검사의 본체다. 새 차이가 생기면 정본을 고치거나, 남겨 둘 이유를
    `design/components.contract.json` 에 적어야 통과한다 — 드리프트를 몇 주 뒤 조사가
    아니라 그날의 실패로 만든다.
    """
    contract = read_contract()
    recorded = contract["divergences"]
    for name, design_props in contract["components"].items():
        found = build_difference(name, design_props)
        if not found:
            continue
        assert name in recorded, f"기록 없는 차이: {name} {found}"
        for side, names in found.items():
            assert recorded[name].get(side, []) == names, (
                f"{name} 의 {side} 가 기록과 다르다: {names} != {recorded[name].get(side, [])}"
            )


def test_every_divergence_carries_a_reason():
    """★ 사유 없는 예외는 기록이 아니라 알리바이다.

    「왜 다른가」를 안 적으면 다음 사람이 고쳐야 할지 그대로 둘지 판단할 수 없다.
    """
    for name, entry in read_contract()["divergences"].items():
        assert entry.get("why", "").strip(), f"사유가 없다: {name}"


def test_every_missing_component_carries_a_reason():
    """정본에 없는 것도 왜 필요한지 적어 둔다 — 올릴 때 그 문장이 명세가 된다."""
    for name, why in read_contract()["missing_in_design"].items():
        assert why.strip(), f"사유가 없다: {name}"
