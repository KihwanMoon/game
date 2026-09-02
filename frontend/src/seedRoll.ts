/**
 * 판을 시작할 때 쓸 시드를 굴린다.
 *
 * **이것은 코어가 아니다.** 코어 안의 무작위는 전부 `DeterministicRng` 를 거치고, 그
 * 규율은 여기서도 안 깨진다 — 굴린 값은 코어의 **입력**이 되고, 그 뒤로는 여전히
 * `런 결과 = f(시드, 규칙표, 코어버전, …)` 이다 (R5). 시드를 사람이 고르든 기계가
 * 굴리든 판은 똑같이 재현된다. 굴린 값이 티켓에 적히기 때문이다.
 *
 * `Math.random` 을 쓰지 않는다. 서버가 `secrets.randbelow` 로 굴리는 것과 같은 급의
 * 난수원을 쓴다 — 시드를 예측할 수 있으면 「유리한 판이 언제 오는지」를 계산할 수 있고,
 * 그것은 T2 가 막으려던 것이 화면 쪽으로 새는 길이다.
 */
import { MAX_SEED } from './core/schemas'

/** 상위 워드에서 가져올 비트 수. 53 - 32 = 21 이다. */
const HIGH_BITS = 0x200000

/** 하위 워드의 자릿값. 2^32. */
const LOW_PLACE = 0x100000000

/**
 * 0 이상 `MAX_SEED` 이하의 시드를 굴린다.
 *
 * 32비트 워드 둘을 이어 붙인다. 상위를 2^21 로 나눈 나머지를 쓰는데, 2^32 가 2^21 의
 * 배수라 나머지가 한쪽으로 쏠리지 않는다 — 쏠리면 특정 판이 남들보다 자주 나온다.
 *
 * @returns 굴린 시드.
 */
export function rollSeed(): number {
  const words = new Uint32Array(2)
  globalThis.crypto.getRandomValues(words)
  const high = (words[0] ?? 0) % HIGH_BITS
  const low = words[1] ?? 0
  return Math.min(MAX_SEED, high * LOW_PLACE + low)
}
