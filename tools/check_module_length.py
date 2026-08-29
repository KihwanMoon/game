"""모듈이 §4 의 줄 수 상한을 넘는지 검사한다."""

import sys
from pathlib import Path

# §4 "모듈이 400줄 초과 또는 책임이 둘 이상 → 파일 분리".
# 정본 §7 표에는 이 규칙의 강제 수단 행이 없고 ruff 에도 대응 규칙이 없다
# (C90 은 복잡도, PLR0915 는 문장 수를 잰다). 그래서 이 검사를 따로 둔다.
MAX_MODULE_LINES = 400


def count_module_lines(target_path: Path) -> int:
    """파일의 줄 수를 센다.

    Args:
        target_path: 셀 대상 파일 경로.

    Returns:
        줄 수. 마지막 줄에 개행이 없어도 한 줄로 센다.
    """
    return len(target_path.read_text(encoding="utf-8").splitlines())


def check_module_length(target_path: Path) -> str:
    """단일 모듈이 줄 수 상한을 지키는지 검사한다.

    Args:
        target_path: 검사할 파이썬 파일 경로.

    Returns:
        "경로: 메시지" 형식의 위반 문자열. 상한 이내면 빈 문자열.
    """
    line_count = count_module_lines(target_path)
    if line_count <= MAX_MODULE_LINES:
        return ""
    return f"{target_path}: {line_count}줄 — 상한 {MAX_MODULE_LINES}줄 (§4 파일 분리)"


def main() -> int:
    """인자로 받은 파일들을 검사하고 종료 코드를 반환한다.

    Returns:
        위반이 하나라도 있으면 1, 없으면 0.
    """
    violations: list[str] = []
    for raw_path in sys.argv[1:]:
        message = check_module_length(Path(raw_path))
        if message:
            violations.append(message)

    for line in violations:
        print(line, file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
