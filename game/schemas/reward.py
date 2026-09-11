"""층 보상 계약 — 무엇을 고를 수 있고 그것이 무엇을 바꾸는가 (GDD §2.2·§6.2).

**핵심 고리의 한 칸이다.** GDD 가 적어 둔 고리는 `방 입장 → 전투 → 클리어 → 보상 선택
→ 규칙 편집 → 다음 방` 인데, 제품에는 **보상 선택이 없었다** — 굴림과 카탈로그는
`services/build_reward.py` 에 있었지만 헤드리스 배치 러너만 그것을 썼고, 실제 게임에서
층을 깨면 화폐·경험치와 처치당 5% 짜리 드롭 복권뿐이었다 (2026-09-11 실제 신고:
「5층 이후에 보상이 안 들어온거같아」 — 층과 무관하게 원래 그랬다).

`schemas/` 에 두는 이유는 **두 코어가 같은 표를 봐야 하기 때문**이다 (CLAUDE.md §12).
브라우저가 전투를 돌리고 서버가 재시뮬하므로, 보상이 바꾼 스탯을 양쪽이 같은 순서로
같은 만큼 얹지 않으면 같은 판이 두 결과를 낸다 (G3).

**후보는 시드에서 나온다.** 티켓 시드와 층으로 굴리므로 서버·클라이언트가 각자 굴려도
같은 셋이 나오고, 서버는 클라이언트가 보낸 선택이 **그 층의 후보 안에 있는지** 다시
굴려 확인한다 — 고른 것을 적어 보내는 자리는 있지만 **없는 보상을 적어 보낼 자리는
없다** (설계/7 §4).
"""

from dataclasses import dataclass

from game.app.core.rng import DeterministicRng

# 한 번에 제시할 후보 수. 셋이면 고르는 값이 생기고, 넷을 넘으면 층마다 고민이 길어져
# 15~25분 런(GDD §1)이 늘어진다.
REWARD_OPTION_COUNT = 3

# 최대 HP 를 올리는 보상은 현재 HP 도 함께 올린다. 그러지 않으면 그 층에서는 아무 일도
# 일어나지 않아 보상으로 안 읽힌다.
STAT_HP_MAX = "hp_max"

REWARD_MODULE = "MODULE"
REWARD_STAT_AFFIX = "STAT_AFFIX"
REWARD_RULE_SLOT = "RULE_SLOT"
REWARD_POTION = "POTION"


@dataclass(frozen=True)
class RewardOption:
    """보상 후보 하나.

    `target_stat` 은 **바꿀 축의 이름**이다. 효과를 분기가 아니라 데이터로 적으면 종류가
    늘어도 적용부가 안 길어지고, 표를 그대로 TS 로 옮기면 두 코어가 같은 말을 한다.
    """

    reward_id: str
    kind: str
    label_ko: str
    target_stat: str
    amount: int


# 상승폭은 GDD §6.1 의 「전 구간 20~30% 이내」에 맞춰 낮게 잡았다. 스탯으로 뭉갤 수
# 있으면 이 게임이 파는 것(로직 설계)이 사라진다.
#
# **순서가 계약이다.** 굴림이 이 순서에서 뽑으므로, 줄을 넣거나 옮기면 같은 시드가 다른
# 후보를 낸다 — 콘텐츠 세대를 올려야 하는 변경이다.
REWARD_CATALOG: tuple[RewardOption, ...] = (
    RewardOption("module_slot", REWARD_MODULE, "확장 슬롯", "rule_slots", 1),
    RewardOption("module_core", REWARD_MODULE, "연산 코어", "cpu_budget", 3),
    RewardOption("affix_attack", REWARD_STAT_AFFIX, "예리함", "attack", 2),
    RewardOption("affix_defense", REWARD_STAT_AFFIX, "견고함", "defense", 1),
    RewardOption("affix_vitality", REWARD_STAT_AFFIX, "활력", STAT_HP_MAX, 10),
    # **여기의 target_stat 은 스탯이 아니라 소모품 태그다.** 주머니가 정수 하나에서
    # 태그별 수로 바뀌면서 이 한 줄만 가리키는 것이 달라졌다 (2026-09-11).
    RewardOption("potion_pair", REWARD_POTION, "포션 꾸러미", "POTION", 2),
    RewardOption("rule_slot", REWARD_RULE_SLOT, "규칙 슬롯", "rule_slots", 1),
)

# 굴림 축의 이름. 층마다 갈라야 앞 층의 굴림 횟수가 뒷 층의 후보를 흔들지 않는다 (R5).
REWARD_STREAM = "reward"


def find_reward(reward_id: str) -> RewardOption | None:
    """id 로 후보를 찾는다.

    Args:
        reward_id: 보상 id.

    Returns:
        찾은 후보. 없으면 None — 옛 티켓이 가리키던 보상을 지웠을 때가 그 경우다.
    """
    for option in REWARD_CATALOG:
        if option.reward_id == reward_id:
            return option
    return None


