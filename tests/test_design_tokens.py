"""토큰 사본이 정본에서 받아온 그대로인가.

**사본은 조용히 썩는다.** `design/tokens/*.css` 는 Claude Design 프로젝트 `7a323244` 의
사본인데, 예전에 열한 개가 어긋난 것을 **몇 주 뒤 전수 조사로** 알았다. 조용한 것은
조사가 되기 전까지 아무도 모르고, 그 사이 두 코어가 다른 값으로 돈다.

컴포넌트는 `components.contract.json` 이 계약을 적어 대조한다. 토큰은 계약이 아니라
값 자체가 전부라 잠금 파일(`design/tokens.lock.json`)이 받아온 순간을 그대로 적어 둔다.

**네트워크를 타지 않는다.** 검사가 정본을 직접 부르면 정본이 잠깐 안 뜰 때 게이트가
막히고, 그러면 사람이 검사를 끈다. 여기서 잡는 것은 「저장소의 사본을 누가 손댔다」이고,
「정본이 바뀌었다」는 받아올 때 알게 된다 — 받아온 값이 잠금과 다른 것이 곧 그 신호다.
"""

import json

from scripts.lock_design_tokens import LOCK_PATH, build_lock, list_drift

# 잠금이 이 수 아래로 떨어지면 파서가 조용히 아무것도 못 읽은 것이다. 파일이 통째로
# 비어도 「차이 없음」으로 통과하는 길을 막는다.
MIN_TOKENS = 150


def read_lock() -> dict:
    """잠금 파일을 읽는다.

    Returns:
        잠긴 문서.
    """
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def test_the_copy_matches_the_lock():
    """★ **사본이 받아온 그대로다.**

    누가 `design/tokens/*.css` 를 손대면 여기서 걸린다. 고칠 일이 있으면 사본이 아니라
    정본을 고치고 다시 받아온 뒤 `scripts.lock_design_tokens` 로 잠근다.
    """
    drift = list_drift(read_lock(), build_lock())
    assert drift == [], "토큰이 잠금과 다르다:\n" + "\n".join(drift)


def test_the_lock_is_not_empty():
    """★ 파서가 아무것도 못 읽으면 「차이 없음」으로 통과한다 — 그 길을 막는다."""
    lock = read_lock()
    assert lock["token_count"] >= MIN_TOKENS
    assert len(lock["tokens"]) == lock["token_count"]


def test_the_lock_keeps_modes_apart():
    """★ 반응형 토큰의 세 값이 서로를 덮으면 안 된다.

    이름만 키로 쓰면 세로·가로 배치가 통째로 바뀌어도 잠금이 그대로다 — 모바일 배치가
    조용히 어긋나는 정확한 경로다.
    """
    modes = {key.split(":")[1] for key in read_lock()["tokens"]}
    assert modes == {"desktop", "portrait", "landscape"}


def test_the_lock_says_where_it_came_from():
    """정본이 둘로 나뉘어 있다 — 어느 쪽에서 왔는지 안 적으면 엉뚱한 곳을 고친다."""
    assert read_lock()["source_project"] == "7a323244-94a4-426b-a3b5-1bb1c949c195"
