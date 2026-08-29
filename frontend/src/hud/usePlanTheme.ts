/**
 * 도면 테마를 토큰에서 읽어 오는 훅.
 *
 * 캔버스는 CSS 를 상속하지 않으므로 색과 치수를 값으로 받아야 한다(`battle/planTheme.ts`).
 * 읽는 일은 그쪽 함수가 하고, 여기서는 **언제 읽는가**만 정한다 — 렌더 중에 읽으면 서버
 * 렌더에 `document` 가 없어 터진다. 그래서 마운트 뒤 한 번 읽는다.
 *
 * 값을 못 읽은 동안은 undefined 다. 화면은 그동안 도면을 그리지 않는다 — 기본값을 채워
 * 두면 토큰이 사라진 화면이 "조금 다른 색" 으로 조용히 그려진다.
 */
import { useEffect, useState } from 'react'

import { createTokenReader, readBatchIntervalMs, readPlanTheme } from '../battle'
import type { PlanTheme } from '../battle'

/** 토큰에서 읽어 온 값들. */
export interface PlanThemeState {
  readonly theme: PlanTheme | undefined
  /** 프레임 하나를 넘기는 간격(ms). `--dur-tick` 에서 온다. */
  readonly intervalMs: number
}

/**
 * 마운트 뒤 한 번 토큰을 읽는다.
 *
 * @returns 도면 테마와 재생 간격. 아직 읽지 못했으면 테마는 undefined, 간격은 0 이다.
 */
export function usePlanTheme(): PlanThemeState {
  const [state, setState] = useState<PlanThemeState>({ theme: undefined, intervalMs: 0 })

  useEffect(() => {
    const read = createTokenReader(document.documentElement)
    setState({ theme: readPlanTheme(read), intervalMs: readBatchIntervalMs(read) })
  }, [])

  return state
}
