from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from snapbridge_mock_receiver.crypto import (
    compute_sas_code,
    derive_transfer_key,
    encrypt_payload,
    generate_private_key_b64,
    public_key_from_private_b64,
    verify_ack_signature,
)


STATE_PATH = Path(__file__).resolve().parent / ".snapbridge-mock" / "state.json"
TEST_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WlH0QAAAABJRU5ErkJggg=="
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local smoke test against the SnapBridge mock receiver.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8765",
        help="Mock receiver base URL. Default: http://127.0.0.1:8765",
    )
    return parser.parse_args()


def http_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} failed with {exc.code}: {body}") from exc


def http_post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed with {exc.code}: {body}") from exc


def load_pairing_code() -> str:
    if not STATE_PATH.exists():
        raise RuntimeError(
            "Mock receiver state file was not found. Start run_mock_receiver.py once before running the smoke test."
        )
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return state["current_pairing_code"]


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    health = http_get_json(f"{base_url}/healthz")
    if health.get("status") != "ok":
        raise RuntimeError(f"Unexpected health response: {health}")

    challenge = http_get_json(f"{base_url}/api/v1/pairing/challenge")
    pairing_code = load_pairing_code()

    sender_private_key = generate_private_key_b64()
    sender_public_key = public_key_from_private_b64(sender_private_key)
    sender_id = str(uuid.uuid4())
    sender_name = "snapbridge-smoke-test"
    sas_code = compute_sas_code(
        local_public_key_b64=challenge["receiver_public_key"],
        remote_public_key_b64=sender_public_key,
        challenge_id=challenge["challenge_id"],
    )

    pairing_request = {
        "sender_id": sender_id,
        "sender_name": sender_name,
        "sender_public_key": sender_public_key,
        "challenge_id": challenge["challenge_id"],
        "pairing_code": pairing_code,
    }
    pairing_result = http_post_json(f"{base_url}/api/v1/pairing/requests", pairing_request)
    request_id = pairing_result["request_id"]
    pairing_status = http_get_json(f"{base_url}/api/v1/pairing/requests/{request_id}")
    if pairing_status.get("status") != "approved":
        raise RuntimeError(f"Expected approved pairing status, got: {pairing_status}")

    pair_id = pairing_status["pair_id"]
    message_id = str(uuid.uuid4())
    file_name = f"smoke-test-{message_id[:8]}.png"
    received_sha256 = hashlib.sha256(TEST_PNG_BYTES).hexdigest()

    metadata = {
        "pair_id": pair_id,
        "sender_id": sender_id,
        "receiver_id": challenge["receiver_id"],
        "message_id": message_id,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mime_type": "image/png",
        "file_name": file_name,
        "width": 1,
        "height": 1,
        "sha256": received_sha256,
    }
    transfer_key = derive_transfer_key(sender_private_key, challenge["receiver_public_key"], pair_id)
    nonce, ciphertext = encrypt_payload(transfer_key, metadata, TEST_PNG_BYTES)

    capture_payload = {
        **metadata,
        "nonce": nonce,
        "ciphertext": ciphertext,
    }
    ack = http_post_json(f"{base_url}/api/v1/captures", capture_payload)

    ack_payload = {
        "message_id": ack["message_id"],
        "status": ack["status"],
        "received_sha256": ack["received_sha256"],
        "saved_uri": ack["saved_uri"],
    }
    if not verify_ack_signature(transfer_key, ack_payload, ack["ack_signature"]):
        raise RuntimeError("Acknowledgement signature verification failed.")

    saved_path = Path(ack["saved_uri"])
    if not saved_path.exists():
        raise RuntimeError(f"Mock receiver reported a saved path that does not exist: {saved_path}")

    summary = {
        "base_url": base_url,
        "health": health,
        "sas_code": sas_code,
        "pair_id": pair_id,
        "message_id": message_id,
        "saved_path": str(saved_path),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI failure path
        print(f"smoke test failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
