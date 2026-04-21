# Contributing to SnapBridge

## Start Here

Read these files before changing code:

- `README.md`
- `docs/status.md`
- `docs/architecture.md`
- `docs/protocol.md`

The repo is in an MVP transition state, so contributor accuracy matters as much as code changes.

## Status Language

Please keep repository wording honest and consistent:

- Say `runnable` only for `apps/windows-sender`.
- Say `source scaffold only` for `apps/android-receiver` unless you have built and tested it on a real device.
- Say `mock-verified` when something has only been exercised against `tools/mock-receiver`.
- Do not describe the Android path as working end-to-end unless it has been validated on hardware.

## Work Areas

The monorepo is intentionally split so contributors can work in parallel:

- `apps/windows-sender`: Windows capture UX, pairing client, transport client.
- `apps/android-receiver`: Android service, pairing UI, gallery save flow.
- `tools/mock-receiver`: local verification target for protocol and transport work.
- `docs` and repo root files: architecture, status, onboarding, roadmap, contributor guidance.

If multiple people are active, prefer staying within one area per change unless the protocol contract itself changes.

## Setup By Area

### Windows Sender

- Python 3.11+
- `pip install -r apps/windows-sender/requirements.txt`

### Mock Receiver

- Python 3.11+
- `pip install -r tools/mock-receiver/requirements.txt`

### Android Receiver

- Java 17+
- Android Studio
- Android SDK Platform 35

The Android receiver is not buildable in this environment by default. Treat it as source-level work until proven otherwise.

## Recommended Local Dev Loop

1. Start `tools/mock-receiver`.
2. Run `tools/mock-receiver/smoke_test_mock_receiver.py` if you need a fast protocol sanity check.
3. Run `apps/windows-sender` for sender-side UX or transfer changes.
4. Update `docs/protocol.md` if the network contract changes.
5. Update `docs/status.md` if repo reality changes.

## Pull Request Expectations

- Keep changes scoped to one component or one cross-cutting contract.
- Document any protocol change in `docs/protocol.md`.
- Call out whether validation was `unit-tested`, `mock-verified`, or `device-tested`.
- Do not remove or soften status caveats unless the underlying capability is actually validated.
