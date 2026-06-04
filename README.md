# Image to PDF Converter & OCR Search Tool (WIP)

A Python GUI application that combines OCR-based document search with image-to-PDF conversion capabilities. Built to help universities digitize and manage pre-digital era scanned transcripts and degrees. Features an intuitive graphical interface with two operation modes: search through image files and PDFs using Optical Character Recognition (OCR) to find specific documents, or bulk convert entire folders of images to searchable PDFs — all without needing to edit code.

## Features

- **Graphical User Interface**: Easy-to-use GUI built with tkinter - no code editing required
- **Dual Operation Modes**: Choose between Search Mode and Bulk Convert Mode via radio buttons
- **Folder Browser**: Browse and select input/output folders with native file dialogs
- **OCR Text Search**: Searches through images and PDFs using Tesseract OCR
- **Bulk Conversion**: Convert all images in a directory (and subdirectories) to searchable PDFs
- **Multiple Format Support**: Handles PDF, JPG, JPEG, PNG, BMP, and TIFF files
- **Fuzzy Matching**: Falls back to partial keyword matching if exact match fails — returns the file(s) with the most keyword hits (all ties included)
- **Year Filtering**: Optional field to refine search results by year
- **Real-time Logging**: Processing status displayed in scrollable log window with progress counters
- **Smart Filename Generation**: Automatically names output PDFs using information extracted from the document (name, course, degree/admission date, document type)
- **Threaded Processing**: Non-blocking operations keep GUI responsive during long tasks
- **Pause & Stop Controls**: Pause processing between files and resume at any time, or stop early — a summary of completed work is always shown
- **Recursive Search**: Searches through entire directory structures
- **User-Friendly**: Clear error messages, success notifications, and conversion summaries
- **Search Index**: OCR results cached in the output folder so repeated searches skip re-OCR'ing unchanged files; shared across multiple application instances with file locking
- **Expandable Previews**: Click any thumbnail to open a full-resolution view scaled to fit screen height
- **Duplicate Handling**: When a destination PDF already exists, prompted with Replace / Append pages / Skip
- **Cross-instance Safety**: Index file uses advisory file locking and atomic writes to prevent corruption when multiple instances access it simultaneously
- **Persistent Settings**: Last-used folders and operation mode are remembered between sessions (stored per-device in the system temp directory, so settings never follow you across machines)
- **Session Logging**: Every processing session writes a timestamped log file to `<output>/logs/` for auditing
- **Export Results**: Search scores and conversion metadata can be exported to a timestamped CSV file
- **Theme Selection**: Toggle between light and dark mode; preference is persisted between sessions
- **Auto-Updater**: On startup, checks GitHub releases for a newer version. If found, you can download and replace the current app automatically — the renamed filename is preserved

## Prerequisites

### Required Software

