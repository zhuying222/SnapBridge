from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request

from .crypto import compute_ack_signature, compute_sas_code, decrypt_payload, derive_transfer_key
from .storage import OUTPUT_DIR, PendingPairRequest, load_state, refresh_challenge, save_state


app = Flask(__name__)
state = load_state()


@app.get("/healthz")
def healthz():
    return jsonify(
        {
            "status": "ok",
            "receiver_id": state.receiver_id,
            "receiver_name": state.receiver_name,
            "paired_sender_count": len(state.paired_senders),
            "pending_request_count": len(state.pending_requests),
        }
    )


@app.get("/api/v1/pairing/challenge")
def pairing_challenge():
    expires_at = datetime.fromisoformat(state.challenge_expires_at)
    if expires_at <= datetime.now(expires_at.tzinfo):
        refresh_challenge(state)
        save_state(state)
    return jsonify(
        {
            "receiver_id": state.receiver_id,
            "receiver_name": state.receiver_name,
            "receiver_public_key": state.receiver_public_key,
            "challenge_id": state.challenge_id,
            "expires_at": state.challenge_expires_at,
        }
    )


@app.post("/api/v1/pairing/requests")
def pairing_request():
    payload = request.get_json(force=True)
    if payload["challenge_id"] != state.challenge_id:
        return jsonify({"error": "challenge_mismatch"}), 410
    if payload["pairing_code"] != state.current_pairing_code:
        return jsonify({"error": "pairing_code_mismatch"}), 409

    request_id = str(uuid.uuid4())
    pair_id = str(uuid.uuid4())
    sas_code = compute_sas_code(
        local_public_key_b64=state.receiver_public_key,
        remote_public_key_b64=payload["sender_public_key"],
        challenge_id=payload["challenge_id"],
    )
    print(f"[pairing] verification code: {sas_code}")
    print(f"[pairing] sender: {payload['sender_name']} ({payload['sender_id']})")
    print("[pairing] auto-approving request in mock receiver.")

    pending = PendingPairRequest(
        request_id=request_id,
        challenge_id=payload["challenge_id"],
        sender_id=payload["sender_id"],
        sender_name=payload["sender_name"],
        sender_public_key=payload["sender_public_key"],
        status="approved",
        pair_id=pair_id,
    )
    state.pending_requests[request_id] = pending.__dict__
    state.paired_senders[payload["sender_id"]] = {
        "pair_id": pair_id,
        "sender_name": payload["sender_name"],
        "sender_public_key": payload["sender_public_key"],
    }
    refresh_challenge(state)
    save_state(state)
    return jsonify({"request_id": request_id, "status": "pending"})


@app.get("/api/v1/pairing/requests/<request_id>")
def pairing_status(request_id: str):
    pending = state.pending_requests.get(request_id)
    if pending is None:
        return jsonify({"error": "not_found"}), 404
    response = {
        "request_id": pending["request_id"],
        "status": pending["status"],
    }
    if pending["status"] == "approved":
        response.update(
            {
                "pair_id": pending["pair_id"],
                "receiver_id": state.receiver_id,
                "receiver_name": state.receiver_name,
                "receiver_public_key": state.receiver_public_key,
            }
        )
    if pending["reason"]:
        response["reason"] = pending["reason"]
    return jsonify(response)


@app.post("/api/v1/captures")
def capture_upload():
    payload = request.get_json(force=True)
    sender = state.paired_senders.get(payload["sender_id"])
    if sender is None:
        return jsonify({"error": "unknown_sender"}), 401
    if sender["pair_id"] != payload["pair_id"]:
        return jsonify({"error": "pair_mismatch"}), 401

    metadata = {
        "pair_id": payload["pair_id"],
        "sender_id": payload["sender_id"],
        "receiver_id": payload["receiver_id"],
        "message_id": payload["message_id"],
        "captured_at": payload["captured_at"],
        "mime_type": payload["mime_type"],
        "file_name": payload["file_name"],
        "width": payload["width"],
        "height": payload["height"],
        "sha256": payload["sha256"],
    }

    transfer_key = derive_transfer_key(
        private_key_b64=state.private_key,
        remote_public_key_b64=sender["sender_public_key"],
        pair_id=payload["pair_id"],
    )
    plaintext = decrypt_payload(transfer_key, metadata, payload["nonce"], payload["ciphertext"])

    import hashlib

    received_sha = hashlib.sha256(plaintext).hexdigest()
    if received_sha != payload["sha256"]:
        return jsonify({"error": "hash_mismatch"}), 400

    output_path = OUTPUT_DIR / payload["file_name"]
    suffix = 1
    while output_path.exists():
        output_path = OUTPUT_DIR / f"{Path(payload['file_name']).stem}-{suffix}.png"
        suffix += 1
    output_path.write_bytes(plaintext)

    ack_payload = {
        "message_id": payload["message_id"],
        "status": "saved",
        "received_sha256": received_sha,
        "saved_uri": str(output_path),
    }
    ack_payload["ack_signature"] = compute_ack_signature(transfer_key, ack_payload)
    print(json.dumps({"saved": str(output_path), "message_id": payload["message_id"]}, ensure_ascii=True))
    return jsonify(ack_payload)


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    print("SnapBridge mock receiver")
    print(f"URL: http://{host}:{port}")
    print(f"Pairing code: {state.current_pairing_code}")
    print(f"Output directory: {OUTPUT_DIR}")
    app.run(host=host, port=port)
