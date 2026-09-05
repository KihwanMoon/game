"""배포봇의 판정 (설계/9_에이전트_운영 §4.5).

**DB 없이 돈다.** 판정 규칙이 맞는지가 여기서 볼 것이고, 그것은 저장소와 무관하다 —
지킴이와 같은 규율이다.

지키는 것은 셋이다.

1. **판정은 종료 코드가 한다.** LLM 에게도, 출력 줄 수에게도 안 묻는다.
2. **못 돌린 게이트는 통과가 아니다.** 도구가 없어 건너뛴 것을 통과로 세면 배포봇이
   도는 자리에 따라 판정이 달라진다.
3. **되돌리는 법이 늘 화면에 있다.** 없으면 컨펌이 아니라 도박이다.
"""

from game.app.deploy.briefing import (
    GATES,
    UNDO_CODE,
    Gate,
    GateResult,
    check_gates,
    check_world,
    list_authors,
    list_breakage,
    list_changes,
    list_undo,
)
from game.app.store.deploy import DeployReading, DraftRow
from game.app.watch.checks import LEVEL_ALARM, LEVEL_OK, LEVEL_WARN, build_finding

PROBE = Gate(name="표본", command=("true",), guards="아무것도")


def build_reading(**patch):
    base = {
        "open_runs": 0,
        "content_drafts": (),
        "catalog_drafts": (),
        "pack_generation": 3,
        "item_generation": 7,
        "drifted_assets": (),
    }
    return DeployReading(**{**base, **patch})


def build_draft(kind="content", name="balance", note="계수 조정", handle="balance_agent"):
    return DraftRow(kind=kind, name=name, note=note, handle=handle)


# ── 게이트 판정 ──────────────────────────────────────────────────────────


def test_a_passing_gate_blocks_nothing():
    assert check_gates((GateResult(gate=PROBE, code=0),)) == ()


def test_a_failing_gate_blocks():
    """★ 판정은 종료 코드다 — 출력 줄을 세지 않는다."""
    blocked = check_gates((GateResult(gate=PROBE, code=1, detail="1 failed"),))
    assert len(blocked) == 1
    assert "종료 코드 1" in blocked[0]


def test_a_gate_that_could_not_run_is_not_a_pass():
    """★ 도구가 없어 건너뛴 것을 통과로 세면 도는 자리에 따라 판정이 달라진다."""
    blocked = check_gates((GateResult(gate=PROBE, code=-1, detail="이 자리에 도구가 없다"),))
    assert len(blocked) == 1
    assert "돌리지 못했다" in blocked[0]


def test_one_failure_among_many_still_blocks():
    """★ 「경고지만 넘어감」을 두면 그 상태가 기본이 된다."""
    results = (
        GateResult(gate=PROBE, code=0),
        GateResult(gate=PROBE, code=2),
        GateResult(gate=PROBE, code=0),
    )
    assert len(check_gates(results)) == 1


def test_the_gates_are_the_ones_that_already_exist():
    """★ 새 검사를 지어내지 않는다 — 갈리는 순간 어느 쪽이 맞는지 물을 사람이 없어진다."""
    commands = [" ".join(gate.command) for gate in GATES]
    assert "./tools/check_all.sh" in commands
    assert any("pytest" in one for one in commands)
    assert any("npm" in one and "build" in one for one in commands)


# ── 세계 판정 ────────────────────────────────────────────────────────────


def test_a_quiet_world_blocks_nothing():
    assert check_world(build_reading(), ()) == ()


def test_an_alarm_from_the_watchdog_blocks():
    """★ 불난 데 배포하지 않는다 — 지킴이의 출력이 배포봇의 입력이다."""
    finding = build_finding("floor", LEVEL_ALARM, "최고층이 안 움직인다", "11/11")
    blocked = check_world(build_reading(), (finding,))
    assert len(blocked) == 1
    assert "최고층이 안 움직인다" in blocked[0]


def test_a_warning_does_not_block():
    """살핌은 막지 않는다 — 막으면 배포가 늘 막혀 있고, 그러면 아무도 안 읽는다."""
    quiet = build_finding("a", LEVEL_OK, "괜찮다", "")
    watched = build_finding("b", LEVEL_WARN, "살펴본다", "")
    assert check_world(build_reading(), (quiet, watched)) == ()


def test_drift_between_the_database_and_the_repository_blocks():
    """★ 발행만 하고 파일화를 안 하면 브라우저의 오프라인 폴백이 다른 게임을 돈다."""
    blocked = check_world(build_reading(drifted_assets=("balance",)), ())
    assert len(blocked) == 1
    assert "publish_content.py" in blocked[0]


