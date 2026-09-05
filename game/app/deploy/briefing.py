"""배포봇의 판정과 컨펌 화면 (설계/9_에이전트_운영 §4.5).

**새 검사를 지어내지 않는다.** 이 저장소에는 이미 게이트가 층층이 있고, 배포봇이 할 일은
그것을 **순서대로 돌리고 하나라도 걸리면 안 넘어가는 것**이다. 새로 만든 검사는 기존
게이트와 갈리는 순간 어느 쪽이 맞는지 물을 사람이 없어진다.

**판정은 종료 코드가 한다.** CLAUDE.md 가 이미 그 규율을 갖고 있다 — 출력 줄을 세는
방식은 도구의 출력 형식이 예상과 다르면 0 을 돌려주고, 그것이 「위반 없음」과 구별되지
않는다. LLM 에게 통과 여부를 묻는 것은 그보다 더 나쁘다 (§5.4).

**여기는 순수 함수다.** DB 도 프로세스도 안 부른다 — 임계값이 바뀔 때 고치는 자리와
읽는 자리가 갈려 있어야 한다 (지킴이와 같은 규율).
"""

from dataclasses import dataclass

from game.app.store.deploy import DeployReading
from game.app.watch.checks import LEVEL_ALARM, Finding

# 되돌리는 법. **넷째가 없으면 컨펌이 아니라 도박이다** (§4.5) — 되돌리는 법을 모르는
# 채 누르는 것은 검토가 아니다. 형식을 고정해 두는 이유는, 그 자리에서 복사해 붙일 수
# 있어야 하기 때문이다.
UNDO_CODE = "git revert <커밋> && docker compose up -d --build frontend backend"
UNDO_CONTENT = "관리 화면에서 이전 세대의 절을 다시 초안으로 올리고 발행한다"
UNDO_CATALOG = "관리 화면 〈아이템〉에서 되돌릴 조작을 초안으로 올리고 발행한다"


@dataclass(frozen=True)
class Gate:
    """돌려야 하는 게이트 하나.

    **명령을 함께 든다.** 배포봇이 못 돌리는 자리(도구가 없는 컨테이너)에서도 사람이
    그대로 옮겨 칠 수 있어야 하고, 그때 옮겨 칠 것이 화면에 있어야 한다.
    """

    name: str
    command: tuple[str, ...]
    # 이 게이트가 무엇을 지키는가. 걸렸을 때 사람이 읽는다.
    guards: str


@dataclass(frozen=True)
class GateResult:
    """게이트 하나를 돌린 결과."""

    gate: Gate
    # 종료 코드. **이것만이 판정이다.** -1 은 「돌리지 못했다」이며 통과가 아니다.
    code: int
    detail: str = ""


# 돌리는 순서. 싼 것부터 둔다 — 린트에서 걸릴 것을 스위트 뒤에 두면 사람이 몇 분을
# 기다린 뒤에야 안다.
GATES = (
    Gate(
        name="저장소 전량 게이트",
        command=("./tools/check_all.sh",),
        guards="린트·서식·독스트링·타입·이름·모듈 길이·구조",
    ),
    Gate(
        name="파이썬 스위트",
        command=("pytest", "-q"),
        guards="골든 리플레이와 회귀",
    ),
    Gate(
        name="프런트엔드 빌드",
        command=("npm", "--prefix", "frontend", "run", "build"),
        guards="타입과 번들 — 두 코어가 같은 시드에서 같은 결과를 내는지(G3)",
    ),
)


def check_gates(results: tuple[GateResult, ...]) -> tuple[str, ...]:
    """게이트 결과에서 막는 사유를 고른다.

    **「경고지만 넘어감」을 두지 않는다.** 그것을 두면 그 상태가 기본이 된다 — 검증의
    두 등급을 섞지 않는 것과 같은 규율이다.

    **못 돌린 게이트는 통과가 아니다.** 도구가 없어 건너뛴 것을 통과로 세면, 배포봇이
    도는 자리에 따라 판정이 달라진다.

    Args:
        results: 돌린 결과들.

    Returns:
        막는 사유들. 비어 있으면 게이트는 전부 통과다.
    """
    return tuple(
        (
            f"{result.gate.name}: 돌리지 못했다 — {result.detail}"
            if result.code < 0
            else f"{result.gate.name}: 종료 코드 {result.code}"
        )
        for result in results
        if result.code != 0
    )


