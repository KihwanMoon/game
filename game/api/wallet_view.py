"""지갑 한 벌을 읽는다 — 푼과 활자를 함께 낸다 (신설 2026-09-15).

**둘은 언제나 같이 읽힌다.** 가방 화면이 「이것을 열 수 있는가」와 「이것을 다시 찍을 수
있는가」를 함께 묻기 때문이다. 따로 내면 화면이 요청을 둘 보내야 하고, 둘 사이에 값이
어긋나는 창이 생긴다.

라우트가 아니라 여기 있는 이유는 **셋이 부르기 때문이다** — 지갑 조회·복구·봉인. 라우트
하나에 두고 다른 라우트가 그것을 임포트하면 의존이 옆으로 흐른다 (§12).
"""

from psycopg_pool import ConnectionPool

from game.api.schemas_item import WalletResponse
from game.app.items.sealed import RECAST_COST
from game.app.store.equipment import REPAIR_COST, read_balance
from game.app.store.letters import read_letters


def build_wallet(pool: ConnectionPool, account_id: int) -> WalletResponse:
    """지갑을 읽어 응답을 만든다.

    Args:
        pool: 연결 풀.
        account_id: 계정 id.

    Returns:
        잔액·활자와 값들.
    """
    return WalletResponse(
        balance=read_balance(pool, account_id),
        repair_cost=REPAIR_COST,
        letters=read_letters(pool, account_id),
        recast_cost=RECAST_COST,
    )
