from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_private_key_b64() -> str:
    private_key = x25519.X25519PrivateKey.generate()
    raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return b64encode(raw)


def public_key_from_private_b64(private_key_b64: str) -> str:
    private_key = x25519.X25519PrivateKey.from_private_bytes(b64decode(private_key_b64))
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64encode(public_key)


def compute_sas_code(local_public_key_b64: str, remote_public_key_b64: str, challenge_id: str) -> str:
    key_parts = sorted([b64decode(local_public_key_b64), b64decode(remote_public_key_b64)])
    digest = hashlib.sha256(challenge_id.encode("utf-8") + b"".join(key_parts)).digest()
    value = int.from_bytes(digest[:4], "big") % 1_000_000
    return f"{value:06d}"


def derive_transfer_key(private_key_b64: str, remote_public_key_b64: str, pair_id: str) -> bytes:
    private_key = x25519.X25519PrivateKey.from_private_bytes(b64decode(private_key_b64))
    remote_public_key = x25519.X25519PublicKey.from_public_bytes(b64decode(remote_public_key_b64))
    shared_secret = private_key.exchange(remote_public_key)
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hashlib.sha256(pair_id.encode("utf-8")).digest(),
        info=b"snapbridge-transfer-v1",
    )
    return hkdf.derive(shared_secret)


def decrypt_payload(transfer_key: bytes, metadata: dict[str, Any], nonce_b64: str, ciphertext_b64: str) -> bytes:
    aesgcm = AESGCM(transfer_key)
    return aesgcm.decrypt(
        b64decode(nonce_b64),
        b64decode(ciphertext_b64),
        canonical_json(metadata),
    )


def encrypt_payload(transfer_key: bytes, metadata: dict[str, Any], plaintext: bytes) -> tuple[str, str]:
    aesgcm = AESGCM(transfer_key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext, canonical_json(metadata))
    return b64encode(nonce), b64encode(ciphertext)


def compute_ack_signature(transfer_key: bytes, ack_payload: dict[str, Any]) -> str:
    return b64encode(hmac.new(transfer_key, canonical_json(ack_payload), hashlib.sha256).digest())


def verify_ack_signature(transfer_key: bytes, ack_payload: dict[str, Any], signature_b64: str) -> bool:
    expected = compute_ack_signature(transfer_key, ack_payload)
    return hmac.compare_digest(expected, signature_b64)
