"""방별 상시 기록의 판정 (2026-09-25).

`routes/run.py` 가 제출을 받고 재시뮬을 부른 뒤, **그 결과가 기록판에 무엇을 하는가**를
여기서 정한다. 라우트는 이미 400줄 상한 턱밑이라 떼어 냈지만, 가르는 선은 책임이다 (§4).

**값은 전부 서버가 낸다** (설계/7_변조방지 §4). CPU 와 줄 수는 검증기를 지난 규칙표에서,
틱은 재시뮬에서 나온다 — 클라이언트는 「기록이다」라고 주장할 자리조차 없다. 방과 시드는
티켓이 정했다.
"""

import hashlib

from game.api.deps import get_context, get_pool
from game.app.items.loadout import build_player_loadout
from game.app.rules.rule_vm import count_cpu_usage
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.store.room_records import RoomRecord, find_my_room_record, save_room_record
from game.app.store.shared_rulesets import save_shared
from game.app.store.tickets import IssuedTicket
from game.schemas.consumable import BASE_CONSUMABLE_SLOTS, FREE_CHARGES
from game.schemas.loadout import build_loadout_payload
from game.schemas.ruleset import parse_ruleset
from game.schemas.run_ticket import MAX_SEED

# 기록 도전은 **1층의 몸으로 1층의 세기에서** 싸운다. 깊은 방도 그렇다 — 기록판이 재는
# 것은 규칙표이지 성장이 아니고, 방마다 층을 따르면 깊은 방은 맨몸으로 영영 못 깬다.
RECORD_FLOOR = 1

# 기록 도전의 몸은 **새로 온 사람의 몸**이다 — 레벨 1, 장비 없음, 빈 기본 칸의 공짜 충전.
# 누구나 가진 몸이어야 「장비가 좋아서」가 기록에 끼지 않는다.
RECORD_LEVEL = 1

# 공유 이름의 머리. 기록판의 줄을 누르면 이 이름으로 열린다.
SHARE_NAME_PREFIX = "기록"


def build_record_seed(room_id: str, core_version: str) -> int:
    """그 방의 기록 시드를 만든다. **모두가 같은 시드를 받아야** 기록이 비교된다.

    방과 코어 버전에서 파생한다 — 데일리가 날짜에서 파생하는 것과 같은 방식이다. 서버가
    정한 값이라 「유리한 시드를 골라 담기」(T2)가 성립하지 않는다.

    Args:
        room_id: 방 id.
        core_version: 이 서버의 코어 버전.

    Returns:
        0 이상 MAX_SEED 이하의 정수.
    """
    digest = hashlib.sha256(f"record:{room_id}:{core_version}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (MAX_SEED + 1)


def build_record_loadout() -> dict:
    """기록 도전의 몸을 로드아웃 절로 만든다.

    **비워 두지 않고 명시한다.** 로드아웃이 없으면 브라우저는 서버가 검증한 적 없는 로컬 판
    경로로 돌고, 두 코어가 거기서 갈리면 기록이 전부 반려된다. 일반 티켓과 같은 모양으로
    실어야 같은 해석을 탄다.

    Returns:
        티켓에 실을 로드아웃 절.
    """
    player = get_context().balance["player"]
    loadout = build_player_loadout(
        {key: int(value) for key, value in player.items() if isinstance(value, int)},
        {},
        RECORD_LEVEL,
        int(player["rule_slots"]),
        None,
        # 빈 기본 칸이 출격 때 채우는 공짜 충전과 같은 값이다 (`count_slot_charges`).
        {tag: count * FREE_CHARGES for tag, count in BASE_CONSUMABLE_SLOTS},
    )
    return build_loadout_payload(loadout)


def apply_record_outcome(
    ticket: IssuedTicket,
    submission_id: int,
    ruleset_payload: dict,
    verified: VerifiedRun,
    account_id: int,
) -> str:
    """검증된 기록 도전을 기록판에 반영하고 한 줄로 알린다.

    **이긴 판만 적는다.** 진 판의 CPU 는 「적게 써서 풀었다」가 아니라 「못 풀었다」다.

    Args:
        ticket: 이 도전의 티켓. 방과 코어 버전이 여기서 온다.
        submission_id: 제출 id.
        ruleset_payload: 제출된 규칙표 절. 재시뮬이 이미 검증기를 통과시켰다.
        verified: 서버가 확정한 결과.
        account_id: 도전한 계정.

    Returns:
        화면에 보일 한 줄. 반려됐으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    if verified.outcome != OUTCOME_PLAYER_WIN:
        return "기록 도전 — 이기지 못해 기록이 안 남았다"
    pool = get_pool()
    ruleset = parse_ruleset(ruleset_payload)
    record = RoomRecord(
        room_id=ticket.room_id,
        core_version=ticket.core_version,
        account_id=account_id,
        cpu=count_cpu_usage(ruleset),
        ticks=verified.ticks,
        rule_count=len(ruleset.rules),
        # **줄을 누르면 그 표가 열린다.** 공유 주소는 내용 해시라 같은 표는 같은 주소다.
        share_id=save_shared(
            pool,
            ruleset_payload,
            f"{SHARE_NAME_PREFIX} · {ticket.room_id}",
            ticket.core_version,
            account_id,
        ),
        submission_id=submission_id,
    )
    is_better = save_room_record(pool, record)
    mine = find_my_room_record(pool, ticket.room_id, ticket.core_version, account_id)
    head = "새 기록" if is_better else "기록 도전"
    line = f"{head} — CPU {record.cpu} · {record.ticks}틱 · {record.rule_count}줄"
    if mine is not None and not is_better:
        line += f" (내 최고 CPU {mine['cpu']} · {mine['ticks']}틱)"
    if mine is not None:
        line += f" · {mine['rank']}위"
    return line
