# Architecture

## Implementation Status

This document describes both the target product shape and the current executable seam in the repository.

- `Implemented and runnable`: `apps/windows-sender`
- `Implemented for local verification`: `tools/mock-receiver`
- `Planned and scaffolded only`: `apps/android-receiver`

Today, the working path is:

```text
Windows sender -> mock receiver
```

The Android receiver is the intended production counterpart, but it is not the current verification target.

## Product Goal

SnapBridge removes the screenshot relay loop between a Windows PC and a tablet used for note-taking. The intended user action is:

1. Click a floating button or press a hotkey on the PC.
2. Drag to select a region on screen.
3. Wait for the image to land in the tablet gallery.
4. Insert it from the note app's image picker.

## Components

### Windows Sender

Current role:

- Keeps a local device profile and the currently paired receiver.
- Provides a floating capture button.
- Captures a selected screen region into PNG bytes.
- Encrypts the payload and sends it to the paired receiver.
- Waits for a delivery acknowledgement tied to the image hash.

Current repo reality:

- Runnable Python MVP.
- Validated locally against the mock receiver.
- Not yet validated against the real Android receiver in this environment.

### Android Receiver

Target role:

- Expose a small local HTTP API on the LAN.
- Display a pairing code and pairing confirmation UI.
- Verify sender identity and pairing requests.
- Decrypt incoming images.
- Save accepted images into a dedicated gallery album.

Current repo reality:

- Source scaffold only.
- Not built in this environment.
- Not device-tested.

### Mock Receiver

Role in the repo:

- Implements the same protocol contract as the planned Android receiver where practical.
- Lets contributors exercise pairing, encryption, upload, and acknowledgement flows locally.
- Saves incoming images to the filesystem instead of Android `MediaStore`.

This tool exists to keep the transport contract executable while Android work is still catching up.

## Transport Choice

The first implementation uses local HTTP on the LAN with application-layer encryption.

Why this over WebRTC or cloud relay:

- lower implementation complexity
- easier debugging
- deterministic local routing
- no dependency on third-party infrastructure
- enough throughput for PNG screenshots on home or campus Wi-Fi

## Security Model

### Pairing

- Receiver generates a long-lived X25519 key pair on first run.
- Sender generates its own long-lived X25519 key pair on first run.
- Receiver shows a six-digit pairing code.
- Sender fetches a challenge from the receiver and computes a six-digit short authentication string from both public keys and the challenge.
- Sender submits the pairing request with the entered pairing code.
- Receiver shows the same short authentication string and asks the user to approve.
- If both screens match and the user approves, each side stores the other side's public key and a shared `pair_id`.

This gives explicit dual confirmation without external infrastructure.

### Transfer

- Sender derives a transfer key with `X25519 + HKDF-SHA256`.
- The PNG payload is encrypted with `AES-256-GCM`.
- Metadata is authenticated as additional authenticated data.
- Receiver verifies the decrypted image hash before saving.
- Receiver returns an acknowledgement authenticated with `HMAC-SHA256`.

## Persistence

### Sender

- Stores config under the user's app-data directory.
- Stores floating button position, paired receiver profile, and local private key.

### Receiver

- Planned Android receiver: stores paired senders and pending requests in app-private storage, then writes incoming images through `MediaStore`.
- Current mock receiver: stores paired senders and state under `tools/mock-receiver/.snapbridge-mock/` and writes files to `tools/mock-receiver/received/`.

## Parallel Development Seams

These are the cleanest boundaries for concurrent work:

- `apps/windows-sender`: capture UX, sender config, pairing client, transfer client
- `apps/android-receiver`: service lifecycle, pairing approval UI, gallery save flow
- `tools/mock-receiver`: protocol test double, local debugging hooks, verification scripts
- `docs`: repo status, protocol contract, contributor guidance

If a change crosses boundaries, the protocol document should be updated in the same branch.

## Planned Improvements

1. Build and validate the Android receiver on actual Huawei hardware.
2. Add `mDNS` receiver discovery.
3. Add retry behavior when the receiver is temporarily offline.
4. Revisit tray and hotkey UX after the device-to-device flow is stable.
