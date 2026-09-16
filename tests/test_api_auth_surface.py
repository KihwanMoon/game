"""공개 표면이 열려 있지 않은가.

여기서 보는 것은 라우트 하나의 동작이 아니라 **표면 전체의 모양**이다. 개별 라우트
검사는 그 라우트가 있을 때만 돌지만, 새로 더한 관리자 경로에 문지기를 안 붙이면
아무 검사도 안 빨개진다 — 그 빈자리를 메우려고 소스를 훑는다.

2026-09-16 에 공개 도메인을 실측하다가 나온 것들이다. `/openapi.json` 이 컨테이너
안에서 200 이었고(밖에서는 nginx 가 `/api/` 만 넘겨 안 닿았다), 그 스키마에는 관리자
경로까지 전부 들어 있었다 — **프록시 규칙 한 줄에 기댄 상태**였다.
"""

import re
from pathlib import Path

from game.api.main import create_app

ROUTES_DIR = Path(__file__).resolve().parent.parent / "game" / "api" / "routes"

ROUTE_DECORATOR = re.compile(r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)")

# 등급별 문지기들. `deps.py` 의 `Current*` 별칭이며, 계정만 푸는 `CurrentAccount` 는
# **여기 없다** — 로그인했다는 것과 관리자라는 것은 다른 말이다.
ADMIN_GUARDS = ("CurrentAdmin", "CurrentAuthor", "CurrentOperator", "CurrentOwner")


def list_admin_routes() -> list[tuple[str, str, str]]:
    """관리자 경로와 그 서명을 모은다.

    데코레이터 바로 아래의 함수 서명을 반환 화살표까지 이어 붙여 본다 — 인자가 여러
    줄로 접혀 있어도 문지기가 서명 어딘가에는 적혀 있다.

    Returns:
        (파일 이름, 경로, 서명) 세 쪽. 관리자 경로가 하나도 없으면 빈 목록.
    """
    found: list[tuple[str, str, str]] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            hit = ROUTE_DECORATOR.search(line)
            if hit is None:
                continue
            route = hit.group(2)
            if "admin" not in path.name and not route.startswith("/api/admin"):
                continue
            signature = ""
            cursor = index + 1
            while cursor < len(lines) and "-> " not in signature:
                signature += lines[cursor]
                cursor += 1
            found.append((path.name, route, signature))
    return found


def test_every_admin_route_has_a_gate() -> None:
    """관리자 경로는 전부 등급 문지기를 받는다."""
    routes = list_admin_routes()
    # 하나도 못 찾았다면 훑기가 깨진 것이다. 0건은 "전부 통과" 와 구별되지 않는다.
    assert len(routes) > 20, f"관리자 경로를 {len(routes)}개밖에 못 찾았다 — 훑기가 깨졌다"
    naked = [
        f"{name} {route}"
        for name, route, signature in routes
        if not any(guard in signature for guard in ADMIN_GUARDS)
    ]
    assert naked == [], f"문지기 없는 관리자 경로: {naked}"


def test_the_schema_endpoint_is_off() -> None:
    """스키마를 밖으로 안 낸다 — 경로와 본문 모양이 통째로 들어 있다.

    라우트 표를 본다. FastAPI 는 세 URL 이 켜져 있을 때만 그 라우트를 **만들므로**,
    표에 없다는 것이 곧 안 나간다는 뜻이다 — DB 없이 볼 수 있는 자리이기도 하다.
    """
    server = create_app()
    assert server.openapi_url is None
    assert server.docs_url is None
    assert server.redoc_url is None
    served = {getattr(route, "path", "") for route in server.routes}
    for path in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"):
        assert path not in served, f"{path} 가 살아 있다"
