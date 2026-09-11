"""층 보상 — 무엇을 주고 무엇을 고르게 하는가 (GDD §2.2).

`routes/run.py` 에서 갈라 나왔다. 저쪽은 **제출을 받는 자리**이고 여기는 **그 제출이
무엇을 낳는가**다. 라우트는 얇게 두고 판정은 서비스가 한다는 규율과 같은 선이며
(CLAUDE.md), 파일이 400줄 상한을 넘은 것이 계기였을 뿐이다 (§4).

**여기가 아이템이 세계에 들어오는 유일한 문이다** (결정 #02).
"""

import secrets

from game.api.deps import get_pool
from game.api.loot_service import create_run_drops, list_floor_defeats
from game.api.schemas_reward import RewardOfferView
from game.app.items.loot import compute_run_currency
from game.app.progression.levels import add_run_xp
from game.app.services.verify_run import VerifiedRun
from game.app.store.accounts import find_player_entity
from game.app.store.equipment import add_currency, mark_item_broken, remove_item
from game.app.store.items import list_equipment, list_inventory
from game.app.store.progress import add_player_xp, read_progress, save_leaderboard
from game.app.store.tickets import IssuedTicket
from game.schemas.reward import build_floor_offers

# 판정 결과의 두 값. `routes/run.py` 와 같은 글자여야 한다 — 갈리면 이긴 판이 조용히
# 보상 없이 지나간다.
VERDICT_VERIFIED = "verified"
OUTCOME_WIN = "PLAYER_WIN"


def apply_death_penalty(account_id: int) -> str:
    """사망 손실을 적용한다 (결정 #34).

    **장착·인벤토리를 통틀어 장비 하나만 뽑는다.** 뽑힌 것이 장착 중이었으면 파손되고
    복구비용을 내야 다시 쓰며, 가방에 있었으면 사라진다 — 그 차이가 "좋은 건 끼고
    다녀라" 는 유인을 만든다.

    몬스터가 사본을 가져가는 절반은 아직 없다. 지속 몬스터가 E단계이고, 받을 개체가
    없는 상태에서 사본만 만들면 주인 없는 아이템이 쌓인다.

    Args:
        account_id: 죽은 계정.

    Returns:
        무슨 일이 있었는지. 잃을 것이 없으면 빈 문자열.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    equipped = [(item.item_id, True) for item in list_equipment(pool, entity_id).values()]
    carried = [
        (entry.item.item_id, False)
        for entry in list_inventory(pool, entity_id)
        if entry.item is not None
    ]
    pool_of_items = equipped + carried
    if not pool_of_items:
        return ""
    item_id, was_equipped = pool_of_items[secrets.randbelow(len(pool_of_items))]
    if was_equipped:
        mark_item_broken(pool, entity_id, item_id)
        return f"장착 중이던 장비가 파손됐다 (#{item_id})"
    remove_item(pool, entity_id, item_id)
    return f"가방의 장비를 잃었다 (#{item_id})"


def apply_run_rewards(
    account_id: int,
    submission_id: int,
    verified: VerifiedRun,
    mode: str,
    core_version: str,
    floor: int = 1,
    ticket_id: str = "",
    start_floor: int = 1,
    rooms_per_floor: int = 0,
) -> str:
    """검증된 런의 보상을 준다.

    **여기가 아이템이 세계에 들어오는 유일한 문이다** (결정 #02). 클라이언트는 아이템을
    만들 수 없고, 발급 경로가 서버 하나뿐이라는 것이 시드 파생의 '재현으로 검증' 을
    대신한다.

    Args:
        account_id: 받을 계정.
        submission_id: 이 결과의 제출 id.
        verified: 서버가 확정한 결과.
        mode: 런 모드. 순위표를 가르는 값이다.
        core_version: 이 서버의 코어 버전. 시즌을 가르는 값이다.
        floor: 이 런의 층. 화폐가 이것에 비례한다 — 안 넘기면 깊이 들어가도 1층 값이다.
        ticket_id: 이 런의 티켓. 처치별 굴림이 스냅샷에서 개체 레벨을 찾는다.
        start_floor: 하강이 시작한 층. 이번 층의 처치만 골라내는 데 쓴다.
        rooms_per_floor: 층 하나에 드는 방 수.

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    is_cleared = verified.outcome == OUTCOME_WIN
    add_currency(get_pool(), account_id, compute_run_currency(is_cleared, floor))
    notes = [f"화폐 +{compute_run_currency(is_cleared, floor)}"]
    # **처치마다 굴린다** (설계/4_아이템 §15.3). 런 단위로 굴리면 몬스터 레벨이 개입할
    # 자리가 없다. 재시뮬이 확정한 처치 목록만 쓴다 — 클라이언트 보고로 굴리면 "많이
    # 잡았다" 고 적어 보내는 것이 곧 파밍이 된다.
    notes.extend(
        create_run_drops(
            account_id,
            submission_id,
            list_floor_defeats(verified.room_kinds, start_floor, floor, rooms_per_floor),
            floor,
            ticket_id,
        )
    )
    # 경험치는 **검증된 런에서만** 오른다. 클라이언트 보고로 오르면 순위표가 곧
    # 거짓이 된다 — 순위의 근거가 누적 경험치이기 때문이다.
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    gained = add_run_xp(is_cleared)
    level = add_player_xp(pool, entity_id, gained)
    notes.append(f"경험치 +{gained}")
    progress = read_progress(pool, entity_id)
    save_leaderboard(pool, str(mode), core_version, account_id, progress.total_xp, level)

    if not is_cleared:
        penalty = apply_death_penalty(account_id)
        if penalty:
            notes.append(penalty)
    return " · ".join(notes)


def build_floor_offer(
    ticket: IssuedTicket, claimed: int, verified: VerifiedRun, is_run_closed: bool
) -> tuple[int, list[RewardOfferView]]:
    """이 제출이 열어 주는 보상 후보 (GDD §2.2).

    **깬 층에서만 연다.** 졌으면 고를 자리가 없고, 런이 닫혔으면 고른 것이 붙을 다음 층이
    없다 — 그때 열어 두면 「고르고 나서 아무 일도 안 일어나는」 화면이 된다.

    **이미 고른 층은 다시 안 연다.** 다시 열면 층마다 바꿔 가며 최적을 맞출 수 있고,
    그러면 「그때 무엇을 골랐는가」가 되돌릴 수 있는 설정이 된다.

    Args:
        ticket: 이 제출이 쓰는 티켓.
        claimed: 이번에 확정한 층.
        verified: 서버가 확정한 판정.
        is_run_closed: 이 제출로 런이 닫혔는가.

    Returns:
        (고를 층, 후보들). 고를 것이 없으면 (0, []).
    """
    if claimed <= 0 or is_run_closed or verified.verdict != VERDICT_VERIFIED:
        return 0, []
    if verified.outcome != OUTCOME_WIN or claimed in ticket.rewards:
        return 0, []
    return claimed, [
        RewardOfferView(
            reward_id=option.reward_id,
            label_ko=option.label_ko,
            target_stat=option.target_stat,
            amount=option.amount,
        )
        for option in build_floor_offers(ticket.seed, claimed)
    ]
