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
  // **산출물에 넣는 진입점은 둘뿐이다** — 제품 화면(`index.html`)과 관리 화면
  // (`admin.html`).
  //
  // 확인용 페이지 셋(`ds.html` 부품 카탈로그, `battle.html` 전투 렌더러, `hud.html`
  // 되감기)은 **일부러 뺐다** (2026-09-16). 공개 도메인에 그대로 서빙되고 있었고,
  // 보안 구멍은 아니지만 부품 이름·렌더러 상태·되감기 조작부까지 내부가 드러난다.
  // 막는 규칙을 세우는 대신 **안 굽는다** — 규칙은 다음 사람이 풀 수 있지만 없는
  // 파일은 못 연다.
  //
  // **개발에서는 그대로 쓴다.** vite 개발 서버는 설정 없이도 루트의 html 을 서빙하므로
  // `npm run dev` 에서 셋 다 열린다. 타입 검사도 그대로 돈다(`tsc --noEmit` 은 이
  // 목록이 아니라 tsconfig 를 본다) — 빠진 것은 굽기뿐이다.
  //
  // 카탈로그를 App.tsx 안에 숨기지 않은 이유는 수명이 다르기 때문이다 — 부품을 보는
  // 페이지와 부품을 쓰는 화면이 한 파일을 나눠 쓰면 전투 화면 작업과 계속 충돌한다.
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('index.html', import.meta.url)),
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
