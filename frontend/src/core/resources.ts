/**
 * 밸런스·룸·규칙표 JSON 을 읽어 타입이 붙은 값으로 만든다.
 *
 * JSON 의 정본은 `game/resources/` 하나이며 **프런트로 복사하지 않는다**. vite 의 별칭
 * `@resources` 가 그 디렉터리를 가리키고, 빌드 시점에 값이 번들로 인라인된다. 사본을 두면
 * 파이썬 코어가 읽는 파일과 조용히 갈라지고, 그 순간 게이트 G3 가 대조하는 두 코어가
 * 서로 다른 데이터로 도는 것이 된다.
 *
 * import 한 JSON 은 TypeScript 가 구조에서 타입을 추론한다. 그 추론형은 예컨대 `rhs` 를
 * `number | boolean | { stat: string }` 의 합집합으로 넓게 잡아 스키마의 좁은 원시 타입과
 * 어긋난다. 그래서 이 파일 한 곳에서만 원시 타입으로 단언하고, 실제 형식 검사는 각
 * 로더가 런타임에 한다 — 단언이 검사를 대신하지 않게 하려는 배치다.
 */
import balanceRaw from '@resources/balance/balance.json'
import blocksRaw from '@resources/balance/blocks.json'
import skillsRaw from '@resources/balance/skills.json'
import roomsRaw from '@resources/rooms/templates.json'
import benchmarkRaw from '@resources/rulesets/benchmark.json'
import enemiesRaw from '@resources/rulesets/enemies.json'
import g0Raw from '@resources/rulesets/g0_examples.json'
import tutorialRaw from '@resources/tutorial/stages.json'

import type {
  BlockCatalog,
  RawBlockCatalog,
  RawRoomFile,
  RawRuleSetFile,
  RawTutorialStage,
  RoomTemplate,
  RuleSet,
  TutorialStage,
} from './schemas'
import {
  loadBlockCatalog,
  loadRoomTemplates,
  loadRuleSets,
  parseTutorialStage,
} from './schemas'

/** balance.json 의 원시 형태. 세부 스키마는 전투 수식을 옮길 때 붙인다. */
export interface RawBalanceFile {
  readonly balance_version: number
  readonly [key: string]: unknown
}

/** 블록 카탈로그 (GDD §3.2). 개수 동결 검사를 통과한 것만 나온다. */
export const BLOCK_CATALOG: BlockCatalog = loadBlockCatalog(
  blocksRaw as unknown as RawBlockCatalog,
)

/** 룸 템플릿 목록 (GDD §4.4). 파일에 적힌 순서를 유지한다. */
export const ROOM_TEMPLATES: readonly RoomTemplate[] = loadRoomTemplates(
  roomsRaw as unknown as RawRoomFile,
)

/** G0 예시 규칙표 3종. */
export const G0_RULESETS: ReadonlyMap<string, RuleSet> = loadRuleSets(
  g0Raw as unknown as RawRuleSetFile,
)

/** 적 규칙표. 몬스터도 플레이어와 같은 DSL 로 기술된다 (GDD §5). */
export const ENEMY_RULESETS: ReadonlyMap<string, RuleSet> = loadRuleSets(
  enemiesRaw as unknown as RawRuleSetFile,
)

/** 벤치마크 규칙표. 배치 러너가 승률을 재는 대상이다. */
export const BENCHMARK_RULESETS: ReadonlyMap<string, RuleSet> = loadRuleSets(
  benchmarkRaw as unknown as RawRuleSetFile,
)

/**
 * 스킬 정의 원본. `balance.json` 에서 갈라 나왔다 — 스킬은 종류가 늘어나는 것이고
 * 밸런스 수치는 조정되는 것이라 수명이 다르다.
 */
export const SKILLS = skillsRaw as unknown as { readonly skills: readonly unknown[] }

/**
 * 밸런스 수치 원본. **스킬을 합쳐 하나의 뷰로 낸다.**
 *
 * 합치는 자리를 여기 하나로 두어, 읽는 쪽은 예전처럼 `balance.skills` 를 그대로 본다 —
 * 파이썬의 `load_balance` 와 같은 배치다. 소비자마다 두 파일을 알게 하면 새 소비자가
 * 생길 때마다 합치는 코드가 늘고, 언젠가 한 곳이 빠진다.
 */
export const BALANCE: RawBalanceFile = {
  ...(balanceRaw as unknown as RawBalanceFile),
  skills: SKILLS.skills,
}

/**
 * 튜토리얼 스테이지 (로드맵 W20).
 *
 * **파이썬과 같은 파일을 읽는다.** 사본을 두면 검사가 통과한 스테이지와 화면이 보여
 * 주는 스테이지가 갈린다 — 「시작으로는 지고 해답으로는 이긴다」가 화면에서만 조용히
 * 깨지는 방식이다.
 */
export const TUTORIAL_STAGES: readonly TutorialStage[] = (
  tutorialRaw as unknown as { readonly stages: readonly RawTutorialStage[] }
).stages.map(parseTutorialStage)

/**
 * 이 코어가 아는 스킬 id 전부, 정렬해서.
 *
 * 캐릭터 시트가 **장착하지 않은 것을 「불가」로** 보여주는 데 쓴다 — 규칙 에디터에서
 * 「불가」가 왜 떴는지는 그 목록에서만 답할 수 있다.
 */
export const ALL_SKILL_IDS: readonly string[] = SKILLS.skills
  .map((skill) => (skill as { readonly id: string }).id)
  .sort()
