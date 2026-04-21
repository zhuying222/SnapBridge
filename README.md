# SnapBridge

SnapBridge is a local-first screenshot relay for tablet note-taking workflows:

- `Windows sender`: capture a screen region from the PC with one click.
- `Tablet receiver`: accept the image on the same LAN and save it directly to the gallery.
- `Pairing and delivery`: explicit pairing, encrypted transfer, and per-image acknowledgement.

## Current Repo Status

This repository is intentionally ahead of the shipping product. Contributors should read its status literally:

- `apps/windows-sender` is the only runnable product component today. It is a Python MVP that can pair, capture, encrypt, upload, and verify acknowledgements.
- `apps/android-receiver` is source scaffold only. It documents the intended Android receiver structure, but it has not been built or device-validated in this environment.
- `tools/mock-receiver` is the current local integration target. It is how contributors can verify the sender and protocol flow without the Android toolchain.

The only verified end-to-end path in this repo today is:

```text
windows-sender -> tools/mock-receiver
```

## Quick Links

- Status snapshot: `docs/status.md`
- Architecture and component boundaries: `docs/architecture.md`
- Protocol contract and mock-specific notes: `docs/protocol.md`
- Contributor workflow: `CONTRIBUTING.md`
- Mock receiver usage: `tools/mock-receiver/README.md`

## Repository Layout

```text
SnapBridge/
  apps/
    windows-sender/     # runnable MVP
    android-receiver/   # source scaffold only
  docs/
  tools/
    mock-receiver/      # local verification target
```

## Local Verification Today

If you want to validate the repo right now, do this:

1. Run `tools/mock-receiver`.
2. Run `apps/windows-sender`.
3. Pair the sender against the mock receiver and send a capture.

Or, for a quicker contributor loop:

1. Run `tools/mock-receiver\run_mock_receiver.py`.
2. Run `tools/mock-receiver\smoke_test_mock_receiver.py`.

That path verifies the protocol and crypto contract locally without claiming Android readiness.

## Security Model

- Pairing is local and explicit.
- Both devices display the same six-digit short authentication string during pairing.
- Approved devices store each other's long-lived public keys.
- Capture payloads are encrypted with a key derived from the paired device keys.
- Every delivery returns an acknowledgement bound to the image hash.

## MVP Constraints

- Same LAN only.
- One active paired receiver per Windows sender profile.
- Gallery insertion on the real tablet is a planned receiver responsibility, not a verified repo capability yet.
- The current sender UX prioritizes fast region capture over tray/hotkey polish.

## Suggested Next Milestones

1. Build and install the Android receiver on the Huawei tablet.
2. Validate pairing and gallery-save flow on a real LAN between Windows and Android.
3. Add receiver discovery so the sender does not require manual URL entry.
4. Harden retry and offline behavior after the real-device path is stable.


附注：接收端放后台就不能接收的话，可以去设置里面管理此应用允许后台运行。
