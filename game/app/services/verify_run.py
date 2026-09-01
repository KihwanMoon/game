"""제출을 재시뮬해서 결과를 확정한다 (docs/설계/7_변조방지 §3).

**서버는 클라이언트의 주장을 저장하지 않는다. 입력을 받아 다시 계산한다.**

이것이 가능한 이유는 두 코어가 비트 단위로 같기 때문이고(게이트 G3), 그 성질은 R5
하나에 걸려 있다. 재시뮬 하나가 세 위협을 함께 막는다.

* T1 결과 위조 — 제출에 결과가 없으므로 위조할 것이 없다.
* T5 코어 변조 — 클라이언트가 무엇을 하든 서버가 같은 입력으로 다시 돌린다.
* T7 규칙표 위반 — 검증기를 **서버에서 다시** 돌린다. 클라이언트 검증은 UX 이지 보안이
  아니다.

판정이 `mismatch` 라고 해서 치트가 아니다. 원인은 셋이며(변조·버전 시차·우리 버그) 세
번째는 실제로 있었다 — 쿨타임이 설정되지 않아 두 코어가 같은 값으로 틀린 적이 있다.
그래서 여기서 계정을 벌하지 않고, 어긋난 지점만 기록한다 (§8).
"""

from dataclasses import dataclass
from typing import Any

from game.app.rules.validator import validate_ruleset
from game.app.services.manage_meta import RunSummary
from game.app.services.run_battle import BattleResult, run_battle
from game.app.services.run_chain import run_room_chain
from game.app.services.run_summary import (
    build_run_summary,
    count_enemy_kinds,
    list_encountered_rulesets,
)
from game.app.simulation.engine import TickEngine
from game.app.simulation.plan import OUTCOME_PLAYER_WIN
from game.app.store.runs import VERDICT_REJECTED, VERDICT_VERIFIED
from game.schemas.blocks import BlockCatalog
from game.schemas.loadout import PlayerLoadout
from game.schemas.monster_snapshot import MonsterSnapshot
from game.schemas.room import RoomTemplate
from game.schemas.ruleset import RuleSet, parse_ruleset

# 플레이어 엔티티 id. 엔진이 이 이름으로 정책을 찾는다.
PLAYER_ID = "player"


@dataclass(frozen=True)
class VerifyContext:
    """검증 서버가 매 요청에 쓰는 자원 묶음.

    프로세스가 사는 동안 하나다. 요청마다 밸런스와 방을 다시 읽으면 재시뮬이 94ms 가
    아니라 파일 I/O 시간이 된다.
    """

    balance: dict
    catalog: BlockCatalog
    rooms: dict[str, RoomTemplate]
    enemy_rulesets: dict[str, RuleSet]


@dataclass(frozen=True)
class VerifiedRun:
    """재시뮬이 확정한 결과."""

    outcome: str
    ticks: int
    player_hp: int
    verdict: str
    detail: str = ""
    # 이 재시뮬이 뽑아낸 결산. **메타 세이브는 이것으로만 갱신된다** — 클라이언트가
    # 보낸 요약을 받으면 해금과 도감을 마음대로 채울 수 있다. 반려된 제출은 None 이다.
    summary: RunSummary | None = None
    # 실제로 깬 방 수. **도달 층이 여기서 나온다** — 하강이 여러 층에 걸치므로 "이겼다"
    # 하나로는 어디까지 갔는지 알 수 없고, 진 판도 몇 층까지는 깼을 수 있다.
    cleared_rooms: int = 0
    # 방마다 (만난 종, 잡은 종). **층 단위 보상이 이것으로 「이번 층의 처치」만 고른다** —
    # 전체를 주면 층을 깰 때마다 지나온 층의 전리품이 다시 나온다.
    room_kinds: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = ()


def check_submission_version(claimed: str, server: str) -> str:
    """클라이언트가 주장하는 코어 버전을 본다.

    버전이 다르면 결과가 재현되지 않는다. 이것은 변조가 아니라 배포 시차일 가능성이
    높으므로, 거절하되 사유를 그대로 적는다 (§8).

    Args:
        claimed: 클라이언트가 보낸 코어 버전.
        server: 이 서버가 도는 코어 버전.

    Returns:
        문제가 없으면 빈 문자열, 있으면 사유.
    """
    if claimed != server:
        return f"코어 버전이 다르다: 클라이언트 {claimed} / 서버 {server}"
    return ""


