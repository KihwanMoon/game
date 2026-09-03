"""디자인 토큰을 피그마가 읽는 형식으로 내보낸다.

**피그마 API 를 쓰지 않는다.** 이 계정은 Starter · View 좌석이라 월 20 호출이 상한인데,
피그마 공식 절차는 디자인 시스템 하나에 20~100 호출을 요구한다 — 중간에 끊기면 절반만
올라간 파일이 남고, 그것이 아무것도 안 올린 것보다 나쁘다. 그래서 표준 JSON 으로 뽑고
피그마 쪽에서는 Tokens Studio 플러그인이 읽는다.

**그리고 이것이 드리프트를 막는 방법이다.** `design/` 이 정본의 사본이라 손으로 옮기면
또 어긋난다(실제로 열한 개가 어긋나 있었다). 토큰이 바뀌면 이 스크립트를 다시 돌린다.

    uv run python -m scripts.export_design_tokens

세 가지를 기계적으로 가른다. 손으로 분류하지 않는 이유는 분류가 사람의 판단이 되는
순간 다음 사람이 다르게 분류하기 때문이다.

* `var()` 하나만 있는 값은 **의미 토큰**이다 — 다른 토큰을 가리킨다.
* 그 밖은 **원시 토큰**이다 — 실제 값을 든다.
* `@media` 안에서 다시 정의되는 것은 **배치 토큰**이며 모드 셋으로 간다.

마지막이 중요하다. 피그마 변수에는 미디어쿼리가 없고 **모드**가 있다. 이 저장소가
브레이크포인트를 `spacing.css` 한 곳에만 두기로 한 규율이 마침 그 모양과 맞는다.
"""

import json
import re
import sys

from game.config import RESOURCES_DIR

# 토큰 원본. `design/` 은 Design 프로젝트 7a323244 의 사본이다.
TOKENS_DIR = RESOURCES_DIR.parent.parent / "design" / "tokens"

# 내보낼 곳. 저장소에 두어 토큰과 함께 버전 관리한다.
OUTPUT_PATH = RESOURCES_DIR.parent.parent / "design" / "tokens.json"

# 한 줄에서 토큰 하나를 집는다. 값은 세미콜론까지이며 주석은 뒤에 붙는다.
DECL_PATTERN = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);(?:\s*/\*\s*(.*?)\s*\*/)?")

# `@media (...)` 의 조건부. 모드 이름을 여기서 짓는다.
MEDIA_PATTERN = re.compile(r"@media\s*([^{]+)\{")

# 값이 오직 다른 토큰 하나를 가리키는가.
ALIAS_PATTERN = re.compile(r"^var\(--([a-z0-9-]+)\)$")

# 주석의 `@kind X` 표기. 저장소가 이미 붙여 둔 힌트라 그대로 존중한다.
KIND_PATTERN = re.compile(r"@kind\s+([a-z]+)")

# 미디어쿼리 조건에서 모드 이름으로. 순서가 곧 판정 순서다.
MODE_BY_MARK: tuple[tuple[str, str], ...] = (
    ("orientation:landscape", "landscape"),
    ("max-width:840px", "portrait"),
)

# 어느 미디어쿼리에도 안 걸리는 기본 배치.
BASE_MODE = "desktop"

# 값 모양에서 타입으로. 위에서부터 먼저 맞는 것을 쓴다.
TYPE_BY_PATTERN: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^#[0-9A-Fa-f]{3,8}$"), "color"),
    (re.compile(r"^-?\d+(\.\d+)?px$"), "dimension"),
    (re.compile(r"^-?\d+(\.\d+)?ms$"), "duration"),
    (re.compile(r"^-?\d+(\.\d+)?(em|rem|%)$"), "dimension"),
    (re.compile(r"^-?\d+(\.\d+)?$"), "number"),
)

# 저장소의 `@kind` 값에서 토큰 타입으로.
TYPE_BY_KIND = {"spacing": "dimension", "other": "other"}


