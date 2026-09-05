"""세계 지킴이 — 세계가 말이 되는가를 계속 묻는다 (설계/9_에이전트_운영 §4.1).

**LLM 이 없다.** 질의와 임계값 비교뿐이라 새 의존성이 0개다 — 봇 러너와 같은 자리에서
같은 모양으로 돈다.

**아무것도 안 고친다.** 이상을 적어 사람에게 올릴 뿐이다. 자동으로 고치면 「왜 그랬는지」가
사라지는데, 이 지킴이가 잡으려는 결함들은 전부 **원인이 이유였지 증상이 아니었다.**

**라우트를 안 탄다.** 봇 러너는 게임을 하므로 라우트 규율을 지나야 하지만, 지킴이는
읽기만 하고 그 값들은 라우트가 안 내주는 것이다(도플갱어 나이·봇 가방 포화·정비가 남긴
일). 대신 **쓰기 질의를 한 줄도 안 둔다** — 그것이 이 프로세스의 경계다.

    GAME_DATABASE_URL=... uv run python -m scripts.run_watchdog          # 한 번 보고 끝
    GAME_DATABASE_URL=... uv run python -m scripts.run_watchdog --loop   # 계속 본다
"""

import argparse
import os
import sys
import time

from psycopg_pool import ConnectionPool

from game.app.store.connection import DATABASE_URL_ENV, create_pool
from game.app.store.watch import read_world
from game.app.store.watch_log import save_watch_findings
from game.app.watch.checks import (
    GLYPHS,
    LEVEL_ALARM,
    LEVEL_OK,
    Finding,
    list_findings,
    resolve_worst,
)

# 얼마나 자주 보는가(초). 결함이 며칠씩 숨어 있던 것이 이 기제의 이유이므로, 분 단위면
# 충분하다 — 더 자주 보면 같은 소견이 로그를 덮는다.
TICK_SEC = 300

# 판정·매물을 볼 창(시간).
WINDOW_HOURS = 24

# 봇이 매물을 볼 수 있게 되기까지의 시간. `bots/shopping.FIRST_LOOK_MINUTES` 와 같은
# 값이어야 한다 — 다르면 「아직 창이 안 지났다」를 「안 팔린다」로 읽는다.
FIRST_LOOK_HOURS = 6


def format_line(finding: Finding) -> str:
    """소견 한 줄을 만든다.

    **글리프와 글자를 함께 적는다.** 색을 못 쓰는 로그이므로 등급이 모양으로도 남아야
    한다 — 참·거짓을 색·글리프·명도 셋으로 적는 것과 같은 규율이다.

    Args:
        finding: 적을 소견.

    Returns:
        한 줄.
    """
    glyph = GLYPHS.get(finding.level, "·")
    return f"  {glyph} {finding.level:4} {finding.key:8} {finding.text}  ({finding.detail})"


def build_report(findings: tuple[Finding, ...]) -> str:
    """소견들을 보고서로 만든다.

    Args:
        findings: 소견들.

    Returns:
        사람이 읽을 여러 줄.
    """
    worst = resolve_worst(findings)
    bad = [one for one in findings if one.level != LEVEL_OK]
    head = f"[지킴이] {worst} — 살필 것 {len(bad)} / {len(findings)}"
    return "\n".join([head, *(format_line(one) for one in findings)])


def apply_watch(pool: ConnectionPool) -> str:
    """한 번 훑고, 남기고, 보고서를 낸다.

    **남기는 것이 로그에 찍는 것보다 중요하다.** 예전에는 찍기만 했고, 컨테이너 로그를
    읽는 사람은 없었다 (알려진이슈 Z1) — 5분마다 정확히 판단해서 아무에게도 안 갔다.

    남기는 것은 **지킴이 자신이 본 것**뿐이다. 세계 상태는 안 건드린다 (§8).

    Args:
        pool: 연결 풀.

    Returns:
        가장 나쁜 등급.
    """
    findings = list_findings(read_world(pool, WINDOW_HOURS, FIRST_LOOK_HOURS))
    changed = save_watch_findings(pool, findings)
    report = build_report(findings)
    # 판단이 바뀐 틱만 그 사실을 적는다. 매 틱 적으면 그 줄이 배경이 되어 안 읽힌다.
    print(f"{report}\n  ({changed}개 지표의 등급이 바뀌었다)" if changed else report, flush=True)
    return resolve_worst(findings)


def main() -> int:
    """지킴이를 돌린다.

    Returns:
        종료 코드. 주소가 없으면 2, 한 번 보기에서 「틀림」이 나오면 1, 아니면 0 —
        **한 번 보기는 게이트로도 쓸 수 있어야 한다.**
    """
    parser = argparse.ArgumentParser(description="세계 지킴이")
    parser.add_argument("--loop", action="store_true", help="계속 본다")
    args = parser.parse_args()

    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if not url:
        print(f"{DATABASE_URL_ENV} 가 없다", file=sys.stderr)
        return 2
    pool = create_pool(url)
    if not args.loop:
        return 1 if apply_watch(pool) == LEVEL_ALARM else 0

    print(f"[지킴이] 시작 — {TICK_SEC}초마다 본다", flush=True)
    while True:
        try:
            apply_watch(pool)
        except (KeyError, ValueError, TypeError) as error:
            # 지킴이가 죽으면 아무도 안 본다. 한 번 실패해도 다음 차례에 다시 본다.
            print(f"[지킴이] 못 읽었다: {error}", file=sys.stderr, flush=True)
        time.sleep(TICK_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
