/**
 * 크롤러가 받아 가는 두 파일이 성립하는가.
 *
 * **둘 다 없었다** (2026-09-20). `frontend/public/` 에 파일이 없는데 nginx 가
 * `try_files $uri $uri/ /index.html` 이라, `robots.txt` 와 `sitemap.xml` 이 **200 으로
 * index.html 을 돌려주고 있었다.** 크롤러는 그 자리에서 HTML 을 받는다 — 없느니만 못하다.
 *
 * 404 였다면 눈에 띄었을 텐데 200 이라 아무 신호도 없었다. 그래서 **내용을 본다.**
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import { SITE_ORIGIN, buildSitemapXml, escapeXml, listFixedEntries } from './sitemap'

const PUBLIC_DIR = fileURLToPath(new URL('../../public/', import.meta.url))
const LASTMOD = '2026-09-20'

describe('robots.txt', () => {
  const text = readFileSync(`${PUBLIC_DIR}robots.txt`, 'utf8')

  it('★ HTML 이 아니다 — 폴백에 걸리면 이것부터 깨진다', () => {
    expect(text).not.toContain('<!doctype html>')
    expect(text).toContain('User-agent:')
  })

  it('★ 사이트맵 자리를 알려 준다 — 적지 않으면 크롤러가 못 찾는다', () => {
    expect(text).toContain(`Sitemap: ${SITE_ORIGIN}/sitemap.xml`)
  })

  it('관리 화면과 API 를 막는다', () => {
    expect(text).toContain('Disallow: /admin.html')
    expect(text).toContain('Disallow: /api/')
  })

  it('★ 네이버를 따로 부른다 — 국내 유입이 거기서 오고 JS 를 안 돌린다', () => {
    expect(text).toContain('User-agent: Yeti')
  })
})

describe('사이트맵', () => {
  it('고정 주소 셋을 싣는다', () => {
    const xml = buildSitemapXml(listFixedEntries(), LASTMOD)
    for (const entry of listFixedEntries()) {
      expect(xml).toContain(`<loc>${SITE_ORIGIN}${entry.path}</loc>`)
    }
  })

  it('관리 화면은 안 싣는다 — 막아 놓고 알려 주는 꼴이 된다', () => {
    expect(buildSitemapXml(listFixedEntries(), LASTMOD)).not.toContain('admin.html')
  })

  it('XML 선언과 네임스페이스로 시작한다', () => {
    const xml = buildSitemapXml(listFixedEntries(), LASTMOD)
    expect(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>')).toBe(true)
    expect(xml).toContain('http://www.sitemaps.org/schemas/sitemap/0.9')
  })

  it('★ 뜻을 갖는 글자를 막는다 — `&` 하나가 사이트맵 전체를 버리게 한다', () => {
    expect(escapeXml(`a&b<c>d"e'f`)).toBe('a&amp;b&lt;c&gt;d&quot;e&apos;f')
    const xml = buildSitemapXml([{ path: '/r/a&b', priority: '0.5', changefreq: 'never' }], LASTMOD)
    expect(xml).toContain('/r/a&amp;b')
  })

  it('날짜를 밖에서 받는다 — 안에서 시계를 읽으면 검사가 날마다 달라진다', () => {
    expect(buildSitemapXml(listFixedEntries(), '1999-01-01')).toContain('<lastmod>1999-01-01</lastmod>')
  })
})
