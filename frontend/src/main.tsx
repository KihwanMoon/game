/** 컴포지션 루트. 디자인 토큰과 앱 스타일을 이 지점에서 배선한다. */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// 토큰 CSS 는 별칭 `@design` 으로 원본을 직접 읽는다. 사본을 두지 않으려는 것이다.
import '@design/styles.css'
import './styles/app.css'
// ds.css 는 `src/ds` 배럴이 스스로 싣는다. 여기서 또 부르면 같은 규칙이 두 번 들어간다.
import './editor/editor.css'
import { App } from './App'
import { loadContentPack } from './content/pack'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

/**
 * 콘텐츠 팩을 먼저 받고 그린다.
 *
 * **렌더 전에 한 번만 갈아 끼운다** (설계/4_아이템 §18). 도는 중에 바꾸면 같은 판이
 * 중간에 다른 데이터로 돌고, 그것이 R5 가 막으려는 것이다.
 *
 * 실패해도 그린다 — 번들에 박힌 것으로 돌면 되고, 그것이 "서버가 없어도 게임은 돈다" 를
 * 지키는 자리다. 기다리는 것은 한 번의 fetch 뿐이라 첫 화면이 눈에 띄게 늦지 않는다.
 */
async function startApp(): Promise<void> {
  await loadContentPack()
  createRoot(container as HTMLElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void startApp()
