/**
 * 추천 규칙표 — 백지에서 시작하지 않게 한다.
 *
 * 규칙 하나를 만들려면 인지 20종·행동 16종·셀렉터 9종에서 여덟 번쯤 골라야 하고, 그
 * 전에 **무엇을 만들지를 스스로 정해야 한다.** 처음 여는 사람이 막히는 곳은 문법이 아니라
 * 그 백지다.
 *
 * 그래서 여기 있는 것은 새로 쓴 것이 아니다. 저장소에 이미 있던 예시 3벌과 벤치마크
 * 13벌이고, 전부 시작 예산(슬롯 5 · CPU 8) 안에 들며 골든이 매일 돌려 검증한다 — 화면에서
 * 닿을 수 없었을 뿐이다.
 *
 * **불러오면 편집 한 단계로 쌓인다.** Ctrl+Z 로 되돌아가므로 "눌렀다가 내 것이 사라졌다"
 * 가 되지 않는다. 공유 코드 불러오기가 이미 쓰는 방식과 같다.
 */
import { useState } from 'react'

import { formatRuleSentence } from './ruleSentence'
import { Button, Panel, ValueExpr } from '../ds'
import type { BlockCatalog, RuleSet } from '../core/schemas'
import type { RuleTemplate } from '../core/resources'

export interface TemplatePanelProps {
  readonly templates: readonly RuleTemplate[]
  readonly catalog: BlockCatalog
  /** 지금 쓸 수 있는 CPU. 예산을 넘는 것은 넘는다고 적는다 — 막지는 않는다. */
  readonly cpuBudget: number
  readonly ruleSlots: number
  readonly onLoad: (ruleset: RuleSet) => void
}

/**
 * 추천 규칙표 목록을 그린다.
 *
 * @param props 템플릿들과 예산, 불러오기 콜백.
 * @returns 패널 요소.
 */
/** 목록 한 줄이 받는 props. */
export interface TemplateRowProps {
  readonly template: RuleTemplate
  readonly catalog: BlockCatalog
  readonly cpuBudget: number
  readonly ruleSlots: number
  readonly isOpen: boolean
  readonly onToggle: (templateId: string) => void
  readonly onLoad: (ruleset: RuleSet) => void
}

/**
 * 추천 규칙표 한 줄을 그린다.
 *
 * 훅을 쓰지 않는다 — 펼침 상태는 패널이 들고 있다. 그래야 검사가 이 함수를 그냥 불러
 * 버튼 하나를 눌러 볼 수 있다.
 *
 * @param props 템플릿 한 벌과 예산, 콜백들.
 * @returns 렌더 트리.
 */
export function TemplateRow(props: TemplateRowProps): React.JSX.Element {
  const { template, catalog } = props
  const isOver =
    template.cpuTotal > props.cpuBudget || template.ruleset.rules.length > props.ruleSlots

  return (
    <li className="tpl__entry">
      <div className="tpl__row">
        <span className="tpl__name">{template.templateId}</span>
        <ValueExpr
          text={`규칙 ${String(template.ruleset.rules.length)} · cpu ${String(template.cpuTotal)} / ${String(props.cpuBudget)}`}
          size="sm"
          dim={!isOver}
        />
      </div>
      {template.strategyKo === '' ? null : <ValueExpr text={template.strategyKo} size="sm" />}
      <div className="tpl__row">
        <Button
          size="sm"
          variant="ghost"
          glyph={props.isOpen ? '▾' : '▸'}
          title="이 규칙표가 무엇을 하는지 한 줄씩 읽는다"
          onClick={() => {
            props.onToggle(template.templateId)
          }}
        >
          미리보기
        </Button>
        <Button
          size="sm"
          variant="primary"
          title="편집기로 불러온다 (되돌리기로 되돌아간다)"
          onClick={() => {
            props.onLoad(template.ruleset)
          }}
        >
          불러오기
        </Button>
      </div>
      {props.isOpen ? (
        <ol className="tpl__rules">
          {template.ruleset.rules.map((rule) => (
            <li className="tpl__rule" key={rule.priority}>
              <ValueExpr
                text={`${String(rule.priority)}. ${formatRuleSentence(rule, catalog)}`}
                size="sm"
              />
            </li>
          ))}
        </ol>
      ) : null}
    </li>
  )
}

/**
 * 추천 규칙표 목록을 그린다.
 *
 * @param props 템플릿들과 예산, 불러오기 콜백.
 * @returns 패널 요소.
 */
export function TemplatePanel(props: TemplatePanelProps): React.JSX.Element {
  const [openId, setOpenId] = useState<string | undefined>(undefined)

  return (
    <Panel
      title="규칙표 고르기"
      meta={`${String(props.templates.length)}벌`}
      tone="panel"
      padded
      scroll
    >
      <div className="tpl">
        <ValueExpr text="고른 것을 불러와 고치는 편이 백지에서 짜는 것보다 빠르다" size="sm" dim />
        <ul className="tpl__list">
          {props.templates.map((item) => (
            <TemplateRow
              key={item.templateId}
              template={item}
              catalog={props.catalog}
              cpuBudget={props.cpuBudget}
              ruleSlots={props.ruleSlots}
              isOpen={openId === item.templateId}
              onToggle={(templateId) => {
                setOpenId(openId === templateId ? undefined : templateId)
              }}
              onLoad={props.onLoad}
            />
          ))}
        </ul>
      </div>
    </Panel>
  )
}
