/**
 * 부품 카탈로그의 컴포지션 루트. `/ds.html` 이 이 파일을 부른다.
 *
 * 제품 화면(`src/main.tsx`)과 분리한 이유는 App.tsx 를 건드리지 않기 위해서다. 카탈로그는
 * 부품을 보는 곳이고 제품 화면은 부품을 쓰는 곳이라 수명이 다르다 — 한 파일을 두 목적이
 * 나눠 쓰면 전투 화면을 짜는 쪽과 계속 충돌한다.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@design/styles.css'
import { Gallery } from './gallery'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

createRoot(container).render(
  <StrictMode>
    <Gallery />
  </StrictMode>,
)
