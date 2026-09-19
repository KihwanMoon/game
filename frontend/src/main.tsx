/** 컴포지션 루트. 디자인 토큰과 앱 스타일을 이 지점에서 배선한다. */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// 토큰 CSS 는 별칭 `@design` 으로 원본을 직접 읽는다. 사본을 두지 않으려는 것이다.
import '@design/styles.css'
import './styles/app.css'
// ds.css 는 `src/ds` 배럴이 스스로 싣는다. 여기서 또 부르면 같은 규칙이 두 번 들어간다.
import './editor/editor.css'
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
  // **앱을 여기서 들인다 — 정적 import 면 안 된다.** ESM 은 이 파일의 본문보다 import 한
  // 모듈의 본문을 먼저 돌린다. `App` 을 위에서 정적으로 들이면 App 의 본문이
  // `loadContentPack()` 보다 **먼저** 돌고, 거기서 `readActivePack()` 으로 잡아 둔
  // 카탈로그·방·적·밸런스가 전부 번들로 굳는다 — 발행한 것이 화면에 한 번도 안 닿는다.
  //
  // 2026-09-19 에 「재주 이름을 고쳐 발행했는데 그대로다」로 드러났다. 이름만이 아니라
  // **팩 전체**가 안 닿고 있었고, 한 번도 발행한 적이 없어서(운영 `published=0`) 여태
  // 안 보였을 뿐이다. 늦게 들이면 App 과 그것이 끌어오는 모듈 전부가 갈아 끼운 뒤에 돈다.
  const { App } = await import('./App')
  createRoot(container as HTMLElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void startApp()