def test_open_runs_do_not_block():
    """★ 열린 판은 막지 않는다.

    발행이 그것을 무효로 만드는 것은 이미 정해진 동작이고 (§3.3), 여기서 막으면 사람이
    많아졌을 때 영영 못 나간다. 몇 건이 끊기는지는 컨펌 화면이 적는다.
    """
    assert check_world(build_reading(open_runs=12), ()) == ()
    assert any("12건" in line for line in list_breakage(build_reading(open_runs=12)))


# ── 컨펌에 올리는 넷 ─────────────────────────────────────────────────────


def test_the_changes_say_who_made_them():
    """★ 에이전트가 올린 것과 사람이 올린 것을 못 가르면 검토가 흐려진다."""
    reading = build_reading(content_drafts=(build_draft(),))
    assert "balance_agent" in list_changes(reading)[0]
    assert list_authors(reading) == ("balance_agent",)


def test_an_unknown_author_is_said_out_loud():
    """빈 칸으로 두면 「없다」와 「모른다」가 구별되지 않는다."""
    reading = build_reading(content_drafts=(build_draft(handle=""),))
    assert list_authors(reading) == ("누구인지 모름",)


def test_publishing_content_says_the_season_splits():
    """★ 세대가 오르면 저장된 리플레이가 무효가 된다 — 누르는 사람이 알아야 한다."""
    broken = list_breakage(build_reading(content_drafts=(build_draft(),)))
    assert any("시즌이 갈리고" in line for line in broken)
    assert any("3" in line for line in broken)


def test_publishing_items_says_the_season_splits():
    reading = build_reading(catalog_drafts=(build_draft(kind="catalog", name="item sword"),))
    assert any("아이템 세대가 7" in line for line in list_breakage(reading))


def test_nothing_to_publish_breaks_nothing():
    assert list_breakage(build_reading()) == ()


def test_the_undo_is_always_there():
    """★ **되돌리는 법이 없으면 컨펌이 아니라 도박이다.**

    나갈 것이 없어도 코드 배포는 되돌릴 일이 있으므로 늘 적는다.
    """
    assert UNDO_CODE in list_undo(build_reading())
    assert len(list_undo(build_reading(content_drafts=(build_draft(),)))) >= 2


def test_the_undo_covers_each_path_that_is_taken():
    """★ 배포 경로가 둘이고 되돌리는 법도 둘이다 — 하나만 적으면 나머지가 남는다."""
    both = list_undo(
        build_reading(
            content_drafts=(build_draft(),),
            catalog_drafts=(build_draft(kind="catalog"),),
        )
    )
    assert len(both) == 3


# ── 실제로 돌리는 자리 ───────────────────────────────────────────────────


def test_a_missing_tool_is_reported_not_skipped():
    """★ 도구가 없으면 **통과가 아니라 걸림**이다.

    건너뛰기로 처리하면 npm 이 없는 컨테이너에서 배포봇이 늘 「올려도 된다」고 말한다.
    """
    from scripts.run_deploybot import CODE_UNRUNNABLE, run_gate

    absent = Gate(name="없는 도구", command=("this-tool-does-not-exist",), guards="—")
    result = run_gate(absent)
    assert result.code == CODE_UNRUNNABLE
    assert check_gates((result,))


def test_an_exit_code_is_taken_as_it_is():
    """★ 판정은 종료 코드다 — 출력이 비어도 0 이면 통과, 있어도 1 이면 걸림."""
    from scripts.run_deploybot import run_gate

    assert run_gate(Gate(name="참", command=("true",), guards="—")).code == 0
    assert run_gate(Gate(name="거짓", command=("false",), guards="—")).code == 1


def test_the_run_stops_at_the_first_failure():
    """★ 뒤엣것을 계속 돌려도 판정은 이미 「안 넘어간다」이고, 그 시간은 사람 것이다."""
    import scripts.run_deploybot as bot

    order = []

    def record(gate):
        order.append(gate.name)
        return GateResult(gate=gate, code=0 if gate.name == "첫째" else 1)

    original_gates, original_run = bot.GATES, bot.run_gate
    bot.GATES = (
        Gate(name="첫째", command=("true",), guards="—"),
        Gate(name="둘째", command=("false",), guards="—"),
        Gate(name="셋째", command=("true",), guards="—"),
    )
    bot.run_gate = record
    try:
        results = bot.list_gate_results(is_skipped=False)
    finally:
        bot.GATES, bot.run_gate = original_gates, original_run
    assert order == ["첫째", "둘째"], "실패한 뒤에도 계속 돌았다"
    assert len(results) == 2


def test_skipping_gates_is_not_passing_them():
    """★ `--skip-gates` 로도 통과가 되지 않는다 — 그러면 우회로가 생긴다."""
    from scripts.run_deploybot import list_gate_results

    results = list_gate_results(is_skipped=True)
    assert len(check_gates(results)) == len(GATES)
