"""도트 격자 — 굽는 쪽이 보는 이름 하나.

**`_build.py` 에서 갈라 나왔다.** 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는
선은 책임이다 (§4) — 격자는 그림이 늘 때마다 자라고 굽는 일은 그대로다.

**그 뒤 격자가 다시 상한을 넘어 둘로 갈렸다.** 가른 선은 `items.json` 의 `kind` 다.
장비는 슬롯 수에서 멈추지만 꺼내 쓰는 것은 쓰임새(`use_tag`)마다 한 장씩 는다 —
부적 하나가 넷으로 갈린 것이 그 예다. 자라는 쪽과 멈춘 쪽을 한 파일에 두면 다음에
넘길 때 또 같은 고민을 한다.

**이름이 곧 파일 이름이고 `catalog_id` 의 접두사다.** 별칭 표를 두면 한쪽만
고쳐지는 날이 온다 (`frontend/src/content/itemArt.ts`).

글자는 `_build.PALETTE` 가 정한다. 새 글자를 쓰려면 그쪽을 먼저 고친다.
"""

from _sprites_gear import GEAR_SPRITES
from _sprites_use import USE_SPRITES

# **겹친 이름은 여기서 잡는다.** 딕셔너리를 합치면 뒤엣것이 앞엣것을 조용히 덮고,
# 그 결과는 SVG 한 장이 안 구워진 것으로만 드러난다 — 굽기는 장수를 세지 않는다.
_COLLIDED = sorted(set(GEAR_SPRITES) & set(USE_SPRITES))
if _COLLIDED:
    raise ValueError(f"두 격자 파일에 같은 이름이 있다: {_COLLIDED}")

SPRITES = {**GEAR_SPRITES, **USE_SPRITES}