def evaluate_submission(
    context: VerifyContext,
    ruleset_payload: dict[str, Any],
    room_id: str,
    seed: int,
    cpu_budget: int,
    rule_slots: int,
    snapshots: tuple[MonsterSnapshot, ...] = (),
    loadout: PlayerLoadout | None = None,
    room_ids: tuple[str, ...] = (),
    floor: int = 1,
    rooms_per_floor: int = 0,
    room_limit: int = 0,
) -> VerifiedRun:
    """제출 하나를 재시뮬해서 판정한다.

    시드와 방은 **티켓에서 온다.** 제출이 그것을 실어 보내면 유리한 판을 골라 담을 수
    있다 (T2).

    Args:
        context: 밸런스·카탈로그·방·적 규칙표가 실린 검증 문맥.
        ruleset_payload: 클라이언트가 보낸 규칙표 절.
        room_id: 티켓이 정한 방.
        seed: 티켓이 정한 시드.
        cpu_budget: 이 계정의 CPU 예산.
        rule_slots: 이 계정의 규칙 슬롯 상한.
        snapshots: **티켓이 얼려 둔** 지속 몬스터 상태. 클라이언트가 보낸 것이 아니다 —
            받으면 약한 스냅샷으로 바꿔 제출할 수 있다 (T8).
        loadout: **티켓이 얼려 둔** 플레이어 전투 입력. 클라이언트가 보낸 것이 아니다.
        room_ids: **티켓이 얼려 둔** 방 목록. 비어 있으면 `room_id` 한 방만 돈다 —
            구버전 티켓이 그 경우다. 여기가 비면 브라우저는 세 방을 도는데 서버는 한
            방만 계산해, 이긴 판이 진 것으로 확정된다.

        floor: **티켓이 얼려 둔** 시작 층. 안 넘기면 재시뮬이 1층으로 돌아, 깊은 층을
            이긴 판이 진 것으로 확정된다 — 반려가 아니라 **틀린 결과가 기록된다.**
        rooms_per_floor: 층 하나에 드는 방 수. 방 순번에서 층을 파생한다.
        room_limit: 여기까지만 돈다. 0 이면 전부 돈다. **층 단위 보상이 이것을 쓴다** —
            층을 깰 때마다 제출하되 서버는 늘 **처음부터** 그 층까지 다시 돌므로, 인계
            HP 를 클라이언트가 보고할 자리가 없다 (T9).

    Returns:
        확정된 결과. 규칙표가 형식이나 예산을 어기면 `rejected` 다.
    """
    try:
        ruleset = parse_ruleset(ruleset_payload)
    except (KeyError, TypeError, ValueError) as error:
        return VerifiedRun("", 0, 0, VERDICT_REJECTED, f"규칙표를 읽을 수 없다: {error}")

    # 서버에서 **다시** 검증한다. 클라이언트 검증은 편집 중 피드백용이다.
    problems = validate_ruleset(ruleset, context.catalog, cpu_budget, rule_slots)
    if problems:
        return VerifiedRun("", 0, 0, VERDICT_REJECTED, f"규칙표 위반: {problems[0]}")

    # 결산은 **서버의 재시뮬에서 뽑는다.** 클라이언트가 보낸 요약을 받으면 해금과
    # 도감을 마음대로 채울 수 있다 (T-계열).
    tallies: list[tuple[tuple[str, ...], tuple[str, ...]]] = []

    def run_and_tally(engine: TickEngine) -> BattleResult:
        """방 하나를 돌리고 그 방의 전과를 적어 둔다.

        Args:
            engine: 조립된 엔진.

        Returns:
            그 방의 결과.
        """
        outcome = run_battle(engine)
        tallies.append(count_enemy_kinds(engine.state))
        return outcome

    rooms = room_ids or (room_id,)
    if room_limit > 0:
        rooms = rooms[:room_limit]
    missing = [name for name in rooms if name not in context.rooms]
    if missing:
        return VerifiedRun("", 0, 0, VERDICT_REJECTED, f"없는 방이다: {missing[0]}")

    # **로드아웃과 방 목록을 반드시 넘긴다.** 빠뜨리면 서버는 맨몸으로 한 방만 다시
    # 돌려, 장비를 끼고 세 방을 이긴 판을 진 것으로 기록한다 — 제출이 반려되는 것이
    # 아니라 **틀린 결과가 확정된다.** 그 결과가 경험치·전리품·순위로 흘러간다.
    result = run_room_chain(
        tuple(context.rooms[name] for name in rooms),
        context.balance,
        context.catalog,
        ruleset,
        context.enemy_rulesets,
        seed,
        snapshots=snapshots,
        loadout=loadout,
        floor=floor,
        rooms_per_floor=rooms_per_floor,
        run_room=run_and_tally,
    )
    encountered = tuple(sorted(kind for tally in tallies for kind in tally[0]))
    defeated = tuple(sorted(kind for tally in tallies for kind in tally[1]))
    return VerifiedRun(
        outcome=result.outcome,
        ticks=result.total_ticks,
        player_hp=result.player_hp,
        verdict=VERDICT_VERIFIED,
        cleared_rooms=result.cleared_rooms,
        room_kinds=tuple(tallies),
        summary=build_run_summary(
            encountered,
            defeated,
            ruleset,
            result.outcome == OUTCOME_PLAYER_WIN,
            list_encountered_rulesets(
                encountered, context.balance["enemies"], dict(context.enemy_rulesets)
            ),
        ),
    )
