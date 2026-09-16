"""격자를 SVG 로 굽는다 — **이 파일이 재현 경로다**.

    python3 design/art/items/bake.py

**SVG 를 손으로 고치지 않는다.** 격자(`_sprites.py`)가 정본이고 SVG 는 산출물이다.
손으로 고치면 다음에 구울 때 조용히 되돌아간다.

**그림을 더할 때**: `_sprites.py` 에 격자를 적고 이것을 돌린다. 이름은 곧 파일 이름이자
`catalog_id` 의 접두사다 (`frontend/src/content/itemArt.ts`). 화면 쪽 검사가 카탈로그
전수를 보므로, 이름이 어긋나면 `npm test` 가 먼저 운다.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from _build import build_svg, check_grid  # noqa: E402 — 경로를 세운 뒤에 읽는다
from _sprites import SPRITES  # noqa: E402 — 같은 이유


def apply_bake() -> int:
    """격자를 전부 검사하고 SVG 로 굽는다.

    Returns:
        구운 장수.

    Raises:
        ValueError: 격자가 16×16 이 아니거나 팔레트에 없는 글자가 섞인 경우.
    """
    out = pathlib.Path(__file__).parent
    for name, rows in sorted(SPRITES.items()):
        check_grid(rows)
        (out / f"{name}.svg").write_text(build_svg(rows), encoding="utf-8")
    return len(SPRITES)


if __name__ == "__main__":
    print(f"{apply_bake()}장 구웠다")
