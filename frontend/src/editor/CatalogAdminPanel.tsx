/**
 * 카탈로그 관리 — 조회·등록·폐기 (설계/4_아이템 §15.7).
 *
 * **삭제 버튼이 없다.** 인스턴스·원장·경매가 `catalog_id` 를 가리키므로 지우면 과거
 * 기록을 못 읽는다. 폐기는 "새로 안 나온다" 만 뜻하고, 폐기된 것도 목록에 남는다.
 *
 * **접사·등급·분류는 여기서 못 고친다.** 고치면 이미 나온 아이템이 소급해 바뀐다 —
 * 인스턴스가 굴린 접사가 없으면 카탈로그 기본값을 쓰기 때문이다. 서버가 409 로 거절하고,
 * 화면은 그 사유를 그대로 적는다. 고칠 수 있는 것은 이름과 최소 층뿐이다.
 *
 * **세대를 머리에 적는다.** 아이템을 고치는 것은 순위표 시즌을 가르는 일이고, 그
 * 사실이 조작 전에 눈에 있어야 한다.
 */
import { useState } from 'react'

import { Button, CellGrid, GlyphState, Panel, Thumb, ValueExpr } from '../ds'
import type { CatalogAdminRow, CatalogAdminView, CatalogAffixSpec } from '../storage'

export interface CatalogAdminPanelProps {
  readonly catalog: CatalogAdminView | undefined
  readonly detail: string
  readonly onRetire: (catalogId: string, isRetired: boolean, reason: string) => void
  /** 이름과 최소 층을 고친다. 나머지는 서버가 저장된 값을 그대로 쓴다 (§15.7). */
  readonly onEdit: (catalogId: string, patch: Record<string, unknown>, reason: string) => void
  /** 새 종류를 등록한다. 절은 서버의 파서가 검사한다 — 화면이 문법을 따로 알 필요가 없다. */
  readonly onCreate: (payload: Record<string, unknown>, reason: string) => void
}

/** 신규 등록 폼이 받는 props. */
export interface CatalogFormProps {
  readonly grades: readonly string[]
  readonly stats: readonly string[]
  readonly onCreate: (payload: Record<string, unknown>, reason: string) => void
}

/** 장비 슬롯. 카탈로그가 쓰는 값 그대로다 — 화면이 새 이름을 지으면 서버가 못 읽는다. */
const SLOTS: readonly string[] = ['WEAPON_MAIN', 'WEAPON_OFF', 'HEAD', 'BODY', 'FEET', 'HANDS']

const KINDS: readonly string[] = ['EQUIPMENT', 'CONSUMABLE', 'QUEST']

/**
 * 접사가 붙을 수 있는 능력치의 **바닥값**.
 *
 * 정본은 서버가 들고 있고 카탈로그 응답에 실려 온다. 이것은 서버가 아직 안 준 순간에만
 * 쓴다 — 화면이 목록을 정본으로 삼으면, 서버가 아는 이름이 늘어도 화면은 옛 목록을
 * 내보이고 사람은 그것이 전부라고 읽는다.
 *
 * 이 목록은 `blocks.json` 의 `rhs_stats` 와 같아야 한다 — 규칙표가 읽지 못하는 능력치에
 * 접사를 붙이면 그 아이템은 성능이 있는데 규칙으로는 안 보인다.
 */
const FALLBACK_STATS: readonly string[] = [
  'attack',
  'defense',
  'hp_max',
  'attack_range',
  'cpu_budget',
  'initiative',
]

/**
 * 고를 수 있는 능력치 목록을 정한다.
 *
 * @param served 서버가 보낸 정본.
 * @returns 서버 목록. 비어 있으면 바닥값.
 */
export function listAffixStats(served: readonly string[]): readonly string[] {
  return served.length === 0 ? FALLBACK_STATS : served
}

const DECIMAL_RADIX = 10

/** 접사 한 줄. 칸은 글자로 들고 있다가 보낼 때 숫자로 바꾼다. */
export interface AffixRow {
  readonly stat: string
  readonly flat: string
  readonly percent: string
  readonly labelKo: string
}

/**
 * 접사 줄 하나를 고친다.
 *
 * @param rows 지금 줄들.
 * @param index 고칠 자리.
 * @param patch 덮어쓸 값.
 * @returns 새 줄들.
 */
