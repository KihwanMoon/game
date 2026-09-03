"""봇 루프 — 세계를 혼자 두지 않는다 (T11 대응, 결정 #48 준비).

**라우트를 그대로 탄다.** `game_net` 안에서 백엔드에 HTTP 로 붙어 `/api/account` →
`/api/ticket` → `/api/run` 을 순서대로 부른다. 서비스 계층을 직접 부르면 티켓 1회용·
코어버전 대조·정비 같은 라우트 규율을 우회하게 되고, 그러면 봇의 런은 「진짜 경로가
도는지」를 더 이상 증명하지 못한다.

**라우트가 아니라 스크립트인 이유**는 `run_world_tick` 과 같다 — 이것은 운영이 부르는
것이다. 엔드포인트로 두면 누구나 세계를 앞으로 밀 수 있다.

    GAME_DATABASE_URL=... GAME_API_URL=http://backend:8000 uv run python -m scripts.run_bots

봇마다 시간당 다섯 판이 상한이고 그것을 `bot_profile.next_run_at` 이 물린다. 루프는
자주 깨어나되 차례가 된 봇만 내보낸다.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

from psycopg_pool import ConnectionPool

from game.app.bots.personas import BOT_PERSONAS
from game.app.bots.play import build_played_ruleset, list_persona_specs, resolve_claim_floors
from game.app.services.run_battle import load_balance
from game.app.services.run_chain import run_room_chain
from game.app.store.bots import (
    BotProfile,
    apply_bot_rest,
    create_bot,
    list_bots,
    list_due_bots,
    save_bot_token,
)
from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.config import (
    BALANCE_PATH,
    BENCHMARK_RULESETS_PATH,
    BLOCKS_PATH,
    ENEMY_RULESETS_PATH,
    G0_RULESETS_PATH,
    ROOM_TEMPLATES_PATH,
)
from game.schemas.blocks import load_block_catalog
from game.schemas.loadout import parse_loadout
from game.schemas.monster_snapshot import parse_snapshot, sort_snapshots
from game.schemas.room import load_room_templates
from game.schemas.ruleset import load_rulesets, parse_ruleset

# 백엔드 주소. 컨테이너 안에서는 서비스 이름으로 닿는다.
API_URL_ENV = "GAME_API_URL"
DEFAULT_API_URL = "http://backend:8000"

# 토큰 헤더. 브라우저가 쓰는 것과 같다.
TOKEN_HEADER = "X-Game-Token"

# 루프가 깨어나는 간격(초). 상한(720초)보다 촘촘해야 차례를 놓치지 않는다.
TICK_SEC = 30

# HTTP 대기 상한(초). 재시뮬이 하강 전체를 도는 제출이 가장 오래 걸린다.
TIMEOUT_SEC = 60

# 봇이 출발하는 방. 서버가 여기서부터 하강을 짠다.
START_ROOM_ID = "corridor"


def send_request(url: str, token: str, payload: dict | None) -> dict | None:
    """백엔드에 한 번 부른다.

    Args:
        url: 전체 주소.
        token: 기기 토큰. 빈 문자열이면 헤더를 안 붙인다.
        payload: 보낼 절. None 이면 GET 이다.

    Returns:
        응답 절. 닿지 못했거나 4xx·5xx 면 None — **봇이 죽지 않는다**. 백엔드가 잠깐
        내려가도 루프가 멈추면 안 되고, 다음 차례에 다시 시도하면 그만이다.

        **사유는 반드시 적는다.** 삼키면 「티켓을 못 받았다」만 남아 무엇이 잘못됐는지
        알 수 없다 — 실제로 그 상태로 배포해 한 번 헤맸다.
    """
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="GET" if body is None else "POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header(TOKEN_HEADER, token)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:  # noqa: S310 내부 주소만 부른다
            return dict(json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as error:
        print(f"[봇] {url} → {error.code} {error.read()[:200]!r}", file=sys.stderr, flush=True)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        print(f"[봇] {url} → {error}", file=sys.stderr, flush=True)
        return None


def build_parts() -> dict:
    """봇이 판을 미리 돌려 보는 데 필요한 자원.

    한 번만 읽는다 — 봇마다 다시 읽으면 루프가 파일 읽기로 채워진다.

    Returns:
        방·밸런스·블록·규칙표 묶음.
    """
    raw: dict[str, dict] = {}
    for path in (BENCHMARK_RULESETS_PATH, G0_RULESETS_PATH):
        for item in json.loads(path.read_text(encoding="utf-8"))["rulesets"]:
            raw[item["ruleset_id"]] = item
    return {
        "rooms": {t.template_id: t for t in load_room_templates(ROOM_TEMPLATES_PATH)},
        "balance": load_balance(BALANCE_PATH),
        "catalog": load_block_catalog(BLOCKS_PATH),
        "enemy": load_rulesets(ENEMY_RULESETS_PATH),
        "raw": raw,
    }


def apply_bot_seed(pool: ConnectionPool, api_url: str) -> None:
    """봇 열이 없으면 만든다.

    **계정을 라우트로 만든다.** 행을 직접 넣으면 익명 계정이 생길 때 함께 서는 것들
    (플레이어 개체·지갑·발견 기록)이 빠지고, 그 봇은 첫 판에서 조용히 다른 길을 탄다.

    Args:
        pool: 연결 풀.
        api_url: 백엔드 주소.
    """
    if len(list_bots(pool)) >= len(BOT_PERSONAS):
        return
    known = {profile.account_id for profile in list_bots(pool)}
    for handle, ruleset_id, cadence, skill in list_persona_specs():
        created = send_request(f"{api_url}/api/account", "", {})
        if created is None:
            print(f"[봇] 계정을 못 만들었다: {handle}", file=sys.stderr)
            continue
        account_id = int(created["account_id"])
        if account_id in known:
            continue
        create_bot(pool, account_id, handle, ruleset_id, cadence, skill)
        save_bot_token(pool, account_id, str(created["token"]))
        print(f"[봇] {handle} 섰다 — 규칙표 {ruleset_id}, 실력 {skill}%")


def run_one_bot(pool: ConnectionPool, api_url: str, bot: BotProfile, parts: dict) -> str:
    """봇 하나가 한 판 논다.

    브라우저와 같은 순서다 — 티켓을 받고, 그 입력으로 직접 돌려 어디까지 깼는지 알고,
    깬 층마다 청구한다. **결과는 보내지 않는다**; 서버가 티켓으로 다시 돌려 확정한다.

    Args:
        pool: 연결 풀.
        api_url: 백엔드 주소.
        bot: 이 봇의 성격.
        parts: 자원 묶음.

    Returns:
        무슨 일이 있었는지 한 줄.
    """
    ticket = send_request(f"{api_url}/api/ticket", bot.token, {"room_id": START_ROOM_ID})
    if ticket is None:
        return "티켓을 못 받았다"
    room_ids = ticket.get("room_ids") or [ticket["room_id"]]
    rooms = parts["rooms"]
    chain = tuple(rooms[room_id] for room_id in room_ids if room_id in rooms)
    if not chain:
        return "방 목록이 비었다"
    raw = parts["raw"].get(bot.ruleset_id)
    if raw is None:
        return f"규칙표가 없다: {bot.ruleset_id}"
    played = build_played_ruleset(raw, bot.skill_pct)
    loadout = ticket.get("loadout")
    result = run_room_chain(
        chain,
        parts["balance"],
        parts["catalog"],
        parse_ruleset(played),
        parts["enemy"],
        seed=int(ticket["seed"]),
        snapshots=sort_snapshots(
            tuple(parse_snapshot(item) for item in ticket.get("monster_snapshot") or ())
        ),
        loadout=parse_loadout(loadout) if loadout else None,
        floor=int(ticket.get("floor", 1)),
        rooms_per_floor=int(ticket.get("rooms_per_floor", 0)),
    )
    floors = resolve_claim_floors(
        int(ticket.get("floor", 1)),
        result.cleared_rooms,
        int(ticket.get("rooms_per_floor", 0)),
        len(chain),
    )
    rewards = []
    for floor in floors:
        # 층마다 청구한다. 마지막 층만 청구하면 중간 층의 정산·전리품이 통째로 빠진다.
        answer = send_request(
            f"{api_url}/api/run",
            bot.token,
            {
                "ticket_id": ticket["ticket_id"],
                "ruleset": played,
                "core_version": ticket["core_version"],
                "floor": floor,
            },
        )
        if answer is None:
            break
        rewards.append(f"{floor}층 {answer.get('reward', '')}".strip())
    cleared = result.cleared_rooms // max(1, int(ticket.get("rooms_per_floor", 1)))
    depth = f"{cleared}층 깼다" if cleared else "1층에서 죽었다"
    return f"{depth} · " + (" · ".join(rewards) if rewards else "정산 없음")


def apply_bot_round(pool: ConnectionPool, api_url: str, parts: dict) -> int:
    """차례가 된 봇들을 한 번씩 내보낸다.

    Args:
        pool: 연결 풀.
        api_url: 백엔드 주소.
        parts: 자원 묶음.

    Returns:
        내보낸 봇 수.
    """
    due = list_due_bots(pool)
    for bot in due:
        # **먼저 쉬게 하고 나서 논다.** 뒤에 미루면 판에서 예외가 났을 때 그 봇이 같은
        # 판을 쉬지 않고 되풀이한다.
        apply_bot_rest(pool, bot.account_id, bot.cadence_sec)
        try:
            note = run_one_bot(pool, api_url, bot, parts)
        except (KeyError, ValueError, TypeError) as error:
            note = f"판이 깨졌다: {error}"
        print(f"[봇] {bot.label} — {note}", flush=True)
    return len(due)


def main() -> int:
    """봇 루프를 돈다.

    Returns:
        종료 코드. 데이터베이스 주소가 없으면 1.
    """
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 1
    api_url = os.environ.get(API_URL_ENV, DEFAULT_API_URL).rstrip("/")
    pool = create_pool(url)
    parts = build_parts()
    apply_bot_seed(pool, api_url)
    print(f"[봇] 루프 시작 — {api_url}, {TICK_SEC}초마다 차례를 본다", flush=True)
    while True:
        apply_bot_round(pool, api_url, parts)
        time.sleep(TICK_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
