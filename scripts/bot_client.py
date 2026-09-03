"""봇이 백엔드를 부르는 통로.

**라우트를 그대로 탄다.** `game_net` 안에서 백엔드에 HTTP 로 붙는다 — 서비스 계층을
직접 부르면 티켓 1회용·코어버전 대조 같은 라우트 규율을 우회하고, 그러면 봇의 런은
「진짜 경로가 도는지」를 더 이상 증명하지 못한다.

러너와 잡일이 함께 쓰므로 따로 뒀다. 여기 있는 것은 전송뿐이고 무엇을 부를지는 모른다.
"""

import json
import sys
import urllib.error
import urllib.request

# 백엔드 주소. 컨테이너 안에서는 서비스 이름으로 닿는다.
API_URL_ENV = "GAME_API_URL"
DEFAULT_API_URL = "http://backend:8000"

# 토큰 헤더. 브라우저가 쓰는 것과 같다.
TOKEN_HEADER = "X-Game-Token"

# HTTP 대기 상한(초). 재시뮬이 하강 전체를 도는 제출이 가장 오래 걸린다.
TIMEOUT_SEC = 60


def send_request(url: str, token: str, payload: dict | None, method: str = "") -> dict | None:
    """백엔드에 한 번 부른다.

    Args:
        url: 전체 주소.
        token: 기기 토큰. 빈 문자열이면 헤더를 안 붙인다.
        payload: 보낼 절. None 이면 GET 이다.
        method: 강제할 메서드. 비우면 payload 유무로 정한다 — 배분은 PUT 이다.

    Returns:
        응답 절. 닿지 못했거나 4xx·5xx 면 None — **봇이 죽지 않는다**. 백엔드가 잠깐
        내려가도 루프가 멈추면 안 되고, 다음 차례에 다시 시도하면 그만이다.

        **사유는 반드시 적는다.** 삼키면 「티켓을 못 받았다」만 남아 무엇이 잘못됐는지
        알 수 없다 — 실제로 그 상태로 배포해 한 번 헤맸다.
    """
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    verb = method or ("GET" if body is None else "POST")
    request = urllib.request.Request(url, data=body, method=verb)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header(TOKEN_HEADER, token)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:  # noqa: S310 내부 주소만 부른다
            return dict(json.loads(response.read().decode("utf-8")))
    except urllib.error.HTTPError as error:
        print(f"[봇] {url} → {error.code} {error.read()[:200]!r}", file=sys.stderr, flush=True)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
        print(f"[봇] {url} → {error}", file=sys.stderr, flush=True)
        return None
