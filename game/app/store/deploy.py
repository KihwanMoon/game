"""배포봇이 읽는 것 (설계/9_에이전트_운영 §4.5).

**게이트가 안 보는 것만 읽는다.** `check_all.sh` 와 두 스위트는 코드가 맞는지를 보지,
**지금 세계가 배포를 받을 수 있는 상태인지**는 안 본다. 그 다섯을 여기서 읽는다.

**질의만 한다.** 판정은 `app/deploy/briefing.py` 가 하고, 그것은 순수 함수라 DB 없이
검사할 수 있다 — 지킴이와 같은 규율이다(§4.1).

**여기서 아무것도 안 고친다.** 배포봇의 검토 권한은 `observer` 다 (§3.1).
"""

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from game.app.store.content_pack import read_pack_generation
from game.app.store.item_catalog import read_generation


@dataclass(frozen=True)
class DraftRow:
    """나갈 것 하나 — **누가 만들었는지 함께 든다**.

    에이전트가 올린 것과 사람이 올린 것을 컨펌 화면에서 못 가르면, 검토한다는 것이
    무엇을 보는 일인지 흐려진다 (§4.5 컨펌에 올리는 것 둘째).
    """

    kind: str
    name: str
    note: str
    handle: str


@dataclass(frozen=True)
class DeployReading:
    """한 번 훑어서 읽은, 배포를 앞둔 세계.

    **판정이 아니라 값이다.** 「올려도 되는가」는 `briefing.py` 가 말한다.
    """

    # 지금 돌고 있는 판. 발행이 이것을 전부 무효로 만든다 (§3.3).
    open_runs: int
    # 나갈 콘텐츠 초안과 아이템 초안. 둘을 갈라 두는 이유는 **반영 경로가 다르기**
    # 때문이다 — 콘텐츠는 파일화까지 해야 맞춰지고(경로 1+2), 아이템은 DB 하나다.
    content_drafts: tuple[DraftRow, ...]
    catalog_drafts: tuple[DraftRow, ...]
    # 지금 세대들. 발행하면 이 값이 움직이고, 그 순간 순위표 시즌이 갈린다.
    pack_generation: int
    item_generation: int
    # DB 가 들고 있는 발행본과 저장소 파일이 갈라진 자산. **여기가 비어야 폴백이 성하다** —
    # 발행만 하고 파일화를 안 하면 브라우저의 오프라인 폴백이 다른 게임을 돈다 (§4.5).
    drifted_assets: tuple[str, ...]


def list_content_drafts(pool: ConnectionPool) -> tuple[DraftRow, ...]:
    """나갈 콘텐츠 초안을 읽는다.

    Args:
        pool: 연결 풀.

    Returns:
        초안들. 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT d.asset, d.note, COALESCE(a.handle, '')"
            " FROM content_draft d LEFT JOIN account a ON a.id = d.updated_by"
            " ORDER BY d.asset"
        ).fetchall()
    return tuple(
        DraftRow(kind="content", name=str(row[0]), note=str(row[1]), handle=str(row[2]))
        for row in rows
    )


def list_catalog_drafts_for_deploy(pool: ConnectionPool) -> tuple[DraftRow, ...]:
    """나갈 아이템 초안을 읽는다.

    `store/catalog_draft.py` 와 갈라 둔 이유는 **보는 각도가 다르기 때문이다** — 저쪽은
    편집 화면이 쓰고 지금 성립하는지를 함께 보며, 이쪽은 「무엇이 나가는가」만 본다.

    Args:
        pool: 연결 풀.

    Returns:
        초안들. 없으면 빈 튜플.
    """
    with pool.connection() as connection:
        rows = connection.execute(
            "SELECT d.catalog_id, d.action, d.reason, COALESCE(a.handle, '')"
            " FROM catalog_draft d LEFT JOIN account a ON a.id = d.updated_by"
            " ORDER BY d.updated_at, d.catalog_id"
        ).fetchall()
    return tuple(
        DraftRow(
            kind="catalog",
            name=f"{row[1]} {row[0]}",
            note=str(row[2]),
            handle=str(row[3]),
        )
        for row in rows
    )


def list_drifted_assets(pool: ConnectionPool, files: dict[str, dict]) -> tuple[str, ...]:
    """DB 의 발행본과 저장소 파일이 갈라진 자산을 고른다.

    **발행은 DB 를 바꾸고 파일은 안 바꾼다.** 파일화는 `scripts/publish_content.py` 가
    따로 하고 그것을 커밋·배포해야 맞춰진다 — 즉 콘텐츠 한 번 바꾸는 데 배포가 두 번이고,
    그 사이에 드리프트가 산다. 갈라진 채로 두면 **브라우저의 오프라인 폴백이 다른 게임을
    돈다** (§4.5).

    Args:
        pool: 연결 풀.
        files: 자산 이름에서 저장소 파일 절로의 대응표.

    Returns:
        갈라진 자산 이름들. 정렬돼 있다.
    """
    with pool.connection() as connection:
        rows = connection.execute("SELECT asset, payload FROM content_published").fetchall()
    drifted = [
        str(row[0]) for row in rows if str(row[0]) in files and dict(row[1]) != files[str(row[0])]
    ]
    return tuple(sorted(drifted))


def read_deploy_state(pool: ConnectionPool, files: dict[str, dict]) -> DeployReading:
    """배포를 앞둔 세계를 훑는다.

    **세대는 정본 함수로 읽는다.** 여기서 SQL 을 다시 쓰면 표 이름이 바뀌었을 때
    배포봇만 옛 자리를 보고, 그러면 「시즌이 갈리나」에 조용히 틀린 답이 나온다 —
    지킴이가 한 연결을 고집한 것과는 다른 판단이다. 저쪽은 지표들이 서로 맞아야 했고,
    이쪽은 정본이 하나여야 한다.

    Args:
        pool: 연결 풀.
        files: 자산 이름에서 저장소 파일 절로의 대응표. 드리프트를 보는 데 쓴다.

    Returns:
        읽은 값들.
    """
    with pool.connection() as connection:
        runs = connection.execute(
            "SELECT count(*) FROM run_ticket WHERE consumed_at IS NULL AND expires_at > now()"
        ).fetchone()
    return DeployReading(
        open_runs=int(runs[0]) if runs else 0,
        content_drafts=list_content_drafts(pool),
        catalog_drafts=list_catalog_drafts_for_deploy(pool),
        pack_generation=read_pack_generation(pool),
        item_generation=read_generation(pool),
        drifted_assets=list_drifted_assets(pool, files),
    )
