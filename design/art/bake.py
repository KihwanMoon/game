"""격자를 SVG 로 굽는다 — **이 파일이 재현 경로다**.

    python3 design/art/bake.py

**한 자리에서 전부 굽는다.** 아이템과 몬스터가 각자 `bake.py` 를 들고 있었는데, 둘 다
같은 `_build` 를 부르고 같은 일을 했다 — 사본이 둘이면 한쪽만 고쳐지는 날이 온다.
mypy 가 그 사본을 먼저 잡았다(`Duplicate module named "bake"`): 패키지가 아니라
`sys.path` 로 읽는 파일이라 폴더가 이름을 안 갈라 준다.

**SVG 를 손으로 고치지 않는다.** 격자가 정본이고 SVG 는 산출물이다. 손으로 고치면
다음에 구울 때 조용히 되돌아간다.

**그림을 더할 때**: 그 식구의 격자 파일에 적고 이것을 돌린다. 이름은 곧 파일 이름이고,
화면이 그 이름으로 그림을 찾는다 — 아이템은 `catalog_id` 의 접두사
(`frontend/src/content/itemArt.ts`), 몬스터는 적 id 그대로
(`frontend/src/content/monsterArt.ts`). 양쪽 다 전수 검사가 있으므로 이름이 어긋나면
`npm test` 가 먼저 운다.
"""

import pathlib
import sys

ART = pathlib.Path(__file__).parent
# 격자 규격과 팔레트는 그림 전부가 함께 본다 — 같은 16×16 에 같은 다섯 색이다.
sys.path.insert(0, str(ART))
sys.path.insert(0, str(ART / "items"))
sys.path.insert(0, str(ART / "monsters"))

from _build import build_svg, check_grid  # noqa: E402 — 경로를 세운 뒤에 읽는다
from _item_sprites import SPRITES as ITEM_SPRITES  # noqa: E402 — 같은 이유
from _monster_sprites import SPRITES as MONSTER_SPRITES  # noqa: E402 — 같은 이유

# 식구 이름에서 (격자, 굽는 곳) 으로. 식구가 늘면 여기 한 줄이 는다.
FAMILIES: dict[str, tuple[dict[str, list[str]], pathlib.Path]] = {
    "items": (ITEM_SPRITES, ART / "items"),
    "monsters": (MONSTER_SPRITES, ART / "monsters"),
}


def apply_bake() -> dict[str, int]:
    """격자를 전부 검사하고 SVG 로 굽는다.

    Returns:
        식구 이름에서 구운 장수로.

    Raises:
        ValueError: 격자가 16×16 이 아니거나 팔레트에 없는 글자가 섞인 경우.
    """
    baked: dict[str, int] = {}
    for family, (sprites, out) in FAMILIES.items():
        for name, rows in sorted(sprites.items()):
            check_grid(rows)
            (out / f"{name}.svg").write_text(build_svg(rows), encoding="utf-8")
        baked[family] = len(sprites)
    return baked


if __name__ == "__main__":
    for _family, _count in apply_bake().items():
        print(f"{_family}: {_count}장 구웠다")