export function buildAffixRows(
  rows: readonly AffixRow[],
  index: number,
  patch: Partial<AffixRow>,
): readonly AffixRow[] {
  return rows.map((row, at) => (at === index ? { ...row, ...patch } : row))
}

/**
 * 접사 줄들을 서버가 읽는 절로 바꾼다.
 *
 * **빈 줄은 버린다.** 능력치만 고르고 값을 안 넣은 줄을 보내면 아무 효과 없는 접사가
 * 아이템에 붙고, 화면에는 이름만 뜬다.
 *
 * @param rows 접사 줄들.
 * @returns 서버가 읽는 절들.
 */
export function buildAffixPayload(rows: readonly AffixRow[]): Record<string, unknown>[] {
  return rows
    .filter((row) => row.flat.trim() !== '' || row.percent.trim() !== '')
    .map((row) => ({
      stat: row.stat,
      flat: Number.parseInt(row.flat, DECIMAL_RADIX) || 0,
      percent: Number.parseInt(row.percent, DECIMAL_RADIX) || 0,
      // **비워 두면 비워 둔 채로 보낸다.** 예전에는 능력치 키를 이름으로 박아서,
      // 이름 칸을 안 채운 아이템이 게임 안에서 「attack +3」 처럼 영어로 떴다.
      // 이름이 없으면 서버가 능력치의 한글 이름으로 적는다.
      label_ko: row.labelKo,
    }))
}

/**
 * 아이템 종류를 새로 등록하는 폼.
 *
 * **접사는 JSON 으로 받는다.** 접사는 개수가 정해져 있지 않고 stat·flat·percent·label 이
 * 함께 가는 절이라, 칸을 늘렸다 줄였다 하는 UI 를 만드는 것보다 절을 그대로 받고 서버의
 * 파서가 검사하게 하는 편이 정확하다 — 화면이 문법을 따로 알면 두 규칙이 생긴다.
 *
 * @param props 등급 목록과 콜백.
 * @returns 렌더 트리.
 */
