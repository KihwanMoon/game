"""세계 현황 조회 — 관리자가 무엇이 벌어지는지 보는 창.

**읽기만 한다.** 이 모듈에는 쓰기가 없다. 개입은 별도 경로에서만 하고 반드시 원장에
남는다(`store/admin.py`).

지금까지 세계 상태를 볼 방법이 아예 없었다. 지속 몬스터가 몇이고 누가 남의 장비를 들고
있는지, 푼이 얼마나 풀렸는지 확인하려면 매번 임시 스크립트를 써야 했다 — 그 상태로는
"세계가 건강한가" 를 아무도 답할 수 없다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.app.store.display_name import build_display_name_sql
from game.app.store.traffic import compute_conversion_pct, read_traffic_window


@dataclass(frozen=True)
class WorldSummary:
    """세계 한눈에 보기."""

    accounts: int
    registered: int
    entities: int
    monsters_alive: int
    items: int
    items_bound: int
    items_held_by_monsters: int
    listings_open: int
    currency_total: int
    verified_runs: int


@dataclass(frozen=True)
class MonsterRow:
    """지속 몬스터 한 줄 — 보유 아이템 수를 함께 센다.

    엘리트가 남의 장비를 들고 있는 것이 World Loop 의 동기이므로(`설계/6_몬스터` §5),
    그것을 세지 않으면 이 표가 세계를 설명하지 못한다.
    """

    record_id: int
    entity_id: int
    catalog_id: str
    tier: str
    zone_floor: int
    entity_slot: str
    level: int
    total_xp: int
    alive: bool
    held_items: int


def read_world_summary(pool: ConnectionPool) -> WorldSummary:
    """세계 요약을 한 번에 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        요약 값들.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT"
            # **활성 계정만 센다.** 비활성이 섞이면 "사람이 몇인가" 가 거짓이 되고,
            # 그 숫자로 밸런스를 판단하게 된다.
            " (SELECT count(*) FROM account WHERE deactivated_at IS NULL),"
            " (SELECT count(*) FROM account"
            "    WHERE login_id IS NOT NULL AND deactivated_at IS NULL),"
            " (SELECT count(*) FROM entity_record),"
            " (SELECT count(*) FROM entity_record WHERE kind = 'MONSTER' AND alive),"
            " (SELECT count(*) FROM item_instance),"
            " (SELECT count(*) FROM item_instance WHERE is_bound),"
            " (SELECT count(*) FROM item_instance i JOIN entity_record e"
            "    ON e.id = i.owner_entity_id WHERE e.kind = 'MONSTER'),"
            " (SELECT count(*) FROM auction_listing WHERE state = 'OPEN'),"
            " (SELECT coalesce(sum(balance), 0) FROM wallet),"
            " (SELECT count(*) FROM run_result WHERE verdict = 'verified')"
        ).fetchone()
    values = [int(item) for item in (row or [0] * 10)]
    return WorldSummary(*values)


def list_world_monsters(pool: ConnectionPool, limit: int = 200) -> tuple[MonsterRow, ...]:
    """지속 몬스터를 층·레벨 순으로 읽는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수.

    Returns:
        층 오름차순, 같은 층에서는 레벨 내림차순.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT e.id, e.id, e.catalog_id, e.tier, e.zone_floor, e.entity_slot,"
            " e.level, e.total_xp, e.alive,"
            " (SELECT count(*) FROM item_instance i WHERE i.owner_entity_id = e.id)"
            " FROM entity_record e WHERE e.kind = 'MONSTER'"
            " ORDER BY e.zone_floor ASC, e.level DESC, e.id ASC LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        MonsterRow(
            record_id=int(row[0]),
            entity_id=int(row[1]),
            catalog_id=str(row[2]),
            tier=str(row[3]),
            zone_floor=int(row[4]),
            entity_slot=str(row[5]),
            level=int(row[6]),
            total_xp=int(row[7]),
            alive=bool(row[8]),
            held_items=int(row[9]),
        )
        for row in rows
    )


@dataclass(frozen=True)
class HeldItemRow:
    """몬스터가 들고 있는 아이템 한 줄.

    **누구에게서 빼앗았는지 함께 본다.** 되찾으러 갈 동기가 World Loop 의 전부이므로
    (`설계/6_몬스터` §5), 원주인을 모르면 이 표가 무엇을 설명하는지 알 수 없다.
    """

    item_id: int
    record_id: int
    monster_id: str
    catalog_id: str
    taken_from_handle: str
    is_broken: bool
    is_bound: bool


def list_held_items(pool: ConnectionPool, limit: int = 200) -> tuple[HeldItemRow, ...]:
    """몬스터가 들고 있는 아이템을 전부 읽는다.

    Args:
        pool: 연결 풀.
        limit: 최대 줄 수.

    Returns:
        개체·아이템 순으로 정렬된 줄들.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT i.id, e.id, e.catalog_id, i.catalog_id,"
            # **이름은 정본을 거친다** (`display_name.py`). 손잡이를 그대로 내면
            # 닉네임을 지은 사람이 화면마다 다른 이름으로 보인다 (2026-09-18 신고).
            f" coalesce({build_display_name_sql('a')}, ''), i.is_broken, i.is_bound"
            " FROM item_instance i"
            " JOIN entity_record e ON e.id = i.owner_entity_id"
            " LEFT JOIN account a ON a.id = i.taken_from"
            " WHERE e.kind = 'MONSTER'"
            " ORDER BY e.id ASC, i.id ASC LIMIT %s",
            (limit,),
        ).fetchall()
    return tuple(
        HeldItemRow(
            item_id=int(row[0]),
            record_id=int(row[1]),
            monster_id=str(row[2]),
            catalog_id=str(row[3]),
            taken_from_handle=str(row[4]),
            is_broken=bool(row[5]),
            is_bound=bool(row[6]),
        )
        for row in rows
    )


