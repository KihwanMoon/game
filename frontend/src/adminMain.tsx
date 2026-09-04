/**
 * 관리 화면의 컴포지션 루트.
 *
 * **게임 화면에서 갈라 둔 이유는 폭이다.** 관리 화면은 표와 격자가 폭을 다 써야 하는데,
 * 게임 화면의 탭 하나는 좁아서 표와 격자가 폭을 다 쓰지 못했다.
 *
 * **경로의 존재는 드러나지만 데이터는 안 드러난다.** 관리 API 는 여전히 404 로 답하고,
 * 이 페이지는 관리자가 아니면 아무것도 못 그린다 — 그 사실만 말한다.
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import '@design/styles.css'
import './styles/app.css'
import './editor/editor.css'
import { AdminScreen } from './admin/AdminScreen'
import { loadContentPack } from './content/pack'

const container = document.getElementById('root')
if (container === null) {
  throw new Error('#root 를 찾지 못했다')
}

/**
 * 팩을 먼저 받고 그린다. 게임 화면과 같은 순서다 — 관리 화면도 지금 도는 자산을 봐야
 * 하고, 그러지 않으면 편집 대상이 화면과 어긋난다.
 */
async function startAdmin(): Promise<void> {
  await loadContentPack()
  createRoot(container as HTMLElement).render(
    <StrictMode>
      <AdminScreen />
    </StrictMode>,
  )
}

void startAdmin()
