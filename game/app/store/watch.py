"""세계 지킴이가 읽는 것 (설계/9_에이전트_운영 §4.1).

**질의만 한다.** 판정은 `app/watch/checks.py` 가 하고, 그것은 순수 함수라 DB 없이
검사할 수 있다 — 임계값이 바뀔 때 고치는 자리와 읽는 자리가 갈려 있어야 한다.

**여기서 아무것도 안 고친다.** 지킴이는 읽기만 하는 계정으로 돈다; 쓰기 질의를 여기
두면 그 규율이 코드에서 사라진다.

무엇을 재는지는 상상이 아니라 실측에서 나왔다 — 2026-09-04~05 에 손으로 찾은 결함
아홉 건이 명세다. 각 질의 위에 그것이 무엇을 잡았을지 적어 뒀다.
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool


@dataclass(frozen=True)
class WorldReading:
    """한 번 훑어서 읽은 세계의 상태.

    **판정이 아니라 값이다.** 「이상하다」는 `checks.py` 가 말한다.
    """

    # 최고 층이 도달 기록보다 **한 칸 넘게** 뒤진 계정 수. 둘은 한 칸 어긋난 두 값이라
    # (「갈 수 있는 층」과 「깬 층」) 차이 1 은 정상이다. 최근에 논 계정만 센다.
    floor_behind: int
    floor_total: int
    # 지금 선 그림자 수와, 가장 최근 것이 선 지 몇 시간 됐는가.
    doppels: int
    doppel_age_hours: int
    # 그림자들이 선 층의 최저·최고. 둘이 같으면 순위표가 한 깊이에 굳은 것이다.
    doppel_floor_min: int
    doppel_floor_max: int
    # 가방이 가득 찬 봇 수.
    bots_full_bag: int
    bots_total: int
    # 차례가 지났는데 한참 안 돈 봇 수. 러너가 죽으면 여기서 드러난다.
    bots_overdue: int
    # 소모품 칸이 전부 빈 채로 남은 사람 계정 수. 정비가 할 일을 남겨 뒀다는 뜻이다.
    people_dry_slots: int
    people_with_rules: int
    # 최근 판정 중 불일치 비율(퍼센트)과 그 표본 수.
    mismatch_pct: int
    verdict_total: int
    # 봇이 볼 수 있게 된 지 오래인데 안 팔린 매물 수.
    stale_listings: int
    open_listings: int
    # 안 나간 콘텐츠 초안 수. 에이전트가 붙으면 여기가 쌓인다.
    drafts: int


def read_world(pool: ConnectionPool, window_hours: int, first_look_hours: int) -> WorldReading:
    """세계를 한 번 훑는다.

    **한 연결로 다 읽는다.** 지표마다 연결을 새로 열면 훑는 사이에 세계가 움직여서,
    서로 안 맞는 숫자들이 한 보고서에 실린다.

    Args:
        pool: 연결 풀.
        window_hours: 최근 얼마를 볼 것인가. 판정·매물이 이 창을 쓴다.
        first_look_hours: 봇이 매물을 볼 수 있게 되기까지의 시간. 그보다 오래 안 팔린
            매물이 「안 팔리는 매물」이다.

    Returns:
        읽은 값들.
    """
    with pool.connection() as connection:
        # 「최고 층이 1 에서 안 움직임」을 잡았을 질의다. 도달 기록은 7 인데 메타
        # 세이브는 1 이었고, 층 보너스 규칙 슬롯이 아무에게도 안 붙고 있었다.
        #
        # **한 칸을 뺀다.** `reached_floor` 는 「갈 수 있는 층」이라 깬 층 + 1 이고
        # (`apply_floor_progress`), `best_floor` 는 「깬 층」이다 — 차이 1 은 정상이다.
        # 이 지킴이가 첫 실행에서 자기 임계값의 오류로 잡아낸 자리다.
        #
        # **최근에 논 계정만 본다.** 오래 안 온 계정은 옛 기록만 갖고 있어서 영영 안
        # 맞춰지고, 그것을 계속 알리면 알림이 시끄러워져 사유 대신 숫자를 올리게 된다.
        floor = connection.execute(
            "SELECT count(*) FILTER ("
            "  WHERE COALESCE((m.payload->>'best_floor')::int, 0) < e.reached_floor - 1),"
            " count(*)"
            " FROM entity_record e"
            " LEFT JOIN meta_save m ON m.account_id = e.owner_account_id"
            " WHERE e.kind = 'PLAYER' AND NOT e.is_doppel AND e.reached_floor > 1"
            "   AND e.updated_at > now() - make_interval(hours => %s)",
            (window_hours,),
        ).fetchone()

        # 「도플갱어 자리 다섯이 하루 만에 굳음」을 잡았을 질의다. 최신 그림자가 선 지
        # 이틀이 넘었고, 다섯이 전부 최저 층에 서 있었다.
        doppel = connection.execute(
            "SELECT count(*),"
            " COALESCE(EXTRACT(EPOCH FROM (now() - max(created_at))) / 3600, 0)::int,"
            " COALESCE(min(zone_floor), 0), COALESCE(max(zone_floor), 0)"
            " FROM entity_record WHERE kind = 'MONSTER' AND is_doppel AND alive"
        ).fetchone()

        # 「봇 가방이 17~19/20 로 고착」을 잡았을 질의다. 그 포화가 갈아 끼우기를 막고,
        # 그것이 다시 `/api/run` 500 의 조건이 됐다.
        bots = connection.execute(
            "SELECT count(*) FILTER (WHERE used >= 18), count(*),"
            " count(*) FILTER (WHERE b.next_run_at <"
            "   now() - make_interval(secs => b.cadence_sec * 4))"
            " FROM bot_profile b"
            " JOIN entity_record e ON e.owner_account_id = b.account_id"
            "   AND e.kind = 'PLAYER' AND NOT e.is_doppel"
            " CROSS JOIN LATERAL ("
            "   SELECT count(*) AS used FROM inventory_slot i WHERE i.entity_id = e.id) AS bag"
        ).fetchone()

        # 「정비가 사람에게 한 번도 안 돎」을 잡았을 질의다. 규칙을 세워 둔 계정의
        # 소모품 칸이 전부 0 충전인 채로 남아 있었다 — 잔액은 13만이었다.
        people = connection.execute(
            "SELECT count(*) FILTER (WHERE dry), count(*)"
            " FROM maintenance_rule r"
            " JOIN account a ON a.id = r.account_id AND NOT a.is_bot"
            " JOIN entity_record e ON e.owner_account_id = r.account_id"
            "   AND e.kind = 'PLAYER' AND NOT e.is_doppel"
            " CROSS JOIN LATERAL ("
            "   SELECT count(*) > 0 AND count(*) FILTER (WHERE charges > 0) = 0 AS dry"
            "   FROM consumable_slot c"
            "   WHERE c.entity_id = e.id AND c.catalog_id <> '') AS slots"
        ).fetchone()

        # 불일치는 변조·버전 시차·우리 버그 셋이 섞인다 (결정 #47). 비율만 보고,
        # 원인은 사람이 가른다.
        verdict = connection.execute(
            "SELECT count(*) FILTER (WHERE verdict = 'mismatch'), count(*)"
            " FROM run_result r"
            " JOIN run_submission s ON s.id = r.submission_id"
            " WHERE s.submitted_at > now() - make_interval(hours => %s)",
            (window_hours,),
        ).fetchone()

        # 「봇이 무기를 영영 안 삼」을 잡았을 질의다. 우선권 창이 지났는데도 안 팔린
        # 매물이 쌓이면, 안 사는 이유가 시간이 아니라 규칙에 있다.
        auction = connection.execute(
            "SELECT count(*) FILTER ("
            "  WHERE listed_at < now() - make_interval(hours => %s)), count(*)"
            " FROM auction_listing WHERE state = 'OPEN'",
            (first_look_hours,),
        ).fetchone()

        drafts = connection.execute("SELECT count(*) FROM content_draft").fetchone()

    return WorldReading(
        floor_behind=int(floor[0] or 0) if floor else 0,
        floor_total=int(floor[1] or 0) if floor else 0,
        doppels=int(doppel[0] or 0) if doppel else 0,
        doppel_age_hours=int(doppel[1] or 0) if doppel else 0,
        doppel_floor_min=int(doppel[2] or 0) if doppel else 0,
        doppel_floor_max=int(doppel[3] or 0) if doppel else 0,
        bots_full_bag=int(bots[0] or 0) if bots else 0,
        bots_total=int(bots[1] or 0) if bots else 0,
        bots_overdue=int(bots[2] or 0) if bots else 0,
        people_dry_slots=int(people[0] or 0) if people else 0,
        people_with_rules=int(people[1] or 0) if people else 0,
        mismatch_pct=(
            int(verdict[0] or 0) * 100 // int(verdict[1]) if verdict and verdict[1] else 0
        ),
        verdict_total=int(verdict[1] or 0) if verdict else 0,
        stale_listings=int(auction[0] or 0) if auction else 0,
        open_listings=int(auction[1] or 0) if auction else 0,
        drafts=int(drafts[0] or 0) if drafts else 0,
    )
