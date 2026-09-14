"""화면에 실리는 1막의 글이 층과 맞는가.

**글은 파이썬이 안 읽는다.** 브라우저만 읽는 자산인데 여기서 보는 이유는, 그 파일이
`max_floor` 와 짝을 맞춰야 하기 때문이다 — 층이 늘면 장도 늘어야 하고, 안 늘면 마지막
층을 깬 사람에게 아무 글도 안 뜬다. **그 실패는 조용하다.**

**세대는 `core_version` 에 안 들어간다.** 글은 판정에 닿지 않으므로 올리면 돌고 있는
티켓만 무효가 된다 (자산 여섯과 다른 축이다). 그래서 이 파일은 `content_versions` 가
아니라 이 시험이 지킨다.
"""

import json

from game.config import BALANCE_PATH

STORY_PATH = BALANCE_PATH.parent.parent / "story" / "act1.json"
STORY = json.loads(STORY_PATH.read_text(encoding="utf-8"))
MAX_FLOOR = int(json.loads(BALANCE_PATH.read_text(encoding="utf-8"))["floor_scale"]["max_floor"])


def test_every_floor_has_a_chapter():
    """★ 층이 늘면 장도 늘어야 한다 — 안 늘면 그 층에 아무 글도 안 뜬다."""
    floors = sorted(int(one["floor"]) for one in STORY["chapters"])
    assert floors == list(range(1, MAX_FLOOR + 1))


def test_no_chapter_is_empty():
    """★ 빈 글은 「글이 없다」가 아니라 「글이 비었다」로 보인다."""
    for chapter in STORY["chapters"]:
        assert chapter["title_ko"].strip() != ""
        assert chapter["note_ko"].strip() != ""


def test_emphasis_marks_are_paired():
    """★ 여는 표시가 홀수면 화면이 가르기를 포기하고 `**` 가 글자로 보인다."""
    notes = [one["note_ko"] for one in STORY["chapters"]]
    notes.append(STORY["shadow"]["note_ko"])
    for note in notes:
        assert note.count("**") % 2 == 0, note[:30]


def test_shadow_card_is_not_bound_to_a_floor():
    """★ 둔갑은 죽은 자리에 선다 — 층을 적어 두면 「5장에서 만난다」가 대개 거짓이 된다."""
    assert "floor" not in STORY["shadow"]
    assert STORY["shadow"]["note_ko"].strip() != ""
