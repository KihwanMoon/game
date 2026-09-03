"""런 티켓과 제출 계약 (docs/설계/3_저장과_멀티플레이 §8, docs/설계/7_변조방지 §4).

**시드는 런의 출처이지 플레이어의 선택이 아니다.** 클라이언트가 시드를 정하면 유리한
시드가 나올 때까지 로컬에서 돌려 보고 그것만 제출할 수 있다 (T2). 지금 고치면 한 줄이고,
랭킹이 생긴 뒤에 고치면 그때까지의 기록이 전부 무효가 된다.

서버는 아직 없다. 여기 있는 것은 **계약과 이음매**이며, 서버가 붙으면 발급처만 바뀐다.

이 파일에서 가장 중요한 것은 `RunSubmission` 에 **없는 것**이다.

* 결과가 없다 — 서버가 재시뮬해서 정한다.
* 시드가 없다 — 티켓에 있다. 받으면 T2 가 열린다.
* 몬스터 스냅샷이 없다 — 티켓에 있다. 받으면 T8 이 열린다.
* 아이템·능력치가 없다 — 서버가 파생·보관한다. 받으면 T3·T4 가 열린다.

문서에만 적으면 "재시뮬이 느리니 이번만" 이라는 지름길이 반드시 생긴다. 필드가 없으면
그 지름길을 낼 수 없고, `test_submission_carries_no_results` 가 되돌아가는 것을 막는다.
"""

from dataclasses import dataclass, fields
from enum import StrEnum

from game.schemas.ruleset import RuleSet

# 엔진 로직 세대. 틱 순서·판정 규칙을 바꾸면 올린다. 블록 목록·밸런스 세대와 함께
# 코어 버전을 이루며, 하나라도 바뀌면 과거 기록이 재현되지 않아 랭킹 시즌이 갈린다.
# e4: 방 배치를 시드로 흔들고 일반 적이 정예로 승격된다 (변수 확장).
ENGINE_VERSION = 6

# 시드 상한. 2**53 - 1 이며, 이것은 밸런스가 아니라 **이식 제약**이다.
#
# TypeScript 코어가 시드를 number 로 들고 다니다 RNG 진입점에서 BigInt 로 바꾼다.
# number 는 53비트라 그 위의 값은 가장 가까운 짝수로 반올림되고, 같은 시드를 적어도
# 두 코어가 다른 난수를 낸다 — G3 가 못 보는 구간이다(골든은 작은 시드만 쓴다).
#
# 서버가 시드를 발급할 때 이 상한을 넘기면 그 순간 클라이언트가 다른 판을 돈다.
# 64비트 시드를 쓰려면 TS 쪽 seed 를 bigint 로 올리는 것이 선행이다
# (결정/1_결정대기목록 #01).
MAX_SEED = (1 << 53) - 1

# 로컬 티켓의 id 접두어. 서버가 발급한 것과 눈으로 구분되어야 한다 — 로컬 티켓이
# 랭킹에 섞이면 그 순간 순위표가 거짓이 된다.
LOCAL_TICKET_PREFIX = "local"


class RunMode(StrEnum):
    """런의 성격. 무엇을 신뢰할 수 있는지가 여기서 갈린다."""

    # 연습. 시드를 사람이 골라도 된다 — 리플레이와 규칙 실험이 이 자리다.
    PRACTICE = "PRACTICE"
    # 순위 대상. 시드를 서버가 발급하고 결과를 서버가 재시뮬해 확정한다.
    RANKED = "RANKED"
    # 하루 한 판. 같은 시드를 모두가 받는다.
    DAILY = "DAILY"


# 서버가 발급해야만 성립하는 모드. 로컬 발급으로 이 모드의 티켓을 만들 수 없다.
SERVER_ONLY_MODES: frozenset[RunMode] = frozenset({RunMode.RANKED, RunMode.DAILY})


@dataclass(frozen=True)
class RunTicket:
    """런 하나를 시작할 권한. 런의 입력 전부가 여기 얼려 있다.

    지속 몬스터가 들어오면 `monster_snapshot` 이 여기 붙는다 (docs/설계/6_몬스터 §5).
    그때도 등식은 유지된다 — 스냅샷이 입력의 일부가 될 뿐이다.
    """

    ticket_id: str
    seed: int
    room_id: str
    floor: int
    mode: RunMode
    core_version: str

    @property
    def is_ranked(self) -> bool:
        """이 티켓의 결과가 순위에 반영되는가."""
        return self.mode in SERVER_ONLY_MODES


@dataclass(frozen=True)
class RunSubmission:
    """제출. 클라이언트가 서버에 보내는 것 전부다.

    필드를 늘리기 전에 docs/설계/7_변조방지 §4 를 먼저 읽는다. 여기 있는 것 중 서버가
    저장하는 것은 규칙표 하나뿐이고, 그마저 검증기를 통과해야 한다.
    """

    ticket_id: str
    ruleset: RuleSet
    core_version: str


