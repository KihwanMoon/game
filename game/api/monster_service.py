"""재시뮬 결과가 지속 몬스터와 전리품에 하는 일 (설계/6_몬스터 §3·§4).

`routes/run.py` 에서 갈라 나왔다. 저쪽은 제출을 받아 재시뮬을 부르는 자리이고, 여기는
**그 결과가 세계에 무엇을 하는가** 다 — `floor_service.py` 가 층에 대해 하는 일을
몬스터에 대해 한다. 파일이 400줄 상한을 넘은 것이 계기였지만, 가르는 선은 책임이다 (§4).

**검증된 런에서만 반영한다.** 클라이언트 보고로 몬스터가 크면, 자기 몬스터를 키우려고
일부러 지는 길이 열린다 (T9).
"""

import secrets

from psycopg_pool import ConnectionPool

from game.api.deps import get_pool
from game.api.discovery_service import record_item_discovery
from game.app.bots.doppel import check_is_doppel
from game.app.services.verify_run import VERDICT_VERIFIED, VerifiedRun
from game.app.simulation.plan import OUTCOME_PLAYER_WIN as OUTCOME_WIN
from game.app.store.accounts import find_player_entity
from game.app.store.doppels import apply_doppel_defeat
from game.app.store.items import list_equipment, list_inventory
from game.app.store.monster_snapshots import load_snapshots
from game.app.store.monsters import (
    add_monster_xp,
    apply_monster_defeat,
    find_monster,
)
from game.app.store.tickets import IssuedTicket
from game.app.store.trophies import apply_recovery, create_trophy
from game.schemas.monster_snapshot import MonsterSnapshot


def resolve_home_floor(
    pool: ConnectionPool, snapshot: MonsterSnapshot, ticket: IssuedTicket
) -> int:
    """이 스냅샷 개체가 사는 층을 **개체 기록에서** 읽는다.

    한때 `max(티켓 층, 레벨)` 로 파생했는데, 그것이 **되먹임 고리**를 만들었다 — 레벨이
    층을 올리고, 오른 층이 상한(`층 × 5`)을 올리고, 올라간 상한이 레벨을 더 올린다.
    상한이 영영 안 걸려서 1층 개체가 레벨 12까지 자랐다(검사가 잡았다). 층은 파생할
    것이 아니라 **적혀 있는 것**이며, 적혀 있지 않을 때만 티켓의 층으로 물러선다.

    Args:
        pool: 연결 풀.
        snapshot: 얼려 둔 개체.
        ticket: 이 런의 티켓.

    Returns:
        판정에 쓸 층.
    """
    record = find_monster(pool, snapshot.record_id)
    if record is None or not record.zone_floor:
        return ticket.floor
    return record.zone_floor


def apply_win_to_monsters(
    pool: ConnectionPool,
    ticket: IssuedTicket,
    snapshots: tuple[MonsterSnapshot, ...],
    account_id: int,
) -> str:
    """이긴 런을 반영한다 — 그 층의 지속 몬스터가 감쇠하고, 내 것을 되찾는다.

    졌을 때와 갈라 둔 이유는 복잡도다. 한 함수에 두 갈래를 두면 각 갈래에 조건이 하나
    붙을 때마다 전체가 읽기 어려워진다 (§4).

    Args:
        pool: 연결 풀.
        ticket: 이 런의 티켓.
        snapshots: 얼려 둔 개체들.
        account_id: 플레이어 계정.

    Returns:
        플레이어에게 보여줄 한 줄.
    """
    notes: list[str] = []
    entity_id = find_player_entity(pool, account_id)
    for item in snapshots:
        # **도플갱어는 목숨을 하나 쓴다** (개정 2026-09-04). 지속 몬스터를 안 지우는
        # 이유는 되찾기 동기가 함께 사라지기 때문인데(결정 #35), 이 종은 애초에 아무것도
        # 안 들어 되찾을 것이 없다 — 그 사유가 안 붙는다.
        #
        # 그렇다고 한 번에 지우지도 않는다. 봇들이 쉼 없이 싸우는 세계에서는 그림자가
        # 서자마자 사라져 사람이 만날 새가 없었다. 셋을 두고 **잡을 때마다 감쇠시켜**,
        # 같은 그림자를 세 번 만나되 만날 때마다 약해지게 한다.
        if check_is_doppel(item.kind_id):
            left = apply_doppel_defeat(pool, item.record_id)
            if left == 0:
                notes.append(f"{item.kind_id} 를 끝내 지웠다")
                continue
            if left > 0:
                level = apply_monster_defeat(
                    pool, item.record_id, resolve_home_floor(pool, item, ticket)
                )
                notes.append(f"{item.kind_id} 목숨 {left} 남음 · 레벨 {item.level}→{level}")
                continue
        # **그 개체가 사는 층으로 판정한다.** 티켓의 시작 층을 쓰면 3층에서 잡은
        # 개체가 1층 기준으로 감쇠해 「레벨 1→1」이 된다 (실제 신고).
        level = apply_monster_defeat(pool, item.record_id, resolve_home_floor(pool, item, ticket))
        # **바뀐 것만 적는다.** 하강이 열 층을 돌아 스냅샷이 서른 마리가 되면서,
        # 「레벨 6→6」 서른 줄이 화폐·전리품을 밀어냈다(실제 신고).
        if level != item.level:
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
        # 그 개체가 들고 있던 **내 것**을 되찾는다 (`설계/6_몬스터` §5).
        # **도플갱어에서는 되찾지 않는다.** 그 개체는 애초에 아무것도 들지 않지만, 길을
        # 코드로 막아 둔다 — 데이터가 비어 있는 것과 길이 없는 것은 다르다.
        if check_is_doppel(item.kind_id):
            continue
        for catalog_id in apply_recovery(pool, item.record_id, account_id, entity_id):
            record_item_discovery(account_id, catalog_id)
            notes.append(f"{catalog_id} 되찾음")
    return " · ".join(notes)


