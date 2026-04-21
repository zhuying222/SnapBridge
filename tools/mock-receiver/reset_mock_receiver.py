from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from snapbridge_mock_receiver.storage import OUTPUT_DIR, STATE_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset SnapBridge mock receiver state.")
    parser.add_argument("--keep-received", action="store_true", help="Keep received image files.")
    parser.add_argument("--keep-state", action="store_true", help="Keep mock pairing and receiver state.")
    return parser.parse_args()


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
        print(f"removed: {path}")
    else:
        print(f"missing: {path}")


def main() -> int:
    args = parse_args()
    if not args.keep_state:
        remove_tree(STATE_DIR)
    if not args.keep_received:
        remove_tree(OUTPUT_DIR)
    if args.keep_state and args.keep_received:
        print("nothing to remove")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