export function CatalogForm(props: CatalogFormProps): React.JSX.Element {
  const statNames = listAffixStats(props.stats)
  const [id, setId] = useState('')
  const [kind, setKind] = useState('EQUIPMENT')
  const [slot, setSlot] = useState('HEAD')
  const [label, setLabel] = useState('')
  const [grade, setGrade] = useState('COMMON')
  const [minFloor, setMinFloor] = useState('1')
  const [range, setRange] = useState('')
  const [useTag, setUseTag] = useState('')
  // **한 줄로 시작한다.** 빈 채로 시작하면 「접사 추가」를 먼저 찾아야 하고, 그러면
  // 접사가 있다는 것 자체를 모른 채 아이템을 만든다. 안 채운 줄은 어차피 안 보내진다.
  const [affixRows, setAffixRows] = useState<readonly AffixRow[]>([
    { stat: statNames[0] ?? '', flat: '', percent: '', labelKo: '' },
  ])
  const [reason, setReason] = useState('')

  return (
    <div className="cat__detail">
      <span className="cat__name">새 종류 등록</span>
      {/* 수정이 막혀 있으므로 등록이 유일한 변경 경로다. 그 사실을 여기에 적는다. */}
      <ValueExpr text="접사·등급을 바꾸려면 여기서 새로 등록하고 옛 id 를 폐기한다" size="sm" dim />
      <label className="cat__field">
        <span>id</span>
        <input
          className="cat__input"
          value={id}
          placeholder="sword_long"
          onChange={(event) => {
            setId(event.target.value)
          }}
        />
      </label>
      <label className="cat__field">
        <span>이름</span>
        <input
          className="cat__input"
          value={label}
          placeholder="장검"
          onChange={(event) => {
            setLabel(event.target.value)
          }}
        />
      </label>
      <div className="cat__row">
        {KINDS.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={name === kind ? 'primary' : 'ghost'}
            onClick={() => {
              setKind(name)
            }}
          >
            {name}
          </Button>
        ))}
      </div>
      {kind !== 'EQUIPMENT' ? null : (
        <div className="cat__row">
          {SLOTS.map((name) => (
            <Button
              key={name}
              size="sm"
              variant={name === slot ? 'primary' : 'ghost'}
              onClick={() => {
                setSlot(name)
              }}
            >
              {name}
            </Button>
          ))}
        </div>
      )}
      <div className="cat__row">
        {props.grades.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={name === grade ? 'primary' : 'ghost'}
            onClick={() => {
              setGrade(name)
            }}
          >
            {name}
          </Button>
        ))}
      </div>
      <label className="cat__field">
        <span>최소 층</span>
        <input
          className="cat__input"
          inputMode="numeric"
          value={minFloor}
          onChange={(event) => {
            setMinFloor(event.target.value)
          }}
        />
      </label>
      {/* 소모품의 쓰임새 (§4). **코드가 읽는 유일한 태그다** — 규칙표의
          `USE_ITEM[kind]` 가 이것을 가리킨다. 비워 두면 어느 규칙도 이 아이템을 못 쓴다. */}
      {kind !== 'CONSUMABLE' ? null : (
        <label className="cat__field">
          <span>쓰임새</span>
          <input
            className="cat__input"
            aria-label="쓰임새"
            value={useTag}
            placeholder="POTION"
            onChange={(event) => {
              setUseTag(event.target.value.toUpperCase())
            }}
          />
        </label>
      )}
      {/* 사거리는 무기의 것이다 (§2.2). 접사로 흉내내면 굴림에서 잘려 활이 근접무기가
          된다. **비워 두면 「안 정한다」** 이고, 0 은 아무것도 못 때리는 무기다. */}
      {!slot.startsWith('WEAPON') || kind !== 'EQUIPMENT' ? null : (
        <label className="cat__field">
          <span>사거리</span>
          <input
            className="cat__input"
            inputMode="numeric"
            aria-label="사거리"
            value={range}
            placeholder="비우면 기본 사거리"
            onChange={(event) => {
              setRange(event.target.value)
            }}
          />
        </label>
      )}
      {/* **접사를 칸으로 받는다.** JSON 을 손으로 치게 하면 따옴표 하나가 틀렸을 때
          서버가 거절하고, 그 사유는 아이템 이야기가 아니라 파서 이야기다. */}
      <span className="cat__name">접사</span>
      {affixRows.map((row, index) => (
        <div className="cat__row" key={`${String(index)}:${row.stat}`}>
          <select
            className="cat__input"
            aria-label={`접사 ${String(index + 1)} 능력치`}
            value={row.stat}
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { stat: event.target.value }))
            }}
          >
            {statNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <input
            className="cat__input"
            inputMode="numeric"
            aria-label={`접사 ${String(index + 1)} 고정값`}
            value={row.flat}
            placeholder="고정"
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { flat: event.target.value }))
            }}
          />
          <input
            className="cat__input"
            inputMode="numeric"
            aria-label={`접사 ${String(index + 1)} 퍼센트`}
            value={row.percent}
            placeholder="%"
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { percent: event.target.value }))
            }}
          />
          <input
            className="cat__input"
            aria-label={`접사 ${String(index + 1)} 이름`}
            value={row.labelKo}
            placeholder="예리함"
            onChange={(event) => {
              setAffixRows(buildAffixRows(affixRows, index, { labelKo: event.target.value }))
            }}
          />
        </div>
      ))}
      <Button
        size="sm"
        variant="ghost"
        glyph="＋"
        title="접사 칸을 하나 더 만든다"
        onClick={() => {
          setAffixRows([
            ...affixRows,
            { stat: statNames[0] ?? '', flat: '', percent: '', labelKo: '' },
          ])
        }}
      >
        접사 추가
      </Button>
      <label className="cat__field">
        <span>사유</span>
        <input
          className="cat__input"
          value={reason}
          placeholder="왜 넣는가 (4자 이상)"
          onChange={(event) => {
            setReason(event.target.value)
          }}
        />
      </label>
      <Button
        size="sm"
        variant="primary"
        disabled={id === ''}
        title="등록한다 — 코어 버전이 바뀌고 드롭 표에 오른다"
        onClick={() => {
          props.onCreate(
            {
              id,
              kind,
              label_ko: label === '' ? id : label,
              slot: kind === 'EQUIPMENT' ? slot : null,
              hands: slot.startsWith('WEAPON') ? 'ONE' : null,
              grade,
              min_floor: Number.parseInt(minFloor, 10) || 1,
              attack_range: range.trim() === '' ? null : Number.parseInt(range, DECIMAL_RADIX),
              use_tag: useTag.trim() === '' ? null : useTag.trim(),
              affixes: buildAffixPayload(affixRows),
            },
            reason,
          )
        }}
      >
        등록
      </Button>
    </div>
  )
}