def list_fought_snapshots(
    snapshots: tuple[MonsterSnapshot, ...], ticket: IssuedTicket, claimed: int
) -> tuple[MonsterSnapshot, ...]:
    """이 제출이 **실제로 싸운** 층의 개체만 고른다.

    티켓은 하강 전체(1~10층)의 개체를 싣는데, 한 번의 제출은 그중 일부 층만 돈다.
    전부에 반영하면 **1층에서 죽은 판이 9층 몬스터를 키운다** — 실제로 그렇게 돌았다:
    봇이 1층에서 죽을 때마다 `arch_summoner 레벨 6→7`, `longbow_archer 7→8` 이 함께
    찍혔다. 만난 적도 없는 개체가 그 죽음으로 자란 것이다.

    이긴 판의 감쇠도 같다. 1층을 깼다고 9층이 약해지면 안 된다.

    **층을 모르는 스냅샷(0)은 그대로 둔다.** 층을 싣기 전에 발급된 티켓이 그 값이고,
    거기서 빼면 그 티켓의 세계 반영이 통째로 사라진다.

    Args:
        snapshots: 티켓이 얼려 둔 개체 전부.
        ticket: 이 런의 티켓.
        claimed: 이번에 확정한 층. 0 이면 하강 전체다.

    Returns:
        이 제출이 싸운 층의 개체들.
    """
    if claimed <= 0:
        return snapshots
    last = max(claimed, ticket.floor)
    return tuple(
        item
        for item in snapshots
        if item.zone_floor == 0 or ticket.floor <= item.zone_floor <= last
    )


def apply_monster_outcome(
    ticket: IssuedTicket,
    submission_id: int,
    verified: VerifiedRun,
    account_id: int,
    claimed: int = 0,
) -> str:
    """이 런의 결과를 지속 몬스터에 반영한다 (docs/설계/6_몬스터 §3·§4, 결정 #34·#35).

    **검증된 런에서만 반영한다.** 클라이언트가 "내가 졌다" 고 보고해서 몬스터가 크는
    구조면, 자기 몬스터를 키우려고 일부러 지는 어뷰징이 열린다 (T9).

    Args:
        ticket: 이 런의 티켓.
        submission_id: 제출 id.
        verified: 서버가 확정한 결과.
        account_id: 플레이어 계정.
        claimed: 이번에 확정한 층. 0 이면 하강 전체다.

    Returns:
        플레이어에게 보여줄 한 줄. 없으면 빈 문자열.
    """
    if verified.verdict != VERDICT_VERIFIED:
        return ""
    pool = get_pool()
    snapshots = list_fought_snapshots(load_snapshots(pool, ticket.ticket_id), ticket, claimed)
    if not snapshots:
        return ""
    notes: list[str] = []
    if verified.outcome == OUTCOME_WIN:
        return apply_win_to_monsters(pool, ticket, snapshots, account_id)

    # 졌으면 그 층의 몬스터가 경험치를 얻고, 하나가 장비 사본을 가져간다 (결정 #34).
    for item in snapshots:
        level = add_monster_xp(
            pool, item.record_id, resolve_home_floor(pool, item, ticket), "PLAYER", submission_id
        )
        if level > item.level:
            notes.append(f"{item.kind_id} 레벨 {item.level}→{level}")
    # 사본을 가져갈 개체를 고를 때 도플갱어를 건너뛴다. 들면 그 순간 「내 것을 들고 있는
    # 개체」가 되고, 되찾기가 그 위에 길을 낸다 — 봇의 장비가 사람에게 가는 통로다.
    holders = [item for item in snapshots if not check_is_doppel(item.kind_id)]
    taken = apply_trophy_transfer(account_id, find_holder(holders, verified.killer_slot))
    if taken:
        notes.append(taken)
    return " · ".join(notes)


def find_holder(holders: list, killer_slot: str) -> int:
    """전리품을 가져갈 개체를 고른다 — **막타를 친 것**이다 (2026-09-06).

    예전에는 늘 `holders[0]` 였다. 그래서 한 마리에 몰렸고(실측으로 996개), 「저 놈이 내
    걸 들고 있다」가 죽인 놈과 무관해졌다.

    **못 찾으면 아무도 안 가져간다.** 막타가 지속 개체가 아니면(그 방에만 있는 잡몹,
    지형 피해) 가져갈 자격이 있는 개체가 없는 것이다 — 그때 아무나 골라 주면 그 사본이
    어디서 왔는지가 다시 거짓이 된다.

    Args:
        holders: 가져갈 수 있는 개체들. 도플갱어는 이미 빠져 있다.
        killer_slot: 막타를 친 개체의 자리. 모르면 빈 문자열.

    Returns:
        개체 id. 없으면 0.
    """
    if not killer_slot:
        return 0
    return next(
        (item.record_id for item in holders if item.entity_id == killer_slot),
        0,
    )


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
    # **안 가져갈 수도 있다** (2026-09-06). 다섯이 차 있고 더 강해지지도 않으면 그냥
    # 지나간다 — 그때 「빼앗겼다」고 적으면 화면이 거짓말을 한다.
    took = create_trophy(
        pool,
        record_id,
        picked.catalog_id,
        [
            {"stat": a.stat, "flat": a.flat, "percent": a.percent, "label_ko": a.label_ko}
            for a in picked.affixes
        ],
        account_id,
    )
    return f"{picked.catalog_id} 를 빼앗겼다" if took else ""
