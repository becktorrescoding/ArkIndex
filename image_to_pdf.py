"""
Image to PDF Converter
----------------------
Requires system tools:  tesseract, ghostscript, poppler
Requires Python pkgs:   ocrmypdf, pytesseract, Pillow, pdf2image

Run the platform installer first if you haven't already:
  Windows : install_windows.bat
  macOS   : bash install_macos.sh
  Linux   : bash install_linux.sh
"""

import sys
import subprocess
import importlib


def _check_python_version():
    if sys.version_info < (3, 9):
        print(
            f"ERROR: Python 3.9+ is required (you have {sys.version}).\n"
            "Run the installer for your platform to upgrade."
        )
        sys.exit(1)


def _check_system_tool(cmd_candidates: list) -> bool:
    """Try each candidate command; return True if any succeeds."""
    for cmd in cmd_candidates:
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    return False


def _check_python_package(package: str) -> bool:
    try:
        importlib.import_module(package)
        return True
    except ImportError:
        return False


def _installer_hint() -> str:
    import platform
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

    # System binaries — each entry is a list of candidate commands to try
    system_tools = [
        (
            "tesseract  (OCR engine)",
            [["tesseract", "--version"]],
        ),
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
        if not any(_check_system_tool([cmd]) for cmd in candidates):
            missing.append(label)

    # Python packages  (import name → pip install name)
    pkg_map = {
        "ocrmypdf":   "ocrmypdf",
        "pytesseract": "pytesseract",
        "PIL":        "Pillow",
        "pdf2image":  "pdf2image",
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

import os
import re
import ocrmypdf
import pytesseract
from PIL import Image
from pathlib import Path
from pdf2image import convert_from_path
import tkinter as tk
import threading
from tkinter import filedialog, messagebox, scrolledtext

class ImageToPDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image to PDF Converter")
        self.root.geometry("1000x900")
        self.root.resizable(width=True, height=True)

        # Variables
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.search_name = tk.StringVar()
        self.search_year = tk.StringVar()
        self.mode = tk.StringVar(value="search")  # ADDED for mode selection
        self.valid_ext = ('.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.TIF', '.tiff', '.tif')

        # Pause / stop control
        self._pause_event = threading.Event()
        self._pause_event.set()   # set = not paused
        self._stop_event  = threading.Event()

        self.create_widgets()

    def create_widgets(self):
        # Title
        title = tk.Label(
            self.root,
            text="Image to PDF Converter",
            font=("Arial", 14, "bold"),
            bg="#2c3e50",
            fg="white",
            pady=10
        )
        title.pack(fill="x")

        # Path Selection
        self.path_frame = tk.Frame(self.root, padx=20, pady=10)
        self.path_frame.pack(fill="x")

        tk.Label(self.path_frame, text="Input Folder:").grid(row=0, column=0, sticky=tk.W, pady=5)
        tk.Entry(self.path_frame, textvariable=self.input_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(self.path_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)

        tk.Label(self.path_frame, text="Output Folder:").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(self.path_frame, textvariable=self.output_path, width=40).grid(row=1, column=1, padx=5)
        tk.Button(self.path_frame, text="Browse", command=self.browse_output).grid(row=1, column=2)

        # Mode Selection
        self.mode_frame = tk.LabelFrame(
            self.root,
            text="Operation Mode",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=10
        )
        self.mode_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Radiobutton(
            self.mode_frame,
            text="Search Mode - Find specific documents by name",
            variable=self.mode,
            value="search",
            command=self.toggle_mode,
            font=("Arial", 9)
        ).pack(anchor="w", pady=3)

        tk.Radiobutton(
            self.mode_frame,
            text="Bulk Convert Mode - Convert all images to PDFs",
            variable=self.mode,
            value="bulk",
            command=self.toggle_mode,
            font=("Arial", 9)
        ).pack(anchor="w", pady=3)

        # Search Options Frame
        self.search_frame = tk.Frame(self.root, padx=20, pady=10)
        self.search_frame.pack(fill="x")

        tk.Label(self.search_frame, text="Search Name:", font=("Arial", 9)).grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(self.search_frame, textvariable=self.search_name, width=30).grid(row=0, column=1, padx=5, sticky="w")

        tk.Label(self.search_frame, text="Year (Optional):", font=("Arial", 9)).grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(self.search_frame, textvariable=self.search_year, width=10).grid(row=1, column=1, padx=5, sticky="w")

        # Button row: Start | Pause | Stop
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=5)

        self.start_button = tk.Button(
            btn_frame,
            text="Start Search",
            command=self.start_search,
            bg="green",
            fg="white",
            font=("Arial", 11, "bold"),
            width=14,
            height=2
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
            state="disabled"
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
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=5)

        # Processing Log
        log_frame = tk.Frame(self.root, padx=20, pady=10)
        log_frame.pack(fill="both", expand=True)

        tk.Label(log_frame, text="Processing Log:", font=("Arial", 10, "bold")).pack(anchor="w")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=70)
        self.log_text.pack(fill="both", expand=True)

    def _reset_buttons(self):
        """Re-enable Start and disable Pause/Stop — always called from main thread."""
        self.start_button.config(state="normal")
        self.pause_button.config(state="disabled", text="Pause", bg="#e67e00")
        self.stop_button.config(state="disabled")
        self._pause_event.set()
        self._stop_event.clear()

    def toggle_pause(self):
        """Pause or resume processing."""
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_button.config(text="Resume", bg="#27ae60")
            self.log("⏸ Paused — click Resume to continue.")
        else:
            self._pause_event.set()
            self.pause_button.config(text="Pause", bg="#e67e00")
            self.log("▶ Resumed.")

    def request_stop(self):
        """Signal the worker thread to stop after the current file."""
        self._stop_event.set()
        self._pause_event.set()   # unblock if paused so thread can exit
        self.pause_button.config(state="disabled")
        self.stop_button.config(state="disabled")
        self.log("⏹ Stop requested — finishing current file...")

    def _check_pause_stop(self):
        """
        Call this between files in any processing loop.
        Blocks while paused. Returns True if a stop has been requested.
        """
        self._pause_event.wait()   # blocks until event is set (i.e. not paused)
        return self._stop_event.is_set()

    def toggle_mode(self):
        """Show/hide search options based on mode"""
        if self.mode.get() == "bulk":
            self.search_frame.pack_forget()
        else:
            self.search_frame.pack(fill="x", padx=20, pady=10, after=self.mode_frame)

    def log(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def browse_input(self):
        folder = filedialog.askdirectory(title="Select Input Folder")
        if folder:
            self.input_path.set(folder)

    def browse_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.output_path.set(folder)

    def start_search(self):
        """Validate inputs and start processing"""
        input_folder = self.input_path.get()
        output_folder = self.output_path.get()

        # Basic validation for all modes
        if not input_folder or not output_folder:
            messagebox.showerror("Error", "Please select both input and output folders.")
            return

        # Mode-specific validation
        if self.mode.get() == "search":
            name = self.search_name.get()
            if not name:
                messagebox.showerror("Error", "Please enter a name to search for.")
                return

        # Reset and start
        self._stop_event.clear()
        self._pause_event.set()
        self.start_button.config(state="disabled")
        self.pause_button.config(state="normal", text="Pause", bg="#e67e00")
        self.stop_button.config(state="normal")

        thread = threading.Thread(target=self.do_search)
        thread.daemon = True
        thread.start()

    def do_search(self):
        """Route to correct mode and handle errors"""
        try:
            if self.mode.get() == "search":
                self.search_mode()
                # Search mode: buttons re-enabled by preview window on close,
                # or immediately below if nothing was found / stopped early.
                return
            else:
                self.bulk_convert_mode()

        except Exception as e:
            self.log(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))

        finally:
            # Always reset for bulk mode; search mode resets via preview close
            if self.mode.get() != "search":
                self.root.after(0, self._reset_buttons)

    def search_mode(self):
        """Search for specific documents"""
        self.log("=== Starting Search Mode ===")

        input_folder = self.input_path.get()
        name = self.search_name.get()
        year = self.search_year.get()

        self.log(f"Searching for {name}")
        matched_files = self.search_folders(input_folder, name)

        if year and matched_files:
            self.log(f"Filtering by year: {year}")
            matched_files = self.search_images(matched_files, year)

        if matched_files and not self._stop_event.is_set():
            self.log(f"Found {len(matched_files)} matching file(s). Opening preview...")
            self.root.after(0, lambda: self.show_preview_window(matched_files))
        else:
            if self._stop_event.is_set():
                self.log("Search stopped — no preview shown.")
            else:
                self.log("No matching files found.")
                messagebox.showinfo("No Results", "No matching documents found.")
            self.root.after(0, self._reset_buttons)

    def bulk_convert_mode(self):
        """Convert all images to PDFs"""
        self.log("=== Starting Bulk Convert Mode ===")

        input_folder = Path(self.input_path.get())
        output_folder = Path(self.output_path.get())

        if not input_folder.exists():
            raise FileNotFoundError(f"Input folder not found: {input_folder}")

        converted = 0
        errors = 0
        total_files = 0

        # Count files
        for root, dirs, files in os.walk(input_folder, followlinks=False):
            for file in files:
                if file.lower().endswith(self.valid_ext):
                    total_files += 1

        self.log(f"Found {total_files} image(s) to convert.")
        self.log("")

        # Convert each file
        stopped = False
        for root, dirs, files in os.walk(input_folder, followlinks=False):
            if stopped:
                break
            for file in files:
                if file.lower().endswith(self.valid_ext):
                    if self._check_pause_stop():
                        self.log("⏹ Stopped by user.")
                        stopped = True
                        break
                    img_path = Path(root) / file

                    try:
                        self.log(f"Converting: {file}")

                        # Extract text and generate structured filename
                        img = self.open_as_image(img_path)
                        w, h = img.size
                        full_text = pytesseract.image_to_string(img)
                        name_text = pytesseract.image_to_string(img.crop((0, 0, w, h // 4)))
                        output_stem, subfolder = self.generate_filename(name_text, full_text, full_text, img_path.stem)

                        output_dir = output_folder / subfolder
                        output_dir.mkdir(parents=True, exist_ok=True)
                        output_file = output_dir / f"{output_stem}.pdf"

                        # Avoid overwriting existing files
                        counter = 1
                        while output_file.exists():
                            output_file = output_dir / f"{output_stem}_{counter}.pdf"
                            counter += 1

                        ocrmypdf.ocr(
                            img_path,
                            output_file,
                            deskew=True,
                            force_ocr=True,
                            output_type="pdf"
                        )

                        converted += 1
                        self.log(f"  ✓ Success ({converted}/{total_files})")
                        self.log("")

                    except Exception as e:
                        errors += 1
                        self.log(f"  ✗ Error: {str(e)}")
                        self.log("")

        # Summary
        self.log("=" * 50)
        if stopped:
            self.log("Bulk conversion stopped by user.")
        else:
            self.log("Bulk conversion complete!")
        self.log(f"Successfully converted: {converted}/{total_files}")
        self.log(f"Errors: {errors}")
        self.log("=" * 50)

        label = "Stopped" if stopped else "Complete"
        messagebox.showinfo(label, f"Converted {converted} of {total_files} file(s).\n{errors} error(s).")

    def show_preview_window(self, matched_files):
        """
        Open a preview window showing thumbnails of all matched files.
        The user selects which ones to convert, then clicks Convert Selected.
        """
        import io
        preview_win = tk.Toplevel(self.root)
        preview_win.title("Preview Matched Files")
        preview_win.geometry("780x560")
        preview_win.resizable(True, True)
        preview_win.grab_set()

        def on_close():
            self.root.after(0, self._reset_buttons)
            preview_win.destroy()

        preview_win.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(
            preview_win,
            text=f"Found {len(matched_files)} match(es) — select files to convert:",
            font=("Arial", 10, "bold"),
            pady=8,
        ).pack(fill="x", padx=15)

        canvas_frame = tk.Frame(preview_win)
        canvas_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        canvas = tk.Canvas(canvas_frame, bg="#f0f0f0")
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner_frame = tk.Frame(canvas, bg="#f0f0f0")
        canvas_window = canvas.create_window((0, 0), window=inner_frame, anchor="nw")

        def on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        inner_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        THUMB_SIZE = (160, 160)
        check_vars = []
        thumb_refs = []

        for idx, file_path in enumerate(matched_files):
            var = tk.BooleanVar(value=True)
            check_vars.append(var)

            row = tk.Frame(inner_frame, bg="#f0f0f0", pady=6, padx=8)
            row.pack(fill="x")

            try:
                img = Image.open(file_path)
                img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PPM")
                tk_img = tk.PhotoImage(data=buf.getvalue())
            except Exception:
                placeholder = Image.new("RGB", THUMB_SIZE, color=(180, 180, 180))
                buf = io.BytesIO()
                placeholder.save(buf, format="PPM")
                tk_img = tk.PhotoImage(data=buf.getvalue())

            thumb_refs.append(tk_img)

            tk.Label(row, image=tk_img, bg="#f0f0f0", relief="solid", bd=1).pack(side="left", padx=(0, 10))

            info_frame = tk.Frame(row, bg="#f0f0f0")
            info_frame.pack(side="left", fill="both", expand=True)

            tk.Label(info_frame, text=os.path.basename(file_path),
                     font=("Arial", 9, "bold"), bg="#f0f0f0", anchor="w", wraplength=480).pack(anchor="w")
            tk.Label(info_frame, text=file_path,
                     font=("Arial", 8), fg="#555", bg="#f0f0f0", anchor="w", wraplength=480).pack(anchor="w", pady=(2, 6))
            tk.Checkbutton(info_frame, text="Include in conversion",
                           variable=var, bg="#f0f0f0", font=("Arial", 9)).pack(anchor="w")

            tk.Frame(inner_frame, bg="#cccccc", height=1).pack(fill="x", padx=8)

        btn_bar = tk.Frame(preview_win)
        btn_bar.pack(fill="x", padx=15, pady=(4, 0))

        tk.Button(btn_bar, text="Select All",
                  command=lambda: [v.set(True) for v in check_vars], width=12).pack(side="left", padx=(0, 5))
        tk.Button(btn_bar, text="Deselect All",
                  command=lambda: [v.set(False) for v in check_vars], width=12).pack(side="left")

        action_bar = tk.Frame(preview_win)
        action_bar.pack(fill="x", padx=15, pady=10)

        def on_convert():
            selected = [f for f, v in zip(matched_files, check_vars) if v.get()]
            if not selected:
                messagebox.showwarning("Nothing Selected", "Please check at least one file to convert.", parent=preview_win)
                return
            preview_win.destroy()
            def run():
                for f in selected:
                    self.convert_image(f)
                self.log(f"Conversion complete — {len(selected)} file(s) converted.")
                messagebox.showinfo("Success", f"{len(selected)} file(s) successfully converted to PDF.")
                self.root.after(0, self._reset_buttons)
            threading.Thread(target=run, daemon=True).start()

        tk.Button(action_bar, text="Convert Selected", command=on_convert,
                  bg="green", fg="white", font=("Arial", 10, "bold"), width=18, height=2).pack(side="right", padx=(5, 0))
        tk.Button(action_bar, text="Cancel", command=on_close,
                  font=("Arial", 10), width=10, height=2).pack(side="right")

    def open_as_image(self, file_path):
        """Open any supported file as a PIL Image (first page for PDFs)."""
        if str(file_path).lower().endswith('.pdf'):
            self.log("Document found")
            pages = convert_from_path(file_path, dpi = 600)
            self.log(f"Number of pages: {len(pages)}")
            return pages[0]
        return Image.open(file_path)

    def search_folders(self, folder_path, search_for):
        """
        Keyword matching against the top third of each document.

        The name is always in the top third but its exact position varies,
        so a fixed crop is unreliable. OCR-ing the top third is fast enough
        and avoids false matches from body text lower on the page.

        Returns file(s) with the highest keyword hit count (ties kept).
        """
        keywords = search_for.split()
        scores = {}

        all_files = [
            os.path.join(root, file)
            for root, dirs, files in os.walk(folder_path, followlinks=False)
            for file in files
            if file.lower().endswith(self.valid_ext)
        ]
        total = len(all_files)
        self.log(f"Scanning {total} file(s)...")

        for i, img_path in enumerate(all_files, start=1):
            if self._check_pause_stop():
                self.log("⏹ Search stopped by user.")
                break
            file = os.path.basename(img_path)
            self.log(f"  Scanning {i}/{total}: {file}")
            try:
                img = self.open_as_image(img_path)
                w, h = img.size
                top_third = img.crop((20, 20, w - 20, h // 3))
                text = pytesseract.image_to_string(top_third)
                matched_words = [word for word in keywords if word.lower() in text.lower()]
                count = len(matched_words)
                if count > 0:
                    scores[img_path] = count
                    if count == len(keywords):
                        self.log(f"  ✓ Full match ({count}/{len(keywords)}): {file}")
                    else:
                        self.log(f"  ~ {count}/{len(keywords)} keyword(s) matched: {file}")
            except Exception as e:
                self.log(f"  ✗ Error processing {file}: {e}")

        if not scores:
            return []

        best = max(scores.values())
        matched = [f for f, c in scores.items() if c == best]
        self.log(f"  Best match: {best}/{len(keywords)} keyword(s) — {len(matched)} file(s)")
        return matched

    def generate_filename(self, name_text, date_text, degree_text, fallback_stem):
        """
        Generate a structured filename and determine the output subdirectory.

        Returns (filename_stem, subfolder) where subfolder is one of:
          "Degrees/<year>", "Transcripts/<year>", or "Unprocessed"

        Resolved filename format (Degrees and Transcripts):
          LastName FirstName MI CourseName Month DD YYYY

        Unprocessed filename format (date could not be extracted):
          Last, First MI CourseName

        Falls back to (original_stem, "Unprocessed") if name/course cannot
        be extracted at all.
        """

        def clean(value):
            """Remove characters invalid in filenames (comma is intentional in this format)."""
            return re.sub(r'[\\/*?:"<>|]', '', value).strip()

        # --- Detect document type ---
        is_degree     = bool(re.search(r'degree\s+received',    degree_text, re.IGNORECASE))
        is_transcript = bool(re.search(r'date\s+of\s+admission', date_text,   re.IGNORECASE))
        doc_folder    = "Degrees" if is_degree else ("Transcripts" if is_transcript else None)

        # --- Extract name ---
        last, first, middle = "", "", ""

        # Extract text that follows the "Name" label on the document
        name_label_match = re.search(
            r'[Nn]ame[:\s]+(.+)',
            name_text
        )
        name_region = name_label_match.group(1).strip() if name_label_match else name_text

        # Format 1: Last, First [MI]
        name_match = re.search(
            r'\b([A-Z][a-zA-Z\'\-]+),\s+([A-Z][a-zA-Z\'\-]+)(?:\s+([A-Z])\.?)?',
            name_region
        )
        if name_match:
            last   = name_match.group(1)
            first  = name_match.group(2)
            middle = name_match.group(3) or ""
        else:
            # Format 2: First [MI] Last
            name_match = re.search(
                r'\b([A-Z][a-zA-Z\'\-]+)(?:\s+([A-Z])\.?)?\s+([A-Z][a-zA-Z\'\-]+)\b',
                name_region
            )
            if name_match:
                first  = name_match.group(1)
                middle = name_match.group(2) or ""
                last   = name_match.group(3)

        if not last or not first:
            self.log(f"  ⚠ Could not extract name — sending to Unprocessed.")
            return fallback_stem, "Unprocessed"

        # --- Extract course/degree name (always, regardless of doc type) ---
        course_name = ""
        course_match = re.search(
            r'degree\s+received[:\s]+([A-Za-z\s]+?)(?:\n|$)',
            degree_text,
            re.IGNORECASE
        )
        if course_match:
            course_name = clean(course_match.group(1)).strip()
        else:
            self.log(f"  ⚠ Could not extract course name.")

        # --- Extract date ---
        MONTH_NAME = (
            r'(?:January|February|March|April|May|June|July|August|'
            r'September|October|November|December|'
            r'Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        )
        DATE_NAMED   = MONTH_NAME + r'\s+\d{1,2},?\s+\d{4}'
        DATE_NUMERIC = r'\d{1,2}/\d{1,2}/\d{2,4}'

        MONTH_MAP = {
            'jan': 'January', 'feb': 'February', 'mar': 'March',
            'apr': 'April',   'may': 'May',       'jun': 'June',
            'jul': 'July',    'aug': 'August',     'sep': 'September',
            'oct': 'October', 'nov': 'November',   'dec': 'December'
        }

        def normalise_date(raw):
            """Convert any matched date string to (Month_DD_YYYY, YYYY)."""
            raw = raw.strip()
            numeric = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})$', raw)
            if numeric:
                month_num, day, year = int(numeric.group(1)), numeric.group(2), numeric.group(3)
                if len(year) == 2:
                    year = '19' + year if int(year) >= 20 else '20' + year
                month_name = list(MONTH_MAP.values())[month_num - 1]
                return f"{month_name}_{day}_{year}", year
            parts = raw.replace(',', '').split()
            if len(parts) == 3:
                month_abbr = parts[0][:3].lower()
                month_name = MONTH_MAP.get(month_abbr, parts[0])
                year = parts[2]
                if len(year) == 2:
                    year = '19' + year if int(year) >= 20 else '20' + year
                return f"{month_name}_{parts[1]}_{year}", year
            return clean(raw).replace(' ', '_'), ""

        date_str, year_str = "", ""
        if is_degree:
            date_match = re.search(
                r'degree\s+received[^\n]*?(' + DATE_NAMED + r'|' + DATE_NUMERIC + r')',
                degree_text, re.IGNORECASE
            )
        else:
            date_match = re.search(
                r'date\s+of\s+admission[:\s]+(' + DATE_NAMED + r'|' + DATE_NUMERIC + r')',
                date_text, re.IGNORECASE
            )

        if date_match:
            date_str, year_str = normalise_date(date_match.group(1))
        else:
            self.log(f"  ⚠ Could not extract date.")

        # --- Determine subfolder ---
        # Only route to Unprocessed if doc type OR course name couldn't be determined.
        # Missing date is acceptable — file still goes to Degrees/Transcripts without it.
        if not doc_folder or not course_name:
            name_part = f"{last}, {first}"
            if middle:
                name_part += f" {middle}"
            unprocessed_name = f"{name_part} {course_name}".strip() if course_name else name_part
            self.log(f"  📄 Unprocessed filename: {unprocessed_name}.pdf")
            return unprocessed_name, "Unprocessed"

        subfolder = f"{doc_folder}/{year_str}" if year_str else f"{doc_folder}/{doc_folder} - No Date"

        # --- Assemble resolved filename ---
        # Format: "Last, First MI CourseName Date" (date optional)
        name_part = f"{last}, {first}"
        if middle:
            name_part += f" {middle}"
        parts = [name_part]
        if course_name:
            parts.append(course_name)
        if date_str:
            parts.append(date_str.replace("_", " "))

        filename = " ".join(clean(p) for p in parts)
        self.log(f"  📄 Generated filename: {filename}.pdf → {subfolder}/")
        return filename, subfolder

    def convert_image(self, image_path):
        """Convert single image to PDF, routing to the correct output subfolder."""
        try:
            img_path = Path(image_path)
            base_output = Path(self.output_path.get())

            self.log(f"Converting {img_path.name} to PDF...")

            img = self.open_as_image(img_path)
            w, h = img.size
            full_text = pytesseract.image_to_string(img)
            name_text = pytesseract.image_to_string(img.crop((0, 0, w, h // 4)))

            output_stem, subfolder = self.generate_filename(
                name_text, full_text, full_text, img_path.stem
            )

            output_dir = base_output / subfolder
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{output_stem}.pdf"

            # Avoid overwriting existing files
            counter = 1
            while output_file.exists():
                output_file = output_dir / f"{output_stem}_{counter}.pdf"
                counter += 1

            ocrmypdf.ocr(
                img_path,
                output_file,
                deskew=True,
                force_ocr=True,
                output_type="pdf"
            )

            self.log(f"✓ Saved to: {subfolder}/{output_file.name}")

        except Exception as e:
            self.log(f"✗ Error converting {image_path}: {e}")

    def search_images(self, matched_files, date):
        """
        Filter name-matched files by year.

        Searches only the top third of each document — the same region used
        for name matching — so years that appear in body text or footers
        don't cause false positives.
        """
        files = []

        for file in matched_files:
            try:
                img = self.open_as_image(file)
                w, h = img.size
                top_third = img.crop((0, 0, w, h // 3))
                text = pytesseract.image_to_string(top_third)

                if date.lower() in text.lower():
                    files.append(file)
                else:
                    self.log(f"  ✗ Year '{date}' not found in top third, skipping: {os.path.basename(file)}")

            except Exception as e:
                self.log(f"  ✗ Error processing {file}: {e}")

        return files


def main():
    root = tk.Tk()
    app = ImageToPDFApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
