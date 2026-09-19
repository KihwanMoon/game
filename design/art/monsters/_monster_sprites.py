"""도트 격자 — 굽는 쪽이 보는 이름 하나.

**아이템 쪽과 같은 모양이다** (`design/art/items/_sprites.py`). 가르는 선도 같은 뜻이다 —
식구가 늘어나는 쪽(도깨비·무당)과 하나씩만 있는 쪽을 한 파일에 두면 다음에 400줄을
넘길 때 또 같은 고민을 한다 (§4).

**이름이 곧 파일 이름이자 `balance.json` 의 적 id 다.** 별칭 표를 두면 한쪽만 고쳐지는
날이 온다 — 아이템이 접두사 규약으로 그것을 피한 자리다
(`frontend/src/content/itemArt.ts`). 적은 종이 23개로 정해져 있어 접두사가 필요 없고,
id 를 그대로 쓰면 화면 검사가 카탈로그 전수를 훑어 빠진 장을 바로 잡는다.

**이름에 폴더가 붙어 있다.** 둘 다 `_sprites.py` 였는데, mypy 가 저장소 전량을
평평한 모듈 이름으로 보므로 `Duplicate module named "_sprites"` 로 검사가 통째로
멈췄다 — 패키지가 아니라 `sys.path` 로 읽는 파일이라 폴더가 이름을 안 갈라 준다.

글자는 `_build.PALETTE` 가 정한다. 새 글자를 쓰려면 그쪽을 먼저 고친다.
"""

from _sprites_goblin import GOBLIN_SPRITES
from _sprites_other import OTHER_SPRITES
from _sprites_shaman import SHAMAN_SPRITES

# **겹친 이름은 여기서 잡는다.** 딕셔너리를 합치면 뒤엣것이 앞엣것을 조용히 덮고, 그
# 결과는 SVG 한 장이 안 구워진 것으로만 드러난다 — 굽기는 장수를 세지 않는다.
_GROUPS = (GOBLIN_SPRITES, SHAMAN_SPRITES, OTHER_SPRITES)
_SEEN: dict[str, int] = {}
_COLLIDED: list[str] = []
for _at, _group in enumerate(_GROUPS):
    for _name in _group:
        if _name in _SEEN:
            _COLLIDED.append(_name)
        _SEEN[_name] = _at
if _COLLIDED:
    raise ValueError(f"격자 파일에 같은 이름이 있다: {sorted(_COLLIDED)}")

SPRITES = {**GOBLIN_SPRITES, **SHAMAN_SPRITES, **OTHER_SPRITES}
