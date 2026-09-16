/// <reference types="node" />
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

import { stripHtmlComments } from './src/build/htmlComments'

const repoRoot = fileURLToPath(new URL('..', import.meta.url))
const designDir = fileURLToPath(new URL('../design', import.meta.url))
const resourcesDir = fileURLToPath(new URL('../game/resources', import.meta.url))

// 개발 서버 포트는 8090 으로 고정한다. Cloudflare Tunnel 이 host:8090 으로 직접
// 들어오기 때문이다 (deploy/README.md).
const DEV_PORT = 8090

/**
 * 빌드에서만 도는 주석 제거 플러그인.
 *
 * 규칙 자체는 `src/build/htmlComments` 에 있다 — 검사가 닿는 자리다.
 *
 * @returns vite 플러그인.
 */
function buildHtmlCommentStripper() {
  return {
    name: 'strip-html-comments',
    // 개발 서버에서는 안 돈다. 소스를 보며 고치는 사람에게는 주석이 있어야 한다.
    apply: 'build' as const,
    transformIndexHtml: {
      // 다른 플러그인이 태그를 다 넣은 뒤에 마지막으로 훑는다.
      order: 'post' as const,
      handler: stripHtmlComments,
    },
  }
}

export default defineConfig({
  plugins: [react(), buildHtmlCommentStripper()],
  resolve: {
    alias: {
      '@design': designDir,
      '@resources': resourcesDir,
    },
  },
  // 진입점이 넷이다. index.html 은 제품 화면, ds.html 은 디자인 시스템 부품
  // 카탈로그(`src/ds/gallery.tsx`), battle.html 은 전투 화면 확인용 페이지
  // (`src/battle/BattleCheck.tsx`), hud.html 은 되감기·사후 분석 확인용 페이지
  // (`src/hud/HudCheck.tsx`)다. 카탈로그를 App.tsx 안에 숨기지 않은 이유는 수명이
  // 다르기 때문이다 — 부품을 보는 페이지와 부품을 쓰는 화면이 한 파일을 나눠 쓰면
  // 전투 화면 작업과 계속 충돌한다. 개발 서버는 설정 없이도 두 html 을 모두 서빙하지만,
  // 빌드는 여기에 적힌 것만 산출물에 넣는다.
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('index.html', import.meta.url)),
        ds: fileURLToPath(new URL('ds.html', import.meta.url)),
        battle: fileURLToPath(new URL('battle.html', import.meta.url)),
        hud: fileURLToPath(new URL('hud.html', import.meta.url)),
        admin: fileURLToPath(new URL('admin.html', import.meta.url)),
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: DEV_PORT,
    strictPort: true,
    fs: { allow: [repoRoot] },
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx'],
  },
})
