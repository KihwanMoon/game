"""자산 파일에서 세대 번호를 읽는다.

**한 곳에서만 읽는다.** 여섯 파일의 버전 키 이름이 제각각이라(`block_list_version`,
`balance_version`, …), 부르는 쪽마다 키를 적으면 오타 하나가 "버전이 안 올라갔다" 로
나타난다 — 그리고 그것은 조용하다.

파싱된 객체가 아니라 **원시 JSON 에서 읽는다.** 세대는 파일의 성질이지 로더가 만들어
내는 값이 아니고, 로더마다 버전을 실어 나르게 하면 로더 여섯 개의 시그니처가 전부
바뀐다.
"""

import json
from pathlib import Path

from game.config import (
    BALANCE_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    ITEMS_PATH,
    ROOM_TEMPLATES_PATH,
    SKILLS_PATH,
)
from game.schemas.run_ticket import ContentVersions

# 자산에서 그 파일이 쓰는 버전 키로. 이름이 통일돼 있지 않은 것은 파일마다 따로
# 자라났기 때문이며, 지금 통일하면 이미 배포된 파일과 어긋난다.
VERSION_KEYS: dict[str, tuple[Path, str]] = {
    "blocks": (BLOCKS_PATH, "block_list_version"),
    "balance": (BALANCE_PATH, "balance_version"),
    "items": (ITEMS_PATH, "item_list_version"),
    "skills": (SKILLS_PATH, "skill_list_version"),
    "rooms": (ROOM_TEMPLATES_PATH, "room_list_version"),
    "enemies": (ENEMY_RULESETS_PATH, "enemy_list_version"),
}


def read_content_versions() -> ContentVersions:
    """여섯 자산의 세대를 읽는다.

    Returns:
        자산별 세대.

    Raises:
        KeyError: 어느 파일에 버전 키가 없는 경우. **기본값을 주지 않는다** — 없는
            버전을 0 으로 채우면 파일이 바뀌어도 코어 버전이 그대로다.
    """
    values = {}
    for name, (path, key) in VERSION_KEYS.items():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if key not in raw:
            raise KeyError(f"{path.name} 에 {key} 가 없다")
        values[name] = int(raw[key])
    return ContentVersions(**values)
