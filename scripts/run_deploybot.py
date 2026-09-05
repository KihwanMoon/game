"""배포봇 — 문을 지킨다 (설계/9_에이전트_운영 §4.5).

**읽고 판단만 한다. 누르는 것은 사람이다.** 자동 배포는 이 저장소의 전제(발행이 시즌을
가른다)와 맞지 않는다 (§8).

하는 일은 셋이다.

1. **있는 게이트를 순서대로 돌린다.** 새 검사를 지어내지 않는다 — 새로 만든 것은 기존
   게이트와 갈리는 순간 어느 쪽이 맞는지 물을 사람이 없어진다.
2. **게이트가 안 보는 것 다섯을 읽는다.** 몇 명이 놀고 있나, 시즌이 갈리나, 골든이
   바뀌나, DB 와 저장소가 갈라지나, 지킴이가 지금 이상을 보고 있나.
3. **컨펌에 올릴 넷을 한 화면에 적는다.** 무엇이 바뀌는가 · 누가 만들었는가 ·
   무엇이 깨지는가 · **되돌리는 법**. 넷째가 없으면 컨펌이 아니라 도박이다.

**하나라도 걸리면 올리지 않는다.** 「경고지만 넘어감」을 두면 그 상태가 기본이 된다.

    GAME_DATABASE_URL=... uv run python -m scripts.run_deploybot
    GAME_DATABASE_URL=... uv run python -m scripts.run_deploybot --skip-gates

`--skip-gates` 는 게이트를 이미 돌려 둔 자리에서 **세계 쪽만** 보려는 것이다. 그때도
판정은 「게이트를 안 봤다」로 남는다 — 통과로 세지 않는다.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from game.app.deploy.briefing import (
    GATES,
    Gate,
    GateResult,
    check_gates,
    check_world,
    list_authors,
    list_breakage,
    list_changes,
    list_undo,
)
from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.content_draft import DRAFT_ASSETS
from game.app.store.deploy import DeployReading, read_deploy_state
from game.app.store.watch import read_world
from game.app.watch.checks import list_findings

# 지킴이와 같은 창을 본다. 다른 창을 쓰면 두 화면이 다른 세계를 말한다.
WINDOW_HOURS = 24
FIRST_LOOK_HOURS = 6

# 게이트 하나에 주는 시간. 스위트가 이보다 오래 걸리면 그것 자체가 볼 일이다.
GATE_TIMEOUT_SEC = 3600

# 「돌리지 못했다」를 뜻하는 코드. **통과가 아니다** — 도구가 없어 건너뛴 것을 통과로
# 세면 배포봇이 도는 자리에 따라 판정이 달라진다.
CODE_UNRUNNABLE = -1


def read_asset_files() -> dict[str, dict]:
    """저장소의 실행 자산 파일들을 읽는다.

    DB 의 발행본과 견주는 데 쓴다 — 발행만 하고 파일화를 안 하면 브라우저의 오프라인
    폴백이 다른 게임을 돈다 (§4.5).

    Returns:
        자산 이름에서 절로의 대응표. 없는 파일은 뺀다.
    """
    found = {}
    for asset, (path, _version_key) in DRAFT_ASSETS.items():
        source = Path(path)
        if source.exists():
            found[asset] = json.loads(source.read_text(encoding="utf-8"))
    return found


def run_gate(gate: Gate) -> GateResult:
    """게이트 하나를 돌린다 — **판정은 종료 코드다**.

    출력 줄을 세지 않는다 — 도구의 출력 형식이 예상과 다르면 0 을 돌려주고, 그것이
    「위반 없음」과 구별되지 않는다 (CLAUDE.md).

    Args:
        gate: 돌릴 게이트.

    Returns:
        결과. 도구가 없으면 `CODE_UNRUNNABLE` 이다.
    """
    try:
        done = subprocess.run(  # noqa: S603  # 명령은 GATES 상수뿐이고 입력을 안 받는다
            list(gate.command),
            check=False,
            timeout=GATE_TIMEOUT_SEC,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return GateResult(gate=gate, code=CODE_UNRUNNABLE, detail="이 자리에 도구가 없다")
    except subprocess.TimeoutExpired:
        return GateResult(gate=gate, code=CODE_UNRUNNABLE, detail="시간이 다 됐다")
    tail = (done.stdout or done.stderr or "").strip().splitlines()
    return GateResult(gate=gate, code=done.returncode, detail=tail[-1] if tail else "")


def list_gate_results(is_skipped: bool) -> tuple[GateResult, ...]:
    """게이트를 순서대로 돌린다 — **첫 실패에서 멈춘다**.

    뒤엣것을 계속 돌려도 판정은 이미 「안 넘어간다」이고, 그 시간은 사람이 고칠 시간을
    빼앗는다.

    Args:
        is_skipped: 게이트를 건너뛸 것인가.

    Returns:
        결과들. 건너뛰면 전부 「돌리지 못했다」로 돌려준다 — 통과로 세지 않는다.
    """
    if is_skipped:
        return tuple(
            GateResult(gate=gate, code=CODE_UNRUNNABLE, detail="건너뛰라고 했다") for gate in GATES
        )
    results = []
    for gate in GATES:
        result = run_gate(gate)
        results.append(result)
        if result.code != 0:
            break
    return tuple(results)


def render_block(title: str, lines: tuple[str, ...], empty: str) -> str:
    """묶음 하나를 글로 만든다.

    Args:
        title: 머리글.
        lines: 적을 줄들.
        empty: 비었을 때 적을 말.

    Returns:
        한 묶음.
    """
    body = "\n".join(f"    - {line}" for line in lines) if lines else f"    {empty}"
    return f"  {title}\n{body}"


def render_briefing(
    reading: DeployReading, results: tuple[GateResult, ...], blockers: tuple[str, ...]
) -> str:
    """컨펌 화면 하나를 만든다.

    Args:
        reading: 배포를 앞둔 세계.
        results: 게이트 결과들.
        blockers: 막는 사유들. 비어 있으면 사람에게 올린다.

    Returns:
        사람이 읽을 보고서.
    """
    gates = tuple(
        f"{'[O] 통과' if r.code == 0 else '[X] 걸림'}  {r.gate.name}"
        f" — {r.gate.guards}{'' if r.code == 0 else f' ({r.detail})'}"
        for r in results
    )
    parts = [
        "배포봇 (설계/9_에이전트_운영 §4.5)",
        "",
        render_block("게이트", gates, "돌린 것이 없다"),
        "",
        render_block("1. 무엇이 바뀌는가", list_changes(reading), "나갈 것이 없다"),
        "",
        render_block("2. 누가 만들었는가", list_authors(reading), "—"),
        "",
        render_block("3. 무엇이 깨지는가", list_breakage(reading), "아무것도 안 깨진다"),
        "",
        render_block("4. 되돌리는 법", list_undo(reading), "—"),
        "",
    ]
    if blockers:
        parts.append(render_block("올리지 않는다", blockers, ""))
        parts.append("")
        parts.append(
            "  하나라도 걸리면 올리지 않는다 — 「경고지만 넘어감」을 두면 그것이 기본이 된다."
        )
    else:
        parts.append("  올려도 된다. **누르는 것은 사람이다** — 아래를 그대로 돌린다.")
        parts.append("")
        parts.append("    docker compose up -d --build frontend backend")
    return "\n".join(parts)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    """명령행 인자를 해석한다.

    Args:
        argv: 프로그램 이름을 뺀 인자들.

    Returns:
        해석된 인자.
    """
    parser = argparse.ArgumentParser(description="배포 전에 게이트와 세계를 함께 본다")
    parser.add_argument(
        "--skip-gates",
        action="store_true",
        help="게이트를 이미 돌려 둔 자리에서 세계 쪽만 본다 (통과로 세지 않는다)",
    )
    return parser.parse_args(argv)


def main() -> int:
    """스크립트 진입점.

    Returns:
        종료 코드. 올려도 되면 0, 하나라도 걸리면 1, 연결이 없으면 1.
    """
    arguments = parse_arguments(sys.argv[1:])
    if not os.environ.get(DATABASE_URL_ENV, "").strip():
        print(f"{DATABASE_URL_ENV} 가 없다")
        return 1
    pool = create_pool()
    reading = read_deploy_state(pool, read_asset_files())
    findings = list_findings(read_world(pool, WINDOW_HOURS, FIRST_LOOK_HOURS))
    results = list_gate_results(arguments.skip_gates)
    blockers = (*check_gates(results), *check_world(reading, findings))
    print(render_briefing(reading, results, blockers))
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
