"""틱 엔진. 7페이즈를 고정 순서로 돈다 (TDD §4.1).

UPKEEP → TELEGRAPH → PERCEPTION → DECIDE → ACT → RESOLVE → CLEANUP.

PERCEPTION 과 DECIDE 를 나누는 이유는 동시성 공정성이다. 모든 엔티티가 같은 시점의
세계를 보고 판단해야 하며, 순차 갱신하면 처리 순서가 유리/불리를 만든다.
"""
