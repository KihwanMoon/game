"""토큰 잠금 파일을 만든다.

**사본이 또 썩는 것을 그날 잡기 위해서다.**

`design/tokens/*.css` 는 Claude Design 프로젝트 `7a323244` 의 사본이다. 예전에 열한 개가
어긋난 것을 **몇 주 뒤 전수 조사로** 알았다. 사본은 조용히 썩고, 조용한 것은 조사가
되기 전까지 아무도 모른다.

잠금 파일은 마지막으로 정본에서 받아온 순간의 값을 그대로 적어 둔다. 게이트는 지금
`design/tokens/*.css` 가 그 값과 같은지만 본다 — **네트워크를 타지 않는다.** 검사가
네트워크를 타면 정본이 잠깐 안 뜰 때 게이트가 막히고, 그러면 사람이 검사를 끈다.

    잡히는 것   저장소의 사본을 누가 손댔다
    안 잡히는 것 정본이 바뀌었다

뒤엣것은 받아올 때 알게 된다: 받아온 값이 잠금과 다르면 그것이 곧 「정본이 바뀌었다」다.
그때 이 스크립트를 다시 돌려 잠금을 갱신하고, 바뀐 내용을 코드에 반영한다.

    uv run python -m scripts.lock_design_tokens          # 갱신
    uv run python -m scripts.lock_design_tokens --check  # 대조만 (게이트가 쓴다)
"""

import argparse
import json
import sys

from scripts.export_design_tokens import TOKENS_DIR, read_declarations

# 잠금 파일 자리. `design/` 안에 두는 이유는 이것이 그 디렉터리에 대한 기록이기 때문이다.
LOCK_PATH = TOKENS_DIR.parent / "tokens.lock.json"

# 잠금 파일 머리말. 다음 사람이 이 파일만 열어도 무엇인지 알아야 한다.
LOCK_NOTE = (
    "design/tokens/*.css 가 정본(Claude Design 7a323244)에서 받아온 순간의 값이다. "
    "게이트가 이것과 대조해 **사본이 손대졌는지**를 본다 — 정본이 바뀐 것은 여기서 못 "
    "잡고, 받아올 때 알게 된다. 값을 고쳐야 하면 이 파일이 아니라 정본을 고치고 "
    "`uv run python -m scripts.lock_design_tokens` 로 다시 잠근다."
)


def build_lock() -> dict:
    """지금 사본에서 잠금 내용을 만든다.

    **모드를 키에 넣는다.** 이름만 쓰면 반응형 토큰의 세 값이 서로를 덮어써서, 배치가
    통째로 바뀌어도 잠금이 그대로다.

    Returns:
        잠금 문서.
    """
    entries: dict[str, str] = {}
    for path in sorted(TOKENS_DIR.glob("*.css")):
        text = path.read_text(encoding="utf-8")
        for name, value, _note, mode in read_declarations(text):
            entries[f"{path.name}:{mode}:--{name}"] = value
    return {
        "_note": LOCK_NOTE,
        "source_project": "7a323244-94a4-426b-a3b5-1bb1c949c195",
        "token_count": len(entries),
        "tokens": dict(sorted(entries.items())),
    }


def list_drift(lock: dict, current: dict) -> list[str]:
    """잠금과 지금 사본의 차이를 줄로 낸다.

    Args:
        lock: 잠긴 문서.
        current: 지금 사본에서 만든 문서.

    Returns:
        사람이 읽을 차이 줄들. 같으면 빈 목록.
    """
    was, now = lock["tokens"], current["tokens"]
    found: list[str] = []
    for key in sorted(set(was) | set(now)):
        if key not in now:
            found.append(f"사라졌다  {key} = {was[key]}")
        elif key not in was:
            found.append(f"생겼다    {key} = {now[key]}")
        elif was[key] != now[key]:
            found.append(f"바뀌었다  {key}: {was[key]} → {now[key]}")
    return found


def main() -> int:
    """잠금을 갱신하거나 대조한다.

    Returns:
        종료 코드. 대조에서 차이가 있으면 1.
    """
    parser = argparse.ArgumentParser(description="디자인 토큰 잠금")
    parser.add_argument("--check", action="store_true", help="갱신하지 않고 대조만 한다")
    args = parser.parse_args()

    current = build_lock()
    if not args.check:
        LOCK_PATH.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"잠갔다 — 토큰 {current['token_count']}개 → {LOCK_PATH}")
        return 0

    if not LOCK_PATH.is_file():
        print(f"잠금 파일이 없다: {LOCK_PATH}", file=sys.stderr)
        return 1
    drift = list_drift(json.loads(LOCK_PATH.read_text(encoding="utf-8")), current)
    if not drift:
        print(f"토큰 {current['token_count']}개 — 잠금과 같다")
        return 0
    print(f"토큰이 잠금과 다르다 ({len(drift)}건):", file=sys.stderr)
    for line in drift:
        print(f"  {line}", file=sys.stderr)
    print(
        "\n사본을 고쳤다면 되돌린다. 정본을 고쳤다면 다시 받아온 뒤"
        " `uv run python -m scripts.lock_design_tokens` 으로 잠근다.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
