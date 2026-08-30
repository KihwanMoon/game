"""장비 사용 제한 판정 (docs/설계/4_아이템 §6·§7).

**판정 기준은 장비 보너스를 제외한 소재 능력치다.** 이것이 이 모듈의 전부이며,
그러지 않으면 착용 순서가 결과를 바꾼다.

    장비 A 가 힘 15 를 요구하고 장비 B 가 힘 +5 를 준다. 소재 힘은 12.
      B 먼저 → 힘 17 → A 착용 가능 → 둘 다 착용
      A 먼저 → 힘 12 → A 착용 불가 → B 만 착용

같은 소지품에서 다른 최종 상태가 나오므로 R5 위반이고, 서버 재검증도 불가능해진다 —
어떤 순서로 착용했는지를 클라이언트가 함께 보내야 하는데 그것은 위조 가능한 입력이다.
B 를 벗었을 때 A 가 어떻게 되는지도 정의되지 않는다.

소재만 보면 순서 의존이 사라지고, 해제 시 연쇄 탈착이 없으며, 서버는 (계정, 아이템)
만으로 재판정할 수 있다. 대가는 "장비를 겹쳐 요구조건을 뚫는" 빌드가 불가능해지는
것이며, 의도한 대가다 — 그 빌드는 재미보다 순서 퍼즐을 만든다.
"""

from dataclasses import dataclass

from game.schemas.item import ItemCatalogEntry, Requirement


@dataclass(frozen=True)
class RequirementCheck:
    """요구조건 한 줄의 판정 결과.

    실측값을 함께 낸다. "장착할 수 없습니다" 만 띄우면 무엇이 얼마나 모자란지 알 수
    없어 P1 위반이고, 규칙 에디터의 조건문 표기(`적거리(2) <= 사거리(3)`)와 같은
    규약을 쓰기 위해 화면이 이 값을 그대로 받는다 (GDD §8.2).
    """

    stat: str
    actual: int
    minimum: int

    @property
    def is_met(self) -> bool:
        """이 줄을 만족하는가."""
        return self.actual >= self.minimum


def check_requirement(requirement: Requirement, base_stats: dict[str, int]) -> RequirementCheck:
    """요구조건 한 줄을 판정한다.

    없는 능력치는 0 으로 본다. 능력치 축이 아직 정해지지 않았으므로(#11), 카탈로그가
    코어가 모르는 이름을 적어도 "모자란다" 로 읽혀야 한다 — 조용히 통과시키면 아직
    존재하지 않는 능력치를 요구하는 장비가 전부 착용 가능해진다.

    Args:
        requirement: 판정할 요구조건.
        base_stats: 장비 보너스를 제외한 소재 능력치.

    Returns:
        실측값이 담긴 판정 결과.
    """
    return RequirementCheck(
        stat=requirement.stat,
        actual=base_stats.get(requirement.stat, 0),
        minimum=requirement.minimum,
    )


def check_requirements(
    entry: ItemCatalogEntry, base_stats: dict[str, int]
) -> tuple[RequirementCheck, ...]:
    """아이템의 요구조건 전부를 판정한다.

    만족한 줄도 함께 낸다. 화면이 조건표를 통째로 그리기 때문이며, 못 채운 줄만 주면
    "무엇을 이미 만족했는가" 를 보여줄 수 없다.

    Args:
        entry: 판정할 카탈로그 항목.
        base_stats: 장비 보너스를 제외한 소재 능력치.

    Returns:
        선언 순서 그대로의 판정 결과들.
    """
    return tuple(check_requirement(item, base_stats) for item in entry.requirements)


def list_unmet_requirements(
    entry: ItemCatalogEntry, base_stats: dict[str, int]
) -> tuple[RequirementCheck, ...]:
    """못 채운 요구조건만 모은다.

    Args:
        entry: 판정할 카탈로그 항목.
        base_stats: 장비 보너스를 제외한 소재 능력치.

    Returns:
        만족하지 못한 줄들. 전부 만족하면 빈 튜플.
    """
    return tuple(check for check in check_requirements(entry, base_stats) if not check.is_met)


def check_can_equip(entry: ItemCatalogEntry, base_stats: dict[str, int]) -> bool:
    """이 장비를 착용할 수 있는가.

    Args:
        entry: 판정할 카탈로그 항목.
        base_stats: 장비 보너스를 제외한 소재 능력치.

    Returns:
        요구조건을 전부 만족하면 True.
    """
    return not list_unmet_requirements(entry, base_stats)
