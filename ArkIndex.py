#!/usr/bin/env python3
"""
Image to PDF Converter
----------------------
Requires system tools:  tesseract, ghostscript
Requires Python pkgs:   ocrmypdf, pytesseract, Pillow, pymupdf

Run the platform installer first if you haven't already:
  Windows : install_windows.bat
  macOS   : bash install_macos.sh
  Linux   : bash install_linux.sh
"""

VERSION = "1.3.0"
GITHUB_REPO = "becktorrescoding/ArkIndex"

import base64
import gzip
import importlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
import urllib.request
import urllib.error
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext

CURRENT_SCRIPT = Path(__file__).resolve()

import ocrmypdf
import pymupdf
import pytesseract
from PIL import Image, ImageFilter, ImageOps, ImageTk


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------


def _check_python_version():
    if sys.version_info < (3, 9):
        print(
            f"ERROR: Python 3.9+ is required (you have {sys.version}).\n"
            "Run the installer for your platform to upgrade."
        )
        sys.exit(1)


def _check_system_tool(cmd: list) -> bool:
    """Try a single command; return True if it succeeds."""
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _check_python_package(package: str) -> bool:
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False


def _detect_system_theme() -> str:
    """Detect OS-level dark mode preference. Returns 'light' or 'dark'."""
    os_name = platform.system()
    try:
        if os_name == "Darwin":
            r = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=2
            )
            return "dark" if r.stdout.strip() == "Dark" else "light"
        elif os_name == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value else "dark"
        else:
            r = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=2,
            )
            return "dark" if "dark" in r.stdout.lower() else "light"
    except Exception:
        return "light"


def _installer_hint() -> str:
    os_name = platform.system()
    if os_name == "Windows":
        return "  Run:  install_windows.bat"
    elif os_name == "Darwin":
        return "  Run:  bash install_macos.sh"
    else:
        return "  Run:  bash install_linux.sh"


def check_dependencies():
    """Verify all required tools and packages are present before launching the GUI."""
    _check_python_version()

    missing = []

    system_tools = [
        ("tesseract  (OCR engine)", [["tesseract", "--version"]]),
        (
            "ghostscript  (PDF engine)",
            [["gs", "--version"], ["gswin64c", "--version"], ["gswin32c", "--version"]],
        ),
    ]
    for label, candidates in system_tools:
        if not any(_check_system_tool(cmd) for cmd in candidates):
            missing.append(label)

    pkg_map = {
        "ocrmypdf": "ocrmypdf",
        "pytesseract": "pytesseract",
        "PIL": "Pillow",
        "fitz": "pymupdf",
    }
    for import_name, install_name in pkg_map.items():
        if not _check_python_package(import_name):
            missing.append(f"Python package '{install_name}'")

    if missing:
        lines = "\n".join(f"  - {m}" for m in missing)
        print(
            "\n" + "=" * 62 + "\n"
            "  Missing dependencies detected:\n\n"
            f"{lines}\n\n"
            "  Please run the installer for your platform:\n"
            f"{_installer_hint()}\n"
            + "=" * 62 + "\n"
        )
        sys.exit(1)


check_dependencies()

# ---------------------------------------------------------------------------
# Date utilities
# ---------------------------------------------------------------------------
_MONTH_LIST = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_NAME_LABEL_RE = re.compile(
    r"(?:Name|Student(?:\s+Name)?|Applicant(?:\s+Name)?)\s*:",
    re.IGNORECASE,
)

_STUDENT_NO_RE = re.compile(r"Student\s+(?:No\.?|#|ID|Number)\b", re.IGNORECASE)

_COURSE_LABEL_RE = re.compile(
    r"(?:Program|Major|Course|Field\s+of\s+Study|Curriculum)\s*:",
    re.IGNORECASE,
)

_MONTH_NAME_PAT = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)
_DATE_NAMED = _MONTH_NAME_PAT + r"[\s,]+\d{1,2}[\s,]+\d{2,4}"
_DATE_NUMERIC = r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}"

_DAYS_IN_MONTH = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _parse_date_to_tuple(raw: str) -> tuple:
    """
    Parse any supported date string into a (YYYY, MM, DD) int tuple for
    sorting/comparison. Returns (9999, 99, 99) on failure so unparseable
    dates sort to the end.

    Supported formats:
        MM/DD/YYYY  MM/DD/YY  (separators: / . -)
        Month DD, YYYY  |  Mon DD YYYY  |  DD Month YYYY
        2-digit years get '19' prepended.
    """
    raw = raw.strip()

    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})$", raw)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= month <= 12 and 1 <= day <= _DAYS_IN_MONTH[month]):
            return 9999, 99, 99
        if len(year) == 2:
            year = "19" + year if int(year) >= 20 else "20" + year
        return int(year), month, day

    parts = [p for p in re.split(r"[\s,]+", raw) if p]
    if len(parts) == 3:
        if parts[0].isdigit():
            day, month_raw, year = parts
        else:
            month_raw, day, year = parts
        month = _MONTH_MAP.get(month_raw[:3].lower())
        if month is None:
            return 9999, 99, 99
        if len(year) == 2:
            year = "19" + year if int(year) >= 20 else "20" + year
        if not (1 <= int(day) <= _DAYS_IN_MONTH[month]):
            return 9999, 99, 99
        return int(year), month, int(day)

    return 9999, 99, 99


def _normalise_date(raw: str) -> tuple:
    """
    Convert any matched date string to ("Month DD, YYYY", "YYYY").
    Returns (None, None) on failure.
    """
    yyyy, mm, dd = _parse_date_to_tuple(raw)
    if (yyyy, mm, dd) == (9999, 99, 99):
        return None, None
    month_name = _MONTH_LIST[mm - 1]
    return f"{month_name} {dd:02d}, {yyyy}", str(yyyy)


def sort_dates_chronologically(date_strings: list[str]) -> list[str]:
    """Return date_strings sorted oldest to newest."""
    return sorted(date_strings, key=_parse_date_to_tuple)


# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

