"""사람 이름은 한 곳에서만 나온다 (2026-09-18).

**같은 사람이 화면마다 다른 이름으로 보였다.** 닉네임을 지어도 둔갑 목록·발행 기록·
초안·저잣거리·봇 상세는 자동 별명(`handle`)을 그대로 적었다 — 여섯 자리가
`build_display_name_sql` 을 안 거치고 `a.handle` 을 직접 뽑고 있었다 (실제 신고).

**정본은 `display_name.py` 다** — `COALESCE(nickname, login_id, handle)`. 사람이 이름을
지었으면 그 이름이, 안 지었으면 자동 별명이 나온다. 봇은 닉네임을 안 쓰므로(U3 —
`bot_` 접두어가 「이것이 봇이다」를 싣는 유일한 채널이다) 자동으로 손잡이로 떨어진다.

**이 검사는 텍스트를 본다.** 질의를 실제로 돌려 보는 검사가 더 좋겠지만, 새 질의가
붙는 순간을 잡으려면 그 질의가 이미 있어야 한다 — 이쪽은 **쓰기 전에** 막는다.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 사람 이름을 내는 코드가 사는 곳.
SEARCHED = (REPO_ROOT / "game" / "app" / "store", REPO_ROOT / "game" / "api")

# `handle` 을 조회에서 직접 뽑는 꼴. 별칭이 붙든 안 붙든 잡는다.
RAW_HANDLE = re.compile(r"(?:SELECT|COALESCE\()\s*\w*\.?handle\b", re.I)

# 이름을 내려는 것이 아니라서 괜찮은 자리.
ALLOWED = {
    # 토큰으로 계정을 푸는 자리. 화면에 적는 값이 아니라 **계정을 가리키는 키**다.
    "accounts.py",
    # 이름이 겹치는지 보는 자리와, 봇 이름의 앞자리를 지키는 자리. 둘 다 `handle`
    # 자체가 대상이라 표시 이름으로 바꾸면 검사가 딴것을 본다.
    "bots.py",
    # 정본 그 자신.
    "display_name.py",
}


def list_raw_handle_reads() -> list[str]:
    """조회에서 `handle` 을 직접 뽑는 자리를 모은다.

    Returns:
        `파일:줄번호  줄` 꼴의 목록. 없으면 빈 목록.
    """
    found: list[str] = []
    for root in SEARCHED:
        for path in sorted(root.rglob("*.py")):
            if path.name in ALLOWED:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                # 주석은 설명이지 질의가 아니다.
                if stripped.startswith("#"):
                    continue
                if RAW_HANDLE.search(line):
                    found.append(f"{path.relative_to(REPO_ROOT)}:{number}  {stripped}")
    return found


def test_no_query_reads_the_handle_directly():
    """★ **사람 이름을 내는 질의는 전부 정본을 거친다.**

    새 질의가 `a.handle` 을 직접 뽑으면 여기서 걸린다. 그때 할 일은 이 목록에 예외를
    더하는 것이 아니라 `build_display_name_sql(별칭)` 을 쓰는 것이다 — 예외를 더해야
    한다면 그 파일이 **이름이 아니라 키**를 다루는지 먼저 확인한다.
    """
    found = list_raw_handle_reads()
    assert found == [], "정본을 안 거치고 손잡이를 뽑는 자리:\n" + "\n".join(found)
