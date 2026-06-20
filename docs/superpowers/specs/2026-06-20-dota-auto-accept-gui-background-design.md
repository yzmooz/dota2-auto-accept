# Dota 2 Auto Accept: compact GUI, application icon, and background acceptance

## Goal

Replace the current large tabbed interface with a compact tray-first GUI, replace the generic square checkmark with a distinctive Dota-themed application icon, and make background acceptance report success only after the ready-check has actually disappeared.

The application remains a Windows-only utility built with CustomTkinter, pystray, Pillow, OpenCV, and pywin32.

## Confirmed product behavior

- On normal launch, show the main window with the engine stopped.
- Monitoring starts only after the user presses **Start**.
- Closing the main window hides it to the system tray instead of terminating the process.
- If monitoring was running before the window was hidden, it continues running in the tray.
- Restoring the window does not change the engine state.
- The default acceptance path must not activate Dota 2 or perform an Alt+Tab-style focus switch.
- A failed background input attempt must never be reported as a successful acceptance.
- Foreground switching remains unavailable as an automatic fallback in the default flow.

## GUI design

Use the approved **Tray Compact** direction:

- Fixed compact window, approximately 460×600 logical pixels.
- Warm light neutral palette with dark text, restrained green success accents, and red Dota accents.
- A small title bar/header with the application mark and an overflow/utility area.
- A large central status mark and one primary status message:
  - `Остановлен`
  - `Ожидаю матч`
  - `Проверяю готовность`
  - `Матч принят`
  - `Не удалось принять`
- One prominent primary button whose state is `Старт` or `Стоп`.
- A concise latest-event card instead of a permanently large console.
- Bottom navigation for `Журнал`, `Telegram`, and `Настройки`.
- Secondary pages reuse the same window rather than opening separate windows.
- Existing detection, Telegram, autostart, and tuning controls remain available on secondary pages, but advanced tuning is visually de-emphasized.
- The visible window has a normal taskbar entry and the branded taskbar/title-bar icon. Hiding the window removes the taskbar entry while preserving the tray icon.

## Icon system

Create a new circular mark based on the supplied visual reference:

- A red stone/rune emblem as the primary mass.
- A luminous green acceptance check in the lower-right quadrant.
- A dark circular medallion with transparent outer corners; no opaque square tile.
- No text, tiny particles, or thin decorative details that disappear at small sizes.

Produce two coordinated renderings:

1. A detailed rendering for the GUI header, executable, title bar, and large Windows taskbar sizes.
2. A simplified high-contrast rendering for 16, 20, 24, and 32 px tray/taskbar use.

Bundle a multi-resolution `logo.ico` and PNG sizes required by Tk, pystray, and PyInstaller. The icon loader must use one shared resource lookup path in source and frozen builds.

## Background acceptance architecture

### Trigger path

Keep the existing Windows event sources:

- `HSHELL_FLASH` as the primary match-ready trigger.
- `EVENT_SYSTEM_FOREGROUND` as a secondary signal.
- A low-frequency safety scan as a fallback.

Triggers schedule an acceptance attempt; they must not run overlapping attempts. Debouncing applies only after verified success, not merely after sending input.

### Detection path

1. Locate the Dota 2 top-level window.
2. Record its original minimized state. If it is minimized, restore it with a no-activate Win32 operation so it remains behind the currently active application.
3. Capture the Dota window using `PrintWindow(PW_RENDERFULLCONTENT)`.
4. Reject unusable captures such as empty or near-black frames.
5. Detect the ready-check using the existing HSV and template methods.
6. Use screen capture only when Dota is already foreground; do not accidentally inspect unrelated foreground content as though it were Dota.

### Input and verification path

1. When the ready-check is detected above threshold, send Enter directly to the Dota window with paired key-down/key-up window messages.
2. Wait a short verification interval.
3. Capture the Dota window again and rerun detection.
4. Report success only when the ready-check is no longer detected across a small stable verification window.
5. If it remains visible, retry within the configured deadline and record that background input was ignored.
6. If the deadline expires, report a failed attempt and continue monitoring for subsequent triggers.
7. If the attempt temporarily restored a minimized Dota window, return it to the minimized state without activation after either success or failure.

The engine must not call `SetForegroundWindow`, synthesize Alt, move the real mouse cursor, or issue a global Enter in this default background path.

## Component boundaries

- `gui.py`: presentation, navigation, UI state binding, and thread-safe status updates.
- `tray.py`: tray lifecycle, menu, simplified icon, show/quit callbacks.
- `engine.py`: trigger lifecycle, serialized acceptance state machine, retries, and result callbacks.
- `detector.py`: window capture validation and ready-check detection only.
- `config.py`: persisted settings with explicit defaults for background input behavior.
- `images/`: generated icon assets and the existing accept-button template.

The engine exposes structured status/result events to the GUI instead of requiring the GUI to infer state from log strings.

## Error handling and reporting

- No Dota window: remain in waiting state and log a concise diagnostic.
- Minimized window cannot be restored without activation: fail the current attempt without stealing focus.
- Empty/black `PrintWindow` capture: retry and report capture failure.
- Ready-check detected but Enter ignored: retry, then report failure without sending a success notification.
- Detector exception or Win32 exception: contain it inside the worker, preserve the message loop, and expose a concise error in the latest-event card and detailed journal.
- Telegram `accepted` notifications are sent only after verified success.
- Quitting from the tray stops listeners and worker threads before destroying the GUI.

## Testing and verification

### Automated tests

- Configuration defaults and persistence include all GUI-controlled engine flags.
- Engine state transitions cover stopped, waiting, detecting, verifying, accepted, and failed.
- Mocked Win32 tests prove the no-focus path never calls foreground activation, global keyboard input, or mouse input.
- Mocked Win32 tests prove an originally minimized Dota window is minimized again after success, failure, or an exception.
- Verification tests distinguish an ignored Enter from a disappeared ready-check.
- Detector capture validation rejects empty and near-black frames.
- Tray callbacks preserve engine state when the window is shown or hidden.
- Icon resources resolve in source and simulated PyInstaller environments.

### Manual Windows checks

- Launch shows the window and leaves monitoring stopped.
- Start begins monitoring; close hides to tray; double-click restores the same running state.
- Window, taskbar, tray, and packaged executable show the intended icon at their native sizes without a square background.
- With Dota visible behind another application, a ready-check is accepted without focus transfer.
- With Dota minimized, the no-activate restore/capture/input/verification flow is tested during a real ready-check.
- The previously active application remains foreground throughout the attempt.
- Dota returns to its original minimized state after the attempt.
- A forced ignored-input scenario produces a failure/retry log and no false Telegram success notification.
- The rebuilt PyInstaller executable starts and exits cleanly.

The real minimized-ready-check test requires a live Dota matchmaking ready-check; automated tests can validate the state machine and absence of focus-stealing calls but cannot prove Source 2 accepts background window messages on the target machine.

## Scope constraints

- Do not replace CustomTkinter or introduce a web-based desktop framework.
- Do not modify Dota files, inject into the process, read process memory, or add anti-cheat-sensitive behavior.
- Do not automatically fall back to focus stealing.
- Do not redesign Telegram bot behavior beyond adapting it to the compact navigation.
- Preserve user-owned uncommitted project changes and avoid unrelated refactors.
