"""보상 후보 생성과 적용 — 방을 클리어할 때마다 고르는 것 (GDD §2.2·§6).

보상은 네 갈래다 — 모듈 / 스탯 접사 장비 / 포션 / 규칙 슬롯. 아이템 생성·접사 굴림·
인벤토리 전량은 Phase 4 몫이므로, 여기서는 **후보를 뽑아 제시하고 고른 하나를 런
상태에 반영하는 골격**까지만 만든다. 지금 검증해야 하는 것은 "방마다의 선택이 다음
방의 결과를 바꾸는가" 하나다.

보상이 바꾸는 대상인 RunState 를 같은 모듈에 둔 이유는, 둘이 언제나 함께 고쳐지기
때문이다 — 보상 종류를 늘리면 그것이 건드릴 필드가 함께 생긴다.

효과를 분기가 아니라 데이터(target_stat·amount)로 적는다. 종류가 늘어도 apply_reward
가 길어지지 않고, Phase 3 의 TypeScript 코어로도 표를 그대로 옮기면 된다.
"""

from dataclasses import dataclass

from game.app.core.rng import DeterministicRng

REWARD_MODULE = "MODULE"
REWARD_STAT_AFFIX = "STAT_AFFIX"
REWARD_POTION = "POTION"
REWARD_RULE_SLOT = "RULE_SLOT"

# 한 번에 제시할 후보 수. 셋이면 고르는 값이 생기고, 넷을 넘으면 방마다 고민이 길어져
# 15~25분 런(GDD §1)이 늘어진다.
REWARD_OPTION_COUNT = 3

# 최대 HP 를 올리는 보상은 현재 HP 도 함께 올린다. 그러지 않으면 그 방에서는 아무 일도
# 일어나지 않아 보상으로 읽히지 않는다.
STAT_HP_MAX = "hp_max"


@dataclass(frozen=True)
class RewardOption:
    """보상 후보 하나. target_stat 은 RunState 의 필드 이름이다."""

    reward_id: str
    kind: str
    label_ko: str
    target_stat: str
    amount: int


# 상승폭은 GDD §6.1 이 정한 "전 구간 20~30% 이내"에 맞춰 낮게 잡았다. 스탯으로 뭉갤 수
# 있으면 이 게임이 파는 것(로직 설계)이 사라진다.
REWARD_CATALOG = (
    RewardOption("module_slot", REWARD_MODULE, "확장 슬롯", "rule_slots", 1),
    RewardOption("module_core", REWARD_MODULE, "연산 코어", "cpu_budget", 3),
    RewardOption("affix_attack", REWARD_STAT_AFFIX, "예리함", "attack", 2),
    RewardOption("affix_defense", REWARD_STAT_AFFIX, "견고함", "defense", 1),
    RewardOption("affix_vitality", REWARD_STAT_AFFIX, "활력", STAT_HP_MAX, 10),
    RewardOption("potion_pair", REWARD_POTION, "포션 꾸러미", "potions", 2),
    RewardOption("rule_slot", REWARD_RULE_SLOT, "규칙 슬롯", "rule_slots", 1),
)


@dataclass
class RunState:
    """런 하나가 방 사이로 들고 다니는 것 (GDD §2.3).

    HP·포션만이 아니라 규칙 슬롯과 CPU 예산도 여기 있다. 모듈 보상이 바꾸는 것이 그
    둘이고, 그것이 다음 방의 설계 여지를 넓히는 실제 경로다 (GDD §6.2).
    """

    hp: int
    hp_max: int
    attack: int
    defense: int
    potions: int
    rule_slots: int
    cpu_budget: int
    modules: tuple[str, ...] = ()


def create_run_state(balance: dict) -> RunState:
    """밸런스 값으로 런 시작 상태를 만든다.

    Args:
        balance: balance.json 을 읽은 딕셔너리.

    Returns:
        보상을 아직 하나도 받지 않은 시작 상태.
    """
    stats = balance["player"]
    return RunState(
        hp=stats["hp_max"],
        hp_max=stats["hp_max"],
        attack=stats["attack"],
        defense=stats["defense"],
        potions=stats["potions"],
        rule_slots=stats["rule_slots"],
        cpu_budget=stats["cpu_budget"],
    )


def build_reward_options(
    rng: DeterministicRng, count: int = REWARD_OPTION_COUNT
) -> tuple[RewardOption, ...]:
    """보상 후보를 겹치지 않게 뽑는다.

    같은 것이 둘 나오면 후보가 셋이어도 선택지는 둘이다. 뽑은 것을 통에서 빼는
    방식이라 중복이 원천적으로 생기지 않는다.

    Args:
        rng: 이 방의 보상 전용 난수원.
        count: 뽑을 후보 수. 카탈로그보다 많이 요구하면 카탈로그 전부를 낸다.

    Returns:
        제시할 후보들.
    """
    pool = list(REWARD_CATALOG)
    picked: list[RewardOption] = []
    for _ in range(min(count, len(pool))):
        picked.append(pool.pop(rng.get_below(len(pool))))
    return tuple(picked)


def apply_reward(state: RunState, option: RewardOption) -> None:
    """고른 보상을 런 상태에 반영한다.

    Args:
        state: 바뀔 런 상태.
        option: 고른 후보.
    """
    setattr(state, option.target_stat, getattr(state, option.target_stat) + option.amount)
    if option.target_stat == STAT_HP_MAX:
        state.hp += option.amount
    if option.kind == REWARD_MODULE:
        state.modules = (*state.modules, option.reward_id)