def build_floor_offers(seed: int, floor: int) -> tuple[RewardOption, ...]:
    """그 층이 제시할 후보 셋을 굴린다.

    이름이 `build_` 인 것은 허용 동사 목록 때문이다 (§1) — 하는 일은 **굴림**이고,
    그 사실은 이 문장과 안의 `rng` 가 말한다.

    **같은 티켓·같은 층이면 언제나 같은 셋이다.** 서버가 저장하지 않고 필요할 때마다 다시
    굴려 확인할 수 있어야, 클라이언트가 보낸 선택을 「그 층의 후보였는가」로 판정할 수
    있다.

    **뽑은 것을 빼면서 뽑는다.** 중복이 원천적으로 생기지 않으므로 같은 보상이 두 칸을
    차지하지 않는다.

    Args:
        seed: 티켓 시드.
        floor: 보상을 제시할 층.

    Returns:
        후보들. 카탈로그보다 많이 요구하면 카탈로그 전부를 낸다.
    """
    rng = DeterministicRng(seed).create_stream(f"{REWARD_STREAM}/{floor}")
    pool = list(REWARD_CATALOG)
    picked: list[RewardOption] = []
    for _ in range(min(REWARD_OPTION_COUNT, len(pool))):
        picked.append(pool.pop(rng.get_below(len(pool))))
    return tuple(picked)


def check_offer_holds(seed: int, floor: int, reward_id: str) -> bool:
    """그 보상이 정말 그 층의 후보였는가.

    Args:
        seed: 티켓 시드.
        floor: 고른 층.
        reward_id: 고른 보상.

    Returns:
        후보 안에 있으면 True.
    """
    return any(option.reward_id == reward_id for option in build_floor_offers(seed, floor))


def read_taken(raw: object) -> dict[int, str]:
    """티켓에 저장된 선택을 읽는다.

    Args:
        raw: 저장된 절. `{"3": "module_slot"}` 모양이며 None 이면 고른 것이 없다.

    Returns:
        층에서 보상 id 로. 못 읽는 값은 버린다 — 옛 티켓이 다른 모양일 수 있다.
    """
    if not isinstance(raw, dict):
        return {}
    taken: dict[int, str] = {}
    for key, value in raw.items():
        if isinstance(value, str) and str(key).lstrip("-").isdigit():
            taken[int(key)] = value
    return taken


def list_taken_before(taken: dict[int, str], before_floor: int) -> tuple[RewardOption, ...]:
    """그 층에 들어가기 **전까지** 고른 보상들.

    **자기 층의 보상은 안 센다.** 보상은 그 층을 깬 **뒤에** 고르는 것이라, 같은 층의
    전투에 소급되면 재시뮬이 브라우저와 다른 판을 돈다 (G3).

    Args:
        taken: 층에서 보상 id 로.
        before_floor: 지금 들어가는 층.

    Returns:
        층 번호 순의 보상들 (R5 — 딕셔너리 순회 순서가 결과에 새면 안 된다).
    """
    found = []
    for floor in sorted(taken):
        if floor >= before_floor:
            continue
        option = find_reward(taken[floor])
        if option is not None:
            found.append(option)
    return tuple(found)


def count_floor_bonus(taken: dict[int, str], before_floor: int) -> dict[str, int]:
    """그 층에 들어가기 **전까지** 고른 것들의 합.

    **자기 층의 보상은 안 센다.** 보상은 그 층을 깬 **뒤에** 고르는 것이라, 같은 층의
    전투에 소급되면 재시뮬이 브라우저와 다른 판을 돈다 (G3).

    **층 번호 순으로 더한다.** 딕셔너리 순회 순서가 결과에 새어 나가면 안 된다 (R5) —
    지금은 전부 덧셈이라 순서가 값을 안 바꾸지만, 그 사실에 기대지 않는다.

    Args:
        taken: 층에서 보상 id 로.
        before_floor: 지금 들어가는 층.

    Returns:
        축에서 더할 값으로. 고른 것이 없으면 빈 표.
    """
    bonus: dict[str, int] = {}
    for option in list_taken_before(taken, before_floor):
        if option.kind == REWARD_POTION:
            continue
        bonus[option.target_stat] = bonus.get(option.target_stat, 0) + option.amount
    return bonus


def count_charge_bonus(taken: dict[int, str], before_floor: int) -> dict[str, int]:
    """그 층에 들어가기 전까지 고른 **소모품** 보상의 합.

    스탯과 가른 이유는 얹는 자리가 다르기 때문이다 — 스탯은 개체에, 충전은 주머니에
    얹는다. 한 표에 담으면 부르는 쪽이 태그와 스탯 이름을 구분해야 한다.

    Args:
        taken: 층에서 보상 id 로.
        before_floor: 지금 들어가는 층.

    Returns:
        소모품 태그에서 더할 충전 수로.
    """
    bonus: dict[str, int] = {}
    for option in list_taken_before(taken, before_floor):
        if option.kind != REWARD_POTION:
            continue
        bonus[option.target_stat] = bonus.get(option.target_stat, 0) + option.amount
    return bonus


__all__ = [
    "REWARD_CATALOG",
    "REWARD_OPTION_COUNT",
    "RewardOption",
    "STAT_HP_MAX",
    "check_offer_holds",
    "count_charge_bonus",
    "count_floor_bonus",
    "find_reward",
    "list_taken_before",
    "read_taken",
    "build_floor_offers",
]
