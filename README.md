# PyCleaner v1.0.1

PyCleaner is a single-file, cross-platform Flask utility designed to safely locate and remove Python virtual environment folders (`venv`) from your system.

This tool is intended for developers who work across many projects and want a fast, visual way to clean up unused virtual environments without manually hunting them down.

---

## Features

- One-file Flask application (no templates, no static folder)
- Embedded Bootstrap UI
- Cross-platform support (Linux, macOS, Windows)
- Recursive search for directories named exactly `venv`
- Checkbox-based selection (select all / select individual)
- Confirmation prompt before deletion
- Permanent removal using `shutil.rmtree`
- Automatic refresh after deletion
- Always-on progress indicator with processing overlay
- Dark mode / light mode toggle (saved in browser)
- Automatically opens default browser on launch

---

## Safety Guardrails

- Only directories named **exactly** `venv` are displayed
- Symlinked directories are skipped
- Each deletion must be explicitly selected and confirmed
- Base path is never deleted unless it is literally named `venv`
- No background processes or hidden deletions

Deletion is permanent. Use responsibly.

---

## Requirements

- Python 3.8+
- Flask

Install Flask if needed:

```bash
pip install flask
```

---

## Running PyCleaner

```bash
python3 pycleaner.py
```

The application will automatically open in your default browser:

```
http://127.0.0.1:5055
```

Press **CTRL+C** in the terminal to stop the server.

---

## Usage

1. Enter a base path to scan
2. Click **Scan**
3. Review all discovered `venv` directories
4. Select which ones to remove
5. Click **Delete selected**
6. Confirm when prompted

---

## Path Examples

**Linux**
```
/home/<user>/projects
/opt
```

**macOS**
```
/Users/<user>/dev
/Applications
```

**Windows**
```
C:\Users\<user>\Projects
D:\dev
```

---

## Version History

### v1.0.1
- Initial public release
- Browser auto-launch on startup
- Dark / light theme toggle
- Embedded UI and progress overlay

---

## License

Personal / Internal Use
Adjust or replace with MIT, GPL, or custom license as needed.

---

Built to stay out of your way and clean up after Python.