def check_world(reading: DeployReading, findings: tuple[Finding, ...]) -> tuple[str, ...]:
    """세계 쪽에서 막는 사유를 고른다.

    **불난 데 배포하지 않는다.** 지킴이(A)의 출력이 배포봇(E)의 입력이다 (§4.5).

    **열린 판은 막지 않는다.** 발행이 그것을 무효로 만드는 것은 이미 정해진 동작이고
    (§3.3), 여기서 막으면 사람이 많아졌을 때 영영 못 나간다 — 몇 건이 끊기는지는
    `list_breakage` 가 컨펌 화면에 적는다.

    Args:
        reading: 배포를 앞둔 세계.
        findings: 지킴이의 소견들.

    Returns:
        막는 사유들.
    """
    blocked = [
        f"세계 지킴이: {finding.text} ({finding.detail})"
        for finding in findings
        if finding.level == LEVEL_ALARM
    ]
    if reading.drifted_assets:
        # 발행만 하고 파일화를 안 한 상태다. 여기서 또 배포하면 폴백이 더 멀어진다.
        blocked.append(
            "DB 와 저장소가 갈라져 있다: "
            + ", ".join(reading.drifted_assets)
            + " — `scripts/publish_content.py` 로 파일화하고 커밋한다"
        )
    return tuple(blocked)


def list_changes(reading: DeployReading) -> tuple[str, ...]:
    """무엇이 바뀌는가 — 컨펌에 올리는 것 첫째.

    Args:
        reading: 배포를 앞둔 세계.

    Returns:
        한 줄씩. 나갈 것이 없으면 빈 튜플.
    """
    return tuple(
        f"{row.kind} · {row.name} · {row.handle or '누구인지 모름'} · {row.note or '사유 없음'}"
        for row in (*reading.content_drafts, *reading.catalog_drafts)
    )


def list_authors(reading: DeployReading) -> tuple[str, ...]:
    """누가 만들었는가 — 컨펌에 올리는 것 둘째.

    에이전트가 올린 것과 사람이 올린 것을 못 가르면, 검토한다는 것이 무엇을 보는
    일인지 흐려진다.

    Args:
        reading: 배포를 앞둔 세계.

    Returns:
        올린 이들. 중복 없이 정렬돼 있다.
    """
    rows = (*reading.content_drafts, *reading.catalog_drafts)
    names = {row.handle or "누구인지 모름" for row in rows}
    return tuple(sorted(names))


def list_breakage(reading: DeployReading) -> tuple[str, ...]:
    """무엇이 깨지는가 — 컨펌에 올리는 것 셋째.

    Args:
        reading: 배포를 앞둔 세계.

    Returns:
        깨지는 것들. 아무것도 안 깨지면 빈 튜플.
    """
    broken = []
    if reading.open_runs:
        broken.append(
            f"돌고 있는 판 {reading.open_runs}건이 무효가 된다 (§3.3) —"
            " 최대 50분 기다리면 저절로 빈다"
        )
    if reading.content_drafts:
        broken.append(
            f"콘텐츠 세대가 {reading.pack_generation} 에서 오른다 —"
            " **순위표 시즌이 갈리고 저장된 리플레이가 무효가 된다**"
        )
    if reading.catalog_drafts:
        broken.append(f"아이템 세대가 {reading.item_generation} 에서 오른다 — 시즌이 갈린다")
    return tuple(broken)


def list_undo(reading: DeployReading) -> tuple[str, ...]:
    """되돌리는 법 — 컨펌에 올리는 것 넷째.

    **이것이 없으면 컨펌이 아니라 도박이다.**

    Args:
        reading: 배포를 앞둔 세계.

    Returns:
        되돌리는 법들.
    """
    steps = [UNDO_CODE]
    if reading.content_drafts:
        steps.append(UNDO_CONTENT)
    if reading.catalog_drafts:
        steps.append(UNDO_CATALOG)
    return tuple(steps)