THEMES = {
    "light": {
        "bg": "#f0f0f0",
        "fg": "#000000",
        "entry_bg": "#ffffff",
        "entry_fg": "#000000",
        "select_bg": "#4a90d9",
        "log_bg": "#ffffff",
        "log_fg": "#000000",
        "title_bg": "#2c3e50",
        "title_fg": "white",
        "button_bg": "#e0e0e0",
        "button_fg": "#000000",
    },
    "dark": {
        "bg": "#2b2b2b",
        "fg": "#e0e0e0",
        "entry_bg": "#3c3c3c",
        "entry_fg": "#e0e0e0",
        "select_bg": "#4a90d9",
        "log_bg": "#1e1e1e",
        "log_fg": "#e0e0e0",
        "title_bg": "#1a1a2e",
        "title_fg": "#e0e0e0",
        "button_bg": "#4a4a4a",
        "button_fg": "#e0e0e0",
    },
}

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ArkIndex")
        self.geometry("1000x900")
        self.resizable(width=True, height=True)

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.search_name = tk.StringVar()
        self.search_year = tk.StringVar()
        self.mode = tk.StringVar(value="search")
        self.valid_ext = (".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".TIF", ".tiff", ".tif")

        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._search_index = None
        self._log_file = None
        self._last_scores = None
        self._last_keywords = None
        self._conversion_log = []
        self._theme = tk.StringVar(value="light")
        self._title_label = None
        self._progress_total = 0
        self._progress_current = 0

        self.create_widgets()
        self._load_settings()
        self._apply_theme()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(1000, lambda: self._check_for_updates(silent=True))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def create_widgets(self):
        title_frame = tk.Frame(self, bg="#2c3e50")
        title_frame.pack(fill="x")

        self._title_label = tk.Label(
            title_frame,
            text="Image to PDF Converter",
            font=("Arial", 14, "bold"),
            bg="#2c3e50",
            fg="white",
            pady=10,
        )
        self._title_label.pack(side="left", padx=10)

        tk.Button(
            title_frame,
            text="☀ Light / Dark",
            command=self._toggle_theme,
            font=("Arial", 8),
            bd=1,
            relief="solid",
            bg="#34495e",
            fg="white",
            padx=6,
            pady=2,
        ).pack(side="right", padx=(0, 10), pady=8)

        tk.Button(
            title_frame,
            text="Check for Updates",
            command=self._check_for_updates,
            font=("Arial", 8),
            bd=1,
            relief="solid",
            bg="#34495e",
            fg="white",
            padx=6,
            pady=2,
        ).pack(side="right", padx=(0, 5), pady=8)

        self.path_frame = tk.Frame(self, padx=20, pady=10)
        self.path_frame.pack(fill="x")

        tk.Label(self.path_frame, text="Input Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        tk.Entry(self.path_frame, textvariable=self.input_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(self.path_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)

        tk.Label(self.path_frame, text="Output Folder:").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(self.path_frame, textvariable=self.output_path, width=40).grid(row=1, column=1, padx=5)
        tk.Button(self.path_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)

        tk.Label(
            self.path_frame, text="Load pre-built encrypted index file", font=("Arial", 8), fg="#666"
        ).grid(row=2, column=1, sticky="w")

        tk.Button(self.path_frame, text="Import Index", command=self._import_index_ui, font=("Arial", 8)).grid(
            row=2, column=2, padx=5, pady=3, sticky="w"
        )

        self._dnd_label = tk.Label(
            self.path_frame,
            text="Drag & drop folders or files here",
            font=("Arial", 8),
            fg="#888",
        )
        self._dnd_label.grid(row=3, column=0, columnspan=3, pady=(4, 0))

        self.mode_frame = tk.LabelFrame(
            self,
            text="Operation Mode",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=10,
        )
        self.mode_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Radiobutton(
            self.mode_frame,
            text="Search Mode - Find specific documents by name",
            variable=self.mode,
            value="search",
            command=self.toggle_mode,
            font=["Arial", 9],
        ).pack(anchor="w", pady=3)

        tk.Radiobutton(
            self.mode_frame,
            text="Bulk Convert Mode - Convert all images to PDFs",
            variable=self.mode,
            value="bulk",
            command=self.toggle_mode,
            font=["Arial", 9],
        ).pack(anchor="w", pady=3)

        self.search_frame = tk.Frame(self, padx=20, pady=10)
        self.search_frame.pack(fill="x")

        tk.Label(self.search_frame, text="Search Name (First Last [Mi]):", font=["Arial", 9]).grid(
            row=0, column=0, sticky="w", pady=5
        )
        tk.Entry(self.search_frame, textvariable=self.search_name, width=30).grid(
            row=0, column=1, padx=5, sticky="w"
        )

        tk.Label(
            self.search_frame,
            text="Optional: Filter by Year (yyyy):\n[Admission/Graduation/DOB]",
            font=["Arial", 9],
        ).grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(self.search_frame, textvariable=self.search_year, width=10).grid(
            row=1, column=1, padx=5, sticky="w"
        )

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)

        self.start_button = tk.Button(
            btn_frame,
            text="Start Search",
            command=self.start,
            bg="green",
            fg="white",
            font=("Arial", 11, "bold"),
            width=14,
            height=2,
        )
        self.start_button.pack(side="left", padx=5)

        self.pause_button = tk.Button(
            btn_frame,
            text="Pause",
            command=self.toggle_pause,
            bg="#e67e00",
            fg="white",
            font=("Arial", 11, "bold"),
            width=10,
            height=2,
            state="disabled",
        )
        self.pause_button.pack(side="left", padx=5)

        self.stop_button = tk.Button(
            btn_frame,
            text="Stop",
            command=self.request_stop,
            bg="#c0392b",
            fg="white",
            font=("Arial", 11, "bold"),
            width=10,
            height=2,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=5)

        self.export_button = tk.Button(
            btn_frame,
            text="Export Results",
            command=self._export_results,
            bg="#2980b9",
            fg="white",
            font=("Arial", 10, "bold"),
            width=14,
            height=2,
        )
        self.export_button.pack(side="left", padx=5)

        progress_frame = tk.Frame(self, padx=20, pady=5)
        progress_frame.pack(fill="x")
        self.progress_bar = ttk.Progressbar(
            progress_frame, mode="determinate", length=200
        )
        self.progress_bar.pack(side="left", padx=(0, 10))
        self.progress_label = tk.Label(
            progress_frame, text="Ready", font=("Arial", 9), anchor="w"
        )
        self.progress_label.pack(side="left", fill="x", expand=True)

        log_frame = tk.Frame(self, padx=20, pady=10)
        log_frame.pack(fill="both", expand=True)

        tk.Label(log_frame, text="Processing Log:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=70)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        self._setup_drag_drop()

    # ------------------------------------------------------------------
    # Progress bar helpers
    # ------------------------------------------------------------------
    def _update_progress(self, current, total):
        """Thread-safe progress bar update."""
        self._progress_current = current
        self._progress_total = total

        def _update():
            if total > 0:
                self.progress_bar["value"] = (current / total) * 100
            self.progress_label.config(
                text=f"{current} / {total} files"
            )

        if threading.current_thread() is not threading.main_thread():
            self.after_idle(_update)
        else:
            _update()

    def _reset_progress(self):
        """Reset progress bar to ready state. Thread-safe."""
        self._progress_current = 0
        self._progress_total = 0

        def _reset():
            self.progress_bar["value"] = 0
            self.progress_label.config(text="Ready")

        if threading.current_thread() is not threading.main_thread():
            self.after_idle(_reset)
        else:
            _reset()

    # ------------------------------------------------------------------
    # Drag & drop / Paste helpers
    # ------------------------------------------------------------------
    def _setup_drag_drop(self):
        """Register the path frame as a file-drop target via TkDND."""
        try:
            self.tk.eval("package require tkdnd 2.0")
            self.tk.call("::tkdnd::drop_target", "register", self.path_frame._w)
            self.tk.createcommand("_arkindex_dnd_callback", self._on_file_drop)
            self.tk.eval(
                f"bind {self.path_frame._w} <<Drop>> "
                f"{{+_arkindex_dnd_callback %D}}"
            )
            self._dnd_label.config(text="Drop folders or image/PDF files here")
            self.log("Drag & drop ready.")
        except tk.TclError:
            self._dnd_label.config(text="Ctrl+V to paste file/folder path")

        self.bind_all("<Control-v>", lambda e: self._paste_from_clipboard())
        self.bind_all("<Control-V>", lambda e: self._paste_from_clipboard())

    def _on_file_drop(self, data):
        """Handle files/folders dropped on the path frame."""
        try:
            paths = list(self.tk.splitlist(data))
        except Exception:
            paths = [data]
        if not paths:
            return
        path = paths[0]
        if os.path.isdir(path):
            self.input_path.set(path)
            self.log(f"Input folder set via drop: {path}")
        elif os.path.isfile(path):
            self._process_dropped_file(path)

    def _paste_from_clipboard(self):
        """Read clipboard and handle as a file/folder path."""
        try:
            raw = self.clipboard_get().strip()
        except tk.TclError:
            return
        if not raw:
            return
        # Strip surrounding quotes if present (common when copying from file manager)
        path = raw.strip("\"'")
        if os.path.isdir(path):
            self.input_path.set(path)
            self.log(f"Input folder set via paste: {path}")
        elif os.path.isfile(path):
            self._process_dropped_file(path)

    def _process_dropped_file(self, file_path):
        """Search-convert a single dropped file."""
        if not self.output_path.get():
            self.after(0, lambda: messagebox.showerror(
                "No Output Folder",
                "Please set an output folder first."
            ))
            self.log("Dropped file ignored — no output folder set.")
            return
        self.log(f"Processing dropped file: {os.path.basename(file_path)}")
        self._stop_event.clear()
        self._pause_event.set()
        self.start_button.config(state="disabled")
        self.pause_button.config(state="normal", text="Pause", bg="#e67e00")
        self.stop_button.config(state="normal")
        def run():
            try:
                self._update_progress(0, 1)
                self.convert_image(file_path)
                self._update_progress(1, 1)
                self.log("Dropped file converted successfully.")
            except Exception as e:
                self.log(f"Error processing dropped file: {e}")
            finally:
                self._reset_progress()
                self.after(0, self._reset_buttons)
        threading.Thread(target=run, daemon=True).start()

    # ------------------------------------------------------------------
    # Pause / Stop / Mode helpers
    # ------------------------------------------------------------------
    def _reset_buttons(self):
        """Re-enable Start and disable Pause/Stop. Always called from main thread."""
        self.start_button.config(state="normal")
        self.pause_button.config(state="disabled", text="Pause", bg="#e67e00")
        self.stop_button.config(state="disabled")
        self._pause_event.set()
        self._stop_event.clear()

    def toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_button.config(text="Resume", bg="#27ae60")
            self.log("Paused - click Resume to continue.")
        else:
            self._pause_event.set()
            self.pause_button.config(text="Pause", bg="#e67e00")
            self.log("Resumed")

    def request_stop(self):
        self._stop_event.set()
        self._pause_event.set()
        self.pause_button.config(state="disabled")
        self.stop_button.config(state="disabled")
        self.log("Stop requested - finishing current file...")

    def _check_pause_stop(self):
        """Block while paused. Returns True if stop has been requested."""
        self._pause_event.wait()
        return self._stop_event.is_set()

    def toggle_mode(self):
        if self.mode.get() == "bulk":
            self.search_frame.pack_forget()
        else:
            self.search_frame.pack(fill="x", padx=20, pady=10, after=self.mode_frame)

    def _toggle_theme(self):
        """Switch between light and dark theme."""
        self._theme.set("dark" if self._theme.get() == "light" else "light")
        self._apply_theme()

    def _check_for_updates(self, silent=False):
        """Check GitHub releases for a newer version (background thread).

        If silent (startup), failures are logged without a dialog.
        If an update is found, prompts the user to download and replace.
        """
        def _check():
            try:
                url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                latest = data.get("tag_name", "").lstrip("v")
                current = VERSION
                current_parts = tuple(int(p) for p in current.split("."))
                latest_parts = tuple(int(p) for p in latest.split(".")) if latest else (0,)

                if latest_parts <= current_parts:
                    if not silent:
                        self.after(0, lambda: messagebox.showinfo(
                            "No Updates", f"You are running the latest version ({current})."
                        ))
                    self.after(0, lambda: self.log(f"Version check: up to date ({current})"))
                    return

                # Update available — prompt user
                msg = (
                    f"Version {latest} is available (you have {current}).\n"
                    "Would you like to download it now?"
                )
                result = [False]
                ev = threading.Event()
                def ask():
                    result[0] = messagebox.askyesno("Update Available", msg)
                    ev.set()
                self.after(0, ask)
                ev.wait()

                if not result[0]:
                    self.after(0, lambda: self.log(f"Update to v{latest} declined."))
                    return

                # Download the new source from the release tag (stable, branch-independent)
                tag = data.get("tag_name", "")
                raw_url = (
                    f"https://raw.githubusercontent.com/{GITHUB_REPO}/{tag}/ArkIndex.py"
                )
                req = urllib.request.Request(raw_url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    new_code = resp.read()

                # Write to a temp file, then atomically replace the current script
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    dir=CURRENT_SCRIPT.parent,
                    prefix=".update_",
                    suffix=".py",
                    delete=False,
                )
                try:
                    tmp.write(new_code)
                    tmp.close()
                    os.replace(tmp.name, str(CURRENT_SCRIPT))
                except Exception:
                    try:
                        os.unlink(tmp.name)
                    except Exception:
                        pass
                    raise

                self.after(0, lambda: self.log(
                    "Update applied. Please restart the application."
                ))
                self.after(0, lambda: messagebox.showinfo(
                    "Update Complete",
                    "The new version has been downloaded and saved.\n"
                    "Please restart the application to use it."
                ))

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    # No releases yet — silently treat as up to date
                    self.after(0, lambda: self.log(
                        f"Version check: no releases found ({GITHUB_REPO})"
                    ))
                else:
                    self.after(0, lambda: self.log(f"Update check failed: {e}"))
                    if not silent:
                        self.after(0, lambda: messagebox.showerror(
                            "Update Check Failed",
                            f"Could not check for updates:\n{e}"
                        ))
            except Exception as e:
                if not silent:
                    self.after(0, lambda: messagebox.showerror(
                        "Update Check Failed",
                        f"Could not check for updates:\n{e}"
                    ))
                self.after(0, lambda: self.log(f"Update check failed: {e}"))

        threading.Thread(target=_check, daemon=True).start()

    def _apply_theme(self):
        """Recursively apply the current theme to all widgets."""
        theme = THEMES[self._theme.get()]
        self.configure(bg=theme["bg"])
        self._theme_widgets(self, theme)

    def _theme_widgets(self, parent, theme):
        """Walk all children and apply theme colors."""
        for child in parent.winfo_children():
            cls = child.winfo_class()
            if cls in ("Frame", "Labelframe"):
                child.configure(bg=theme["bg"])
                if cls == "Labelframe":
                    try:
                        child.tk.call(child._w, "configure",
                                      "-foreground", theme["fg"])
                    except tk.TclError:
                        pass
            elif cls == "Label":
                child.configure(bg=theme["bg"], fg=theme["fg"])
            elif cls in ("Entry", "Text"):
                child.configure(
                    bg=theme["entry_bg"],
                    fg=theme["entry_fg"],
                    insertbackground=theme["fg"],
                    selectbackground=theme["select_bg"],
                )
            elif cls == "Canvas":
                child.configure(bg=theme["bg"])
            elif cls == "Radiobutton":
                child.configure(bg=theme["bg"], fg=theme["fg"],
                              selectcolor=theme["bg"],
                              activebackground=theme["bg"])
            elif cls == "Button":
                if child not in (
                    self.start_button,
                    self.pause_button,
                    self.stop_button,
                    self.export_button,
                ):
                    child.configure(bg=theme["button_bg"], fg=theme["button_fg"],
                                  activebackground=theme["button_bg"])
            self._theme_widgets(child, theme)

        # Style the title label explicitly
        if self._title_label:
            self._title_label.configure(bg=theme["title_bg"], fg=theme["title_fg"])

        # Re-color title bar container
        title_frame = self._title_label.master if self._title_label else None
        if title_frame:
            title_frame.configure(bg=theme["title_bg"])

    # ------------------------------------------------------------------
    # Logging & browsing
    # ------------------------------------------------------------------
    def log(self, message):
        if threading.current_thread() is not threading.main_thread():
            self.after_idle(lambda m=message: self.log(m))
            return
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see(tk.END)
        self.update_idletasks()
        self._write_log_file(message)

    def _write_log_file(self, message):
        """Append *message* to the session log file in <output>/logs/."""
        if not self._log_file:
            out = self.output_path.get().strip()
            if not out:
                return
            try:
                ts = time.strftime("%Y-%m-%d_%H-%M-%S")
                log_dir = Path(out) / "logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                self._log_file = log_dir / f"session_log_{ts}.txt"
            except OSError:
                return
        try:
            with open(self._log_file, "a") as f:
                f.write(f"{message}\n")
        except OSError:
            pass

    def _settings_path(self):
        """Path to the instance-local settings file in the system temp directory."""
        import tempfile
        user = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))
        return Path(tempfile.gettempdir()) / f"tiff_lookup_settings_{user}.json"

    def _save_settings(self):
        """Persist current folders, mode, theme, and window geometry."""
        data = {
            "input_path": self.input_path.get(),
            "output_path": self.output_path.get(),
            "mode": self.mode.get(),
            "theme": self._theme.get(),
            "geometry": self.winfo_geometry(),
        }
        try:
            with open(self._settings_path(), "w") as f:
                json.dump(data, f)
        except OSError:
            pass

    def _load_settings(self):
        """Restore folders, mode, theme, and window geometry from saved settings."""
        path = self._settings_path()
        try:
            with open(path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            # First run — detect system theme as default
            self._theme.set(_detect_system_theme())
            return
        if data.get("input_path"):
            self.input_path.set(data["input_path"])
        if data.get("output_path"):
            self.output_path.set(data["output_path"])
        if data.get("mode") in ("search", "bulk"):
            self.mode.set(data["mode"])
            self.toggle_mode()
        if data.get("theme") in ("light", "dark"):
            self._theme.set(data["theme"])
        else:
            self._theme.set(_detect_system_theme())
        if data.get("geometry"):
            self.geometry(data["geometry"])

    def _on_close(self):
        """Save settings before quitting."""
        self._save_settings()
        self.destroy()

    def _export_results(self):
        """Save matched-file scores and conversion log to a user-chosen CSV."""
        if not self._last_scores and not self._conversion_log:
            messagebox.showinfo(
                "No Results",
                "No search or conversion results to export yet.\n\n"
                "Run a search or bulk conversion first.",
                parent=self,
            )
            return

        ts = time.strftime("%Y-%m-%d_%H-%M-%S")
        path = filedialog.asksaveasfilename(
            title="Export Results",
            defaultextension=".csv",
            initialfile=f"results_{ts}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return

        try:
            with open(path, "w", newline="") as f:
                import csv
                writer = csv.writer(f)

                if self._last_scores:
                    writer.writerow(["=== Search Results ==="])
                    writer.writerow(["File Path", "Total Matches", "Name Context", "Score"])
                    for file_path, score in sorted(
                        self._last_scores.items(), key=lambda x: x[1], reverse=True
                    ):
                        name_ctx = score // 1000
                        total = score % 1000
                        writer.writerow([file_path, total, name_ctx, score])
                    writer.writerow([])

                if self._conversion_log:
                    writer.writerow(["=== Conversion Log ==="])
                    writer.writerow([
                        "Source File", "Output File", "Degree Type",
                        "Course", "Date", "Year",
                    ])
                    for entry in self._conversion_log:
                        writer.writerow([
                            entry["source"], entry["output"], entry["degree_type"],
                            entry["course"], entry["date"], entry["year"],
                        ])
                    writer.writerow([])

            self.log(f"Results exported to {path}")
            messagebox.showinfo("Export Complete", f"Results saved to:\n{path}", parent=self)
        except OSError as e:
            self.log(f"Export failed: {e}")
            messagebox.showerror("Export Failed", str(e), parent=self)

    def _preprocess_for_ocr(self, img):
        """Enhance image for better OCR accuracy.
        
        Applies grayscale, autocontrast, denoise, and sharpen using Pillow.
        Returns an RGB PIL Image ready for pytesseract.
        """
        img = img.convert("L")
        img = ImageOps.autocontrast(img, cutoff=3)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = img.filter(ImageFilter.SHARPEN)
        return img.convert("RGB")

    def browse_input(self):
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.input_path.set(folder)

    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_path.set(folder)

    # ------------------------------------------------------------------
    # Threading entry point
    # ------------------------------------------------------------------
    def start(self):
        input_folder = self.input_path.get()
        output_folder = self.output_path.get()

        if not input_folder or not output_folder:
            messagebox.showerror("Error", "Please provide input folder and output folder")
            return

        if self.mode.get() == "search":
            name = self.search_name.get()
            if not name:
                messagebox.showerror("Error", "Please provide name to search")
                return

        self._stop_event.clear()
        self._pause_event.set()
        self.start_button.config(state="disabled")
        self.pause_button.config(state="normal", text="Pause", bg="#e67e00")
        self.stop_button.config(state="normal")

        thread = threading.Thread(target=self.route_mode)
        thread.daemon = True
        thread.start()

    def route_mode(self):
        try:
            if self.mode.get() == "search":
                self.search_mode()
                return
            else:
                self.bulk_mode()
        except Exception as e:
            self.log(f"Error: {str(e)}")
            self.after(0, lambda e=e: messagebox.showerror("Error", str(e)))
        finally:
            if self.mode.get() == "bulk":
                self.after(0, self._reset_buttons)

    # ------------------------------------------------------------------
    # Search mode
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_name(text: str) -> str:
        """Extract name from OCR text using name labels, returned as 'First [Middle] Last'."""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            m = _NAME_LABEL_RE.search(line)
            if not m:
                continue
            after_label = line[m.end():].strip().rstrip(".")
            if after_label and _STUDENT_NO_RE.search(after_label):
                after_label = ""
            if not after_label:
                for j in range(i + 1, min(i + 3, len(lines))):
                    candidate = lines[j].strip().rstrip(".")
                    if candidate:
                        after_label = candidate
                        if _STUDENT_NO_RE.search(after_label):
                            after_label = ""
                            continue
                        break
            if after_label:
                return after_label
        return ""

    @staticmethod
    def _format_name(raw: str) -> str:
        """
        Parse name in 'Last, First Mi' or 'First Mi Last' format.
        Returns 'Last, First [Mi.]'.
        """
        raw = raw.strip().rstrip(".")
        if "," in raw:
            last_part, rest = raw.split(",", 1)
            last = last_part.strip().rstrip(".")
            parts = rest.strip().split()
            first = parts[0].rstrip(".")
            middle_parts = [p.rstrip(".") for p in parts[1:]]
        else:
            parts = raw.split()
            first = parts[0].rstrip(".")
            last = parts[-1].rstrip(".")
            middle_parts = [p.rstrip(".") for p in parts[1:-1]]
        middle = " ".join(middle_parts)
        if middle:
            return f"{last}, {first} {middle}."
        return f"{last}, {first}"

    @staticmethod
    def _has_valid_match(text: str, keyword: str) -> bool:
        """True if *keyword* appears as a whole word not preceded by a digit on the same line."""
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        for line in text.split("\n"):
            for m in pattern.finditer(line):
                j = m.start() - 1
                while j >= 0 and line[j].isspace():
                    j -= 1
                if j < 0 or not line[j].isdigit():
                    return True
        return False

    @staticmethod
    def _in_name_context(text: str, keyword: str) -> bool:
        """Return True if *keyword* as a whole word appears within 2 lines of a name label."""
        pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if _NAME_LABEL_RE.search(line):
                for j in range(i, min(i + 3, len(lines))):
                    if pattern.search(lines[j]):
                        return True
        return False

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Return a similarity ratio (0-1) between two strings."""
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio()

    def search_mode(self):
        self.log("=== Starting Search ===")

        if not self._ensure_index():
            self.log("Search cancelled — no index available.")
            self.after(0, self._reset_buttons)
            return

        input_folder = self.input_path.get()
        name = self.search_name.get()
        self.log(f"Searching for: {name}")

        keywords = name.lower().split()
        scores = {}

        all_files = [
            os.path.join(root, file)
            for root, dirs, files in os.walk(input_folder, followlinks=False)
            for file in files
            if file.lower().endswith(self.valid_ext)
        ]
        total = len(all_files)
        self.log(f"Scanning {total} file(s)...")
        self._update_progress(0, total)

        index = self._load_index()
        self._search_index = index
        cache_hits = 0

        for i, file_path in enumerate(all_files, start=1):
            self._update_progress(i, total)
            if self._check_pause_stop():
                self.log("Search stopped by user.")
                self._reset_progress()
                break

            image = os.path.basename(file_path)
            self.log(f"Scanning {i}/{total}: {image}")
            try:
                cached = self._get_cached_text(index, file_path)
                if cached:
                    text = cached
                    cache_hits += 1
                else:
                    img = self.open_as_image(file_path)
                    if img is None:
                        continue
                    w, h = img.size
                    if w <= 40 or h <= 60:
                        self.log(f"  Skipped — image too small for OCR: {image}")
                        continue
                    top_third = img.crop((20, 20, w - 20, (h // 3) + 60))
                    text = pytesseract.image_to_string(self._preprocess_for_ocr(top_third))
                    self._index_entry(index, file_path, ocr_text=text)
                matched_words = [
                    word for word in keywords if self._has_valid_match(text, word)
                ]
                count = len(matched_words)
                if count > 0:
                    name_ctx = sum(
                        1 for kw in matched_words if self._in_name_context(text, kw)
                    )
                    scores[file_path] = name_ctx * 1000 + count
                    ctx_info = f", {name_ctx}/{len(keywords)} in name context" if name_ctx else ""
                    if count == len(keywords):
                        self.log(f"Full match ({count}/{len(keywords)}{ctx_info}): {file_path}")
                    else:
                        self.log(f"~ {count}/{len(keywords)} keyword(s) matched{ctx_info}: {file_path}")
            except Exception as e:
                self.log(f"Error processing {file_path}: {e}")

        self._save_index(index)
        self._search_index = None
        self._last_scores = scores
        self._last_keywords = keywords
        if total > 0:
            self.log(f"Index cache hits: {cache_hits}/{total}")

        # -- Also search already-converted PDFs in the output folder ----
        output_folder = self.output_path.get()
        seen_paths = set(all_files)
        pdf_hits = 0
        if output_folder and os.path.isdir(output_folder):
            self.log("Searching already-converted PDFs...")
            pdf_files = []
            for root, dirs, files in os.walk(output_folder, followlinks=False):
                for file in files:
                    fp = os.path.join(root, file)
                    if file.lower().endswith(".pdf") and fp not in seen_paths:
                        pdf_files.append(fp)
            pdf_total = len(pdf_files)
            self._update_progress(0, total + pdf_total)
            for i, file_path in enumerate(pdf_files, start=1):
                self._update_progress(total + i, total + pdf_total)
                if self._check_pause_stop():
                    self._reset_progress()
                    break
                try:
                    doc = pymupdf.open(file_path)
                    try:
                        text = "".join(page.get_text() for page in doc)
                    finally:
                        doc.close()
                    if not text.strip():
                        continue
                    matched_words = [
                        word for word in keywords if self._has_valid_match(text, word)
                    ]
                    count = len(matched_words)
                    if count > 0:
                        name_ctx = sum(
                            1 for kw in matched_words if self._in_name_context(text, kw)
                        )
                        scores[file_path] = name_ctx * 1000 + count
                        pdf_hits += 1
                        ctx_info = f", {name_ctx}/{len(keywords)} in name context" if name_ctx else ""
                        self.log(f"PDF match ({count}/{len(keywords)}{ctx_info}): {file_path}")
                except Exception as e:
                    self.log(f"Error reading PDF {file_path}: {e}")
            if pdf_hits:
                self.log(f"Found {pdf_hits} matching PDF(s) in output folder.")

        if not scores:
            self.log("No matching image(s) found.")
            self._reset_progress()
            self.after(0, lambda: messagebox.showerror("No Results", "No matching image(s) found."))
            self.after(0, self._reset_buttons)
            return

        best = max(scores.values())
        matched = [f for f, c in scores.items() if c == best]
        self.log(f"Best match: {best}/{len(keywords)} keyword(s) - {len(matched)} file(s)")
        self.matches_found(matched)

    def matches_found(self, matches):
        year = self.search_year.get()

        if year and matches:
            self.log(f"Filtering by year provided: {year}")
            matches = self.filter_year(year, matches)

        if matches and not self._stop_event.is_set():
            self._reset_progress()
            self.log(f"Found {len(matches)} matching image(s)...")
            self.after(0, self.show_preview_window, matches)
        else:
            self._reset_progress()
            if self._stop_event.is_set():
                self.log("Search stopped - no preview shown.")
            else:
                self.log("No matching image(s) found.")
                self.after(0, lambda: messagebox.showerror("No Results", "No matching image(s) found."))
            self.after(0, self._reset_buttons)

    def filter_year(self, year, images):
        self.log(f"Filtering by year: {year}")
        filtered = []
        for file_path in images:
            try:
                text = None
                if self._search_index is not None:
                    text = self._get_cached_text(self._search_index, file_path)
                if text is None:
                    img = self.open_as_image(file_path)
                    if img is None:
                        continue
                    w, h = img.size
                    if w <= 40 or h <= 60:
                        continue
                    top_third = img.crop((20, 20, w - 20, (h // 3) + 60))
                    text = pytesseract.image_to_string(self._preprocess_for_ocr(top_third))
                if year.lower() in text.lower():
                    filtered.append(file_path)
                else:
                    self.log(
                        f"Year '{year}' not found in top third, skipping: "
                        f"{os.path.basename(file_path)}"
                    )
            except Exception as e:
                self.log(f"Error: {str(e)}")
        return filtered

    # ------------------------------------------------------------------
    # Bulk mode
    # ------------------------------------------------------------------
    def bulk_mode(self):
        self.log("=== Starting Bulk mode ===")

        if not self._ensure_index():
            self.log("Bulk conversion cancelled — no index available.")
            self.after(0, self._reset_buttons)
            return

        input_folder = self.input_path.get()
        converted = 0
        errors = 0
        total_files = 0

        for root, dirs, files in os.walk(input_folder, followlinks=False):
            for file in files:
                if file.lower().endswith(self.valid_ext):
                    total_files += 1

        self.log(f"Found {total_files} images to convert...")
        self.log("")
        self._update_progress(0, total_files)

        stopped = False
        processed = 0
        for root, dirs, files in os.walk(input_folder, followlinks=False):
            if stopped:
                break
            for file in files:
                if file.lower().endswith(self.valid_ext):
                    if self._check_pause_stop():
                        self.log("Stopped by user.")
                        stopped = True
                        break
                    try:
                        file_path = os.path.join(root, file)
                        self.log(f"Converting: {file}")
                        self.convert_image(file_path)
                        converted += 1
                    except Exception as e:
                        errors += 1
                        self.log(f"Error: {str(e)}")
                        self.log("")
                    processed += 1
                    self._update_progress(processed, total_files)

        self.log("=" * 50)
        if stopped:
            self.log("Stopped by user.")
        else:
            self.log("Bulk conversion completed.")
        self.log(f"Successfully converted {converted} / {total_files} image(s).")
        self.log(f"Errors: {errors}")
        self.log("=" * 50)

        self._reset_progress()
        label = "Stopped" if stopped else "Complete"
        details = f"Converted {converted} of {total_files} image(s)."
        if errors:
            details += f"\nErrors: {errors}"
        self.after(0, lambda lbl=label: messagebox.showinfo(lbl, details))

    # ------------------------------------------------------------------
    # Preview window
    # ------------------------------------------------------------------
    def show_preview_window(self, matches):
        self.preview_win = tk.Toplevel(self)
        self.preview_win.title("Preview Matched Files")
        self.preview_win.geometry(self.geometry())
        self.preview_win.resizable(True, True)
        self.preview_win.grab_set()

        def on_close():
            self._reset_progress()
            self.after(0, self._reset_buttons)
            self.preview_win.destroy()

        self.preview_win.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(
            self.preview_win,
            text=f"Found {len(matches)} match(es) - select images to convert:",
            font=("Arial", 12, "bold"),
        ).pack(fill="x", padx=15)

        self.canvas_frame = tk.Frame(self.preview_win)
        self.canvas_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        self.canvas = tk.Canvas(self.canvas_frame, bg="#f0f0f0")
        scrollbar = tk.Scrollbar(self.canvas_frame, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.inner_frame = tk.Frame(self.canvas_frame, bg="#f0f0f0")
        canvas_window = self.canvas.create_window((0, 0), window=self.inner_frame, anchor="nw")

        def on_frame_configure(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        def on_canvas_configure(event):
            self.canvas.itemconfig(canvas_window, width=self.canvas.winfo_width())

        self.inner_frame.bind("<Configure>", on_frame_configure)
        self.canvas.bind("<Configure>", on_canvas_configure)

        thumb_size = (160, 160)
        check_vars = []
        self.thumb_refs = []

        for file_path in matches:
            var = tk.BooleanVar(value=True)
            check_vars.append((file_path, var))

            row = tk.Frame(self.inner_frame, bg="#f0f0f0", padx=8, pady=6)
            row.pack(fill="x")

            try:
                img = self.open_as_image(file_path)
                img.thumbnail(thumb_size)
            except Exception as e:
                self.log(f"Error loading preview: {str(e)}")
                img = Image.new("RGB", thumb_size, color=(180, 180, 180))

            tk_img = ImageTk.PhotoImage(img)
            self.thumb_refs.append(tk_img)

            tk_label = tk.Label(
                row,
                image=tk_img,
                bg="#f0f0f0",
                relief="solid",
                bd=1,
                cursor="hand2",
            )
            tk_label.pack(side="left", padx=(0, 10))
            tk_label.bind(
                "<Button-1>",
                lambda e, fp=file_path: self._show_large_preview(fp),
            )

            info_frame = tk.Frame(row, bg="#f0f0f0")
            info_frame.pack(side="left", fill="both", expand=True)

            tk.Label(
                info_frame,
                text=os.path.basename(file_path),
                font=("Arial", 9, "bold"),
                bg="#f0f0f0",
                anchor="w",
                wraplength=480,
            ).pack(anchor="w")

            tk.Label(
                info_frame,
                text=file_path,
                font=["Arial", 8],
                fg="#555",
                bg="#f0f0f0",
                anchor="w",
                wraplength=480,
            ).pack(anchor="w", pady=(2, 6))

            tk.Checkbutton(
                info_frame,
                text="Include In Conversion",
                variable=var,
                bg="#f0f0f0",
                font=["Arial", 8],
            ).pack(anchor="w")

            tk.Frame(self.inner_frame, bg="#cccccc", height=1).pack(fill="x", padx=8)

        btn_bar = tk.Frame(self.preview_win)
        btn_bar.pack(fill="x", padx=15, pady=(4, 0))

        tk.Button(
            btn_bar,
            text="Select All",
            command=lambda: [v.set(True) for _, v in check_vars],
            width=12,
        ).pack(side="left", padx=(0, 5))
        tk.Button(
            btn_bar,
            text="Deselect All",
            command=lambda: [v.set(False) for _, v in check_vars],
            width=12,
        ).pack(side="left")

        action_bar = tk.Frame(self.preview_win)
        action_bar.pack(fill="x", padx=15, pady=15)

        def on_convert():
            selected = [f for f, v in check_vars if v.get()]
            if not selected:
                messagebox.showwarning(
                    "Nothing Selected",
                    "Please check at least one file to convert",
                    parent=self.preview_win,
                )
                return

            self.preview_win.destroy()

            def run():
                total = len(selected)
                self._update_progress(0, total)
                for idx, f in enumerate(selected, start=1):
                    self.convert_image(f)
                    self._update_progress(idx, total)
                self._reset_progress()
                self.log(f"Conversion complete - {total} file(s) converted")
                self.after(0, lambda: messagebox.showinfo(
                    "Success",
                    f"{total} file(s) successfully converted to PDF.",
                ))
                self.after(0, self._reset_buttons)

            threading.Thread(target=run, daemon=True).start()

        tk.Button(
            action_bar,
            text="Convert Selected",
            command=on_convert,
            bg="green",
            fg="white",
            font=("Arial", 10, "bold"),
            width=18,
            height=2,
        ).pack(side="right", padx=(5, 0))
        tk.Button(
            action_bar,
            text="Cancel",
            command=on_close,
            font=("Arial", 10, "bold"),
            width=10,
            height=2,
        ).pack(side="right")

    def _show_large_preview(self, file_path):
        try:
            img = self.open_as_image(file_path)
        except Exception as e:
            messagebox.showerror("Preview Error", f"Could not open image:\n{e}", parent=self.preview_win)
            return

        img = img.convert("RGB")

        win = tk.Toplevel(self.preview_win)
        win.title(os.path.basename(file_path))
        win.resizable(True, True)

        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        max_w = screen_w - 80
        max_h = screen_h - 120

        new_w, new_h = img.width, img.height
        if new_w > max_w or new_h > max_h:
            ratio = min(max_w / new_w, max_h / new_h)
            new_w = int(new_w * ratio)
            new_h = int(new_h * ratio)
            display_img = img.resize((new_w, new_h), Image.LANCZOS)
        else:
            display_img = img.copy()

        tk_img = ImageTk.PhotoImage(display_img)
        refs = [tk_img]

        def _cleanup():
            refs.clear()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _cleanup)

        tk.Label(
            win,
            image=tk_img,
            bg="#f0f0f0",
            relief="solid",
            bd=1,
        ).pack(padx=10, pady=10)

        tk.Label(
            win,
            text=file_path,
            font=["Arial", 8],
            fg="#555",
            wraplength=display_img.width,
        ).pack(padx=10, pady=(0, 10))

    # ------------------------------------------------------------------
    # Image / PDF helpers
    # ------------------------------------------------------------------
    def open_as_image(self, file_path):
        """Open any supported file as a PIL Image. Returns None on failure."""
        path = str(file_path).lower()
        try:
            if path.endswith(".pdf"):
                doc = pymupdf.open(file_path)
                try:
                    page = doc[0]
                    pix = page.get_pixmap(dpi=300)
                    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                finally:
                    doc.close()
            return Image.open(file_path)
        except Exception as e:
            self.log(f"Could not open image: {file_path} — {e}")
            return None

    def _prompt_replace_or_append(self, file_name):
        """Ask user what to do with a duplicate destination filename.
        Blocks calling thread; runs dialog on main thread.
        Returns 'replace', 'append', or 'skip'."""
        result = [None]
        event = threading.Event()

        def ask():
            ans = messagebox.askyesnocancel(
                "File Exists",
                f"File already exists:\n{file_name}\n\n"
                f"Yes  = Replace existing file\n"
                f"No   = Append (merge) pages\n"
                f"Cancel = Skip this file",
                parent=self,
            )
            if ans:
                result[0] = "replace"
            elif ans is False:
                result[0] = "append"
            else:
                result[0] = "skip"
            event.set()

        self.after(0, ask)
        event.wait()
        return result[0]

    def convert_image(self, file_path):
        self.log(f"Converting: {os.path.basename(file_path)}")
        img = self.open_as_image(file_path)
        if img is None:
            self.log("  Skipped — could not read file.")
            return False
        w, h = img.size
        if w <= 40 or h <= 60:
            self.log("  Skipped — image too small for OCR crop region.")
            return False
        top_third = img.crop((20, 20, w - 20, (h // 3) + 60))
        text = pytesseract.image_to_string(self._preprocess_for_ocr(top_third))
        file_name, folder, degree_type, course, date_str, year_str = self.generate_filename(text)

        self._conversion_log.append({
            "source": str(file_path),
            "output": str(Path(self.output_path.get()) / folder / f"{file_name}.pdf"),
            "degree_type": degree_type,
            "course": course,
            "date": date_str,
            "year": year_str,
        })

        # Update index with OCR text and conversion metadata
        index = self._load_index()
        self._index_entry(
            index, file_path,
            ocr_text=text,
            degree_type=degree_type,
            course=course,
            date=date_str,
            year=year_str,
            generated_filename=str(folder / file_name),
        )
        self._save_index(index)

        output_dir = Path(self.output_path.get()) / folder
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{file_name}.pdf"

        if output_file.exists():
            if self.mode.get() == "bulk":
                # Automated duplicate check for bulk mode
                try:
                    existing_text = ""
                    doc = pymupdf.open(output_file)
                    try:
                        for page in doc:
                            existing_text += page.get_text()
                    finally:
                        doc.close()
                    ratio = self._text_similarity(text, existing_text)
                    if ratio >= 0.85:
                        self.log(f"  Skipped — duplicate content ({ratio:.0%} match).")
                        return True
                except Exception as e:
                    self.log(f"  Warning: could not check existing PDF: {e}")

                # Different content — append pages to the existing PDF
                self.log("  Content differs — appending pages.")
                temp_file = output_dir / "temp.pdf"
                ocrmypdf.ocr(
                    file_path,
                    temp_file,
                    deskew=True,
                    force_ocr=True,
                    output_type="pdf",
                )
                self._verify_text_layer(temp_file, text)
                main_doc = pymupdf.open(output_file)
                temp_doc = pymupdf.open(temp_file)
                try:
                    main_doc.insert_pdf(temp_doc)
                finally:
                    main_doc.close()
                    temp_doc.close()
                os.remove(temp_file)
                self.log("  Appended.")
                return True
            else:
                choice = self._prompt_replace_or_append(output_file.name)
                if choice == "skip":
                    self.log("  Skipped.")
                    return True
                if choice == "replace":
                    ocrmypdf.ocr(
                        file_path,
                        output_file,
                        deskew=True,
                        force_ocr=True,
                        output_type="pdf",
                    )
                    self._verify_text_layer(output_file, text)
                    self.log("  Replaced.")
                    return True

                # append
                temp_file = output_dir / "temp.pdf"
                ocrmypdf.ocr(
                    file_path,
                    temp_file,
                    deskew=True,
                    force_ocr=True,
                    output_type="pdf",
                )
                self._verify_text_layer(temp_file, text)
                main_doc = pymupdf.open(output_file)
                temp_doc = pymupdf.open(temp_file)
                try:
                    main_doc.insert_pdf(temp_doc)
                finally:
                    main_doc.close()
                    temp_doc.close()
                os.remove(temp_file)
                self.log("  Appended.")
                return True
        else:
            ocrmypdf.ocr(
                file_path,
                output_file,
                deskew=True,
                force_ocr=True,
                output_type="pdf",
            )
            self._verify_text_layer(output_file, text)
        return False

    # ------------------------------------------------------------------
    # PDF text layer verification
    # ------------------------------------------------------------------
    def _verify_text_layer(self, pdf_path, source_text):
        """Check that the output PDF has a searchable text layer.
        Logs a warning if the extracted text is empty or significantly
        shorter than the source OCR text. Never raises exceptions."""
        try:
            doc = pymupdf.open(pdf_path)
            try:
                extracted = "".join(page.get_text() for page in doc)
            finally:
                doc.close()
            if not extracted.strip():
                self.log(
                    f"  Warning: output PDF has no extractable text layer — "
                    f"OCR may have failed silently: {os.path.basename(pdf_path)}"
                )
            elif source_text and len(extracted) < len(source_text) * 0.1:
                self.log(
                    f"  Warning: output PDF text layer is very sparse "
                    f"({len(extracted)} vs {len(source_text)} chars) — "
                    f"OCR may be incomplete: {os.path.basename(pdf_path)}"
                )
        except Exception as e:
            self.log(f"  Warning: could not verify text layer: {e}")

    # ------------------------------------------------------------------
    # Search index
    # ------------------------------------------------------------------
    def _index_path(self):
        out = self.output_path.get().strip()
        if not out:
            self.log("Warning: output folder not set, cannot determine index path")
            return ""
        return os.path.join(out, "file_index_python_search_engine.json")

    def _lock_index(self, shared=False):
        """Lock the index lock-file. Returns fd / HANDLE, raises on failure."""
        lock_path = self._index_path() + ".lock"
        if os.name == "nt":
            return _lock_index_windows(lock_path, shared)
        fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
        import fcntl
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        fcntl.flock(fd, mode)
        return fd

    def _unlock_index(self, fd_or_handle):
        """Release a lock obtained by _lock_index."""
        if os.name == "nt":
            _unlock_index_windows(fd_or_handle)
            return
        try:
            import fcntl
            fcntl.flock(fd_or_handle, fcntl.LOCK_UN)
        finally:
            os.close(fd_or_handle)

    def _ensure_index(self):
        """Check if the index file exists. If missing, prompt user on the main thread.

        Returns True to proceed, False to cancel the calling operation.
        Safe to call from any thread.
        """
        path = self._index_path()
        if not path:
            return False
        if os.path.exists(path):
            return True

        result = [None]
        event = threading.Event()

        def ask():
            ans = messagebox.askyesnocancel(
                "Index Not Found",
                "No search index exists in the output folder.\n\n"
                "Yes   = Create a new empty index\n"
                "No    = Select an existing encrypted index file to import\n"
                "Cancel = Stop",
                parent=self,
            )
            if ans:
                result[0] = "create"
            elif ans is False:
                import_path = filedialog.askopenfilename(
                    title="Select Index File to Import",
                    filetypes=[("Index files", "*.json"), ("All files", "*.*")],
                    parent=self,
                )
                result[0] = import_path if import_path else "cancel"
            else:
                result[0] = "cancel"
            event.set()

        self.after(0, ask)
        event.wait()

        choice = result[0]
        if choice == "create":
            self._save_index({})
            self.log("New empty index created in output folder.")
            return True
        if choice != "cancel":
            try:
                self._import_index_file(choice)
                self.log(f"Index imported from {choice}.")
                return True
            except Exception as e:
                self.log(f"Failed to import index: {e}")
                self.after(0, lambda e=e: messagebox.showerror("Import Failed", str(e)))
                return False
        return False

    def _import_index_file(self, file_path):
        """Validate an encrypted index file and copy it to the output folder.

        Raises on failure (invalid format, I/O error, etc.).
        """
        with open(file_path) as f:
            raw = f.read()
        if not raw.strip():
            raise ValueError("File is empty")
        decoded = base64.b64decode(raw)
        decompressed = gzip.decompress(decoded)
        data = json.loads(decompressed)
        index_path = self._index_path()
        if not index_path:
            raise ValueError("Output folder not set")
        with open(index_path, "w") as f:
            f.write(raw)
        return data

    def _import_index_ui(self):
        """Button handler — pick an encrypted index file and import it. Main thread only."""
        path = filedialog.askopenfilename(
            title="Select Index File to Import",
            filetypes=[("Index files", "*.json"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            data = self._import_index_file(path)
            n = len(data)
            self.log(f"Index imported from {path} — {n} entr{'y' if n == 1 else 'ies'}.")
            messagebox.showinfo(
                "Import Successful",
                f"Index imported with {n} entr{'y' if n == 1 else 'ies'}.",
                parent=self,
            )
        except Exception as e:
            self.log(f"Index import failed: {e}")
            messagebox.showerror("Import Failed", str(e), parent=self)

    def _load_index(self):
        path = self._index_path()
        if not path:
            return {}
        fd = self._lock_index(shared=True)
        try:
            with open(path) as f:
                raw = f.read()
            if not raw.strip():
                return {}
            decoded = base64.b64decode(raw)
            decompressed = gzip.decompress(decoded)
            return json.loads(decompressed)
        except (FileNotFoundError, json.JSONDecodeError, base64.binascii.Error, OSError):
            return {}
        finally:
            self._unlock_index(fd)

    def _save_index(self, index):
        path = self._index_path()
        if not path:
            return
        fd = self._lock_index(shared=False)
        try:
            raw = json.dumps(index, indent=2).encode()
            compressed = gzip.compress(raw)
            encoded = base64.b64encode(compressed).decode()
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                f.write(encoded)
            os.replace(tmp, path)
        except OSError as e:
            self.log(f"Warning: could not save index: {e}")
        finally:
            self._unlock_index(fd)

    def _get_cached_text(self, index, file_path):
        abs_path = os.path.abspath(file_path)
        entry = index.get(abs_path)
        if entry is None:
            return None
        try:
            if entry.get("mtime") != os.path.getmtime(file_path):
                return None
        except OSError:
            return None
        return entry.get("ocr_text")

    def _index_entry(self, index, file_path, ocr_text=None, **kw):
        abs_path = os.path.abspath(file_path)
        entry = index.get(abs_path, {})
        if ocr_text is not None:
            entry["ocr_text"] = ocr_text
        try:
            entry["mtime"] = os.path.getmtime(file_path)
        except OSError:
            pass
        entry.update(kw)
        index[abs_path] = entry

    # ------------------------------------------------------------------
    # Filename generation
    # ------------------------------------------------------------------
    def generate_filename(self, text):
        """
        Generate a structured filename and determine output subdirectory.

        Returns: (filename_stem, subfolder) where subfolder is one of:
            "Degree/<year>", "Transcript/<year>", or "Error/<type>"

        Filename template:
            "Last, First [Mi.] (Degree Course) Month DD, YYYY"
        """

        def clean(value):
            """Remove characters invalid in filename."""
            return re.sub(r'[\\/*?:"<>|]', "", value).strip()

        raw_name = self._extract_name(text)
        if raw_name:
            self.log(f"  OCR-extracted name: {raw_name!r}")
        else:
            raw_name = self.search_name.get().strip()
            if raw_name:
                self.log(f"  Using search-field name: {raw_name!r}")
        if not raw_name:
            self.log("  Could not extract name - routing to Error/Name.")
            return "Unknown", Path("Error/Name"), "", "", "", ""
        name = self._format_name(raw_name)

        # -- Detect document type & degree --------------------------
        is_degree = False
        degree_text = ""
        doc_folder = "Transcript"
        for pattern in (
            r"(Associate\s+in\s+(?:\S+\s*){1,2})",
            r"(Bachelor\s+of\s+Science\s+in\s+(?:\S+\s*){1,2})",
            r"(Certificate\s+of\s+Graduation\s+)",
        ):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                degree_text = m.group(0)
                doc_folder = "Degree"
                is_degree = True
                break
        self.log(f"Document Type: {doc_folder}")

        # -- Extract course (up to 9 words) -------------------------
        course_text = ""
        if degree_text:
            lines = text.split("\n")
            degree_line_idx = None
            degree_line = None
            first_word = degree_text.split()[0]

            for i, line in enumerate(lines):
                if re.search(re.escape(first_word), line, re.IGNORECASE):
                    degree_line_idx = i
                    degree_line = line
                    break

            if degree_line_idx is not None:
                degree_start = re.search(re.escape(first_word), degree_line, re.IGNORECASE)
                if degree_start:
                    before_degree = degree_line[: degree_start.start()].strip()
                    if re.search(r"Graduated[\s-]*Received", before_degree, re.IGNORECASE):
                        course_label_line_idx = degree_line_idx - 2
                        if course_label_line_idx >= 0:
                            course_label_line = lines[course_label_line_idx]
                            course_match = re.search(
                                r"Course[:\s]+(.+)", course_label_line, re.IGNORECASE
                            )
                            if course_match:
                                words = course_match.group(1).strip().split()
                                course_text = " ".join(words[:9])
                    else:
                        words = before_degree.split()
                        course_text = " ".join(words[-9:]).strip()
            self.log(f"Course Found: {course_text}")
        else:
            for line in text.split("\n"):
                m = _COURSE_LABEL_RE.search(line)
                if m:
                    after = line[m.end():].strip()
                    if after:
                        words = after.split()
                        course_text = " ".join(words[:9]).strip()
                        break
            if course_text:
                self.log(f"Course found: {course_text}")

        # -- Extract date -------------------------------------------
        date_pattern = r"(" + _DATE_NAMED + r"|" + _DATE_NUMERIC + r")"
        if is_degree:
            context_pat = r"degree\s+received[^\n]*?" + date_pattern
        else:
            context_pat = r"date\s+of\s+admission[:\s]+" + date_pattern

        raw_dates = [
            m.group(1) for m in re.finditer(context_pat, text, re.IGNORECASE)
        ] + [
            m.group(0) for m in re.finditer(date_pattern, text, re.IGNORECASE)
        ]
        seen = set()
        raw_dates = [d for d in raw_dates if not (d in seen or seen.add(d))]

        date_str = year_str = ""
        if raw_dates:
            sorted_dates = sort_dates_chronologically(raw_dates)
            rejected_dates = 0
            while sorted_dates:
                try:
                    date_str, year_str = _normalise_date(sorted_dates[-1])
                except Exception:
                    rejected_dates += 1
                    self.log(f"Rejected dates count: {rejected_dates}")
                    date_str = None
                if date_str is not None:
                    self.log(f"  Accepted: {sorted_dates[-1]!r} -> {date_str!r}")
                    break
                sorted_dates.pop()

        # -- Assemble filename & folder -----------------------------
        if not date_str:
            self.log("  Could not extract date - routing to Error/Date.")
            return clean(name), Path("Error/Date"), doc_folder, course_text, "", ""
        else:
            self.log(f"Found date: {date_str}")

        program_part = f" ({course_text})" if course_text else ""
        file_name = clean(f"{name} {program_part} {date_str}")
        folder = Path(doc_folder) / year_str
        self.log(f"File Name: {file_name}")
        return file_name, folder, doc_folder, course_text, date_str, year_str


def _lock_index_windows(lock_path, shared):
    """Open/create a lock file and acquire a lock via LockFileEx.

    Returns the Windows HANDLE (closable via CloseHandle).
    """
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 1
    FILE_SHARE_WRITE = 2
    OPEN_ALWAYS = 4
    FILE_ATTRIBUTE_NORMAL = 0x80

    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p

    handle = kernel32.CreateFileW(
        lock_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())

    class OVERLAPPED(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_void_p),
            ("InternalHigh", ctypes.c_void_p),
            ("Offset", ctypes.c_uint32),
            ("OffsetHigh", ctypes.c_uint32),
            ("hEvent", ctypes.c_void_p),
        ]

    overlapped = OVERLAPPED()
    flags = 0 if shared else 2  # 2 = LOCKFILE_EXCLUSIVE_LOCK
    kernel32.LockFileEx.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(OVERLAPPED),
    ]
    if not kernel32.LockFileEx(handle, flags, 0, 1, 0, ctypes.byref(overlapped)):
        kernel32.CloseHandle(handle)
        raise ctypes.WinError(ctypes.get_last_error())

    return handle


def _unlock_index_windows(handle):
    """Release a Windows lock and close the handle."""
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class OVERLAPPED(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_void_p),
            ("InternalHigh", ctypes.c_void_p),
            ("Offset", ctypes.c_uint32),
            ("OffsetHigh", ctypes.c_uint32),
            ("hEvent", ctypes.c_void_p),
        ]

    overlapped = OVERLAPPED()
    kernel32.UnlockFileEx.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(OVERLAPPED),
    ]
    kernel32.UnlockFileEx(handle, 0, 1, 0, ctypes.byref(overlapped))
    kernel32.CloseHandle(handle)


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
