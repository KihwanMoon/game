/**
 * 캐릭터 시트 — 지금 내 전투 입력이 무엇인가 (결정 #13, #51).
 *
 * **이 화면이 없으면 규칙을 짤 수 없다.** 이 게임의 규칙은 `적거리 <= 사거리` 처럼 자기
 * 스탯을 참조하는데, 자기 사거리를 볼 데가 없으면 그 조건이 언제 참이 되는지 모른 채
 * 쓰게 된다. 활을 끼우면 같은 규칙표가 저절로 다르게 도는 것이 이 게임의 설계인데
 * (결정 #13), 무엇이 달라졌는지 보이지 않으면 그 설계가 유저에게 닿지 않는다.
 *
 * **각 항의 출처를 병기한다.** 디자인 §8.2 가 조건문에 실측값을 함께 적으라고 한 것과
 * 같은 이유다 — 「공격 25」만 적으면 그것이 장비 덕인지 능력치 덕인지 알 수 없고,
 * 그러면 다음에 무엇을 바꿔야 할지도 알 수 없다.
 *
 * **장착하지 않은 스킬을 함께 보여준다.** 규칙 에디터의 「불가」 상태가 왜 떴는지는
 * 여기서만 답할 수 있다 — 그 스킬을 여는 장비를 안 끼고 있다는 것이 답이다.
 */
import { buildAttributeBonus } from '../core/progression/attributes'
import { GlyphState, Panel, ValueExpr } from '../ds'
import type { ProgressView } from '../storage'

export interface CharacterPanelProps {
  readonly progress: ProgressView | undefined
  /** balance.json 의 플레이어 기본 스탯. 출처를 가르는 기준점이다. */
  readonly baseStats: Readonly<Record<string, number>>
  /** 이 코어가 아는 스킬 전부. 장착하지 않은 것을 「불가」로 보여주는 데 쓴다. */
  readonly allSkills: readonly string[]
  readonly isOnline: boolean
}

const OFFLINE_HINT = '서버에 닿지 못했다 — 장비와 능력치는 서버가 안다'

/** 전투 스탯 한 줄. 화면에 적는 순서가 곧 이 배열의 순서다. */
const COMBAT_ROWS: readonly { readonly key: string; readonly label: string }[] = [
  { key: 'hpMax', label: '최대체력' },
  { key: 'attack', label: '공격력' },
  { key: 'defense', label: '방어력' },
  { key: 'attackRange', label: '사거리' },
  { key: 'initiative', label: '선공권' },
]

/** 전투 스탯 이름에서 balance.json 의 열쇠로. 두 이름이 다른 것은 표기 규약 차이다. */
const BASE_KEYS: ReadonlyMap<string, string> = new Map([
  ['hpMax', 'hp_max'],
  ['attack', 'attack'],
  ['defense', 'defense'],
  ['attackRange', 'attack_range'],
  ['initiative', 'initiative'],
])

/**
 * 값 하나를 「기본 + 장비 + 능력치 = 최종」으로 쪼갠다.
 *
 * **장비 몫은 빼서 구한다.** 장비는 퍼센트 접사를 쓸 수 있어 한 항으로 떨어지지 않는데,
 * 레벨과 능력치 몫은 정확히 알므로 나머지가 장비다. 이 방식이라 합이 언제나 최종과 같다.
 *
 * @param final 서버가 확정한 최종값.
 * @param base balance.json 의 기본값.
 * @param fromAttributes 능력치가 준 몫.
 * @param fromLevel 레벨이 준 몫.
 * @returns 화면에 적을 네 값.
 */
export function splitStatSources(
  final: number,
  base: number,
  fromAttributes: number,
  fromLevel: number,
): { base: number; gear: number; attributes: number; level: number; final: number } {
  return {
    base,
    gear: final - base - fromAttributes - fromLevel,
    attributes: fromAttributes,
    level: fromLevel,
    final,
  }
}

