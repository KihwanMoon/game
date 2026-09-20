"""공유 페이지의 껍데기 — 크롤러와 사람이 함께 읽는 한 장.

`page.py` 에서 갈라 나왔다. 저쪽은 **규칙표를 어떻게 적는가**이고 여기는 **그것을
어떤 장에 담는가**다 — 도감 쪽에서 `codex`·`codexPage` 를 가른 것과 같은 선이다.
"""

from html import escape

SITE_NAME = "Sealed Stacks"
SITE_ORIGIN = "https://sealedstacks.com"
STYLESHEET = "/codex.css"

# 설명이 너무 길면 검색 결과에서 잘린다. 자르는 자리를 우리가 정한다.
MAX_DESCRIPTION = 150


def build_description(name: str, rule_count: int, cpu: int) -> str:
    """검색 결과에 뜰 한 줄.

    Args:
        name: 규칙표 이름.
        rule_count: 규칙 줄 수.
        cpu: CPU 합계.

    Returns:
        설명 한 줄.
    """
    text = f"{name} — 규칙 {rule_count}줄 · CPU {cpu}. 비각의 규칙표를 그대로 열어 고쳐 쓴다."
    return text[:MAX_DESCRIPTION]


def render_share_page(name: str, path: str, body: str, description: str) -> str:
    """공유 페이지 한 장을 만든다.

    **`noindex` 를 안 건다.** 이 장들이 검색으로 들어오는 문이고, 내용은 사람이 지은
    규칙표라 서로 다르다 — 같은 틀에 다른 알맹이가 들어가는 것은 얇은 페이지가 아니다.

    Args:
        name: 규칙표 이름.
        path: 이 장의 경로.
        body: `<main>` 안에 들어갈 조각.
        description: 검색 결과에 뜰 한 줄.

    Returns:
        HTML 전문.
    """
    title = f"{name} · 규칙표 · {SITE_NAME}"
    url = f"{SITE_ORIGIN}{path}"
    return f"""<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#0E131C" />
    <meta name="robots" content="index, follow" />
    <title>{escape(title)}</title>
    <meta name="description" content="{escape(description)}" />
    <link rel="canonical" href="{escape(url)}" />
    <link rel="icon" href="/brand/favicon.ico" sizes="16x16 32x32 48x48" />
    <link rel="stylesheet" href="{STYLESHEET}" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="{SITE_NAME}" />
    <meta property="og:title" content="{escape(title)}" />
    <meta property="og:description" content="{escape(description)}" />
    <meta property="og:url" content="{escape(url)}" />
    <meta property="og:locale" content="ko_KR" />
  </head>
  <body>
    <nav class="cx__nav">
      <a href="/">비각</a> · <a href="/codex/">도감</a>
    </nav>
    <main>
      {body}
    </main>
    <footer class="cx__foot">
      <p><a href="/privacy.html">개인정보처리방침</a> · <a href="/terms.html">이용약관</a></p>
    </footer>
  </body>
</html>
"""


def render_missing_page() -> str:
    """없는 주소에 내는 장.

    **빈 404 를 내지 않는다.** 링크는 오래 남고, 그것을 눌러 들어온 사람에게 아무것도
    안 보여 주면 사이트가 죽은 것으로 읽힌다.

    Returns:
        HTML 전문.
    """
    body = (
        '<article class="cx">\n'
        "      <h1>없는 규칙표</h1>\n"
        "      <p>이 주소의 규칙표를 찾지 못했다. 지워졌거나, 주소가 잘못 옮겨졌다.</p>\n"
        '      <p><a href="/">비각으로 가서 직접 지어 본다</a></p>\n'
        "      </article>"
    )
    return render_share_page("없는 규칙표", "/r/", body, "이 주소의 규칙표를 찾지 못했다.")
