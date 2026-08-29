"""파이썬 난수원의 기준 수열을 JSON 으로 내보낸다 (게이트 G3).

Phase 3 의 TypeScript 코어는 파이썬 코어와 같은 수열을 내야 한다. 두 구현이 같은지를
사람이 눈으로 대조하면 회귀를 놓치므로, 파이썬 쪽 출력을 파일로 고정해 두고 TS 테스트가
그 파일을 읽어 대조한다. 기준의 정본은 언제나 파이썬 코어다.

64비트 값은 문자열로 적는다. JSON 숫자는 자바스크립트에서 배정도 실수로 읽히므로
2^53 을 넘는 값이 조용히 반올림된다 — 그러면 대조가 통과해도 의미가 없다.

    uv run python -m scripts.export_rng_golden
"""

import json
from pathlib import Path
from typing import Any

from game.app.core.rng import DeterministicRng, get_label_hash

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "frontend/src/core/golden/rng_golden.json"

# 뽑을 개수. 늘리면 TS 쪽 기대값도 함께 커진다.
SAMPLE_COUNT = 16

UINT64_SEEDS = (0, 1, 12345, 777, 31337, 2**64 - 1)
SEED_MASK_INPUTS = (-1, -12345, 2**64, 2**64 + 7)
LABEL_SAMPLES = ("", "floor:2", "node:5", "floor:2/node:5/loot", "층:2/방:5", "seed")
BELOW_CASES = ((4242, 1), (4242, 2), (4242, 3), (4242, 6), (9, 7), (9, 8), (1, 100), (1, 1000))
RANGE_CASES = ((2024, 1, 6), (7, -5, 5), (11, 0, 0))
CHOICE_ITEMS = ("goblin_rusher", "goblin_archer", "goblin_summoner")
STREAM_CASES = ((42, "floor:2"), (42, "floor:2/node:5/loot"), (12345, "node:5"))


def build_uint64_cases() -> list[dict[str, Any]]:
    """시드별 원시 64비트 수열을 만든다.

    Returns:
        시드와 그 시드의 앞 SAMPLE_COUNT 개 출력 목록.
    """
    return [
        {"seed": str(seed), "values": [str(value) for value in _iter_uint64(seed)]}
        for seed in UINT64_SEEDS
    ]


def _iter_uint64(seed: int) -> list[int]:
    """시드 하나의 수열을 SAMPLE_COUNT 개 뽑는다.

    Args:
        seed: 시작 시드.

    Returns:
        뽑은 값 목록.
    """
    rng = DeterministicRng(seed)
    return [rng.get_uint64() for _ in range(SAMPLE_COUNT)]


def build_seed_mask_cases() -> list[dict[str, str]]:
    """음수·초과 시드가 64비트로 접히는 결과를 만든다.

    Returns:
        입력 시드와 접힌 시드의 쌍 목록.
    """
    return [
        {"input": str(value), "seed": str(DeterministicRng(value).seed)}
        for value in SEED_MASK_INPUTS
    ]


def build_label_hash_cases() -> list[dict[str, str]]:
    """라벨 해시 기준값을 만든다.

    Returns:
        라벨과 FNV-1a 해시의 쌍 목록.
    """
    return [{"label": label, "value": str(get_label_hash(label))} for label in LABEL_SAMPLES]


def build_below_cases() -> list[dict[str, Any]]:
    """거절 표집 결과를 만든다.

    마스크 폭이 다르면 버려지는 횟수가 달라져 이후 수열 전체가 어긋난다. 그것을 잡는
    것이 이 표본의 목적이다.

    Returns:
        시드·상한과 뽑힌 값 목록.
    """
    cases: list[dict[str, Any]] = []
    for seed, bound in BELOW_CASES:
        rng = DeterministicRng(seed)
        cases.append(
            {
                "seed": str(seed),
                "bound": bound,
                "values": [rng.get_below(bound) for _ in range(SAMPLE_COUNT)],
            }
        )
    return cases


def build_range_cases() -> list[dict[str, Any]]:
    """구간 표집 결과를 만든다.

    Returns:
        시드·구간과 뽑힌 값 목록.
    """
    cases: list[dict[str, Any]] = []
    for seed, low, high in RANGE_CASES:
        rng = DeterministicRng(seed)
        cases.append(
            {
                "seed": str(seed),
                "low": low,
                "high": high,
                "values": [rng.get_range(low, high) for _ in range(SAMPLE_COUNT)],
            }
        )
    return cases


def build_choice_cases() -> list[dict[str, Any]]:
    """시퀀스 선택 결과를 만든다.

    Returns:
        시드·후보와 골라진 원소 목록.
    """
    rng = DeterministicRng(88)
    return [
        {
            "seed": "88",
            "items": list(CHOICE_ITEMS),
            "values": [rng.get_choice(CHOICE_ITEMS) for _ in range(SAMPLE_COUNT)],
        }
    ]


def build_stream_cases() -> list[dict[str, Any]]:
    """라벨로 갈라진 스트림의 수열을 만든다.

    Returns:
        시드·라벨과 그 스트림의 수열 목록.
    """
    cases: list[dict[str, Any]] = []
    for seed, label in STREAM_CASES:
        stream = DeterministicRng(seed).create_stream(label)
        cases.append(
            {
                "seed": str(seed),
                "label": label,
                "stream_seed": str(stream.seed),
                "values": [str(stream.get_uint64()) for _ in range(SAMPLE_COUNT)],
            }
        )
    return cases


def build_golden_document() -> dict[str, Any]:
    """기준 문서 전체를 만든다.

    Returns:
        JSON 으로 쓸 딕셔너리.
    """
    return {
        "_comment": [
            "파이썬 코어(game/app/core/rng.py)에서 생성한 기준 수열이다. 손으로 고치지 않는다.",
            "재생성: uv run python -m scripts.export_rng_golden",
            "64비트 값은 자바스크립트의 정밀도 손실을 피하려고 문자열로 적었다.",
        ],
        "sample_count": SAMPLE_COUNT,
        "uint64": build_uint64_cases(),
        "seed_mask": build_seed_mask_cases(),
        "label_hash": build_label_hash_cases(),
        "below": build_below_cases(),
        "range": build_range_cases(),
        "choice": build_choice_cases(),
        "stream": build_stream_cases(),
    }


def export_rng_golden(target_path: Path) -> Path:
    """기준 수열을 파일로 쓴다.

    Args:
        target_path: 쓸 경로. 상위 디렉터리가 없으면 만든다.

    Returns:
        쓴 경로.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    document = build_golden_document()
    target_path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return target_path


def main() -> None:
    """기준 수열을 기본 경로에 내보낸다."""
    written = export_rng_golden(GOLDEN_PATH)
    print(f"기준 수열을 썼다: {written}")


if __name__ == "__main__":
    main()
