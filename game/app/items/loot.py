"""전리품 발급 — **서버만 굴린다** (결정 #02, docs/설계/4_아이템 §8).

전투 시뮬레이션 밖에 있다. 코어는 아이템을 모르므로 `결과 = f(시드, 규칙표, 코어버전)`
이 그대로이고, 리플레이와 골든이 영향받지 않는다. 대가는 오프라인에서 아이템이 나오지
않는 것이다 — 티켓이 없으면 제출할 수 없고, 제출이 없으면 발급도 없다.

`secrets` 를 쓰는 것은 R5 위반이 아니다. 게임 난수가 아니라 **예측 불가능해야 하는 값**
이고 코어 밖이다. 예측 가능하면 어느 자리에서 무엇이 나오는지 미리 계산해 그 판만
완주하는 골라 담기가 열린다.

이 모듈이 API 층 밖으로 새면 안 된다. 발급 경로가 서버 하나뿐이라는 것이 시드 파생의
'재현으로 검증' 을 대신하는 자리이기 때문이다.
"""

import secrets
from dataclasses import dataclass

from game.schemas.item import Affix, ItemCatalogEntry, ItemKind

# 승리한 런이 전리품을 낼 확률. 매판 나오면 인벤토리가 곧 가득 차고, 너무 드물면
# 파밍 동기가 서지 않는다 — 밸런스가 정해지기 전의 출발값이다.
WIN_DROP_PERCENT = 60

# 패배해도 나올 확률. 0 이 아닌 이유는 "실패해도 자산이 남는다"(GDD §2.3)를 아이템에도
# 얇게 걸어 두기 위해서다. 이기는 것이 확실히 낫지만 진 판이 완전히 빈손은 아니다.
LOSS_DROP_PERCENT = 15

# 굴림당 붙는 접사 수. 하나는 심심하고 셋은 읽기 어렵다.
MIN_AFFIX_ROLLS = 1
MAX_AFFIX_ROLLS = 2

# 접사 값이 흔들리는 폭 (퍼센트). 카탈로그 기본값의 80~120% 사이에서 정해진다 —
# 같은 이름의 아이템이 조금씩 다르게 나와야 파밍이 성립한다.
AFFIX_MIN_PERCENT = 80
AFFIX_MAX_PERCENT = 120
PERCENT_BASE = 100

# 승리 보상 화폐. 층이 깊을수록 는다.
# 난이도 개편(층당 5방·스킬 v3·복리 스케일)과 함께 올렸다 — 층이 5/3배 길어지고
# 적이 세졌으므로, 층 하나의 값도 그만큼 커야 보충·복구 경제가 돌아간다.
WIN_CURRENCY = 80
LOSS_CURRENCY = 20


@dataclass(frozen=True)
class LootRoll:
    """굴림 하나의 결과. 아이템이 안 나올 수도 있다."""

    catalog_id: str | None
    affixes: tuple[Affix, ...]
    currency: int


def get_below(bound: int) -> int:
    """0 이상 bound 미만의 예측 불가능한 정수.

    Args:
        bound: 상한(미포함). 1 이하면 0 이다.

    Returns:
        뽑힌 정수.
    """
    return secrets.randbelow(bound) if bound > 1 else 0


def convert_affix_roll(affix: Affix) -> Affix:
    """접사 값을 굴림 폭 안에서 흔든다.

    정수 나눗셈이며 내림이다. 0 이 되는 것을 막지 않는다 — 나쁘게 굴린 아이템이 있어야
    좋게 굴린 것이 뜻을 갖는다.

    Args:
        affix: 카탈로그의 기준 접사.

    Returns:
        값이 흔들린 접사.
    """
    span = AFFIX_MAX_PERCENT - AFFIX_MIN_PERCENT + 1
    percent = AFFIX_MIN_PERCENT + get_below(span)
    return Affix(
        stat=affix.stat,
        flat=affix.flat * percent // PERCENT_BASE,
        percent=affix.percent * percent // PERCENT_BASE,
        label_ko=affix.label_ko,
    )


def list_droppable(catalog: dict[str, ItemCatalogEntry]) -> tuple[ItemCatalogEntry, ...]:
    """전리품으로 나올 수 있는 것을 모은다.

    퀘스트 아이템은 빠진다 — 퀘스트가 주는 것이지 굴려서 나오는 것이 아니다.

    정렬해서 돌려주는 이유는 R5 가 아니라 재현성이다. 뽑기 자체는 무작위지만, 후보
    목록이 실행마다 다른 순서면 같은 난수가 다른 아이템을 낸다.

    Args:
        catalog: 아이템 카탈로그.

    Returns:
        catalog_id 순으로 정렬된 후보들.
    """
    found = [entry for entry in catalog.values() if entry.kind is not ItemKind.QUEST]
    return tuple(sorted(found, key=lambda entry: entry.catalog_id))


def compute_run_currency(is_cleared: bool, floor: int = 1) -> int:
    """이 런이 주는 화폐를 낸다.

    **화폐는 런 단위로 남는다.** 아이템은 처치마다 굴리도록 바뀌었지만(설계/4_아이템
    §15.3), 화폐까지 처치마다 주면 방에 적이 많은 것이 곧 수입이 되어 방 설계가
    난이도가 아니라 수입 조절 장치가 된다.

    Args:
        is_cleared: 이겼는가.
        floor: 도달한 층.

    Returns:
        줄 화폐.
    """
    return (WIN_CURRENCY if is_cleared else LOSS_CURRENCY) * max(1, floor)


def create_loot_roll(
    catalog: dict[str, ItemCatalogEntry], is_cleared: bool, floor: int = 1
) -> LootRoll:
    """검증된 런 하나의 전리품을 굴린다.

    Args:
        catalog: 아이템 카탈로그.
        is_cleared: 이겼는가.
        floor: 도달한 층. 화폐가 이것에 비례한다.

    Returns:
        굴림 결과. `catalog_id` 가 None 이면 아이템이 안 나온 것이다.
    """
    currency = (WIN_CURRENCY if is_cleared else LOSS_CURRENCY) * max(1, floor)
    chance = WIN_DROP_PERCENT if is_cleared else LOSS_DROP_PERCENT
    if get_below(PERCENT_BASE) >= chance:
        return LootRoll(catalog_id=None, affixes=(), currency=currency)

    candidates = list_droppable(catalog)
    if not candidates:
        return LootRoll(catalog_id=None, affixes=(), currency=currency)
    entry = candidates[get_below(len(candidates))]

    rolls = MIN_AFFIX_ROLLS + get_below(MAX_AFFIX_ROLLS - MIN_AFFIX_ROLLS + 1)
    affixes = tuple(convert_affix_roll(item) for item in entry.affixes[:rolls])
    return LootRoll(catalog_id=entry.catalog_id, affixes=affixes, currency=currency)
