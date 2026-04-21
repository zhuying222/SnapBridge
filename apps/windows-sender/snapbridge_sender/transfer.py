from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import requests

from .crypto import (
    derive_transfer_key,
    encrypt_payload,
    sha256_hex,
    verify_ack_signature,
)
from .models import ReceiverProfile, SenderSettings


class TransferError(RuntimeError):
    pass


class TransferClient:
    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def send_capture(
        self,
        settings: SenderSettings,
        image_bytes: bytes,
        width: int,
        height: int,
    ) -> dict[str, Any]:
        receiver = settings.receiver
        if receiver is None:
            raise TransferError("No paired receiver configured.")

        transfer_key = derive_transfer_key(
            private_key_b64=settings.private_key,
            remote_public_key_b64=receiver.receiver_public_key,
            pair_id=receiver.pair_id,
        )

        captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        metadata = {
            "pair_id": receiver.pair_id,
            "sender_id": settings.device_id,
            "receiver_id": receiver.receiver_id,
            "message_id": str(uuid4()),
            "captured_at": captured_at,
            "mime_type": "image/png",
            "file_name": datetime.now().strftime("capture-%Y%m%d-%H%M%S.png"),
            "width": width,
            "height": height,
            "sha256": sha256_hex(image_bytes),
        }
        nonce, ciphertext = encrypt_payload(transfer_key, metadata, image_bytes)
        payload = {**metadata, "nonce": nonce, "ciphertext": ciphertext}

        response = requests.post(
            f"{receiver.receiver_url.rstrip('/')}/api/v1/captures",
            json=payload,
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            self._raise_transfer_error(response)
        body = response.json()

        ack_signature = body.pop("ack_signature", None)
        if not ack_signature:
            raise TransferError("Receiver acknowledgement is missing its signature.")

        if not verify_ack_signature(transfer_key, body, ack_signature):
            raise TransferError("Receiver acknowledgement signature is invalid.")

        if body.get("received_sha256") != metadata["sha256"]:
            raise TransferError("Receiver acknowledgement hash does not match the sent image.")

        if body.get("status") != "saved":
            raise TransferError(f"Receiver returned status {body.get('status')!r}.")

        return body

    @staticmethod
    def _raise_transfer_error(response: requests.Response) -> None:
        detail = TransferClient._error_detail(response)
        if detail:
            raise TransferError(f"Receiver rejected the upload ({response.status_code}): {detail}")
        raise TransferError(f"Receiver rejected the upload ({response.status_code}).")

    @staticmethod
    def _error_detail(response: requests.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            text = response.text.strip()
            return text[:200] if text else None

        if isinstance(payload, dict):
            for key in ("reason", "error", "message", "detail"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None
