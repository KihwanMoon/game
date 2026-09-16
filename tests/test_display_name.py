"""표시 이름 — 화면마다 다른 이름이 뜨면 안 된다 (2026-09-16).

**실제로 그랬다.** 순위표는 아이디를, 둔갑 전적과 관리자 화면은 자동 생성 별명
(`user_3f9a…`)을 보여 줬다. 같은 사람이 화면을 옮길 때마다 다른 이름이 되니 「누가
누구인지」가 끊겼다 — 내 둔갑이 남의 장에 서는 게임에서 그것은 기제의 절반을 못 쓰게 한다.

여기서 지키는 것은 넷이다.

1. **순서가 하나다.** 닉네임 → 아이디 → 자동 별명.
2. **접어서 유일하다.** 대소문자만 다른 이름을 허용하면 순위표에서 남을 흉내 낼 수 있다.
3. **자동 별명의 머리말을 못 쓴다.** `bot_` 으로 시작하는 이름은 화면에서 봇으로 읽힌다.
4. **자동 별명은 안 바뀐다.** 그것은 내부 이름이고, 닉네임은 보여 주기 위한 이름이다.
"""

import os

import pytest

from game.app.store.connection import DATABASE_URL_ENV

pytestmark = pytest.mark.skipif(
    not os.environ.get(DATABASE_URL_ENV, "").strip(),
    reason=f"{DATABASE_URL_ENV} 가 없다 — 컨테이너 게이트에서 돈다",
)


@pytest.fixture
def client():
    fastapi_testclient = pytest.importorskip("fastapi.testclient")
    from game.api.main import create_app

    with fastapi_testclient.TestClient(create_app()) as running:
        yield running


def build_headers(token):
    return {"X-Game-Token": token}


def build_account(client):
    """익명 계정 하나."""
    token = client.post("/api/account").json()["token"]
    return token, client.get("/api/account", headers=build_headers(token)).json()["account_id"]


def test_the_order_is_one(client):
    """★ 닉네임 → 아이디 → 자동 별명. 앞엣것이 비면 뒤로 내려간다."""
    from game.api.deps import get_pool
    from game.app.store.credentials import register_login
    from game.app.store.display_name import apply_nickname, read_display_name

    pool = get_pool()
    _token, account_id = build_account(client)

    assert read_display_name(pool, account_id).startswith("user_"), "자동 별명이 아니다"

    register_login(pool, account_id, f"id{account_id}", "비밀번호1234")
    assert read_display_name(pool, account_id) == f"id{account_id}", "아이디로 안 내려갔다"

    apply_nickname(pool, account_id, "하윤")
    assert read_display_name(pool, account_id) == "하윤", "닉네임이 앞서지 않는다"


def test_names_are_unique_when_folded(client):
    """★ 대소문자만 다른 이름은 못 쓴다 — 순위표에서 남을 흉내 낼 수 있다."""
    from game.api.deps import get_pool
    from game.app.store.display_name import apply_nickname

    pool = get_pool()
    _first_token, first = build_account(client)
    _second_token, second = build_account(client)

    assert apply_nickname(pool, first, "Hayun") is True
    assert apply_nickname(pool, second, "hayun") is False, "접으면 같은 이름이 둘 섰다"


def test_reserved_prefixes_are_refused(client):
    """★ 자동으로 붙는 이름의 머리말은 못 쓴다 — `bot_` 은 화면에서 봇으로 읽힌다."""
    from game.app.store.display_name import check_nickname

    assert check_nickname("bot_hayun") != ""
    assert check_nickname("user_hayun") != ""
    assert check_nickname("하윤") == ""


def test_shape_is_checked(client):
    """★ 길이와 글자를 본다 — 공백을 받으면 앞뒤에 붙여 남과 같아 보이는 이름이 생긴다."""
    from game.app.store.display_name import check_nickname

    assert check_nickname("가") != "", "너무 짧은데 통과했다"
    assert check_nickname("가" * 17) != "", "너무 긴데 통과했다"
    assert check_nickname("하 윤") != "", "공백이 통과했다"
    assert check_nickname("ha_yun-1") == ""


def test_setting_a_name_does_not_move_the_handle(client):
    """★ 자동 별명은 안 바뀐다 — 내부 이름과 보여 주는 이름은 다른 것이다."""
    token, _account_id = build_account(client)
    before = client.get("/api/account", headers=build_headers(token)).json()["handle"]

    response = client.post(
        "/api/account/nickname", json={"nickname": "무영"}, headers=build_headers(token)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["handle"] == before, "자동 별명이 바뀌었다"
    assert body["nickname"] == "무영"
    assert body["display_name"] == "무영"


def test_a_taken_name_is_refused_by_the_route(client):
    """★ 이미 쓰이는 이름은 409 다 — 조용히 덮으면 앞사람의 이름이 사라진다."""
    first_token, _first = build_account(client)
    second_token, _second = build_account(client)
    client.post(
        "/api/account/nickname", json={"nickname": "선점"}, headers=build_headers(first_token)
    )

    again = client.post(
        "/api/account/nickname", json={"nickname": "선점"}, headers=build_headers(second_token)
    )

    assert again.status_code == 409


def test_the_same_name_can_be_set_again(client):
    """★ 제 이름을 다시 정하는 것은 막지 않는다 — 막으면 대소문자만 고칠 수 없다."""
    token, _account_id = build_account(client)
    client.post("/api/account/nickname", json={"nickname": "각수"}, headers=build_headers(token))

    again = client.post(
        "/api/account/nickname", json={"nickname": "각수"}, headers=build_headers(token)
    )

    assert again.status_code == 200


def test_the_leaderboard_row_keeps_its_columns(client):
    """★ 이름을 바꿔 끼우면서 **열 자리가 밀렸다** (2026-09-16).

    조회에서 열 둘을 하나로 합쳤는데 뒤 열을 읽는 첨자를 안 옮겨서, `level` 과
    `account_id` 가 한 칸씩 어긋났다. 줄이 없으면 그 코드가 안 돌아 **격리해서는
    통과했고**, 전량에서만 깨졌다 — 그래서 여기서 줄이 실제로 있는 상태로 본다.
    """
    from game.api.deps import get_pool
    from game.app.store.display_name import apply_nickname
    from game.app.store.progress import list_leaderboard, save_leaderboard

    pool = get_pool()
    _token, account_id = build_account(client)
    apply_nickname(pool, account_id, "열자리")
    save_leaderboard(pool, "PRACTICE", "columns.v1", account_id, 4_242, 13)

    row = next(
        one
        for one in list_leaderboard(pool, "PRACTICE", "columns.v1")
        if one["account_id"] == account_id
    )

    assert row["handle"] == "열자리", "이름 자리가 어긋났다"
    assert row["score"] == 4_242, "점수 자리가 어긋났다"
    assert row["level"] == 13, "레벨 자리가 어긋났다"
