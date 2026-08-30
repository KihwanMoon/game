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

from game.app.rules.rule_vm import build_rule_vm
from game.app.rules.validator import validate_ruleset
from game.app.services.run_battle import assign_enemy_policies, build_engine, run_battle
from game.app.store.runs import VERDICT_REJECTED, VERDICT_VERIFIED
from game.schemas.blocks import BlockCatalog
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

    if room_id not in context.rooms:
        return VerifiedRun("", 0, 0, VERDICT_REJECTED, f"없는 방이다: {room_id}")

    engine = build_engine(context.rooms[room_id], context.balance, seed=seed)
    engine.policies[PLAYER_ID] = build_rule_vm(ruleset, context.catalog, engine.config.kind_types)
    assign_enemy_policies(engine, context.balance, context.catalog, context.enemy_rulesets)
    result = run_battle(engine)
    return VerifiedRun(
        outcome=result.outcome,
        ticks=result.ticks,
        player_hp=result.player_hp,
        verdict=VERDICT_VERIFIED,
    )
