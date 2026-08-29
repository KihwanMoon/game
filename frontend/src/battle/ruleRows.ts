/**
 * 규칙표 한 줄이 화면에 나갈 형태 — 데스크톱 세 열과 모바일 시트가 **같은 표를 쓴다.**
 *
 * 두 배치가 규칙 줄을 각자 만들면 언젠가 한쪽만 실측값을 병기하거나 한쪽만 누적 CPU 를
 * 적는 상태가 된다. 그것은 화면 폭에 따라 플레이어가 다른 정보를 받는다는 뜻이고,
 * 이 게임에서 규칙표는 장식이 아니라 판단의 근거이므로 그런 차이를 두면 안 된다 (P1).
 *
 * 여기서 하는 일은 **추적 결과를 규칙표 순서에 다시 얹는 것**뿐이다. 판정 자체는
 * `ruleTrace` 가 코어의 계획에서 얻는다 — 그 경계를 다시 계산하지 않는다.
 */

import type { BlockCatalog, Rule } from '../core/schemas'
import type { RuleRowState } from '../ds'
import { formatActionText, formatPendingCondition, type RuleTrace } from './ruleTrace'

/** 화면이 그릴 규칙 줄 하나. `RuleRow` 의 props 와 짝이 맞는다. */
export interface RuleRowView {
  /** 우선순위. RuleRow 의 index 다. */
  readonly priority: number
  readonly state: RuleRowState
  /** 실측값이 병기된 조건문. */
  readonly condition: string
  /** 행동절. */
  readonly action: string
  /** 이 줄까지의 누적 CPU 와 예산. */
  readonly cpu: { readonly used: number; readonly budget: number }
  /** 이번 틱에 실제로 발동했는가. */
  readonly armed: boolean
  /** 켜져 있는가. 꺼진 줄은 판에 실리지 않으므로 추적 결과도 없다. */
  readonly enabled: boolean
}

/** `buildRuleRows` 가 받는 값들. */
export interface RuleRowsInput {
  /** 규칙표 전량. **꺼진 줄까지 포함한다** — 화면은 끈 줄도 보여야 다시 켤 수 있다. */
  readonly rules: readonly Rule[]
  /** 이번 틱의 추적 결과. 아직 한 틱도 돌지 않았으면 undefined. */
  readonly trace: RuleTrace | undefined
  readonly catalog: BlockCatalog
  /** 플레이어 CPU 예산. */
  readonly cpuBudget: number
  /** 꺼진 규칙의 우선순위들. 오름차순이며 비어 있으면 전부 켜진 것이다. */
  readonly disabled: readonly number[]
}

/**
 * 규칙표를 화면이 그릴 줄들로 바꾼다.
 *
 * @param input 규칙표·추적 결과·블록 카탈로그·CPU 예산·꺼진 우선순위들.
 * @returns 규칙표 순서 그대로의 줄들.
 */
export function buildRuleRows(input: RuleRowsInput): readonly RuleRowView[] {
  return input.rules.map((rule) => {
    const enabled = !input.disabled.includes(rule.priority)
    // 꺼진 줄은 판에 실리지 않는다. 추적 결과가 없는 것이 정상이므로 찾지 않는다.
    const traced = enabled
      ? input.trace?.rows.find((one) => one.priority === rule.priority)
      : undefined
    return {
      priority: rule.priority,
      state: traced?.state ?? ('pending' as RuleRowState),
      condition: traced?.condition ?? formatPendingCondition(rule, input.catalog),
      action: traced?.action ?? formatActionText(rule, input.catalog),
      cpu: { used: traced?.cpuUsed ?? rule.cpuCost, budget: input.cpuBudget },
      armed: traced?.armed ?? false,
      enabled,
    }
  })
}
