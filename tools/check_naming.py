"""함수·메서드 이름이 {동사}_{목적어} 규칙을 따르는지 검사한다."""

import ast
import sys
from pathlib import Path

# 2.1 의 동사 목록과 항상 일치해야 한다.
# 문서와 코드가 갈라지면 사람이 통과시킨 이름을 게이트가 막는다.
# fmt: skip 은 압축 배열을 유지하려는 것이다 — 없으면 ruff format 이 한 줄에
# 하나씩 펼쳐 이 블록이 ruff format --check 를 통과하지 못한다 (7.1).
ALLOWED_VERBS = frozenset(
    {
        "get", "set", "create", "build", "make", "load", "save", "read",
        "write", "parse", "render", "convert", "validate", "check", "run",
        "execute", "fetch", "send", "update", "delete", "remove", "add",
        "apply", "compute", "calculate", "extract", "filter", "sort",
        "merge", "split", "init", "register", "resolve", "handle",
        "process", "train", "predict", "infer", "export", "ensure",
        "main", "test", "list", "find", "iter", "count", "format",
        "describe", "normalize", "start", "stop", "reset", "refresh",
        "retry", "rename", "prepare", "drop", "mark", "call", "publish",
        "subscribe", "request", "poll", "probe", "purge", "assign",
        "monitor", "manage", "track", "wait", "close", "open", "plan",
        "scan", "store", "record", "evaluate", "embed", "promote",
    }
)  # fmt: skip

# 술어 함수는 불리언 변수와 같은 규칙을 따른다 (2장).
# 동사를 강제하면 check_is_expired 같은 겹말이 나온다.
PREDICATE_PREFIXES = ("is_", "has_", "should_", "can_")

# 외부 인터페이스가 이름을 정하는 경우 (2장). 프레임워크가 URL·필드명·주입 인자명에서
# 이름을 끌어오므로 동사_목적어를 강제하면 드롭인 교체 계약이 깨진다.
# pytest 픽스처가 여기 드는 이유는 이름이 곧 주입되는 값이기 때문이다 — `assembled` 를
# `build_assembled` 로 바꾸면 그 이름이 테스트 인자로 그대로 들어간다.
INTERFACE_DECORATORS = (
    "router.",
    "app.",
    "field_validator",
    "model_validator",
    "validator",
    "pytest.fixture",
    "pytest_asyncio.fixture",
    "fixture",
)

# 목록에 없는 동사를 써야 할 때의 예외 표기 (2.1, 11장).
# 사유 없는 억제는 리뷰에서 반려한다.
SUPPRESS_MARKER = "# naming: allow"

# {동사}_{목적어} 이므로 밑줄로 나눈 조각이 최소 2개여야 한다.
MIN_NAME_PARTS = 2

# 목적어 없이 동사 하나만으로 뜻이 통하는 관용 이름.
BARE_VERB_NAMES = frozenset({"main", "run"})


def _get_decorator_name(node: ast.expr) -> str:
    """데코레이터 노드에서 이름 문자열을 추출한다.

    Args:
        node: 데코레이터 표현식 노드.

    Returns:
        데코레이터 이름. 이름을 뽑을 수 없는 형태면 빈 문자열.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_exempt(node: ast.FunctionDef | ast.AsyncFunctionDef, line: str, outer_ids: set) -> bool:
    """이 함수를 네이밍 검사에서 빼야 하는지 판단한다.

    Args:
        node: 검사 대상 함수 노드.
        line: 그 함수의 `def` 줄 원문(억제 표기 확인용).
        outer_ids: 모듈·클래스 몸통에 직접 놓인 함수들의 id 집합.

    Returns:
        검사에서 제외하면 True.
    """
    # 함수 안에 정의된 함수는 그 함수 밖에서 부를 수 없는 일회용이다(클로저·모킹 대역).
    # 이름이 계약이 아니라 그 자리의 설명이므로 검사하지 않는다.
    if id(node) not in outer_ids:
        return True
    name = node.name
    # 던더 메서드와 프로퍼티는 파이썬 관용을 따르므로 검사에서 제외한다.
    if name.startswith("__") and name.endswith("__"):
        return True
    if any(_get_decorator_name(d) in {"property", "cached_property"} for d in node.decorator_list):
        return True
    if any(ast.unparse(d).startswith(INTERFACE_DECORATORS) for d in node.decorator_list):
        return True
    if name.lstrip("_").startswith(PREDICATE_PREFIXES):
        return True
    return SUPPRESS_MARKER in line


def check_file_naming(target_path: Path) -> list[str]:
    """단일 파일에서 네이밍 규칙 위반 목록을 수집한다.

    Args:
        target_path: 검사할 파이썬 파일 경로.

    Returns:
        "경로:줄번호: 메시지" 형식의 위반 문자열 리스트. 위반이 없으면 빈 리스트.
    """
    violations: list[str] = []
    source = target_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tree = ast.parse(source)

    # 클래스 메서드는 클래스명이 목적어 역할을 하므로 동사 하나로 뜻이 통한다 (2장).
    # ast.walk 는 부모를 알려 주지 않으므로 ClassDef 를 먼저 훑어 메서드를 모은다.
    method_ids = {
        id(body_node)
        for class_node in ast.walk(tree)
        if isinstance(class_node, ast.ClassDef)
        for body_node in class_node.body
        if isinstance(body_node, ast.FunctionDef | ast.AsyncFunctionDef)
    }
    module_level = [n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    outer_ids = method_ids | {id(n) for n in module_level}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if _is_exempt(node, lines[node.lineno - 1], outer_ids):
            continue

        name = node.name
        parts = name.lstrip("_").split("_")
        if parts[0] not in ALLOWED_VERBS:
            violations.append(
                f"{target_path}:{node.lineno}: '{name}' 은(는) 허용 동사로 시작해야 한다"
            )
        elif (
            len(parts) < MIN_NAME_PARTS
            and parts[0] not in BARE_VERB_NAMES
            and id(node) not in method_ids
        ):
            violations.append(f"{target_path}:{node.lineno}: '{name}' 에 목적어가 없다")

    return violations


def main() -> int:
    """인자로 받은 파일들을 검사하고 종료 코드를 반환한다.

    Returns:
        위반이 하나라도 있으면 1, 없으면 0.
    """
    all_violations: list[str] = []
    for raw_path in sys.argv[1:]:
        all_violations.extend(check_file_naming(Path(raw_path)))

    for line in all_violations:
        print(line, file=sys.stderr)
    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main())