const OFFLINE_HINT = '서버에 닿지 못했다 — 카탈로그는 서버가 안다'

/** 고른 아이템 하나의 상세와 편집 칸. */
export interface CatalogDetailProps {
  readonly row: CatalogAdminRow
  readonly onRetire: (catalogId: string, isRetired: boolean, reason: string) => void
  readonly onEdit: (catalogId: string, patch: Record<string, unknown>, reason: string) => void
  readonly grades: readonly string[]
  readonly stats: readonly string[]
}

/**
 * 고른 아이템의 상세와 편집 칸을 그린다.
 *
 * 패널에서 갈라 둔 이유는 검사 때문만이 아니다 — 고른 것 하나에만 걸리는 상태(이름·층·
 * 사유)를 패널이 들고 있으면, 다른 아이템을 골랐을 때 앞의 입력이 남는다.
 *
 * @param props 아이템 한 줄과 콜백.
 * @returns 렌더 트리.
 */
export function CatalogDetail(props: CatalogDetailProps): React.JSX.Element {
  const { row } = props
  const statNames = listAffixStats(props.stats)
  const [reason, setReason] = useState('')
  const [label, setLabel] = useState('')
  const [floor, setFloor] = useState('')
  const [range, setRange] = useState('')
  const [useTag, setUseTag] = useState('')
  const [grade, setGrade] = useState('')
  // **안 건드리면 접사를 안 보낸다.** 서버는 빈 목록을 "안 바꾼다" 로 읽으므로, 화면이
  // "고쳤다" 와 "안 건드렸다" 를 스스로 구분해야 한다.
  const [affixRows, setAffixRows] = useState<readonly AffixRow[] | undefined>(undefined)

  return (
    <div className="cat__detail">
      <span className="cat__name">{row.catalogId}</span>
      <ValueExpr
        text={`${row.kind}${row.slot === '' ? '' : ` · ${row.slot}`} · ${row.grade} · ${String(row.minFloor)}층~${row.attackRange === 0 ? '' : ` · 사거리 ${String(row.attackRange)}`}`}
        size="sm"
        dim
      />
      {row.affixes.length === 0 ? null : <ValueExpr text={row.affixes.join(' · ')} size="sm" />}
      {row.requirements.length === 0 ? null : (
        <ValueExpr text={`요구 ${row.requirements.join(' · ')}`} size="sm" dim />
      )}
      {/* 굴림에 걸리는 값이라 눈에 있어야 한다 — 0 이면 등록돼 있어도 안 나온다. */}
      <ValueExpr
        text={
          row.dropWeight === 0
            ? '드롭 표에 없다 — 굴려도 안 나온다'
            : `드롭 가중치 ${String(row.dropWeight)}`
        }
        size="sm"
        dim={row.dropWeight > 0}
      />

      <label className="cat__field">
        <span>사유</span>
        <input
          className="cat__input"
          value={reason}
          onChange={(event) => {
            setReason(event.target.value)
          }}
          placeholder="왜 고치는가 (4자 이상)"
        />
      </label>

      {/* **이름 칸이 없었다.** 「최소 층 +1」 버튼만 있어서 이름은 고칠 방법이
        아예 없었고, 그것이 "편집이 안 된다" 의 절반이었다. */}
      <label className="cat__field">
        <span>이름</span>
        <input
          className="cat__input"
          value={label}
          placeholder={row.labelKo}
          aria-label="아이템 이름"
          onChange={(event) => {
            setLabel(event.target.value)
          }}
        />
      </label>
      <label className="cat__field">
        <span>최소 층</span>
        <input
          className="cat__input"
          inputMode="numeric"
          value={floor}
          placeholder={String(row.minFloor)}
          aria-label="최소 층"
          onChange={(event) => {
            setFloor(event.target.value)
          }}
        />
      </label>
      {/* 소모품만 쓰임새를 갖는다 (§4). 비워 두면 지금 값을 그대로 둔다. */}
      {row.kind !== 'CONSUMABLE' ? null : (
        <label className="cat__field">
          <span>쓰임새</span>
          <input
            className="cat__input"
            aria-label="쓰임새"
            value={useTag}
            placeholder={row.useTag === '' ? '없음 — 어느 규칙도 못 쓴다' : row.useTag}
            onChange={(event) => {
              setUseTag(event.target.value.toUpperCase())
            }}
          />
        </label>
      )}
      {/* 무기만 사거리를 갖는다 (§2.2). **비워 두면 지금 값을 그대로 둔다** — 빈 칸을
          0 으로 읽으면 이름만 고치려던 편집이 활을 아무것도 못 때리는 것으로 만든다. */}
      {!row.slot.startsWith('WEAPON') ? null : (
        <label className="cat__field">
          <span>사거리</span>
          <input
            className="cat__input"
            inputMode="numeric"
            value={range}
            placeholder={row.attackRange === 0 ? '기본 사거리' : String(row.attackRange)}
            aria-label="사거리"
            onChange={(event) => {
              setRange(event.target.value)
            }}
          />
        </label>
      )}

      {/* 등급과 접사를 여기서 고친다 (§15.11). 인스턴스가 자기 값을 갖게 된 뒤로 이
          수정이 이미 나온 아이템에 소급하지 않는다 — 앞으로 나올 것에만 걸린다. */}
      <div className="cat__row">
        {props.grades.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={(grade === '' ? row.grade : grade) === name ? 'primary' : 'ghost'}
            onClick={() => {
              setGrade(name)
            }}
          >
            {name}
          </Button>
        ))}
      </div>

      {affixRows === undefined ? (
        <Button
          size="sm"
          variant="ghost"
          glyph="✎"
          title="접사를 고친다 — 지금 값에서 시작한다"
          onClick={() => {
            setAffixRows(
              row.affixRows.length === 0
                ? [{ stat: statNames[0] ?? '', flat: '', percent: '', labelKo: '' }]
                : row.affixRows.map(buildRowFromSpec),
            )
          }}
        >
          접사 고치기
        </Button>
      ) : (
        <>
          {affixRows.map((affix, index) => (
            <div className="cat__row" key={`${String(index)}:${affix.stat}`}>
              <select
                className="cat__input"
                aria-label={`고칠 접사 ${String(index + 1)} 능력치`}
                value={affix.stat}
                onChange={(event) => {
                  setAffixRows(buildAffixRows(affixRows, index, { stat: event.target.value }))
                }}
              >
                {statNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <input
                className="cat__input"
                inputMode="numeric"
                aria-label={`고칠 접사 ${String(index + 1)} 고정값`}
                value={affix.flat}
                placeholder="고정"
                onChange={(event) => {
                  setAffixRows(buildAffixRows(affixRows, index, { flat: event.target.value }))
                }}
              />
              <input
                className="cat__input"
                inputMode="numeric"
                aria-label={`고칠 접사 ${String(index + 1)} 퍼센트`}
                value={affix.percent}
                placeholder="%"
                onChange={(event) => {
                  setAffixRows(buildAffixRows(affixRows, index, { percent: event.target.value }))
                }}
              />
              <input
                className="cat__input"
                aria-label={`고칠 접사 ${String(index + 1)} 이름`}
                value={affix.labelKo}
                placeholder="예리함"
                onChange={(event) => {
                  setAffixRows(buildAffixRows(affixRows, index, { labelKo: event.target.value }))
                }}
              />
            </div>
          ))}
          <Button
            size="sm"
            variant="ghost"
            glyph="＋"
            onClick={() => {
              setAffixRows([
                ...affixRows,
                { stat: statNames[0] ?? '', flat: '', percent: '', labelKo: '' },
              ])
            }}
          >
            접사 추가
          </Button>
        </>
      )}

      <div className="cat__row">
        <Button
          size="sm"
          variant="primary"
          title="고친 값을 저장한다 — 이미 나온 아이템은 안 바뀐다 (§15.11)"
          onClick={() => {
            props.onEdit(
              row.catalogId,
              {
                label_ko: label === '' ? row.labelKo : label,
                min_floor: Number.parseInt(floor, DECIMAL_RADIX) || row.minFloor,
                grade: grade === '' ? row.grade : grade,
                // 빈 칸은 「안 바꾼다」다. 0 으로 보내면 활이 아무것도 못 때리게 된다.
                ...(range.trim() === ''
                  ? {}
                  : { attack_range: Number.parseInt(range, DECIMAL_RADIX) }),
                ...(useTag.trim() === '' ? {} : { use_tag: useTag.trim() }),
                ...(affixRows === undefined ? {} : { affixes: buildAffixPayload(affixRows) }),
              },
              reason,
            )
          }}
        >
          고치기
        </Button>
        <Button
          size="sm"
          variant={row.isRetired ? 'primary' : 'secondary'}
          title={
            row.isRetired
              ? '다시 나오게 한다'
              : '새로 안 나오게 한다 — 이미 나온 것은 그대로 남는다'
          }
          onClick={() => {
            props.onRetire(row.catalogId, !row.isRetired, reason)
          }}
        >
          {row.isRetired ? '되살리기' : '폐기'}
        </Button>
      </div>
    </div>
  )
}

