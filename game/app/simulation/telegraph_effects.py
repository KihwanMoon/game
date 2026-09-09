"""예고가 터질 때 대상에게 얹는 것 (설계/5_스킬 §1).

`telegraph.py` 에서 갈라 나왔다. 저쪽은 **언제 터지는가**이고 이쪽은 **터졌을 때 피해
말고 무엇이 남는가**다. 400줄 상한이 계기였지만 가르는 선은 책임이다 (§4).

**평면 필드를 대신하지 않는다.** `coef_pct`·`heal_pct`·`guard_pct` 의 뜻은 그대로이고
여기 있는 것은 덧붙이기다 — 거기서 파생시키려던 설계가 반증에서 세 번 깨졌다:
`coef_pct: 0` 의 뜻이 단계마다 바뀌고, `find_skill` 의 폴백 계약이 뒤집히고, 전제
검사가 early return 이라 `[GUARD, DAMAGE]` 가 적 없을 때 보호막까지 안 걸렸다.

**붙는 시점이 발동이라는 것이 그 셋을 한꺼번에 없앤다.** 그때는 누가 그 칸에 섰는지
이미 정해져 있어 「대상이 없어서 못 걸었다」가 생기지 않는다.
"""

from typing import Protocol

from game.app.core.event_log import EventLog
from game.app.simulation.state import Entity, WorldState
from game.app.simulation.telegraph_record import Telegraph
from game.app.skills.catalog import EFFECT_STATUS


class BlastRecorder(Protocol):
    """로그를 남기는 쪽. 예고판이 이것을 만족한다.

    **판이 쓰는 기록기를 그대로 쓴다.** 사본을 두면 같은 발동이 두 모양으로 적힌다.
    """

    def record_blast(
        self,
        state: WorldState,
        log: EventLog,
        telegraph: Telegraph,
        expr: str,
        outcome: str,
        delta: int | None,
        target_id: str | None = None,
    ) -> None:
        """한 줄 남긴다."""
        ...


def apply_blast_effects(
    board: BlastRecorder,
    state: WorldState,
    log: EventLog,
    telegraph: Telegraph,
    victim: Entity,
) -> None:
    """맞은 대상에게 스킬의 효과를 얹는다.

    **피해와 별개다.** 피해 0 인 장판이 상태만 거는 것이 이 자리이고, 그것이 평면
    필드로는 못 적는 것이었다 — 「피해를 주면서 둔화도 건다」도 여기서 성립한다.

    **진영을 안 가린다.** 피해와 같은 규칙이다 — 예고는 좌표에 떨어지므로 시전자의
    아군도 맞고, 그래야 통로로 유인하는 전술이 성립한다 (GDD §4.3).

    Args:
        board: 로그를 남길 예고판.
        state: 세계 상태.
        log: 이벤트 로그.
        telegraph: 발동한 예고.
        victim: 맞은 대상.
    """
    for effect in telegraph.effects:
        if effect.kind != EFFECT_STATUS or not effect.status:
            continue
        # 더 긴 쪽을 남긴다. 겹칠 때 짧은 것으로 덮으면 뒤에 온 약한 장판이 앞의
        # 강한 것을 지운다.
        before = victim.statuses.get(effect.status, 0)
        victim.statuses[effect.status] = max(before, effect.duration)
        board.record_blast(
            state,
            log,
            telegraph,
            f"{telegraph.skill_id} {effect.status}",
            f"{victim.entity_id} {effect.status} {effect.duration}틱",
            None,
            victim.entity_id,
        )
