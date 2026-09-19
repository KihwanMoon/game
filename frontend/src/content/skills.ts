/**
 * 지금 도는 재주 — **발행된 팩에서 읽는다** (2026-09-19).
 *
 * **고쳐 발행했는데 화면이 안 바뀌었다** (실제 신고). 팩이 스킬 절을 나르게 고친 날
 * (`content/pack`) 화면 쪽은 그대로 두어서, 이름·목록이 여전히 **빌드에 박힌
 * `skills.json`** 에서 나왔다 — 관리자가 「유성 낙하」로 고쳐 발행해도 전투 로그와
 * 팔레트는 「메테오」라고 적었다.
 *
 * **`core/resources` 가 이 일을 못 한다.** 그쪽은 번들 상수들의 자리이고, 팩을 읽으려면
 * `content/pack` 을 불러야 하는데 그 모듈이 `core/resources` 를 부른다 — 순환이다.
 * 그래서 팩을 아는 쪽(여기)이 읽고, 코어는 번들만 안다.
 *
 * **서버에 못 닿으면 번들로 떨어진다.** 그때는 팩 세대가 0 이고 `balance.skills` 가
 * 번들 것이므로 같은 코드가 그대로 돈다 — 갈래를 따로 두지 않는다.
 */
import { readActivePack } from './pack'

/** 재주 한 줄에서 화면이 읽는 것들. 나머지는 코어가 본다. */
interface PackSkill {
  readonly id: string
  readonly label_ko?: string
  readonly actor?: string
}

/**
 * 지금 도는 재주 전부.
 *
 * @returns 팩의 재주 줄들. 절이 이상하면 빈 배열 — 화면이 죽는 것보다 낫다.
 */
function listPackSkills(): readonly PackSkill[] {
  const raw = readActivePack().balance.skills
  return Array.isArray(raw) ? (raw as readonly PackSkill[]) : []
}

/**
 * 그 재주의 이름.
 *
 * @param skillId 재주 id.
 * @returns 한글 이름. 팩에 이름이 없으면 id — 지어내면 화면이 정본에 없는 말을 한다.
 */
export function readSkillName(skillId: string): string {
  const found = listPackSkills().find((one) => one.id === skillId)
  return found?.label_ko ?? skillId
}

/**
 * 재주 id 에서 한글 이름으로. 팔레트가 문구를 덧칠할 때 쓴다.
 *
 * @returns 이름표. 이름이 없는 재주는 id 를 그대로 든다.
 */
export function readSkillNames(): ReadonlyMap<string, string> {
  return new Map(
    listPackSkills().flatMap((one) => (one.label_ko === undefined ? [] : [[one.id, one.label_ko]])),
  )
}

/**
 * 정본이 이 재주에 붙인 한글 이름. **없으면 undefined 다.**
 *
 * **`readSkillName` 과 가르는 이유**는 부르는 쪽이 제 폴백을 아래에 깔 수 있어야 하기
 * 때문이다. `?? id` 를 여기서 해 버리면 「정본에 이름이 없다」와 「정본이 id 를 이름으로
 * 정했다」가 구별되지 않고, 그래서 화면들이 손으로 적은 이름을 **정본 위에** 얹었다 —
 * 발행한 「돌려치기」가 편집기에서는 「광역 공격」, 전투 줄에서는 「광역」이었다
 * (2026-09-19). 폴백은 정본 **아래**에 깔려야 한다.
 *
 * @param skillId 재주 id.
 * @returns 정본의 한글 이름. 정본에 이름이 없으면 undefined.
 */
export function findSkillName(skillId: string): string | undefined {
  return listPackSkills().find((one) => one.id === skillId)?.label_ko
}

/**
 * 이 코어가 아는 재주 id 전부, 정렬해서.
 *
 * @returns 재주 id 들.
 */
export function listAllSkillIds(): readonly string[] {
  return listPackSkills()
    .map((one) => one.id)
    .sort()
}

/**
 * 적만 쓰는 재주들. `skills.json` 의 `actor: "enemy"` 가 정본이다.
 *
 * 이것들도 블록 카탈로그와 인지 목록에는 들어 있다 — 적 규칙표가 쿨타임을 물어야 하고,
 * 그 두 목록이 갈리면 인지값이 키째로 안 만들어진다. **거르는 자리는 목록이 아니라
 * 화면이다**: 팔레트만 뺀다.
 *
 * @returns 적 전용 재주 id 들.
 */
export function listEnemyOnlySkillIds(): ReadonlySet<string> {
  return new Set(listPackSkills().filter((one) => one.actor === 'enemy').map((one) => one.id))
}
