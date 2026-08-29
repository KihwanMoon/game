/**
 * 블록 팔레트 — 인지 / 행동 / 셀렉터 (GDD §8.1 좌측).
 *
 * 목록은 전부 `blocks.json` 에서 온다. 여기서 클릭 하나가 규칙표를 한 단계 진전시킨다.
 *
 * - 인지 변수: **새 규칙**을 만들고 그 변수를 조건으로 넣는다. 비교와 값은 기본값이
 *   채워져 나오므로 만든 즉시 검증을 통과한다.
 * - 행동 / 셀렉터: **선택된 규칙**의 THEN 절과 TARGET 절을 바꾼다.
 *
 * 팔레트에서 규칙표로 드래그하지 않는 이유가 둘이다. 드래그는 클릭보다 느리고, 키보드로는
 * 재현할 수 없다 — 키보드만으로 규칙 하나를 완성할 수 있어야 한다는 요구를 드래그 전용
 * 팔레트는 처음부터 만족할 수 없다. 순서 바꾸기에만 드래그를 쓴다.
 */
import { Button, Panel } from '../ds'
import type { BlockCatalog } from '../core/schemas'
import { listActionGroups, listPerceptionGroups, listSelectors } from './blockOptions'

/** PalettePanel 의 props. */
export interface PalettePanelProps {
  readonly catalog: BlockCatalog
  readonly hasSelection: boolean
  /** 행동·셀렉터가 적용될 규칙의 번호. 선택이 어디인지 글로도 적는다. */
  readonly selectedPriority?: number | undefined
  readonly onPickPerception: (blockId: string) => void
  readonly onPickAction: (actionId: string) => void
  readonly onPickSelector: (selectorId: string) => void
}

/**
 * 팔레트를 그린다.
 *
 * @param props 카탈로그와 콜백들.
 * @returns 렌더 트리.
 */
export function PalettePanel(props: PalettePanelProps): React.JSX.Element {
  const { catalog } = props
  const meta = `${String(catalog.perceptions.size)}·${String(catalog.actions.size)}·${String(catalog.selectors.size)}`

  return (
    <Panel title="블록 팔레트" meta={meta} padded={false} scroll>
      <div className="palette">
        <p className="palette__hint">
          인지 변수를 누르면 그 조건으로 규칙이 하나 생긴다. 행동·셀렉터는{' '}
          {props.selectedPriority === undefined
            ? '선택된 규칙'
            : `선택된 규칙 [${String(props.selectedPriority)}]`}
          에 적용된다.
        </p>

        <section className="palette__section">
          <h3 className="palette__kind">인지 변수</h3>
          {listPerceptionGroups(catalog).map((group) => (
            <div className="palette__group" key={group.category}>
              <span className="palette__group-name">{group.labelKo}</span>
              {group.blocks.map((item) => (
                <Button
                  key={item.blockId}
                  variant="ghost"
                  size="sm"
                  block
                  glyph={item.returns === 'bool' ? '◇' : '#'}
                  title={item.param === null ? item.blockId : `${item.blockId}[${item.param.name}]`}
                  onClick={() => { props.onPickPerception(item.blockId) }}
                >
                  {item.labelKo}
                </Button>
              ))}
            </div>
          ))}
        </section>

        <section className="palette__section">
          <h3 className="palette__kind">행동</h3>
          {listActionGroups(catalog).map((group) => (
            <div className="palette__group" key={group.category}>
              <span className="palette__group-name">{group.labelKo}</span>
              {group.blocks.map((item) => (
                <Button
                  key={item.blockId}
                  variant="ghost"
                  size="sm"
                  block
                  glyph={item.targeted ? '▷' : '□'}
                  disabled={!props.hasSelection}
                  title={item.blockId}
                  onClick={() => { props.onPickAction(item.blockId) }}
                >
                  {item.labelKo}
                </Button>
              ))}
            </div>
          ))}
        </section>

        <section className="palette__section">
          <h3 className="palette__kind">셀렉터</h3>
          <div className="palette__group">
            {listSelectors(catalog).map((item) => (
              <Button
                key={item.blockId}
                variant="ghost"
                size="sm"
                block
                glyph="◎"
                disabled={!props.hasSelection}
                title={item.blockId}
                onClick={() => { props.onPickSelector(item.blockId) }}
              >
                {item.labelKo}
              </Button>
            ))}
          </div>
        </section>
      </div>
    </Panel>
  )
}
