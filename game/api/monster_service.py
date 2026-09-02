"""재시뮬 결과가 지속 몬스터와 전리품에 하는 일 (설계/6_몬스터 §3·§4).

`routes/run.py` 에서 갈라 나왔다. 저쪽은 제출을 받아 재시뮬을 부르는 자리이고, 여기는
**그 결과가 세계에 무엇을 하는가** 다 — `floor_service.py` 가 층에 대해 하는 일을
몬스터에 대해 한다. 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는 선은 책임이다 (§4).

**검증된 런에서만 반영한다.** 클라이언트 보고로 몬스터가 크면, 자기 몬스터를 키우려고
일부러 지는 길이 열린다 (T9).
"""

import secrets

from game.api.deps import get_pool
from game.api.discovery_service import record_item_discovery
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN as OUTCOME_WIN
from game.app.store.accounts import find_player_entity
from game.app.store.items import list_equipment, list_inventory
from game.app.store.monsters import add_monster_xp, apply_monster_defeat, load_snapshots
from game.app.store.tickets import IssuedTicket
from game.app.store.trophies import apply_recovery, create_trophy
from game.schemas.monster_snapshot import MonsterSnapshot


def resolve_home_floor(snapshot: MonsterSnapshot, ticket: IssuedTicket) -> int:
    """이 스냅샷 개체가 사는 층.

    **스냅샷이 제 층을 안 싣는다.** 지금은 티켓의 시작 층에서 파생할 수밖에 없는데,
    레벨이 곧 층이라는 규약(난이도 개편)을 역으로 쓰면 정확하다 — 층 = 레벨로 태어나고
    감쇠도 층 아래로 안 내려가므로, 레벨이 그 개체의 층 하한이다.

    Args:
        snapshot: 얼려 둔 개체.
        ticket: 이 런의 티켓.

    Returns:
        판정에 쓸 층.
    """
    return max(ticket.floor, snapshot.level)


def apply_monster_outcome(
    ticket: IssuedTicket, submission_id: int, verified: VerifiedRun, account_id: int
) -> str:
    """이 런의 결과를 지속 몬스터에 반영한다 (docs/설계/6_몬스터 §3·§4, 결정 #34·#35).

    **검증된 런에서만 반영한다.** 클라이언트가 "내가 졌다" 고 보고해서 몬스터가 크는
    구조면, 자기 몬스터를 키우려고 일부러 지는 어뷰징이 열린다 (T9).

    Args:
        ticket: 이 런의 티켓.
        submission_id: 제출 id.
        verified: 서버가 확정한 결과.
        account_id: 플레이어 계정.

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    pool = get_pool()
    snapshots = load_snapshots(pool, ticket.ticket_id)
    if not snapshots:
        return ""
    notes: list[str] = []
    if verified.outcome == OUTCOME_WIN:
        # 이겼으면 그 층의 지속 몬스터가 전부 감쇠한다 — 플레이어의 승리가 세계에
        # 흔적을 남긴다 (결정 #35).
        entity_id = find_player_entity(pool, account_id)
        for item in snapshots:
            # **그 개체가 사는 층으로 판정한다.** 티켓의 시작 층을 쓰면 3층에서 잡은
            # 개체가 1층 기준으로 감쇠해 「레벨 1→1」이 된다 (실제 신고).
            level = apply_monster_defeat(pool, item.record_id, resolve_home_floor(item, ticket))
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
            # 그 개체가 들고 있던 **내 것**을 되찾는다 (`설계/6_몬스터` §5). 도감이
            # "내 아이템을 들고 있다" 고 말해 놓고 잡아도 못 돌려받으면, World Loop 의
            # 동기가 화면에만 있고 세계에는 없다.
            for catalog_id in apply_recovery(pool, item.record_id, account_id, entity_id):
                record_item_discovery(account_id, catalog_id)
                notes.append(f"{catalog_id} 되찾음")
        return " · ".join(notes)

    # 졌으면 그 층의 몬스터가 경험치를 얻고, 하나가 장비 사본을 가져간다 (결정 #34).
    for item in snapshots:
        level = add_monster_xp(
            pool, item.record_id, resolve_home_floor(item, ticket), "PLAYER", submission_id
        )
        if level > item.level:
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
    taken = apply_trophy_transfer(account_id, snapshots[0].record_id)
    if taken:
        notes.append(taken)
    return " · ".join(notes)


def apply_trophy_transfer(account_id: int, record_id: int) -> str:
    """뽑힌 장비의 **사본**을 몬스터에게 넘긴다 (결정 #34).

    원본은 `apply_death_penalty` 가 처리한다 — 장착 중이었으면 파손, 가방이었으면 삭제.
    사본이라 아이템 총량이 늘지만, 몬스터의 것은 거래 대상이 아니므로 경제에 흘러들지
    않는다. 도감이 "내 아이템을 들고 있다" 를 말할 수 있게 하는 것이 이 사본의 목적이다.

    Args:
        account_id: 죽은 계정.
        record_id: 가져갈 몬스터.

    Returns:
        무슨 일이 있었는지. 가져갈 것이 없으면 빈 문자열.
    """
    pool = get_pool()
    entity_id = find_player_entity(pool, account_id)
    equipped = list(list_equipment(pool, entity_id).values())
    carried = [entry.item for entry in list_inventory(pool, entity_id) if entry.item is not None]
    candidates = equipped + carried
    if not candidates:
        return ""
    picked = candidates[secrets.randbelow(len(candidates))]
    create_trophy(
        pool,
        record_id,
        picked.catalog_id,
        [
            {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
            for a in picked.affixes
        ],
        account_id,
    )
    return f"{picked.catalog_id} 를 빼앗겼다"
