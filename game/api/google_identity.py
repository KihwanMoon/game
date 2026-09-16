"""구글이 서명한 신원 토큰을 서버가 직접 검증한다 (설계/7_변조방지 §4).

**클라이언트가 보낸 이메일·이름을 믿지 않는다.** 믿는 순간 「나는 누구다」라고 적어
보내는 것이 곧 로그인이 되고, 누구든 남의 계정으로 들어온다. 서버가 보는 것은 구글의
**서명**뿐이다.

**담는 것은 `sub` 하나다.** 이메일은 바뀌고 재사용되므로 신원의 열쇠로 못 쓴다. 이름과
사진은 게임에 쓸 자리가 없고, 안 담으면 개인정보처리방침이 그만큼 짧아진다.

**HTTP 의존성을 안 늘린다.** 공개키(JWKS)는 `urllib.request` 로 받아 캐시한다 — 이 하나를
위해 런타임에 HTTP 클라이언트를 더 넣을 이유가 없다. 늘어난 것은 RS256 검증에 필요한
`pyjwt[crypto]` 뿐이다.

**꺼져 있는 것이 기본이다.** `GAME_GOOGLE_CLIENT_ID` 가 없으면 이 경로 전체가 503 으로
막힌다 — 설정이 빠진 채로 배포됐을 때 조용히 아무나 통과하는 것보다 낫다.
"""

import json
import os
import time
import urllib.request
from typing import Any

import jwt
from jwt import PyJWKClient

# 구글의 공개키 자리와 발급자. **정본은 구글의 디스커버리 문서이지만 값이 바뀌지 않는다** —
# 바뀌면 검증이 전부 실패하므로 조용한 사고가 아니라 즉시 드러나는 사고가 된다.
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# 클라이언트 id 를 담는 환경변수. `game/config.py` 의 접두어 규약을 따른다.
CLIENT_ID_ENV = "GAME_GOOGLE_CLIENT_ID"

# 시계 오차 허용치(초). 서버와 구글의 시계가 몇 초 어긋나도 갓 발급된 토큰이 만료로
# 떨어지면 안 된다. 크게 잡으면 만료된 토큰이 그만큼 더 산다.
CLOCK_SKEW_SECONDS = 30

# 공개키를 다시 받는 주기(초). 구글이 키를 돌리므로 영원히 캐시하면 어느 날 전부 실패한다.
KEY_CACHE_SECONDS = 3600

_key_client: PyJWKClient | None = None
_key_fetched_at = 0.0


def read_client_id() -> str:
    """이 서버가 받는 구글 클라이언트 id.

    Returns:
        클라이언트 id. 안 정했으면 빈 문자열이고, 그때 구글 로그인은 꺼진 것이다.
    """
    return os.environ.get(CLIENT_ID_ENV, "").strip()


def get_key_client() -> PyJWKClient:
    """구글 공개키 묶음을 든 클라이언트. 주기적으로 다시 받는다.

    **캐시가 필요하다.** 로그인마다 구글에 붙으면 구글이 느릴 때 로그인도 함께 느려지고,
    호출 수도 불필요하게 는다.

    Returns:
        키 클라이언트.
    """
    global _key_client, _key_fetched_at  # noqa: PLW0603 — 키 캐시 하나. 요청마다 새로 받지 않기 위한 유일한 전역이다
    now = time.monotonic()
    if _key_client is None or now - _key_fetched_at > KEY_CACHE_SECONDS:
        _key_client = PyJWKClient(GOOGLE_JWKS_URL, cache_keys=True)
        _key_fetched_at = now
    return _key_client


def read_discovery() -> dict[str, Any]:
    """구글의 디스커버리 문서를 읽는다 (운영 확인용).

    코드 경로는 `GOOGLE_JWKS_URL` 을 고정해서 쓴다. 이 함수는 그 값이 아직 맞는지 사람이
    확인할 때만 쓴다 — 자동으로 따라가게 하면 구글이 주는 주소로 검증 대상이 바뀐다.

    Returns:
        디스커버리 문서.
    """
    with urllib.request.urlopen(  # noqa: S310 — 주소가 상수다. 사용자 입력이 안 들어온다
        "https://accounts.google.com/.well-known/openid-configuration", timeout=10
    ) as response:
        return dict(json.loads(response.read()))


def resolve_google_subject(credential: str, client_id: str, nonce: str) -> str:
    """ID 토큰을 검증하고 구글의 고정 식별자를 낸다.

    **넷을 함께 본다.** 서명만 보면 다른 앱을 위해 발급된 토큰이 통과하고(`aud`), 발급자를
    안 보면 아무나 서명한 것이 통과하며(`iss`), 만료를 안 보면 옛 토큰이 영원히 살고(`exp`),
    논스를 안 보면 **가로챈 토큰을 그대로 다시 보내는 것**이 통과한다(`nonce`).

    Args:
        credential: 구글이 준 ID 토큰(JWT).
        client_id: 이 서버가 받는 클라이언트 id. `aud` 가 이것이어야 한다.
        nonce: 서버가 발급했던 일회용 값. 토큰의 `nonce` 가 이것이어야 한다.

    Returns:
        구글의 고정 식별자(`sub`).

    Raises:
        ValueError: 서명·발급자·수신자·만료·논스 중 하나라도 어긋나는 경우. 사유는 사람이
            읽을 수 있게 담되, **무엇이 틀렸는지는 화면에 그대로 내보내지 않는다** —
            공격자에게 어디까지 맞췄는지 알려 주는 셈이다.
    """
    try:
        key = get_key_client().get_signing_key_from_jwt(credential)
        claims = jwt.decode(
            credential,
            key.key,
            algorithms=["RS256"],
            audience=client_id,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["exp", "iat", "aud", "iss", "sub"]},
        )
    except Exception as error:  # noqa: BLE001 — jwt 가 던지는 예외가 여럿이고 처리가 하나다
        raise ValueError(f"구글 토큰을 확인하지 못했다: {error}") from error

    # **발급자를 직접 본다.** `jwt.decode(issuer=...)` 도 여럿을 받지만 타입 스텁이 하나만
    # 받는다고 적혀 있어, 통과시키려면 형 변환으로 그 사실을 가려야 한다. 그리고 구글이
    # 두 표기를 모두 쓰는 이유가 여기 주석으로 남는 편이 낫다.
    if str(claims.get("iss", "")) not in GOOGLE_ISSUERS:
        raise ValueError("발급자가 구글이 아니다")
    if str(claims.get("nonce", "")) != nonce:
        raise ValueError("논스가 어긋난다")
    subject = str(claims.get("sub", ""))
    if not subject:
        raise ValueError("구글 토큰에 식별자가 없다")
    return subject