1. **Python 3.9+** — Download from [python.org](https://www.python.org/downloads/)
2. **Tesseract OCR** — See installation instructions below
3. **Python packages** — `ocrmypdf`, `pytesseract`, `pillow`, `pymupdf`

---

## Installation

### Recommended: Platform Installer

For the quickest setup, run the platform-specific installer. It handles Python, Tesseract, Ghostscript, and all Python packages automatically.

| Platform    | Command                                                 |
|-------------|---------------------------------------------------------|
| **Windows** | `install_windows.bat` (double-click or run in terminal) |
| **macOS**   | `bash install_macos.sh`                                 |
| **Linux**   | `bash install_linux.sh`                                 |

If your system is missing required tools, the installer will attempt to install them. On Windows, it uses `winget` when available and falls back to direct downloads otherwise.

---

### Manual Installation

If the platform installer is not suitable for your environment, follow the steps below.

---

### 1. Clone or Download this Repository

```bash
git clone https://github.com/becktorrescoding/image_to_pdf
```
Or download and extract the ZIP from the GitHub page.

---

### 2. Install Tesseract OCR

#### Windows

1. Download the latest installer from the [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) page (recommended over the official releases for Windows)
2. Run the installer — note the installation path, which defaults to:
   ```
   C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR\
   ```
3. **Add Tesseract to your PATH:**
   - Open the **Start Menu** and search for `Environment Variables`
   - Click **"Edit the system environment variables"**
   - In the System Properties window click **"Environment Variables..."**
   - Under **"System variables"**, find and select **`Path`**, then click **"Edit..."**
   - Click **"New"** and add the Tesseract installation path:
     ```
     C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR\
     ```
   - Click **OK** on all windows to save
4. **Verify the installation** by opening a new Command Prompt and running:
   ```bash
   tesseract --version
   ```
   You should see the Tesseract version number printed.

> **Note**: If you see a `TesseractNotFoundError` when running the app, you can alternatively set the path directly in `app.py` by adding this line near the top of the file:
> ```python
> pytesseract.pytesseract.tesseract_cmd = r'C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
> ```

---

#### macOS

1. Install [Homebrew](https://brew.sh) if you don't have it already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Install Tesseract:
   ```bash
   brew install tesseract
   ```
3. Homebrew automatically adds Tesseract to your PATH. **Verify the installation:**
   ```bash
   tesseract --version
   ```
   You should see the Tesseract version number printed.

> **Note**: If the command is not found after installing, add Homebrew's bin directory to your PATH manually by adding this line to your `~/.zshrc` or `~/.bash_profile`:
> ```bash
> export PATH="/usr/local/bin:$PATH"
> ```
> Then run `source ~/.zshrc` (or `source ~/.bash_profile`) and try again.

---

#### Linux (Debian/Ubuntu)

1. Update your package list and install Tesseract:
   ```bash
   sudo apt-get update
   sudo apt-get install tesseract-ocr
   ```
2. Tesseract is automatically added to your PATH. **Verify the installation:**
   ```bash
   tesseract --version
   ```
   You should see the Tesseract version number printed.

> **Note**: For other distributions use the equivalent package manager, e.g. `sudo dnf install tesseract` on Fedora or `sudo pacman -S tesseract` on Arch.

---

### 3. Install Python Dependencies

```bash
pip install ocrmypdf pytesseract pillow pymupdf
```

### 4. Launch the Application

```bash
python app.py
```


### Main Interface
The application features a clean, intuitive interface:
- **Folder Selection**: Browse buttons for easy path selection
- **Mode Selection**: Radio buttons to switch between Search and Bulk Convert modes
- **Search Fields**: Name and optional year input (Search Mode only)
- **Processing Log**: Real-time status updates in scrollable text area
- **Green Start Button**: Initiates processing
- **Pause Button** (orange): Pauses after the current file; label changes to "Resume" while paused
- **Stop Button** (red): Stops processing after the current file and shows a completion summary

### Typical Workflows

**Search Mode:**
1. Select input folder containing scanned images
2. Select output folder for converted PDFs
3. Select "Search Mode"
4. Enter student name
5. (Optional) Enter graduation year for filtering
6. Click "Start Search"
7. Use **Pause** to suspend between files or **Stop** to cancel early
8. Review matched files in the preview window; click any thumbnail to view full-size
9. Confirm conversion; if a filename already exists, choose Replace / Append / Skip
10. Receive success notification when complete

**Bulk Convert Mode:**
1. Select input folder containing images
2. Select output folder for converted PDFs
3. Select "Bulk Convert Mode"
4. Click "Start Search"
5. Monitor progress in log window (shows X/total count)
6. Use **Pause** to suspend or **Stop** to cancel early — a summary of what was converted is always shown
7. Receive summary dialog when complete

## Configuration

**No configuration needed!** The GUI allows you to select folders through browse dialogs at runtime. Simply:

1. Launch the application
2. Click "Browse" to select your input folder (where images are located)
3. Click "Browse" to select your output folder (where PDFs will be saved)
4. Choose your operation mode and click "Start Search"

**Optional**: If you want to set default paths in the code, edit `app.py`:
- Modify `self.input_path` and `self.output_path` initialization in `__init__()`

## Usage

### Running the Application

```bash
python app.py
```

A graphical window will open with the following interface:

---

### Step-by-Step Usage

#### 1. Select Folders
- **Input Folder**: Click "Browse" next to "Input Folder" and select the folder containing your images
- **Output Folder**: Click "Browse" next to "Output Folder" and select where you want PDFs saved

#### 2. Choose Operation Mode
Use the radio buttons to select your mode:
- **Search Mode**: Find specific documents by name (shows search fields)
- **Bulk Convert Mode**: Convert all images in the input folder (hides search fields)

#### 3. Search Mode — Enter Search Criteria
- **Search Name**: Type the student name to search for (e.g., "John Smith")
- **Year (Optional)**: Enter a graduation year (e.g., "98") to filter results. Leave blank to skip year filtering.

#### 4. Start Processing
Click the green **"Start Search"** button to begin. Once running, two additional buttons become available:
- **Pause** (orange) — suspends processing after the current file finishes. The button label changes to **Resume**; click again to continue.
- **Stop** (red) — signals the worker to stop after the current file. A summary dialog will appear showing how many files were processed.

#### 5. Monitor Progress
The Processing Log window shows real-time status.

**Search Mode example:**
```
=== Starting Search ===
Searching for John Smith
Scanning 86 file(s)...
  Scanning 1/86: scan_001.jpg
  Scanning 2/86: scan_002.jpg
  ✓ Match found: scan_002.jpg
  Scanning 3/86: scan_003.jpg
...
Best match: 2/2 keyword(s) — 1 file(s)
Filtering by year: 98
Found 1 matching image(s)...
[Preview window opens — user confirms selection]
Converting: scan_003.jpg
  Document Type: Transcript
  Found date: March 03, 1975
  File Name: Smith_John_Transcript_March_03_1975
Conversion complete - 1 file(s) converted
```

**Bulk Convert Mode example:**
```
=== Starting Bulk mode ===
Found 42 images to convert...

Converting: scan_001.jpg
  Document Type: Degree
  Course Found: Mechanical Engineering
  Found date: June 12, 1979
  File Name: Smith_John_A._(Mechanical_Engineering)_June_12_1979

Converting: scan_002.png
  Document Type: Transcript
  Found date: March 03, 1975
  File Name: Doe_Jane_March_03_1975
...
Paused - click Resume to continue.
Resumed
...
Stop requested - finishing current file...
Stopped by user.
==================================================
Bulk conversion stopped by user.
Successfully converted 12 / 42 image(s).
Errors: 0
==================================================
```

#### 6. Results
- **Search Mode**: Success message box appears; PDF saved to output folder
- **Bulk Convert Mode**: Summary dialog shows total converted and any errors
- If no matches found (Search Mode), you'll see an informational message

---

### Search Behavior

**Keyword Matching:**
The application searches for the name you enter using whole-word matching:
- Splits your search into keywords (e.g., `"John Freeman"` → `["John", "Freeman"]`)
- Uses `\b` word boundaries so `"Pete"` does not match `"Peter"`
- Rejects matches where the keyword is preceded by a digit on the same line (e.g., `"123 Freeman"` in an address is skipped)
- Returns the file(s) with the **highest keyword score** — all ties are kept and shown in the preview

**Name-Context Scoring:**
Keywords are also checked for proximity to name labels (`Name:`, `Student Name:`, `Student:`, `Applicant Name:`):
- Matches near a name label receive a multiplier (`name_ctx × 1000 + total_matches`)
- This ensures `"Freeman"` under a `Name:` field outranks `"Freeman"` appearing in body text
- Example: if two files match 2 keywords but only one has those keywords in the name region, the latter wins

**Year Filtering:**
If you enter a year, matched files are filtered to only those containing that year in their text.

**Search Index:**
OCR results from previous searches are cached in `file_index_python_search_engine.json` inside the output folder. Repeated searches skip re-OCR'ing files that haven't changed. The index is shared safely across multiple running instances via file locking and atomic writes.

---

### Example Workflows

**Scenario 1**: Find and convert a transcript for "Jane Doe" who graduated in 1998

1. Launch app: `python app.py`
2. Browse input to: `C:/University/ScannedRecords`
3. Browse output to: `C:/University/Converted`
4. Select **Search Mode**
5. Enter name: `Jane Doe`
6. Enter year: `98`
7. Click "Start Search"
8. Find PDF at: `C:/University/Converted/scan_xyz.pdf`

**Scenario 2**: Bulk convert an entire archive of scanned degrees

1. Launch app: `python app.py`
2. Browse input to: `C:/University/DegreeArchive`
3. Browse output to: `C:/University/Converted`
4. Select **Bulk Convert Mode**
5. Click "Start Search"
6. Wait for completion summary

## How It Works

### GUI Architecture

The application uses a **class-based tkinter GUI** with the following structure:

```
Application (tk.Tk)
├── __init__()              # Initialize window and variables
├── create_widgets()        # Build GUI interface
├── toggle_pause()          # Pause or resume processing
├── request_stop()          # Signal worker thread to stop after current file
├── _check_pause_stop()     # Called between files; blocks while paused, returns True if stopped
├── _reset_buttons()        # Re-enable Start and disable Pause/Stop
├── toggle_mode()           # Show/hide search fields based on mode
├── _toggle_theme()         # Switch between light and dark mode
├── _check_for_updates()    # Check GitHub for newer version; auto-download and replace on user consent
├── _on_close()             # Save settings on window close
├── browse_input()          # Handle input folder selection
├── browse_output()         # Handle output folder selection
├── start()                 # Validate inputs and start thread
├── route_mode()            # Route to correct mode (runs in thread)
├── search_mode()           # Search Mode workflow
├── matches_found()         # Handle search results and year filtering
├── filter_year()           # Filter matched files by year
├── bulk_mode()             # Bulk Convert Mode workflow
├── show_preview_window()   # Preview matched files before converting
├── _show_large_preview()   # Full-size preview on thumbnail click
├── open_as_image()         # Open image or PDF first page as PIL Image (via PyMuPDF)
├── convert_image()         # Convert single image to searchable PDF
├── _prompt_replace_or_append()  # Prompt user on duplicate filename
├── generate_filename()     # Extract fields from OCR text and build filename
├── _extract_name()         # Pull student name from OCR via name labels
├── _format_name()          # Parse 'Last, First' or 'First Last' into standard form
├── _has_valid_match()      # Whole-word match rejecting digit-preceded occurrences
├── _in_name_context()      # Check if keyword appears near a name label
├── _export_results()       # Save search/conversion results to CSV
├── _load_index()           # Load search index from disk
├── _save_index()           # Save search index to disk
├── _get_cached_text()      # Retrieve cached OCR text if mtime matches
├── _index_entry()          # Add/update entry in search index
├── _ensure_index()         # Prompt to create or import index if missing
├── _import_index_file()    # Validate and copy an encrypted index file
├── _import_index_ui()      # Button handler for importing an index
├── _lock_index()           # Acquire file lock for index access
├── _unlock_index()         # Release file lock
├── _lock_windows()         # Windows LockFileEx (shared/exclusive)
├── _unlock_windows()       # Windows UnlockFileEx
├── _write_log_file()       # Append message to session log in <output>/logs/
├── _settings_path()        # Path to per-device settings in system temp directory
├── _save_settings()        # Persist folders and mode to disk
├── _load_settings()        # Restore folders and mode from disk
└── log()                   # Display messages in GUI (thread-safe)
```

### Automatic Filename Generation (Search Mode)

When a document is converted in Search Mode, the output PDF is automatically named using information extracted from the OCR text rather than the original scanned filename.

**Degree format:**
```
Last, First [MI.] (Course) Month DD, YYYY
```
Example: `Doe, John A. (Mechanical Engineering) May 20, 1998.pdf`

**Transcript format:**
```
Last, First [MI.] (Course) Month DD, YYYY
```
Example: `Doe, John A. (Computer Science) March 03, 1975.pdf`

**How it works:**
1. Detects document type by looking for degree patterns (`Associate in`, `Bachelor of Science in`, `Certificate of Graduation`) or transcript markers (`date of admission`)
2. Extracts the student name from OCR text using name labels (`Name:`, `Student Name:`, `Student:`, `Applicant Name:`), supporting both `"Last, First Mi"` and `"First Mi Last"` formats. Falls back to the search-field entry if OCR extraction returns nothing. Routes to `Error/Name` if name cannot be determined.
3. **Course extraction**: Looks for the course name on degree documents in two locations:
   - Text immediately before the degree keyword on the same line (up to 9 words)
   - If the line contains "Graduated-Received", checks two lines above the degree for a "Course:" label
   - For **transcripts**, scans for `Program:`, `Major:`, `Course:`, `Field of Study:`, or `Curriculum:` labels
4. Skips student-number text (`Student No.`, `Student #`, `Student ID`) that may appear on the same line as the name label
5. Extracts the relevant date — graduation date for degrees, admission date for transcripts. Context-based ("Degree: ..." / "date of admission: ...") and generic date patterns are combined and deduplicated. Invalid date-like strings (e.g. OCR noise like "34-65-5413") are automatically rejected with a retry loop.
6. Normalizes dates to a consistent `Month DD, YYYY` format regardless of how they appear in the document — both `June 12, 1979` and `06/12/79` will produce `June 12, 1979`. 2-digit years are expanded automatically (`79` → `1979`, years `00–19` are assumed to be 2000s)
7. Assembles the parts into a clean filename, stripping invalid characters

**Fallback behavior:**
If the name cannot be extracted, a warning is logged and the file is routed to an `Error/Name` folder. If the date cannot be extracted, it is routed to `Error/Date`. The conversion still completes — only the filename and destination differ.

### Search Mode Workflow

1. **User Input**: User enters name and optional year via GUI fields
2. **Validation**: System checks all required fields are filled
3. **Threading**: Search runs in background thread (GUI stays responsive); Pause and Stop buttons become active
4. **Index Check**: Before OCR'ing each file, the search index is consulted. If a cached OCR text exists and the file hasn't been modified, OCR is skipped entirely
5. **OCR Processing**: The name region of each file is processed with Tesseract OCR (faster and more precise than full-page OCR)
6. **Index Update**: Newly OCR'd results are stored in the index and saved to disk
7. **Text Matching**: Extracted text is compared against search criteria
8. **Fallback**: If no exact match, automatically tries partial matching — returns the file(s) with the most keyword hits
9. **Filtering**: Optional year filter applied if provided (also benefits from the index cache)
10. **Preview**: Matched files displayed as thumbnails in a preview window. Click any thumbnail to open a full-resolution view. Select which files to convert via checkboxes.
11. **Conversion**: Selected file(s) converted to searchable PDF with OCRmyPDF. If a destination filename already exists, the user is prompted: Replace / Append pages / Skip.
12. **Notification**: User notified of success/failure

### Bulk Convert Mode Workflow

1. **Validation**: System checks input and output folders are provided
2. **File Discovery**: Recursively counts all valid image files in input folder
3. **Threading**: Conversion runs in background thread (GUI stays responsive); Pause and Stop buttons become active
4. **Batch Conversion**: Each image converted to searchable PDF with OCRmyPDF; pause/stop is checked between every file
5. **Index Update**: Converted file metadata (OCR text, degree type, course, date, generated filename) is stored in the search index
6. **Progress Tracking**: Log shows per-file results and running count (X/total)
7. **Error Handling**: Individual file errors are logged; processing continues
8. **Early Stop**: If stopped by user, summary reports how many files completed before stopping
9. **Summary**: Completion dialog reports total converted and error count

### Search Index

- **Location**: `file_index_python_search_engine.json` inside the output folder
- **Content**: Base64 + gzip encoded JSON mapping file paths to OCR text, degree type, course, date, year, generated filename, and file modification timestamp
- **Cache Invalidation**: If a source file's modification time changes, it is automatically re-OCR'd on the next search
- **Cross-instance Safety**: Uses `fcntl.flock` (Unix) / `LockFileEx` via `ctypes` (Windows) — shared locks for reads, exclusive locks for writes, functioning correctly over SMB network drives
- **Utility Script**: Run `python decode_index.py <path-to-index>` to decode the index to human-readable JSON

### Duplicate File Handling

When `convert_image()` detects that the destination PDF already exists, it prompts the user with a three-button dialog:
- **Yes** (Replace) — overwrites the existing file
- **No** (Append) — merges the new pages into the existing PDF
- **Cancel** (Skip) — leaves the existing file untouched

The prompt is synchronized from the background thread to the main thread so the GUI remains responsive.

### Technical Details

- **OCR Engine**: Tesseract (via pytesseract) extracts text from images
- **PDF Creation**: OCRmyPDF creates searchable PDFs with deskewing and forced OCR
- **PDF Rendering**: PyMuPDF (fitz) renders PDF pages as images for preview and processing
- **Threading**: `threading.Thread` prevents GUI freezing during processing; `threading.Event` objects (`_pause_event`, `_stop_event`) coordinate pause and stop signals between the GUI and worker thread
- **Logging**: Thread-safe via `after_idle()` deferral to the main thread
- **Auto-Updater**: `urllib.request` fetches the latest release from the GitHub API; `os.replace()` provides atomic file replacement preserving the renamed script name
- **File Handling**: `pathlib.Path` for cross-platform path management
- **Index Encoding**: gzip compressed + base64 encoded to prevent casual reading outside the application
- **Error Handling**: Try-except blocks catch and log errors gracefully

### Supported File Types

- PDF (`.pdf`)
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- BMP (`.bmp`)
- TIFF (`.tif`, `.tiff`, `.TIF`)

## Output

### Search Mode — Success
- **Preview Window**: All matched files shown as thumbnails with checkboxes; click any thumbnail for full-size preview
- **Searchable PDFs**: Selected document(s) saved to output folder with auto-generated structured filenames
- **Log Messages**: Real-time progress shown in GUI log window
- **Success Dialog**: Pop-up notification confirms how many files were converted

### Bulk Convert Mode — Success
- **Searchable PDFs**: All converted documents saved to output folder with auto-generated structured filenames (falls back to `Error/Date` routing if date cannot be extracted)
- **Progress Log**: Per-file status showing generated filename and running count
- **Summary Dialog**: Reports total files converted and number of errors

### No Matches Case (Search Mode)
- **Informational Dialog**: "No matching files found" message
- **Log Details**: Shows search attempts and why no matches were found

### Stopped by User
- **Log Message**: `Stopped by user.` appears in the log
- **Summary Dialog**: Reports how many files were converted before stopping
- **Start Button**: Re-enabled immediately so a new operation can begin

### Error Case
- **Error Dialog**: Specific error message displayed
- **Log Details**: Full error details in log window for debugging
- **Bulk Convert**: Errors are logged per file; remaining files continue processing

## Error Handling

The GUI includes comprehensive error handling:

### Input Validation
- **Empty Fields**: Error dialog if name or paths missing
- **Invalid Paths**: System validates folder existence before processing
- **Mode-aware**: Search Mode requires a name; Bulk Convert Mode does not

### Processing Errors
- **OCR Failures**: Logged with filename and error details
- **Image Read Errors**: Skips corrupted files, continues processing others
- **Conversion Errors**: Detailed error message logged per file

### User Experience
- **Non-blocking Errors**: GUI remains responsive even during errors
- **Error Logs**: All errors displayed in log window for review
- **Graceful Degradation**: Partial matches attempted if exact match fails (Search Mode)

### Common Error Messages

| Error                                          | Cause                             | Solution                          |
|------------------------------------------------|-----------------------------------|-----------------------------------|
| "Please select both input and output folders." | Missing folder paths              | Browse and select both folders    |
| "Please enter a name to search for."           | Search Mode with empty name field | Enter a name to search            |
| "Error processing [file]"                      | Corrupted or unreadable image     | Check image file integrity        |
| "No matching files found"                      | No documents contain search text  | Verify spelling, try partial name |
| Tesseract error                                | OCR engine not installed          | Install Tesseract OCR             |

## Privacy & Data Security

All OCR and PDF processing is performed **entirely locally on your machine**. No document text, metadata, or file contents are transmitted over the internet.

The only network requests made are:
- **Auto-Updater** (opt-out by declining the update prompt): On startup, a request is sent to `api.github.com` to check for a newer version. If you choose to update, the new `app.py` is downloaded from `raw.githubusercontent.com`. No personal or document data is included in these requests.

| Dependency    | Data Collection | Network Access       |
|---------------|-----------------|----------------------|
| Tesseract OCR | None            | None — fully offline |
| OCRmyPDF      | None            | None — fully offline |
| Pillow        | None            | None — fully offline |
| PyMuPDF       | None            | None — fully offline |
| tkinter       | None            | None — fully offline |

This makes the tool suitable for handling sensitive documents such as university transcripts and degrees, where student records should remain confidential and within your institution's systems.

> **Tip**: For added assurance, you can run the application on an air-gapped machine or monitor outbound network traffic with a tool like Wireshark to independently verify no data leaves your system.

## Limitations

- **OCR Accuracy**: Depends on image quality, text clarity, and scan resolution
- **Processing Speed**: Large directories or high-resolution images can be slow; the search index mitigates repeated OCR for unchanged files
- **Network Drives**: May be slower than local storage; consider copying files locally first
- **Filename generation accuracy**: Auto-naming relies on OCR quality — poor scans may fall back to `Error/Date` routing
- **Year Format**: Searches for year as a text string in OCR output; works with both 2-digit and 4-digit years depending on what appears in the document
- **Memory Usage**: Processing very large images may consume significant RAM

## Troubleshooting

### GUI Won't Open
**Symptom**: Double-clicking does nothing or window appears then closes

**Solutions**:
- Run from terminal to see error messages: `python app.py`
- Check Python version (requires 3.9+)
- Verify tkinter is installed: `python -m tkinter` (should open test window)

### "Tesseract not found" Error
**Symptom**: `TesseractNotFoundError` when clicking "Start Search"

**Solutions**:
- Ensure Tesseract OCR is installed — see the [Installation](#installation) section for your OS
- Open a terminal and run `tesseract --version` to confirm it's on your PATH
- **Windows**: If it's still not found after adding to PATH, open a fresh Command Prompt (the old one won't pick up the change) and try again. Alternatively, set the path directly in `app.py`:
  ```python
  pytesseract.pytesseract.tesseract_cmd = r'C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
  ```
- **macOS**: Run `source ~/.zshrc` or `source ~/.bash_profile` after updating PATH, then retry

### OCRmyPDF Errors
**Symptom**: PDF conversion fails

**Solutions**:
- Install Ghostscript (required by OCRmyPDF)
- Check output folder is writable
- Verify sufficient disk space
- Try with smaller/simpler image first

### No Matches Found (Search Mode)
**Symptom**: "No matching files found" message

**Solutions**:
- Verify image quality is clear enough for OCR
- Check spelling of search name
- Try searching for just first or last name
- Test with known document to verify OCR is working
- Images with handwriting may not work well

### GUI Freezes
**Symptom**: Window becomes unresponsive

**Solutions**:
- Wait - processing may take time for large folders
- Check log window for progress updates
- Force quit and try with smaller folder first
- Reduce image resolution if files are very large

### Browse Button Not Working
**Symptom**: Clicking Browse does nothing

**Solutions**:
- Check file system permissions
- Try running as administrator (Windows)
- Verify folder paths don't contain special characters

### Output PDF is Empty or Corrupted
**Symptom**: PDF created but contains no content

**Solutions**:
- Check original image contains readable text
- Verify image file isn't corrupted
- Try with different image format
- Increase image contrast before processing

## Future Enhancements

Potential improvements for future versions:

### GUI Improvements
- **Drag & Drop**: Drop files directly into window

### Functionality
- **Custom Match Threshold**: Slider to adjust partial match percentage

### Advanced Features
- **Regular Expression Search**: Pattern matching for complex queries
- **Annotation**: Add notes or highlights to converted PDFs

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Copyright (c) 2025 Tomás beck Torres

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the issues page if you want to contribute.

**How to contribute:**

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

**Areas where contributions are especially welcome:**
- GUI improvements (themes, layouts, new widgets)
- Performance optimizations
- Additional file format support
- Multi-language support
- Documentation improvements
- Bug fixes and testing

## Contact

Tomás Beck Torres - becktorrescoding@gmail.com

Website - becktorrescoding@odoo.com

Project Link: [https://github.com/becktorrescoding/image_to_pdf](https://github.com/becktorrescoding/image_to_pdf)

## Acknowledgments

- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - OCR engine
- [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF) - PDF conversion tool
- [pytesseract](https://github.com/madmaze/pytesseract) - Python wrapper for Tesseract
- [Pillow](https://python-pillow.org/) - Python imaging library
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF rendering and manipulation
