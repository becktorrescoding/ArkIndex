"""
Image to PDF Converter
----------------------
Requires system tools:  tesseract, ghostscript, poppler
Requires Python pkgs:   ocrmypdf, pytesseract, Pillow, pymupdf

Run the platform installer first if you haven't already:
  Windows : install_windows.bat
  macOS   : bash install_macos.sh
  Linux   : bash install_linux.sh
"""

import importlib
import os
import platform
import re
import subprocess
import sys
import threading
from pathlib import Path

import ocrmypdf
import pymupdf
import pytesseract
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

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
        (
            "poppler / pdftoppm  (PDF-to-image, required by pdf2image)",
            [["pdftoppm", "-v"], ["pdftoppm", "--version"]],
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
_MONTH_NAME_PAT = (
    r"(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
)
_DATE_NAMED = _MONTH_NAME_PAT + r"[\s,]+\d{1,2}[\s,]+\d{2,4}"
_DATE_NUMERIC = r"\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}"


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
        if len(year) == 2:
            year = "19" + year
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
            year = "19" + year
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
# Application
# ---------------------------------------------------------------------------
class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Image to PDF Converter")
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

        self.create_widgets()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def create_widgets(self):
        title = tk.Label(
            self,
            text="Image to PDF Converter",
            font=("Arial", 14, "bold"),
            bg="#2c3e50",
            fg="white",
            pady=10,
        )
        title.pack(fill="x")

        self.path_frame = tk.Frame(self, padx=20, pady=10)
        self.path_frame.pack(fill="x")

        tk.Label(self.path_frame, text="Input Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        tk.Entry(self.path_frame, textvariable=self.input_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(self.path_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)

        tk.Label(self.path_frame, text="Output Folder:").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(self.path_frame, textvariable=self.output_path, width=40).grid(row=1, column=1, padx=5)
        tk.Button(self.path_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)

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
            text="Optional: Year [Admission/Graduation/DOB] (yyyy):",
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

        log_frame = tk.Frame(self, padx=20, pady=10)
        log_frame.pack(fill="both", expand=True)

        tk.Label(log_frame, text="Processing Log:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=70)
        self.log_text.pack(fill="both", expand=True)

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

    # ------------------------------------------------------------------
    # Logging & browsing
    # ------------------------------------------------------------------
    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.update_idletasks()

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
        self._pause_event.clear()
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
            messagebox.showerror("Error", str(e))
        finally:
            if self.mode.get() == "bulk":
                self.after(0, self._reset_buttons)

    # ------------------------------------------------------------------
    # Search mode
    # ------------------------------------------------------------------
    def search_mode(self):
        self.log("=== Starting Search ===")

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

        for i, file_path in enumerate(all_files, start=1):
            if self._check_pause_stop():
                self.log("Search stopped by user.")
                break

            image = os.path.basename(file_path)
            self.log(f"Scanning {i}/{total}: {image}")
            try:
                img = self.open_as_image(file_path)
                w, h = img.size
                top_third = img.crop((20, 20, w - 20, (h // 3) + 60))
                text = pytesseract.image_to_string(top_third)
                matched_words = [
                    word for word in keywords if word.lower() in text.lower()
                ]
                count = len(matched_words)
                if count > 0:
                    scores[file_path] = count
                    if count == len(keywords):
                        self.log(f"Full match ({count}/{len(keywords)}): {file_path}")
                    else:
                        self.log(f"~ {count}/{len(keywords)} keyword(s) matched: {file_path}")
            except Exception as e:
                self.log(f"Error processing {file_path}: {e}")

        if not scores:
            self.log("No matching image(s) found.")
            messagebox.showerror("No Results", "No matching image(s) found.")
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
            self.log(f"Found {len(matches)} matching image(s)...")
            self.after(0, self.show_preview_window, matches)
        else:
            if self._stop_event.is_set():
                self.log("Search stopped - no preview shown.")
            else:
                self.log("No matching image(s) found.")
                messagebox.showerror("No Results", "No matching image(s) found.")
            self.after(0, self._reset_buttons)

    def filter_year(self, year, images):
        self.log(f"Filtering by year: {year}")
        filtered = []
        for file_path in images:
            try:
                img = self.open_as_image(file_path)
                w, h = img.size
                top_third = img.crop((0, 0, w, h // 3))
                text = pytesseract.image_to_string(top_third)
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

        stopped = False
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

        self.log("=" * 50)
        if stopped:
            self.log("Stopped by user.")
        else:
            self.log("Bulk conversion completed.")
        self.log(f"Successfully converted {converted} / {total_files} image(s).")
        self.log(f"Errors: {errors}")
        self.log("=" * 50)

        label = "Stopped" if stopped else "Complete"
        messagebox.showinfo(label, f"Converted {converted} of {total_files} image(s).\nErrors: {errors}")

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
            self.canvas.itemconfig(canvas_window, width=event.width())

        self.inner_frame.bind("<Configure>", on_frame_configure)
        self.canvas.bind("<Configure>", on_canvas_configure)

        thumb_size = (160, 160)
        check_vars = []
        thumb_refs = []

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
            thumb_refs.append(tk_img)

            tk.Label(
                row,
                image=tk_img,
                bg="#f0f0f0",
                relief="solid",
                bd=1,
            ).pack(side="left", padx=(0, 10))

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
                for f in selected:
                    self.convert_image(f)
                self.log(f"Conversion complete - {len(selected)} file(s) converted")
                messagebox.showinfo(
                    "Success",
                    f"{len(selected)} file(s) successfully converted to PDF.",
                )
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

    # ------------------------------------------------------------------
    # Image / PDF helpers
    # ------------------------------------------------------------------
    def open_as_image(self, file_path):
        """Open any supported file as a PIL Image."""
        path = str(file_path).lower()
        if path.endswith(".pdf"):
            doc = pymupdf.open(file_path)
            page = doc[0]
            pix = page.get_pixmap(dpi=300)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return Image.open(file_path)

    def convert_image(self, file_path):
        img = self.open_as_image(file_path)
        w, h = img.size
        top_third = img.crop((20, 20, w - 20, (h // 3) + 60))
        text = pytesseract.image_to_string(top_third)
        file_name, folder = self.generate_filename(text)

        output_dir = Path(self.output_path.get()) / folder
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{file_name}.pdf"

        if output_file.exists():
            temp_file = output_dir / "temp.pdf"
            ocrmypdf.ocr(
                file_path,
                temp_file,
                deskew=True,
                force_ocr=True,
                output_type="pdf",
            )
            main_doc = pymupdf.open(output_file)
            temp_doc = pymupdf.open(temp_file)
            main_doc.insert_pdf(temp_doc)
            main_doc.close()
            temp_doc.close()
            os.remove(temp_file)
        else:
            ocrmypdf.ocr(
                file_path,
                output_file,
                deskew=True,
                force_ocr=True,
                output_type="pdf",
            )

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

        name = self.search_name.get().strip()
        if len(name.split()) == 3:
            name += "."

        # -- Detect document type & degree --------------------------
        is_degree = False
        degree_text = ""
        doc_folder = "Transcript"
        for pattern in (
            r"(Associate\s+in\s+(?:\S+\s*){1,2})",
            r"(Bachelor\s+of\s+Science\s+in\s+(?:\S+\s*){1,2})",
            r"(Certificate\s+of\s+Graduation\s",
        ):
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                degree_text = m.group(0)
                doc_folder = "Degree"
                is_degree = True
                break

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

        # -- Extract date -------------------------------------------
        date_pattern = r"(" + _DATE_NAMED + r"|" + _DATE_NUMERIC + r")"
        if is_degree:
            context_pat = r"degree\s+received[^\n]*?" + date_pattern
        else:
            context_pat = r"date\s+of\s+admission[:\s]+" + date_pattern

        raw_dates = [
            m.group(1) for m in re.finditer(context_pat, text, re.IGNORECASE)
        ]

        if not raw_dates:
            raw_dates = [
                m.group(0) for m in re.finditer(date_pattern, text, re.IGNORECASE)
            ]

        date_str = year_str = ""
        if raw_dates:
            sorted_dates = sort_dates_chronologically(raw_dates)
            date_str, year_str = _normalise_date(sorted_dates[-1])
            if date_str is None:
                self.log("  Could not normalise extracted date.")

        # -- Assemble filename & folder -----------------------------
        if not date_str:
            self.log("  Could not extract date - routing to Error/Date.")
            return clean(name), Path("Error/Date")

        program_part = f" ({course_text})" if course_text else ""
        file_name = clean(f"{name}{program_part} {date_str}")
        folder = Path(doc_folder) / year_str
        return file_name, folder


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