@dataclass(frozen=True)
class ContentVersions:
    """런 결과를 바꿀 수 있는 자산들의 세대.

    **정수 여섯 개를 위치 인자로 받지 않는 이유가 있다.** 전부 int 라 두 개를 바꿔 넣어도
    타입이 못 막고, 그런 사고가 이 저장소에서 이미 한 번 났다(개체 id 자리에 계정 id).
    이름을 붙이면 그 사고가 컴파일 전에 걸린다.

    엔진 로직(`ENGINE_VERSION`)은 파일이 아니라 코드라 여기 없다 —
    `build_core_version` 이 마지막에 붙인다.
    """

    blocks: int
    balance: int
    items: int
    skills: int
    rooms: int
    enemies: int


def build_core_version(versions: ContentVersions, pack: int = 0) -> str:
    """코어 버전 문자열을 만든다.

    하나라도 바뀌면 과거 기록이 재현되지 않으므로 랭킹 시즌이 갈린다 (docs/설계/3 §7).

    **여섯 자산을 전부 넣는다.** 예전에는 블록과 밸런스 둘만 봉인했는데, 스킬 계수나 방
    배치를 고치면 과거 리플레이가 달라지는데도 시즌이 안 갈렸다 — 저장된 리플레이가
    조용히 거짓이 되는 길이었다. 관리자가 콘텐츠를 고칠 수 있게 되면 그 일이 상시로
    일어난다.

    **팩 세대가 축 하나를 더 갖는다** (§18). 스킬·블록·밸런스·룸·적이 발행으로 바뀌면
    파일 세대는 그대로인데 실제로 도는 데이터가 달라지므로, 그 사실이 문자열에 남아야
    한다. 발행한 적이 없으면 0 이고, 그때는 파일 세대들이 그대로 시즌을 가른다.

    Args:
        versions: 자산별 세대.
        pack: 발행 세대. 발행한 적이 없으면 0.

    Returns:
        `b6.v2.i1.s2.r1.a1.p0.e1` 형태의 버전 문자열.
    """
    return (
        f"b{versions.blocks}.v{versions.balance}.i{versions.items}"
        f".s{versions.skills}.r{versions.rooms}.a{versions.enemies}"
        f".p{pack}.e{ENGINE_VERSION}"
    )


def create_local_ticket(
    seed: int,
    room_id: str,
    core_version: str,
    floor: int = 1,
    mode: RunMode = RunMode.PRACTICE,
) -> RunTicket:
    """로컬에서 연습용 티켓을 만든다.

    **연습 모드만 만들 수 있다.** 순위·데일리는 서버가 발급해야 성립하며, 로컬이 그것을
    만들 수 있으면 시드 서버 발급이 아무것도 막지 못한다.

    티켓 id 는 입력에서 그대로 파생한다. 시간이나 난수를 쓰면 같은 시드가 같은 티켓을
    내지 않아 리플레이가 깨진다 (R5).

    Args:
        seed: 이 런의 시드.
        room_id: 방 id.
        core_version: 코어 버전 문자열.
        floor: 층.
        mode: 런 모드. 연습이 아니면 거부한다.

    Returns:
        만들어진 티켓.

    Raises:
        ValueError: 서버 발급이 필요한 모드를 로컬로 만들려는 경우이거나, 시드가
            이식 가능한 범위를 벗어난 경우.
    """
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"시드가 이식 범위를 벗어났다: {seed} (상한 {MAX_SEED})")
    if mode in SERVER_ONLY_MODES:
        raise ValueError(f"{mode} 티켓은 서버가 발급해야 한다 — 로컬 발급은 순위를 거짓으로 만든다")
    ticket_id = f"{LOCAL_TICKET_PREFIX}:{mode}:{room_id}:{floor}:{seed}"
    return RunTicket(
        ticket_id=ticket_id,
        seed=seed,
        room_id=room_id,
        floor=floor,
        mode=mode,
        core_version=core_version,
    )


def build_submission(ticket: RunTicket, ruleset: RuleSet) -> RunSubmission:
    """제출을 만든다. 티켓이 시드와 방을 이미 들고 있으므로 다시 넣지 않는다.

    Args:
        ticket: 이 런의 티켓.
        ruleset: 이 런에 쓴 규칙표.

    Returns:
        만들어진 제출.
    """
    return RunSubmission(
        ticket_id=ticket.ticket_id,
        ruleset=ruleset,
        core_version=ticket.core_version,
    )


def list_submission_fields() -> tuple[str, ...]:
    """제출이 실제로 담는 필드 이름.

    검사가 이 목록을 본다. 결과·시드·스냅샷이 늘어나면 그 자리에서 붉어진다.

    Returns:
        선언 순서 그대로의 필드 이름.
    """
    return tuple(item.name for item in fields(RunSubmission))