def read_declarations(text: str) -> list[tuple[str, str, str, str]]:
    """CSS 한 편에서 토큰 선언을 순서대로 뽑는다.

    **미디어쿼리 안인지를 함께 들고 나온다.** 이름만 모으면 같은 토큰의 세 값이 서로를
    덮어써서, 반응형이 통째로 사라진 채 내보내진다.

    Args:
        text: CSS 원문.

    Returns:
        (이름, 값, 주석, 모드) 목록.
    """
    found: list[tuple[str, str, str, str]] = []
    mode = BASE_MODE
    depth = 0
    for line in text.splitlines():
        media = MEDIA_PATTERN.search(line)
        if media is not None:
            mode = resolve_mode(media.group(1))
            depth = 0
        depth += line.count("{") - line.count("}")
        if depth <= 0 and mode != BASE_MODE and "{" not in line and "}" in line:
            mode = BASE_MODE
        for name, value, note in DECL_PATTERN.findall(line):
            found.append((name, value.strip(), note or "", mode))
    return found


def resolve_mode(condition: str) -> str:
    """미디어쿼리 조건에서 모드 이름을 정한다.

    Args:
        condition: `@media` 뒤의 조건부.

    Returns:
        모드 이름. 아는 표지가 없으면 기본 배치다.
    """
    flat = condition.replace(" ", "")
    for mark, mode in MODE_BY_MARK:
        if mark in flat:
            return mode
    return BASE_MODE


def resolve_type(value: str, note: str) -> str:
    """값과 주석에서 토큰 타입을 정한다.

    **주석의 `@kind` 가 먼저다.** 저장소가 이미 판단해 적어 둔 것이라, 값 모양으로 다시
    추측하면 그 판단을 무시하게 된다 — `--plan-cols:12` 는 숫자처럼 보이지만 치수가
    아니라 격자 칸 수다.

    Args:
        value: 토큰 값.
        note: 선언 뒤의 주석.

    Returns:
        W3C 디자인 토큰 타입.
    """
    kind = KIND_PATTERN.search(note)
    if kind is not None:
        return TYPE_BY_KIND.get(kind.group(1), "other")
    for pattern, name in TYPE_BY_PATTERN:
        if pattern.match(value):
            return name
    return "other"


def build_reference(value: str, owner_by_name: dict[str, str]) -> str:
    """값 안의 `var()` 를 Tokens Studio 참조로 바꾼다.

    합성값(`1px solid var(--line)`)도 안쪽만 바꿔 그대로 둔다 — 통째로 버리면 괘선
    토큰이 값을 잃는다.

    Args:
        value: 토큰 값.
        owner_by_name: 토큰 이름에서 그것이 사는 셋 이름으로.

    Returns:
        참조로 바뀐 값.
    """

    def swap(match: re.Match[str]) -> str:
        name = match.group(1)
        owner = owner_by_name.get(name)
        return f"{{{owner}.{name}}}" if owner else match.group(0)

    return re.sub(r"var\(--([a-z0-9-]+)\)", swap, value)


def resolve_owner(name: str, value: str, modes: set[str]) -> str:
    """이 토큰이 어느 셋에 사는가.

    Args:
        name: 토큰 이름.
        value: 토큰 값.
        modes: 이 토큰이 정의된 모드들.

    Returns:
        셋 이름.
    """
    if modes - {BASE_MODE}:
        return "layout"
    return "semantic" if ALIAS_PATTERN.match(value) else "primitive"


def build_token_sets(declarations: list[tuple[str, str, str, str]]) -> dict:
    """선언 목록을 Tokens Studio 셋으로 묶는다.

    Args:
        declarations: `read_declarations` 가 낸 것들.

    Returns:
        셋 이름에서 토큰 절로의 대응표.
    """
    modes_by_name: dict[str, set[str]] = {}
    for name, _value, _note, mode in declarations:
        modes_by_name.setdefault(name, set()).add(mode)
    base_value = {name: value for name, value, _n, mode in declarations if mode == BASE_MODE}
    owner_by_name = {
        name: resolve_owner(name, base_value.get(name, ""), modes)
        for name, modes in modes_by_name.items()
    }

    sets: dict[str, dict] = {"primitive": {}, "semantic": {}}
    for name, value, note, mode in declarations:
        owner = owner_by_name[name]
        key = f"layout/{mode}" if owner == "layout" else owner
        sets.setdefault(key, {})[name] = {
            "$value": build_reference(value, owner_by_name),
            "$type": resolve_type(value, note),
        }
    return build_layout_fallback(apply_alias_types(sets))


