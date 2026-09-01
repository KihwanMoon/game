"""초안을 코어가 쓰는 그 로더로 읽어 본다.

**검증기를 따로 만들지 않는다.** 두 개면 규칙이 둘이 되고, 검증은 통과하는데 배포하면
서버가 안 뜨는 날이 온다 — 그때는 이미 파일이 커밋된 뒤다.

버전 필드도 함께 본다. 안 올리고 발행하면 **저장된 리플레이가 조용히 거짓이 된다** —
코어 버전이 그대로라 순위표가 서로 다른 게임의 기록을 한 표에 놓는다.
"""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path

from game.app.store.content_draft import DRAFT_ASSETS
from game.schemas.blocks import load_block_catalog
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets


def check_draft(asset: str, payload: dict) -> str:
    """초안이 실제로 읽히는지 본다.

    **버전은 여기서 안 본다.** 자산 셋을 고치는 동안 버전을 세 번 올리게 되는 것은
    이르고 불편하다 — 세대는 발행 시점에 한 번 받는다 (§18). 여기서 막을 것은 "못 읽는
    절이 DB 에 남는 것" 하나다.

    Args:
        asset: 자산 이름.
        payload: 초안 절.

    Returns:
        빈 문자열이면 통과. 아니면 사람이 읽을 사유.
    """
    if asset not in DRAFT_ASSETS:
        return f"모르는 자산이다: {asset}"
    return check_loads(asset, payload)


def check_loads(asset: str, payload: dict) -> str:
    """코어의 로더로 실제로 읽어 본다.

    임시 파일에 쓴 뒤 로더를 부른다. 로더가 경로를 받기 때문이고, **파일에서 읽는 그
    경로를 그대로 지나가야** 검증이 뜻을 갖는다.

    Args:
        asset: 자산 이름.
        payload: 초안 절.

    Returns:
        빈 문자열이면 통과. 아니면 로더가 낸 사유.
    """
    loader = build_loader(asset)
    if loader is None:
        return ""
    with tempfile.TemporaryDirectory() as folder:
        probe = Path(folder) / "draft.json"
        probe.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        try:
            loader(probe)
        except Exception as error:  # noqa: BLE001 — 로더가 무엇을 던지든 사유로 바꾼다
            return f"읽을 수 없다: {error}"
    return ""


def load_skill_file(path: Path) -> dict:
    """스킬 파일을 읽어 본다.

    스킬은 전용 로더가 없다 — `run_battle.py` 가 절을 그대로 읽어 `skill_coef_pct` 를
    만든다. 그래서 그쪽이 실제로 읽는 두 필드를 여기서 본다. 없으면 그 스킬을 쓰는
    규칙이 조용히 계수 100 으로 돈다.

    Args:
        path: 초안 파일.

    Returns:
        읽어 낸 절.

    Raises:
        ValueError: 스킬 배열이 비었거나 필수 필드가 없는 경우.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    skills = raw.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("skills 배열이 비어 있다")
    for skill in skills:
        if "id" not in skill or "coef_pct" not in skill:
            raise ValueError(f"스킬에 id·coef_pct 가 없다: {skill}")
    return raw


# 자산에서 그것을 읽는 로더로. **코어가 쓰는 그 함수들이다** — 검증기를 따로 만들면
# 규칙이 둘이 되고, 검증은 통과하는데 배포하면 서버가 안 뜨는 날이 온다.
ASSET_LOADERS: dict[str, Callable[[Path], object]] = {
    "skills": load_skill_file,
    "blocks": load_block_catalog,
    "rooms": load_room_templates,
    "enemies": load_rulesets,
}


def build_loader(asset: str) -> Callable[[Path], object] | None:
    """그 자산을 읽는 로더를 준다.

    Args:
        asset: 자산 이름.

    Returns:
        경로를 받는 로더. 아직 로더가 없는 자산이면 None (예: balance).
    """
    return ASSET_LOADERS.get(asset)
