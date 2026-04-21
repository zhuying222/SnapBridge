# Windows Sender

This is the first runnable SnapBridge component. It provides:

- a circular always-on-top floating capture orb
- a built-in settings window for receiver URL, device name, and pairing
- region capture with Pillow
- one-click resend of the last captured image in the current session
- encrypted upload and acknowledgement verification

## Run

```powershell
cd D:\111\SnapBridge\apps\windows-sender
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_sender.py
```

## Daily Use

- Left-click the floating orb to start region capture and send the result immediately.
- Drag the orb to reposition it anywhere on the desktop. The sender remembers the new position.
- Right-click the orb to open the quick menu with `Capture and Send`, `Resend Last Capture`, `Settings`, `Clear Pairing`, and `Exit`.
- Hover the orb to see the latest sender status. During capture, the orb hides itself so it does not end up inside the screenshot.
- Open `Settings` the first time to confirm the device name, enter the receiver URL, and pair with the tablet using the code shown on the receiver.

## Current MVP Notes

- The UI is still `tkinter`, but the sender now uses a transparent borderless orb plus a compact status bubble instead of the earlier rectangular panel.
- Pairing still follows the documented `challenge -> request -> pending -> approved/rejected` flow and keeps the existing protocol field names unchanged.
- Successful sends report through the floating status bubble instead of interrupting every capture with a modal dialog.
- The sender stores its config in `%APPDATA%\SnapBridge\sender-config.json`.
- The config remembers a preferred receiver URL separately from the active paired receiver record.
- Tray integration, auto-discovery, and retry queue are planned next.
