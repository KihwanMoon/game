"""방마다 이름이 있는가.

**id 가 화면에 나오고 있었다** (2026-09-14 신고). 상단 바가 `4층 · pillars` 라고 적었고,
방 고르는 목록도 영문 id 서른한 줄이었다. 데이터에 이름 칸이 아예 없었으므로 화면이
적을 것이 그것뿐이었다 — **없는 것은 안 보이는 것이 아니라 id 로 보인다.**

파서는 `label_ko` 를 필수로 요구하지 않는다. 발행된 콘텐츠 팩은 DB 에 굳어 있어 이 칸이
없는 옛 팩이 남아 있고, 필수로 만들면 그 팩을 실은 클라이언트가 뜨지 않는다. 그래서
**저장소 파일은 여기서 본다** — 느슨한 파서와 엄한 게이트를 함께 둔다.

액트가 늘면 방도 는다(`기획/4_세계관` §4). 새 방에 이름을 안 붙이면 그 방만 id 로
보이므로, 이 시험이 그때 걸어 준다.
"""

from game.config import ROOM_TEMPLATES_PATH
from game.schemas.room import load_room_templates

TEMPLATES = load_room_templates(ROOM_TEMPLATES_PATH)


def test_every_room_has_a_name():
    """★ 이름 없는 방은 화면에 id 로 나온다."""
    missing = tuple(one.template_id for one in TEMPLATES if one.label_ko == "")
    assert missing == (), f"이름이 없다: {missing}"


def test_room_names_do_not_collide():
    """★ 두 방이 같은 이름이면 고르는 사람이 어느 쪽인지 알 수 없다."""
    seen: dict[str, str] = {}
    for template in TEMPLATES:
        clash = seen.get(template.label_ko)
        assert clash is None, (
            f"「{template.label_ko}」 를 {clash} 와 {template.template_id} 가 함께 쓴다"
        )
        seen[template.label_ko] = template.template_id


def test_title_falls_back_to_id():
    """★ 이름이 없어도 빈 칸이 아니라 id 가 보인다 — 「방이 사라졌다」로 읽히면 안 된다."""
    for template in TEMPLATES:
        assert template.title != ""