/**
 * 가산분을 부호와 함께 적는다. 0 이면 가운뎃점이다 — 「+0」이 줄마다 늘어서면 읽히지 않는다.
 *
 * @param value 가산분.
 * @param suffix 단위. 퍼센트 줄에만 쓴다.
 * @returns 화면에 적을 문자열.
 */
export function formatDelta(value: number, suffix = ''): string {
  if (value === 0) {
    return '·'
  }
  return `${value > 0 ? '+' : ''}${String(value)}${suffix}`
}

/**
 * 캐릭터 시트를 그린다.
 *
 * @param props 성장 상태와 기준값.
 * @returns 패널 요소.
 */
export function CharacterPanel(props: CharacterPanelProps): React.JSX.Element {
  const { progress, baseStats, allSkills, isOnline } = props
  const loadout = progress?.loadout
  const bonus = buildAttributeBonus(progress?.stats ?? {})
  const equipped = new Set(loadout?.skills ?? [])

  return (
    <Panel
      title="캐릭터"
      meta={progress === undefined ? '' : `레벨 ${String(progress.level)}`}
      tone="panel"
      padded
      scroll
    >
      <div className="chr">
        {!isOnline || loadout === undefined || progress === undefined ? (
          <ValueExpr text={OFFLINE_HINT} size="sm" dim />
        ) : (
          <>
            <div className="chr__head">전투 입력 · 기본 · 장비 · 능력치 = 최종</div>
            <ul className="chr__list">
              {COMBAT_ROWS.map((row) => {
                const base = baseStats[BASE_KEYS.get(row.key) ?? ''] ?? 0
                const split = splitStatSources(
                  loadout[row.key as 'attack'],
                  base,
                  bonus[row.key as 'attack'] ?? 0,
                  0,
                )
                return (
                  <li className="chr__row" key={row.key}>
                    <span className="chr__label">{row.label}</span>
                    <ValueExpr
                      text={`${String(split.base)} ${formatDelta(split.gear)} ${formatDelta(split.attributes)}`}
                      size="sm"
                      dim
                    />
                    <ValueExpr text={`= ${String(split.final)}`} size="sm" />
                  </li>
                )
              })}
            </ul>

            <div className="chr__head">규칙 예산</div>
            <ul className="chr__list">
              <li className="chr__row">
                <span className="chr__label">CPU</span>
                <ValueExpr
                  text={`${String(baseStats.cpu_budget ?? 0)} ${formatDelta(progress.bonusCpu)} ${formatDelta(bonus.cpuBudget)}`}
                  size="sm"
                  dim
                />
                <ValueExpr text={`= ${String(loadout.cpuBudget)}`} size="sm" />
              </li>
              <li className="chr__row">
                <span className="chr__label">규칙 슬롯</span>
                <ValueExpr
                  text={`${String(baseStats.rule_slots ?? 0)} ${formatDelta(progress.bonusRuleSlots)} ·`}
                  size="sm"
                  dim
                />
                <ValueExpr text={`= ${String(loadout.ruleSlots)}`} size="sm" />
              </li>
              <li className="chr__row">
                <span className="chr__label">스킬위력</span>
                <ValueExpr
                  text={`100% · ${formatDelta(loadout.skillPowerPct - 100, '%')}`}
                  size="sm"
                  dim
                />
                <ValueExpr text={`= ${String(loadout.skillPowerPct)}%`} size="sm" />
              </li>
            </ul>

            <div className="chr__head">스킬 · 장착한 것만 규칙에 쓸 수 있다</div>
            <ul className="chr__list">
              {allSkills.map((skill) => (
                <li className="chr__row" key={skill}>
                  <GlyphState
                    state={equipped.has(skill) ? 'true' : 'blocked'}
                    size="sm"
                    label={skill}
                  />
                  {equipped.has(skill) ? null : (
                    <ValueExpr text="이 스킬을 여는 장비를 끼면 열린다" size="sm" dim />
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </Panel>
  )
}
