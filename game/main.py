"""컴포지션 루트. 설정을 읽고 코어를 조립해 실행한다 (표준 문서 §12).

지금은 틱 엔진이 없으므로 결정론 하네스가 살아 있는지만 확인한다. 로드맵 Phase 1 W1
에서 틱 엔진이 들어오면 이 자리에서 조립한다 — 이 파일이 코어를 조립하는 유일한
지점이고, 코어의 어떤 모듈도 여기를 거꾸로 참조하지 않는다 (TDD §2).
"""

import argparse
import sys

from game.app.core.rng import DeterministicRng
from game.config import SimulationConfig, load_config

PREVIEW_DRAW_COUNT = 5


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자 목록.

    Returns:
        해석된 인자. seed 가 None 이면 환경변수/기본값을 쓴다는 뜻이다.
    """
    parser = argparse.ArgumentParser(description="결정론 시뮬레이션 코어 진입점")
    parser.add_argument("--seed", type=int, default=None, help="시드. 생략 시 설정값을 쓴다")
    return parser.parse_args(argv)


def build_config(arguments: argparse.Namespace) -> SimulationConfig:
    """명령행 인자를 설정에 덮어씌운다.

    Args:
        arguments: 해석된 명령행 인자.

    Returns:
        인자가 반영된 설정.
    """
    config = load_config()
    if arguments.seed is None:
        return config
    return SimulationConfig(
        seed=arguments.seed,
        max_ticks=config.max_ticks,
        speed_label=config.speed_label,
    )


def run_self_check(config: SimulationConfig) -> None:
    """같은 시드가 같은 수열을 내는지 확인하고 결과를 출력한다.

    Args:
        config: 실행 설정.
    """
    first = DeterministicRng(config.seed)
    second = DeterministicRng(config.seed)
    draws = [first.get_uint64() for _ in range(PREVIEW_DRAW_COUNT)]
    repeats = [second.get_uint64() for _ in range(PREVIEW_DRAW_COUNT)]

    print(f"seed       : {config.seed}")
    print(f"max_ticks  : {config.max_ticks}")
    print(f"first draws: {draws}")
    print(f"결정론      : {'일치' if draws == repeats else '불일치 — R5 위반'}")


def main() -> int:
    """진입점.

    Returns:
        정상 종료면 0.
    """
    config = build_config(parse_arguments(sys.argv[1:]))
    run_self_check(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
