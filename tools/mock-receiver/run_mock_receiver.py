from __future__ import annotations

import argparse

from snapbridge_mock_receiver.server import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SnapBridge mock receiver.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on. Default: 8765")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(host=args.host, port=args.port)
