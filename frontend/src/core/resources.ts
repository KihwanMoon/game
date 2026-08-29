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
import roomsRaw from '@resources/rooms/templates.json'
import benchmarkRaw from '@resources/rulesets/benchmark.json'
import enemiesRaw from '@resources/rulesets/enemies.json'
import g0Raw from '@resources/rulesets/g0_examples.json'

import type {
  BlockCatalog,
  RawBlockCatalog,
  RawRoomFile,
  RawRuleSetFile,
  RoomTemplate,
  RuleSet,
} from './schemas'
import { loadBlockCatalog, loadRoomTemplates, loadRuleSets } from './schemas'

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

/** 밸런스 수치 원본. 전투 수식을 옮기기 전까지는 그대로 통과시킨다. */
export const BALANCE: RawBalanceFile = balanceRaw as unknown as RawBalanceFile
