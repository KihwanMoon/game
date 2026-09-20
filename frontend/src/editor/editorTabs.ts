/**
 * 규칙표 탭의 계약 — `RuleEditor` 와 `RuleEditMobile` 이 함께 쓴다.
 *
 * **따로 사는 이유는 순환 참조다.** 에디터가 모바일 화면을 부르고 모바일 화면이 탭
 * 계약을 읽으므로, 계약이 에디터 안에 있으면 값(`COMBAT_TAB_ID`)을 가져오는 순간 두
 * 모듈이 서로를 부른다.
 */
import type { ReactNode } from 'react'

/**
 * 에디터 탭 하나 — **화면 하나를 통째로 갈아 끼운다.**
 *
 * 처음에는 규칙표만 둘이었다(전투·정비). 그런데 곁다리 패널들이 **서랍이라는 또 하나의
 * 탭 줄** 안에 살고 있어서, 화면에 탭 줄이 둘이 됐다 — 「가방」에 가려면 규칙표 탭에서
 * 서랍을 찾고 서랍 안에서 가방을 골라야 했다. **어느 탭 안의 어느 탭인지를 외우게 하는
 * 구조**이고, 두 줄이 서로 다른 것을 뜻한다는 근거도 없었다. 그래서 한 줄로 폈다.
 *
 * **팔레트·검증은 있을 수도 없을 수도 있다.** 규칙표 탭은 셋을 다 쓰고(팔레트·본문·검증),
 * 가방·세계 같은 탭은 본문 하나다 — 없는 열을 빈 채로 세우면 화면의 3분의 2가 빈다.
 *
 * **팔레트를 본문과 함께 받는 이유**는 둘이 한 몸이기 때문이다. 본문만 갈아 끼우면
 * 정비 규칙을 고치는 동안 왼쪽에 전투 블록 팔레트가 남고, 그것을 누르면 **안 보이는
 * 규칙표가 바뀐다.**
 */
export interface EditorTab {
  readonly id: string
  readonly label: string
  /** 가운데 본문. 탭이 반드시 가진 하나다. 편집기 탭은 `null` 이다 — 아래를 본다. */
  readonly main: ReactNode
  /**
   * 이 탭이 곧 규칙 편집기인가.
   *
   * **본문을 안 받는다.** 편집기는 규칙 목록·카드·팔레트를 스스로 그리므로 밖에서
   * 넘길 수 있는 조각이 아니다 — 그래서 `main` 이 `null` 이고 이 표시가 대신한다.
   *
   * **탭 줄에 박아 두지 않으려고 생겼다** (2026-09-20). 예전에는 전투 버튼이 코드에
   * 맨 앞으로 박혀 있어서 **순서를 부르는 쪽이 못 정했다** — 무엇을 첫 탭으로 둘지는
   * 화면 구성의 일이지 이 부품의 일이 아니다.
   */
  readonly isEditor?: boolean
  /** 왼쪽 팔레트 열. 없으면 본문이 폭을 쓴다. */
  readonly palette?: ReactNode
  /** 오른쪽 검증 열. 없으면 본문이 폭을 쓴다. */
  readonly check?: ReactNode
  /** 상단 바의 계량. 전투는 CPU 게이지, 정비는 행 수·잔액이 여기 선다. */
  readonly gauge?: ReactNode
  /** 하단 바의 안내. */
  readonly foot?: ReactNode
}

/**
 * 이 탭이 세 열을 쓰는가.
 *
 * @param tab 볼 탭.
 * @returns 팔레트나 검증이 하나라도 있으면 참.
 */
export function checkWideTab(tab: EditorTab): boolean {
  return tab.palette !== undefined || tab.check !== undefined
}

/** 전투 내력 탭의 id. 편집기 자체인 탭이며, 자리는 부르는 쪽이 정한다. */
export const COMBAT_TAB_ID = 'combat'