/**
 * 카탈로그 관리 화면을 그린다.
 *
 * @param props 카탈로그와 조작 콜백.
 * @returns 패널 요소.
 */
export function CatalogAdminPanel(props: CatalogAdminPanelProps): React.JSX.Element | null {
  const { catalog } = props
  const [picked, setPicked] = useState('')

  if (catalog === undefined) {
    return (
      <Panel title="카탈로그 관리" tone="panel" padded>
        <ValueExpr text={OFFLINE_HINT} size="sm" dim />
      </Panel>
    )
  }

  const row = catalog.items.find((item) => item.catalogId === picked)

  return (
    <Panel
      title="카탈로그 관리"
      meta={`세대 ${String(catalog.generation)} · ${String(catalog.items.length)}종`}
      tone="panel"
      padded
      scroll
    >
      <div className="cat">
        <GlyphState
          state="danger"
          size="sm"
          label="고치면 코어 버전이 바뀐다 — 순위표 시즌이 갈린다"
        />
        {/* **고르기 전에 있어야 한다.** 상세 안에 두면 규칙을 아는 시점이 늦고, 그때는
            이미 "왜 안 되지" 를 겪은 뒤다. */}
        <ValueExpr
          text="접사·등급·분류는 여기서 못 고친다 — 새 id 로 등록하고 옛 id 를 폐기한다"
          size="sm"
          dim
        />
        {props.detail === '' ? null : <ValueExpr text={props.detail} size="sm" />}

        <CellGrid
          cells={catalog.items.map((item) => ({
            id: item.catalogId,
            thumb: (
              <Thumb
                kind={item.slot === '' ? item.kind : item.slot}
                label={item.labelKo}
                state={item.isRetired ? 'locked' : 'known'}
              />
            ),
            name: item.labelKo,
            meta: [
              `${item.grade} · ${String(item.minFloor)}층~`,
              item.isRetired ? '폐기' : `가중치 ${String(item.dropWeight)}`,
            ],
            isSelected: item.catalogId === picked,
          }))}
          onSelect={(id) => {
            setPicked(id)
          }}
          emptyText="카탈로그가 비어 있다"
        />

        <CatalogForm
          grades={catalog.grades}
          stats={catalog.stats}
          onCreate={props.onCreate}
        />

        {row === undefined ? null : (
          <CatalogDetail
            row={row}
            grades={catalog.grades}
            stats={catalog.stats}
            onRetire={props.onRetire}
            onEdit={props.onEdit}
          />
        )}
      </div>
    </Panel>
  )
}


/**
 * 서버가 보낸 접사 절을 편집 칸으로 옮긴다.
 *
 * **적어 둔 문자열에서 되돌리지 않는다.** 「튼튼함 +8」 에는 능력치 축이 안 담겨 있어,
 * 되돌리면 축이 목록의 첫 항목으로 떨어진다 — 이름만 고치려던 편집이 `hp_max` 접사를
 * `attack` 으로 바꿔 저장하고, 그 사실은 저장한 뒤에야 드러난다.
 *
 * @param spec 서버가 보낸 접사 절.
 * @returns 편집 칸 한 줄. 0 은 빈 칸으로 둔다 — 안 그러면 고정과 퍼센트가 둘 다 채워진
 *   것처럼 보인다.
 */
export function buildRowFromSpec(spec: CatalogAffixSpec): AffixRow {
  return {
    stat: spec.stat,
    flat: spec.flat === 0 ? '' : String(spec.flat),
    percent: spec.percent === 0 ? '' : String(spec.percent),
    labelKo: spec.labelKo,
  }
}