def apply_alias_types(sets: dict[str, dict]) -> dict:
    """참조만 든 토큰의 타입을 가리키는 쪽에서 물려받는다.

    **별칭은 제 타입을 모른다.** `--text-accent:var(--brass)` 의 값은 참조 한 개라 모양만
    봐서는 색인지 치수인지 알 수 없고, 그대로 두면 전부 `other` 가 된다 — 피그마는 타입으로
    변수 종류를 정하므로, `other` 로 올라간 색은 색상 변수가 아니라 문자열 변수가 된다.

    체인을 끝까지 따라간다. 의미 토큰이 다른 의미 토큰을 가리키는 자리가 있다.

    Args:
        sets: 셋 대응표.

    Returns:
        타입이 채워진 셋 대응표.
    """
    by_name = {name: token for rows in sets.values() for name, token in rows.items()}
    for token in by_name.values():
        seen: set[str] = set()
        current = token
        while current["$type"] == "other":
            match = re.fullmatch(r"\{[a-z/]+\.([a-z0-9-]+)\}", str(current["$value"]))
            if match is None or match.group(1) in seen:
                break
            seen.add(match.group(1))
            target = by_name.get(match.group(1))
            if target is None:
                break
            if target["$type"] != "other":
                token["$type"] = target["$type"]
                break
            current = target
    return sets


def build_layout_fallback(sets: dict[str, dict]) -> dict:
    """배치 토큰의 빈 모드를 기본 배치 값으로 채운다.

    **모드마다 전량이 있어야 한다.** 피그마 변수는 모드에 값이 없으면 그 모드에서
    비어 버리는데, CSS 는 재정의하지 않은 값이 그대로 이어지는 것을 전제로 쓰여 있다.

    Args:
        sets: 셋 대응표.

    Returns:
        모드가 채워진 셋 대응표.
    """
    desktop = sets.get(f"layout/{BASE_MODE}", {})
    for _mark, mode in MODE_BY_MARK:
        target = sets.setdefault(f"layout/{mode}", {})
        for name, token in desktop.items():
            target.setdefault(name, dict(token))
    return sets


def build_metadata(sets: dict[str, dict]) -> dict:
    """플러그인이 읽는 셋 순서와 테마를 만든다.

    Args:
        sets: 셋 대응표.

    Returns:
        `$metadata` 와 `$themes` 를 더한 문서.
    """
    order = ["primitive", "semantic"] + [f"layout/{BASE_MODE}"]
    order += [f"layout/{mode}" for _mark, mode in MODE_BY_MARK]
    themes = [
        {
            "id": mode,
            "name": mode,
            "selectedTokenSets": {
                "primitive": "source",
                "semantic": "enabled",
                f"layout/{mode}": "enabled",
            },
        }
        for mode in [BASE_MODE, *[name for _mark, name in MODE_BY_MARK]]
    ]
    return {**sets, "$themes": themes, "$metadata": {"tokenSetOrder": order}}


def main() -> int:
    """토큰을 읽어 JSON 으로 내보낸다.

    Returns:
        종료 코드. 토큰 디렉터리가 없으면 1.
    """
    if not TOKENS_DIR.is_dir():
        print(f"토큰 디렉터리가 없다: {TOKENS_DIR}", file=sys.stderr)
        return 1
    declarations: list[tuple[str, str, str, str]] = []
    for path in sorted(TOKENS_DIR.glob("*.css")):
        declarations.extend(read_declarations(path.read_text(encoding="utf-8")))
    document = build_metadata(build_token_sets(declarations))
    OUTPUT_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts = {name: len(rows) for name, rows in document.items() if isinstance(rows, dict)}
    print(f"{OUTPUT_PATH} 에 썼다")
    for name, count in counts.items():
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
