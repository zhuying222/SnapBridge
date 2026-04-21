# Protocol v1

This is the current network contract for the MVP.

Implementation status:

- `Implemented and exercised`: `apps/windows-sender` with `tools/mock-receiver`
- `Intended to match later`: `apps/android-receiver`

The mock receiver is a development test double, not the shipping tablet receiver. Its behavior is intentionally close to the protocol, but it has a few development-oriented differences called out below.

All bodies are JSON unless stated otherwise. Binary content is encrypted and base64-encoded in the MVP.

## Terms

- `device_id`: stable UUID generated on first launch.
- `public_key`: X25519 public key, base64 encoded.
- `pair_id`: stable identifier for one approved sender-receiver relationship.
- `sas_code`: short authentication string, six digits shown on both devices.

## Current Coverage

Verified in this repo today:

- pairing challenge retrieval
- pairing request submission
- pairing status polling
- encrypted capture upload
- acknowledgement signature verification

Not yet verified in this repo today:

- the Android receiver serving these endpoints on-device
- real gallery insertion through Android `MediaStore`
- cross-device LAN behavior between the Windows sender and a Huawei tablet

## Mock Receiver Differences

The mock receiver exists to accelerate local development, so it intentionally differs from the target Android receiver in a few ways:

- pairing requests are auto-approved after logging the verification code
- saved images are written to the local filesystem, not Android `MediaStore`
- contributor-only tooling may inspect or reset mock state directly on disk

These differences are useful for development, but they should not be mistaken for production receiver behavior.

## 1. Pairing Challenge

### `GET /api/v1/pairing/challenge`

Response:

```json
{
  "receiver_id": "9ca9c0b9-6f36-41f8-8b7a-0ce0f4f31512",
  "receiver_name": "Huawei MatePad",
  "receiver_public_key": "<base64>",
  "challenge_id": "0f84ddf2-f8fe-4cde-a577-4a5486cdce61",
  "expires_at": "2026-04-21T08:20:00Z"
}
```

The sender computes:

```text
sas_code = mod_1_000_000(sha256(challenge_id || sorted(public_key_a, public_key_b)))
```

Both devices display the same six digits.

## 2. Pairing Request

### `POST /api/v1/pairing/requests`

Request:

```json
{
  "sender_id": "e557b02c-8bce-4cf0-b6ef-0fd086bb33d9",
  "sender_name": "Lenovo-Yoga",
  "sender_public_key": "<base64>",
  "challenge_id": "0f84ddf2-f8fe-4cde-a577-4a5486cdce61",
  "pairing_code": "824193"
}
```

Response:

```json
{
  "request_id": "81302b4c-406e-49af-8e96-0d8602afc69d",
  "status": "pending"
}
```

## 3. Pairing Status

### `GET /api/v1/pairing/requests/{request_id}`

Pending:

```json
{
  "request_id": "81302b4c-406e-49af-8e96-0d8602afc69d",
  "status": "pending"
}
```

Approved:

```json
{
  "request_id": "81302b4c-406e-49af-8e96-0d8602afc69d",
  "status": "approved",
  "pair_id": "2e4cfc2c-1d7a-4a34-ae52-cc7b0cc84927",
  "receiver_id": "9ca9c0b9-6f36-41f8-8b7a-0ce0f4f31512",
  "receiver_name": "Huawei MatePad",
  "receiver_public_key": "<base64>"
}
```

Rejected:

```json
{
  "request_id": "81302b4c-406e-49af-8e96-0d8602afc69d",
  "status": "rejected",
  "reason": "sas_mismatch"
}
```

## 4. Capture Upload

### `POST /api/v1/captures`

Request:

```json
{
  "pair_id": "2e4cfc2c-1d7a-4a34-ae52-cc7b0cc84927",
  "sender_id": "e557b02c-8bce-4cf0-b6ef-0fd086bb33d9",
  "receiver_id": "9ca9c0b9-6f36-41f8-8b7a-0ce0f4f31512",
  "message_id": "4b435f0d-62a9-411b-a7ca-b4ea4fb2a1bc",
  "captured_at": "2026-04-21T08:21:04Z",
  "mime_type": "image/png",
  "file_name": "capture-20260421-162104.png",
  "width": 900,
  "height": 540,
  "sha256": "<hex>",
  "nonce": "<base64>",
  "ciphertext": "<base64>"
}
```

Encryption details:

- shared secret: `X25519(sender_private_key, receiver_public_key)`
- transfer key: `HKDF-SHA256(shared_secret, salt=sha256(pair_id), info="snapbridge-transfer-v1")`
- payload encryption: `AES-256-GCM(transfer_key, nonce, plaintext=image_bytes, aad=canonical_json(metadata_without_ciphertext))`

## 5. Capture Acknowledgement

Response:

```json
{
  "message_id": "4b435f0d-62a9-411b-a7ca-b4ea4fb2a1bc",
  "status": "saved",
  "received_sha256": "<hex>",
  "saved_uri": "content://media/external/images/media/81441",
  "ack_signature": "<base64>"
}
```

`ack_signature`:

```text
HMAC-SHA256(
  transfer_key,
  canonical_json({
    "message_id": "...",
    "status": "...",
    "received_sha256": "...",
    "saved_uri": "..."
  })
)
```

## Error Handling

- `400`: malformed request or invalid hash
- `401`: sender not paired or invalid cryptographic proof
- `404`: unknown pairing request
- `409`: pairing code mismatch or duplicate message id
- `410`: challenge expired
- `500`: local save failure
