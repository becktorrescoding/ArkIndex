# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.3.0] - 2026-06-18

### Added
- **Batch progress bar** — `ttk.Progressbar` + label between the buttons and log. Thread-safe `_update_progress()` and `_reset_progress()` wired into bulk mode, search mode, and the preview window's Convert Selected.
- **PDF text layer verification** — `_verify_text_layer()` checks every output PDF after `ocrmypdf.ocr()` and warns if the text layer is empty or <10% of source length.
- **Search within generated PDFs** — `search_mode()` now walks the output folder for PDFs, extracts text via PyMuPDF, applies the same keyword/name-context scoring, and adds results to the preview alongside image matches.
- **Drag-and-drop + paste** — `_setup_drag_drop()` tries tkdnd (no-op if unavailable), binds Ctrl+V globally, `_paste_from_clipboard()` handles file/folder pasting, and `_process_dropped_file()` converts a single dropped file.
- **Shebang** — `#!/usr/bin/env python3` at the top of `ArkIndex.py` so `./ArkIndex.py` works directly.
- **CI/CD workflow** — GitHub Actions CI (`ci.yml`) runs on push/PR to master across Python 3.10–3.13; checks import, syntax, and install scripts.

### Fixed
- **Degree date regex** — `Degree[:\s]*?` tightened to `degree\s+received[^\n]*?` to avoid matching unrelated lines.
- **Empty filename** — Empty filename result is now returned as `"Unknown"` instead of an empty string.
- **Certificate regex** — Regex was missing `\s+` after the degree name; added so `Certificate of Graduation` is detected.
- **PyMuPDF doc leaks** — `open_as_image` and `convert_image` now call `doc.close()` in their `finally` blocks.
- **Two-digit year heuristic** — Years ≥20 are treated as 19xx, years <20 as 20xx.
- **Auto-updater branch** — Release is fetched using the release tag (not hardcoded `master`), so the updater works correctly regardless of the default branch name.
- **Inconsistent crop between search_mode and filter_year** — Both now use the same crop coordinates.
- **Per-month day validation** — Added `_DAYS_IN_MONTH` to validate day-in-month instead of blanket `day ≤ 31`.

### Changed
- **Linux installer** — Detects Python via broader search (python3.9–3.14), refreshes the package index before installing, installs Tesseract, and corrected the run command to `ArkIndex.py`.
- **Install scripts (all platforms)** — Run commands updated to reference `ArkIndex.py` instead of `app.py`.

## [1.2.1] - 2026-06-02

### Fixed
- **Windows locking crash** — `_get_osfhandle` was being called from `kernel32.dll` where it doesn't exist (it's a C runtime function). Replaced the entire approach with `CreateFileW` which returns a `HANDLE` directly, bypassing `_get_osfhandle`, `msvcrt`, and `ucrtbase` entirely. Also fixed `UnlockFileEx.argtypes` which had the wrong number of parameters (6 vs 5).
- **OCR crash on non-RGB images** — CMYK, palette, and other unusual image modes caused `OSError: cannot write mode CMYK as PNG` when pytesseract tried to save the crop to a temp PNG. All crops are now converted to `RGB` before passing to `image_to_string`.
- **Crash on corrupted/truncated images** — `Image.open` could raise `UnidentifiedImageError` on bad files. `open_as_image` now catches the exception, logs the file path, and returns `None`. Callers skip `None` results instead of crashing.
- **Crash on tiny images** — Images smaller than 40×60 pixels caused invalid crop coordinates. A minimum-size guard now skips them with a log message.
- **Updater 404 error** — The auto-updater hardcoded `main` as the branch for the raw download URL, but the repo uses `master`. Now hardcodes `master` instead.

### Changed
- **Renamed project to ArkIndex** — All references updated in app.py, README, and IDE configuration files.

## [1.2.0] - 2026-06-02

### Added
- **Auto-Updater** — On startup, checks GitHub releases via the GitHub API. On user consent, downloads the new `app.py` from `raw.githubusercontent.com` and atomically replaces the current script, preserving the filename even if renamed.
- **"Check for Updates" button** — Manual trigger in the title bar. Failures silently logged on startup; shown as dialogs on manual click.
- **Version tracking** — `VERSION`, `GITHUB_REPO`, and `CURRENT_SCRIPT` module-level constants.
- **Session logging** — Every `log()` call appends a timestamped file to `<output>/logs/session_log_<timestamp>.txt`.
- **Export Results button** — Writes search scores and conversion metadata to a timestamped CSV.
- **Light/Dark theme toggle** — Button in title bar with recursive widget-walk theming by widget class. `THEMES` dict with two color schemes. Preference saved and restored between sessions.
- **Persistent settings** — Saves and restores `input_path`, `output_path`, `mode`, and `theme` to a JSON file. Loaded on startup; saved on close.
- **Import Index button** — Button in the path frame that validates a gzip+base64 JSON file and saves it as the active search index.
- **Bulk mode duplicate auto-handle** — When a destination PDF already exists in bulk mode, text is extracted from the existing PDF via `pymupdf` and compared with source OCR text using `difflib.SequenceMatcher`. ≥85% similar → skip; <85% similar → append pages to the existing PDF.

### Changed
- **Settings storage location** — Moved from `~/.image_file_lookup_settings.json` to the system temp directory, scoped by username. Settings are now per-device and never follow you across machines.

### Fixed
- **Cross-device settings leak** — Settings no longer travel via NFS/roaming profiles.