def count_levels(pool: ConnectionPool) -> tuple[tuple[int, int], ...]:
    """플레이어 레벨 분포를 센다.

    **분포가 없으면 레벨 곡선을 튜닝할 수 없다** — 평균만 보면 한 사람이 멀리 간 것과
    모두가 조금씩 온 것을 구분하지 못한다.

    Args:
        pool: 연결 풀.

    Returns:
        (레벨, 인원) 쌍들. 레벨 오름차순.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            # 비활성 계정의 개체는 분포에서 뺀다 — 검사가 만든 레벨 1 수십 개가
            # 곡선의 앞머리를 눌러 "다들 초반에 멈춘다" 로 읽힌다.
            "SELECT e.level, count(*) FROM entity_record e"
            " JOIN account a ON a.id = e.owner_account_id"
            " WHERE e.kind = 'PLAYER' AND a.deactivated_at IS NULL"
            " GROUP BY e.level ORDER BY e.level ASC"
        ).fetchall()
    return tuple((int(row[0]), int(row[1])) for row in rows)


@dataclass(frozen=True)
class WorldPulse:
    """세계에 사람이 얼마나 오는가 (2026-09-17, 2026-09-18 개정).

    **두 수가 다른 것을 센다.** `players` 는 **출격을 누른 사람**이다 — `App.tsx` 의
    `requireAccount` 가 "여는 것만으로는 안 만든다" 고 못박고 있어서, 계정 행은 앱을 연
    순간이 아니라 판을 남기려는 순간에 생긴다. `window_visits` 는 **열어 본 사람**이고
    Cloudflare 가 엣지에서 센 것을 `traffic_day` 로 받아 적은 값이다.

    **옛 주석이 틀렸었다.** 여기에는 "처음 들어오면 익명 계정이 생기므로 account 수가 곧
    「앱을 연 사람 수」에 가깝다" 고 적혀 있었는데, 그 전제가 코드와 어긋났다. 그래서
    「다녀간 사람」이라는 이름으로 판을 낸 사람을 세고 있었고, 진짜 방문자는 아무도 재지
    않고 있었다.

    **봇을 뺀다.** 봇 계정도 `account` 행이라 그동안 「다녀간 사람」에 섞여 있었다
    (10/138 = 7%). `is_bot` 컬럼으로 가른다 — 이름 접두어는 화면에 싣는 표시이고 이쪽이
    사실이다.

    **누적과 창을 함께 든다.** 누적 절대값은 계측을 갈아 끼우는 순간 점프해 예전 값과
    이어 붙일 수 없으므로, 화면이 기간을 밝힐 수 있어야 한다.
    """

    visitors: int
    joined: int
    fresh_today: int
    fresh_week: int
    runs: int
    window_days: int = 0
    window_visits: int = 0
    window_played: int = 0
    conversion_pct: int = 0
    traffic_source: str = ""


def read_world_pulse(pool: ConnectionPool, window_days: int = 7) -> WorldPulse:
    """세계의 접속 현황을 읽는다.

    **한 문장으로 센다.** 다섯 번 왕복하면 화면 한 줄에 조회가 다섯 번 붙는다.
    트래픽은 다른 표에 있어 한 번 더 간다.

    Args:
        pool: 연결 풀.
        window_days: 들름·전환을 볼 창(일). 오늘을 포함한다.

    Returns:
        누적 수치와 창 안의 깔때기. 계측을 아직 안 받아 왔으면 창 값이 0 이며,
        그것과 「아무도 안 왔다」는 `window_visits` 로 구별한다.
    """
    with pool.connection() as connection:
        row = connection.execute(
            "SELECT count(*),"
            " count(*) FILTER (WHERE login_id IS NOT NULL),"
            " count(*) FILTER (WHERE created_at::date = current_date),"
            " count(*) FILTER (WHERE created_at > now() - interval '7 days'),"
            " (SELECT count(*) FROM run_submission),"
            " count(*) FILTER (WHERE created_at > now() - make_interval(days => %s))"
            " FROM account"
            # **컬럼으로 가른다.** 이름 접두어(`bot_`)는 화면에 봇임을 싣는 **표시**
            # 채널이고, `is_bot` 이 사실이다. 관리자가 봇 이름을 고칠 수 있게 된 뒤로
            # (U3) 이름으로 세면 개명 한 번에 수가 틀어진다.
            " WHERE deactivated_at IS NULL AND NOT is_bot",
            (window_days,),
        ).fetchone()
    if row is None:
        return WorldPulse(visitors=0, joined=0, fresh_today=0, fresh_week=0, runs=0)
    window = read_traffic_window(pool, window_days)
    played = int(row[5])
    return WorldPulse(
        visitors=int(row[0]),
        joined=int(row[1]),
        fresh_today=int(row[2]),
        fresh_week=int(row[3]),
        runs=int(row[4]),
        window_days=window_days,
        window_visits=window.visits,
        window_played=played,
        conversion_pct=compute_conversion_pct(window.visits, played),
        traffic_source=window.source,
    )
