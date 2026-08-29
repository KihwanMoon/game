"""헤드리스 스크립트 묶음.

패키지 파일을 둔 이유는 스크립트끼리 서로를 import 하기 때문이다.
`export_analysis_golden` 은 `export_golden` 의 전투 조립을 그대로 쓴다 — 두 기준 문서가
서로 다른 배선으로 돌면 대조가 무의미해진다. 패키지가 아니면 같은 파일이 `export_golden`
과 `scripts.export_golden` 두 이름으로 잡혀 mypy 가 막는다.
"""
