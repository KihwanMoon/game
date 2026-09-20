/**
 * 사이트맵을 굽는다 — **크롤러에게 무엇이 있는지 말하는 유일한 수단이다.**
 *
 * 이 사이트는 SPA 라 크롤러가 받아 가는 본문이 부트 화면 68자뿐이다. 링크를 따라갈
 * 것도 없으므로, 색인되길 바라는 주소는 **여기에 적어 주지 않으면 존재하지 않는다.**
 *
 * **파일로 두지 않고 굽는 이유.** 도감 페이지가 자산 개수만큼 생긴다 — 몬스터가 한
 * 마리 늘 때마다 사람이 사이트맵을 고쳐야 한다면 그 줄은 반드시 낡는다.
 *
 * `robots.txt` 는 반대로 **손으로 적은 정적 파일**이다(`public/robots.txt`). 내용이
 * 자산을 안 따라가고, 크롤러가 제일 먼저 찾는 파일이라 굽다가 실패하면 통째로 빈다.
 *
 * 도감 주소는 `build/codex` 가 만들고 플러그인이 이 목록에 이어 붙인다.
 */

/** 이 사이트의 주소. `og:url` 과 같아야 한다 — 다르면 크롤러가 둘을 다른 사이트로 본다. */
export const SITE_ORIGIN = 'https://sealedstacks.com'

/** 사이트맵 한 줄. */
export interface SitemapEntry {
  /** `/` 로 시작하는 경로. */
  readonly path: string
  /** 0.0~1.0. 같은 사이트 안에서의 상대 비중일 뿐 순위를 사지 못한다. */
  readonly priority: string
  /** 얼마나 자주 바뀌는가. 크롤러에게 주는 힌트이고 약속은 아니다. */
  readonly changefreq: string
}

/**
 * 자산과 무관하게 늘 있는 주소들.
 *
 * **관리 화면은 없다.** `robots.txt` 가 막고 있고, 사이트맵에 적으면 막아 놓고 알려
 * 주는 꼴이 된다.
 *
 * @returns 고정 주소들.
 */
export function listFixedEntries(): readonly SitemapEntry[] {
  return [
    { path: '/', priority: '1.0', changefreq: 'weekly' },
    { path: '/privacy.html', priority: '0.3', changefreq: 'yearly' },
    { path: '/terms.html', priority: '0.3', changefreq: 'yearly' },
  ]
}

/**
 * XML 에서 뜻을 갖는 글자를 막는다.
 *
 * 주소에 `&` 가 들어가면 사이트맵 전체가 파싱 실패로 버려진다 — 한 줄이 아니라 전부다.
 *
 * @param raw 넣을 문자열.
 * @returns 막은 문자열.
 */
export function escapeXml(raw: string): string {
  return raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

/**
 * 사이트맵 XML 을 만든다.
 *
 * @param entries 적을 주소들.
 * @param lastmod `YYYY-MM-DD`. 부르는 쪽이 넘긴다 — 여기서 시계를 읽으면 검사가 날마다
 *     다른 값을 보게 된다.
 * @param origin 사이트 주소.
 * @returns XML 문자열.
 */
export function buildSitemapXml(
  entries: readonly SitemapEntry[],
  lastmod: string,
  origin: string = SITE_ORIGIN,
): string {
  const rows = entries.map(
    (entry) =>
      `  <url>\n` +
      `    <loc>${escapeXml(origin + entry.path)}</loc>\n` +
      `    <lastmod>${lastmod}</lastmod>\n` +
      `    <changefreq>${entry.changefreq}</changefreq>\n` +
      `    <priority>${entry.priority}</priority>\n` +
      `  </url>`,
  )
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    `${rows.join('\n')}\n` +
    '</urlset>\n'
  )
}
