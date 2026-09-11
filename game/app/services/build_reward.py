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
from game.schemas.loadout import PlayerLoadout
from game.schemas.reward import (
    REWARD_CATALOG,
    REWARD_MODULE,
    REWARD_OPTION_COUNT,
    STAT_HP_MAX,
    RewardOption,
)

# **카탈로그와 굴림은 `schemas/reward.py` 가 정본이다** (2026-09-11). 보상 선택을 제품에
# 붙이면서 두 코어가 같은 표를 봐야 했고, TS 로 이식되는 자산은 `schemas/` 에 산다
# (CLAUDE.md §12). 여기 남은 것은 **헤드리스 배치 러너의 런 상태**뿐이다.
REWARD_POTION = "POTION"


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
    # 들고 다니는 소모품. **정렬된 쌍으로 담는다** — 딕셔너리 순회 순서가 런 상태에
    # 새어 나가면 안 된다 (R5).
    #
    # **예전에는 `potions: int` 하나였다** (2026-09-11 에 고쳤다). 그래서 층을 도는
    # 쪽(`run_room_loop`)이 방에 들어갈 때마다 주머니를 `{"POTION": n}` 으로 덮었고,
    # **주문서는 들고 들어가도 사라졌다.** 실제 판(`run_chain`)은 전부 인계하므로 두
    # 경로가 다른 판을 돌고 있었다 — 배치로 잰 값이 실제 판과 같아야 한다는 이 모듈의
    # 규율이 바로 그 자리에서 깨져 있었고, 주문서 넷을 재려 하자마자 드러났다.
    consumables: tuple[tuple[str, int], ...] = ()
    rule_slots: int = 0
    cpu_budget: int = 0
    modules: tuple[str, ...] = ()


def create_run_state(balance: dict, loadout: PlayerLoadout | None = None) -> RunState:
    """밸런스 값으로 런 시작 상태를 만든다.

    **장비가 있으면 기본값을 대체한다** (결정 #13). 얹지 않는 이유는 얹으면 같은 장비가
    밸런스 패치마다 다른 값을 내기 때문이고, 이것은 `run_battle.build_engine` 이 이미
    쓰는 규율이다 — 두 곳이 같은 말을 해야 배치로 잰 값이 실제 판과 같다.

    Args:
        balance: balance.json 을 읽은 딕셔너리.
        loadout: 이번 런의 장비. None 이면 맨몸이다.

    Returns:
        보상을 아직 하나도 받지 않은 시작 상태.
    """
    stats = balance["player"]
    if loadout is None:
        return RunState(
            hp=stats["hp_max"],
            hp_max=stats["hp_max"],
            attack=stats["attack"],
            defense=stats["defense"],
            consumables=(("POTION", stats["potions"]),),
            rule_slots=stats["rule_slots"],
            cpu_budget=stats["cpu_budget"],
        )
    return RunState(
        hp=loadout.hp_max,
        hp_max=loadout.hp_max,
        attack=loadout.attack,
        defense=loadout.defense,
        # **전부 들고 간다.** 물약만 옮기면 주문서를 끼운 칸이 판에서 사라진다.
        consumables=tuple(sorted(loadout.consumables)),
        rule_slots=loadout.rule_slots,
        cpu_budget=loadout.cpu_budget,
    )


def read_charges(state: RunState, use_tag: str) -> int:
    """지금 들고 있는 그 소모품의 수.

    Args:
        state: 런 상태.
        use_tag: 소모품 태그.

    Returns:
        남은 수. 안 들고 있으면 0.
    """
    return dict(state.consumables).get(use_tag, 0)


def apply_charges(state: RunState, use_tag: str, count: int) -> None:
    """그 소모품의 수를 고쳐 쓴다.

    **정렬해 다시 담는다.** 순서가 런 상태에 새어 나가면 같은 시드가 다른 판을 돈다 (R5).

    Args:
        state: 런 상태. 제자리에서 바뀐다.
        use_tag: 소모품 태그.
        count: 새 수.
    """
    left = dict(state.consumables)
    left[use_tag] = count
    state.consumables = tuple(sorted(left.items()))


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
    # 소모품만 갈래가 하나 있다. 주머니가 **태그별 수**라 필드 이름으로 못 짚는다 —
    # 갈래가 여기 하나뿐이므로 종류가 늘어도 이 함수는 그대로다.
    if option.kind == REWARD_POTION:
        apply_charges(
            state, option.target_stat, read_charges(state, option.target_stat) + option.amount
        )
        return
    setattr(state, option.target_stat, getattr(state, option.target_stat) + option.amount)
    if option.target_stat == STAT_HP_MAX:
        state.hp += option.amount
    if option.kind == REWARD_MODULE:
        state.modules = (*state.modules, option.reward_id)
