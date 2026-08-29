"""프리셋 공유 코드 — `v2:` + gzip(JSON) + base64 (GDD §10 A등급, TDD §9).

규칙표를 문자열 하나로 만들어 주고받는다. 도감이 적의 논리를 공개하는 것과 같은
방향의 장치다 — 남의 카운터를 읽고 자기 것과 비교할 수 있어야 실패가 정보가 된다 (P1).

세 겹을 쓰는 이유가 각각 다르다.
- `v2:` 접두어: 코드를 풀기 전에 마이그레이션 여부를 판정한다. 본문을 풀어 보고서야
  버전을 알면, 형식이 바뀌었을 때 풀이 자체가 예외로 끝나 판정할 기회가 없다.
- gzip: 규칙표 JSON 은 키 이름이 반복돼 잘 줄어든다.
- urlsafe base64: 채팅·URL 에 그대로 붙일 수 있어야 한다. 표준 base64 의 `+` `/` 는
  URL 에서 깨진다.

**같은 프리셋은 언제나 같은 코드여야 한다.** gzip 헤더에는 mtime 이 들어가므로 그것을
0 으로 고정한다. 고정하지 않으면 같은 규칙표가 1초 뒤에 다른 코드가 되어, 코드가 같은지
비교하는 것으로 규칙표가 같은지 볼 수 없게 된다 (R5).
"""

import base64
import gzip
import json

from game.schemas.meta_save import RulePreset, build_preset_payload, parse_preset

# TDD §9 가 못박은 접두어다. 값이 2 인 것은 규칙 DSL 의 세대이지 이 모듈의 판수가 아니다.
PRESET_CODE_VERSION = 2
PRESET_CODE_SEPARATOR = ":"
PRESET_CODE_PREFIX = f"v{PRESET_CODE_VERSION}{PRESET_CODE_SEPARATOR}"

GZIP_LEVEL = 9
# 결정론을 위해 시각을 넣지 않는다. 코어는 시스템 시간을 읽지 않는다 (TDD §1.1).
GZIP_MTIME = 0

# base64 는 4의 배수 길이를 요구한다. 붙여넣기로 패딩이 잘려 오는 일이 잦아 복원한다.
BASE64_BLOCK = 4


def get_code_version(code: str) -> int:
    """공유 코드의 버전을 본문을 풀지 않고 읽는다.

    Args:
        code: `v2:...` 형태의 공유 코드.

    Returns:
        접두어가 가리키는 버전 정수.

    Raises:
        ValueError: 접두어가 `v<정수>:` 형태가 아닌 경우.
    """
    head, separator, _ = code.strip().partition(PRESET_CODE_SEPARATOR)
    if not separator or not head.startswith("v") or not head[1:].isdigit():
        raise ValueError(f"공유 코드는 v<버전>: 로 시작해야 한다: {code[:16]!r}")
    return int(head[1:])


def export_preset_code(preset: RulePreset) -> str:
    """프리셋을 공유 코드 문자열로 만든다.

    JSON 을 정렬된 키로 좁게 찍는다. 키 순서가 실행마다 달라지면 같은 규칙표가 다른
    코드를 내고, 그러면 코드 비교가 규칙표 비교를 대신하지 못한다.

    Args:
        preset: 내보낼 프리셋.

    Returns:
        `v2:` 로 시작하는 공유 코드.
    """
    payload = build_preset_payload(preset)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    packed = gzip.compress(raw.encode("utf-8"), compresslevel=GZIP_LEVEL, mtime=GZIP_MTIME)
    return PRESET_CODE_PREFIX + base64.urlsafe_b64encode(packed).decode("ascii")


def parse_preset_code(code: str) -> RulePreset:
    """공유 코드를 프리셋으로 되돌린다. export_preset_code 의 역방향이다.

    Args:
        code: `v2:` 로 시작하는 공유 코드. 앞뒤 공백은 무시한다.

    Returns:
        복원된 프리셋.

    Raises:
        ValueError: 접두어가 없거나, 버전이 이 코어의 것이 아니거나, 본문이 깨진 경우.
    """
    text = code.strip()
    version = get_code_version(text)
    if version != PRESET_CODE_VERSION:
        raise ValueError(
            f"이 코어가 읽을 수 없는 프리셋 세대다: v{version} != v{PRESET_CODE_VERSION}"
        )
    body = text[len(PRESET_CODE_PREFIX) :]
    padded = body + "=" * (-len(body) % BASE64_BLOCK)
    try:
        packed = base64.urlsafe_b64decode(padded.encode("ascii"))
        raw = gzip.decompress(packed).decode("utf-8")
        return parse_preset(json.loads(raw))
    except (ValueError, OSError, EOFError, KeyError, TypeError) as error:
        # 깨진 코드는 층마다 예외 종류가 다르다 — base64·gzip·JSON·스키마가 각각
        # 다른 것을 던진다. 붙여넣다 잘린 코드 하나에 그 넷을 다 아는 호출자를
        # 요구할 수 없으므로 여기서 한 종류로 모은다.
        raise ValueError(f"프리셋 코드를 풀 수 없다: {error}") from error
