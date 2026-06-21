# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows-only tool that auto-clicks the **«ПРИНЯТЬ»** (Accept) button when a
Dota 2 match is found. Single-purpose, two small scripts, no framework.

## Commands

```bash
# Setup (Git Bash on Windows)
source .venv/Scripts/activate            # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run (waits for a match, then clicks Accept)
python accept_dota.py

# Diagnose detection without waiting for a match — open the ready-check (or show
# the button image on screen), then:
python accept_dota.py --test             # prints match confidence, does NOT click
python accept_dota.py --test --click     # also performs the click (for testing)

# Regenerate the button template (other resolution / UI language)
python make_template.py path/to/fullscreen_screenshot.png        # auto-finds the green button
python make_template.py path/to/screenshot.png  X Y W H          # manual crop box fallback
```

There is **no test suite, linter, or build step**. "Testing" means running
`accept_dota.py --test` against a live screen.

## Architecture

The core design decision (see README): Dota 2 is Source 2 / Panorama — its UI is
rendered as pixels with **no externally accessible element tree**, and Game State
Integration does **not** report the matchmaking ready-check. So the only viable
approach is on-screen detection. To avoid constant screen-scraping, detection is
**event-driven** and only runs the moment Windows signals a found match.

**`accept_dota.py`** — the whole runtime, structured as trigger → action:

- **Triggers (OS events, not polling).** A hidden message-only window
  (`win32gui.CreateWindow` + `RegisterShellHookWindow`) and a single
  `win32gui.PumpMessages()` loop drive everything:
  - `HSHELL_FLASH` (taskbar flash — the "red blinking" when a match is found) is
    the primary trigger, handled in `_wnd_proc`.
  - `EVENT_SYSTEM_FOREGROUND` (Dota window comes to front) is the backup trigger,
    via a ctypes `SetWinEventHook` callback (`_foreground_callback`). Its
    `WINFUNCTYPE` proc is kept in the module-global `_win_event_proc` so the GC
    can't free it mid-run (doing so crashes the process).
  - Optional `WM_TIMER` safety scan every `SAFETY_SCAN_SEC` (0 disables).
- **Action (`try_accept`).** On any trigger: grab the screen (`mss`), run
  `find_button` (multi-scale `cv2.matchTemplate` over `SCALES` against
  `images/accept_button.png`), and if confidence ≥ `MATCH_THRESHOLD`, click the
  match center. `DEBOUNCE_SECONDS` prevents repeat clicks; `RETRY_SECONDS` keeps
  retrying because the flash can slightly precede the popup render. Cursor
  position is saved/restored around the click; `force_foreground` nudges the Dota
  window forward (ALT-key trick to bypass the foreground lock) first.
- **Dota window identity** (`is_dota`): title == "Dota 2", else exe path ends in
  `dota2.exe`. Used to filter both triggers.

**`make_template.py`** — standalone helper to (re)create
`images/accept_button.png` by HSV-masking the green button in a fullscreen
screenshot. The same green-detection logic was used to build the bundled
template; the shipped template is captured at **1920×1080, Russian UI**.

All tunables live in the settings block at the top of `accept_dota.py`.

## Constraints & gotchas

- **Windows only** — relies on `pywin32` and WinAPI hooks.
- The bundled template is resolution/language-specific. Multi-scale matching
  absorbs small differences; large ones require regenerating it via
  `make_template.py`.
- `pyautogui.FAILSAFE` (cursor to top-left) only aborts an in-progress click — it
  is **not** a process kill switch. Stop with Ctrl+C.
- `images/image_348.png` (the source screenshot) is git-ignored; only the cropped
  `images/accept_button.png` is committed.
## GitHub publishing rules

When preparing this repository for GitHub:

* Never create, modify, push to, or delete repositories inside GitHub organizations.
* Never use `hsemlcourse` or any organization as the repository owner.
* Create repositories only under my personal GitHub account.
* Before running `gh repo create`, show the exact command and ask for confirmation.
* Before running `git push`, show the remote URL and ask for confirmation.
* Prefer private repositories unless I explicitly ask for public.
* Always run `git status` before committing or pushing.
* Always show `git diff` before committing.
* Always check that no secrets are committed: `.env`, API keys, tokens, passwords, local configs, `settings.json`.
* Make sure `.gitignore` excludes local/private files before the first commit.
* Do not run destructive Git commands without explicit confirmation: `git reset --hard`, `git clean`, `git push --force`, repository deletion, or branch deletion.
* After publishing, show the final repository URL and summarize exactly what was pushed.
Allowed GitHub owner:
- yzmooz