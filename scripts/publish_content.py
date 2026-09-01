"""초안을 파일로 발행한다 (설계/4_아이템 §15.7 의 반대편).

**사람 손을 타는 것이 설계다.** 스킬·블록·밸런스·룸·적 규칙표는 두 코어가 함께 읽는
실행 자산이라 런타임에 바꿀 수 없다. 브라우저는 그것을 빌드 시점에 번들로 인라인하므로,
발행은 **파일을 고치고 커밋·배포해야** 실제로 반영된다.

자동으로 반영되면 순위표 시즌이 아무도 모르게 갈린다.

`ops` 서비스로 돌린다 — 저장소가 마운트돼 있어 파일이 실제로 저장소에 쓰인다.

    docker compose run --rm ops uv run python -m scripts.publish_content
    docker compose run --rm ops uv run python -m scripts.publish_content --asset skills --apply
"""

import argparse
import json
from pathlib import Path

from game.app.content.validate import check_draft
from game.app.store.connection import create_pool
from game.app.store.content_draft import DRAFT_ASSETS, list_drafts, read_draft


def read_current_version(path: Path, version_key: str) -> int:
    """지금 파일의 세대를 읽는다.

    Args:
        path: 자산 파일.
        version_key: 그 파일이 쓰는 버전 키.

    Returns:
        세대. 파일이 없으면 0.
    """
    if not path.exists():
        return 0
    raw = json.loads(path.read_text(encoding="utf-8"))
    return int(raw.get(version_key, 0))


def apply_publish(asset: str, payload: dict) -> Path:
    """초안을 자산 파일로 쓴다.

    Args:
        asset: 자산 이름.
        payload: 초안 절.

    Returns:
        쓴 파일 경로.
    """
    path = Path(DRAFT_ASSETS[asset][0])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    """스크립트 진입점."""
    parser = argparse.ArgumentParser(description="콘텐츠 초안을 파일로 발행한다")
    parser.add_argument("--asset", help="발행할 자산. 생략하면 목록만 본다")
    parser.add_argument("--apply", action="store_true", help="실제로 파일을 쓴다")
    args = parser.parse_args()

    pool = create_pool()
    try:
        if args.asset is None:
            drafts = list_drafts(pool)
            print(f"초안 {len(drafts)}건")
            for asset, note, at in drafts:
                print(f"  {asset:10s} {at}  {note}")
            print("\n발행하려면 --asset <이름> --apply")
            return

        payload = read_draft(pool, args.asset)
        if payload is None:
            print(f"초안이 없다: {args.asset}")
            return
        path, version_key = DRAFT_ASSETS[args.asset]
        current = read_current_version(Path(path), version_key)
        problem = check_draft(args.asset, payload)
        if problem:
            print(f"발행할 수 없다 — {problem}")
            return
        print(f"검증 통과: {args.asset} {version_key} {current} → {payload[version_key]}")
        if not args.apply:
            print("미리보기다. 실제로 쓰려면 --apply 를 붙인다.")
            return
        written = apply_publish(args.asset, payload)
        print(f"\n썼다: {written}")
        print("**아직 게임에 반영되지 않았다.** 커밋하고 배포해야 두 코어가 그것을 읽는다.")
    finally:
        pool.close()


if __name__ == "__main__":
    main()
