"""실행 설정 로드.

표준 문서 §12 는 이 자리에 pydantic settings 를 권하지만, TDD §1.2 가 Phase 1 을
표준 라이브러리만으로 못박았고 이 구간 코드는 명시적으로 버릴 코드다. 의존성 하나가
곧 Phase 3 이관 비용(R4)이므로 dataclass 와 os.environ 으로 대신한다. Phase 3 에서
TypeScript 로 넘어갈 때 이 파일은 이식 대상이 아니다.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# 번들된 데이터의 위치. 밸런스 수치는 코드에 하드코딩하지 않고 전량 JSON 이며(TDD §2),
# 그 JSON 이 어디 있는지는 한 곳에만 적는다.
PACKAGE_ROOT = Path(__file__).resolve().parent
RESOURCES_DIR = PACKAGE_ROOT / "resources"
BLOCKS_PATH = RESOURCES_DIR / "balance" / "blocks.json"
BALANCE_PATH = RESOURCES_DIR / "balance" / "balance.json"
# 스킬은 balance.json 에서 갈라 나왔다 — 스킬은 종류가 늘어나는 것이고 밸런스 수치는
# 조정되는 것이라 수명이 다르다. 합치는 자리는 load_balance 하나다.
SKILLS_PATH = RESOURCES_DIR / "balance" / "skills.json"
ITEMS_PATH = RESOURCES_DIR / "balance" / "items.json"
ROOM_TEMPLATES_PATH = RESOURCES_DIR / "rooms" / "templates.json"
G0_RULESETS_PATH = RESOURCES_DIR / "rulesets" / "g0_examples.json"
# 동결 이후에 들어온 블록을 쓰는 표들. benchmark 는 블록 18/14/9 로 동결돼 있고
# g0 는 게이트 자료라 둘 다 못 건드리는데, 그 뒤에 들어온 블록을 쓰는 표가 하나도
# 없어 팔레트가 보여 주는 것을 아무것도 시연하지 않고 있었다.
LATER_BLOCKS_RULESETS_PATH = RESOURCES_DIR / "rulesets" / "later_blocks.json"
ENEMY_RULESETS_PATH = RESOURCES_DIR / "rulesets" / "enemies.json"
BENCHMARK_RULESETS_PATH = RESOURCES_DIR / "rulesets" / "benchmark.json"
TUTORIAL_STAGES_PATH = RESOURCES_DIR / "tutorial" / "stages.json"

DEFAULT_SEED = 1
DEFAULT_MAX_TICKS = 400
DEFAULT_SPEED_LABEL = "instant"

ENV_PREFIX = "GAME_"


@dataclass(frozen=True)
class SimulationConfig:
    """시뮬레이션 1회 실행에 필요한 설정.

    frozen 인 이유는 실행 도중 설정이 바뀌면 리플레이가 재현되지 않기 때문이다.
    """

    seed: int = DEFAULT_SEED
    max_ticks: int = DEFAULT_MAX_TICKS
    speed_label: str = DEFAULT_SPEED_LABEL


def get_env_int(key: str, fallback: int) -> int:
    """환경변수를 정수로 읽는다. 없거나 정수가 아니면 기본값을 쓴다.

    Args:
        key: 접두어를 뺀 환경변수 이름. 예: "SEED".
        fallback: 값이 없거나 해석할 수 없을 때 쓸 값.

    Returns:
        읽어들인 정수, 또는 fallback.
    """
    raw = os.environ.get(f"{ENV_PREFIX}{key}")
    if raw is None:
        return fallback
    try:
        return int(raw)
    except ValueError:
        return fallback


def load_config() -> SimulationConfig:
    """환경변수에서 설정을 읽어 구성한다.

    Returns:
        읽어들인 설정. 환경변수가 하나도 없으면 전부 기본값이다.
    """
    return SimulationConfig(
        seed=get_env_int("SEED", DEFAULT_SEED),
        max_ticks=get_env_int("MAX_TICKS", DEFAULT_MAX_TICKS),
        speed_label=os.environ.get(f"{ENV_PREFIX}SPEED_LABEL", DEFAULT_SPEED_LABEL),
    )
