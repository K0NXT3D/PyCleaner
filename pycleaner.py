#!/usr/bin/env python3
"""
============================================================
PyCleaner v1.0.1
Cross-Platform Python Virtual Environment Cleanup Utility
============================================================
Author: R. Seaverns (K0NxT3D)
Project: pycleaner
Version: 1.0.1
License: Personal / Internal Use
Platform: Linux / macOS / Windows
Language: Python 3

------------------------------------------------------------
What this does
------------------------------------------------------------
PyCleaner is a single-file Flask web app that helps you locate and delete
Python virtual environment folders named "venv".

Features:
- Embedded Bootstrap UI (no external templates)
- User-provided base path for scanning
- Cross-platform path support (Linux/macOS/Windows)
- Recursively searches for directories named exactly: "venv"
- Displays results with checkboxes + Select All
- Confirmation prompt ("Are you sure?") before deletion
- Deletes selected folders (recursive)
- Refreshes the list after deletion
- Always-available progress overlay + progress bar while processing
- Dark mode / light mode switch (client-side, persisted via localStorage)

Safety notes:
- Deletion is permanent (uses shutil.rmtree).
- Only directories named EXACTLY "venv" are listed.
- Symlinks are skipped to avoid deleting linked locations unintentionally.
- The app will not delete the base path itself unless it is literally named "venv"
  (still must be selected).

Run:
  python3 pycleaner.py

Then open:
  http://127.0.0.1:5055

Tip:
- For large scans, give it a specific project root (not "/").
- On Linux/macOS: /home/<user>/projects or /Users/<user>/dev
- On Windows: C:\\Users\\<user>\\Projects

------------------------------------------------------------
Changelog
------------------------------------------------------------
v1.0.1
- Initial release: scan, list, select, confirm, delete, refresh
- UI: embedded Bootstrap, dark/light switch, progress overlay
============================================================
"""

from __future__ import annotations

import os
import shutil
import time
import webbrowser
import threading
from dataclasses import dataclass
from typing import List, Tuple, Optional

from flask import Flask, request, redirect, url_for, render_template_string, flash


# ============================================================
# Configuration
# ============================================================

APP_NAME = "PyCleaner"
VERSION = "1.0.1"
HOST = "127.0.0.1"
PORT = 5055
SECRET_KEY = os.environ.get("PYCLEANER_SECRET", "pycleaner-dev-secret-change-me")

# Hard safety limits (helps avoid scanning the whole planet by accident)
MAX_RESULTS = 5000
DEFAULT_EXAMPLE_PATHS = {
    "linux": "/home/<user>/projects  or  /opt",
    "mac": "/Users/<user>/dev  or  /Applications",
    "win": r"C:\Users\<user>\Projects  or  D:\dev",
}

# Optional: small delay used to make progress overlay visible even for quick actions
UI_DELAY_SECONDS = 0.05


app = Flask(__name__)
app.secret_key = SECRET_KEY


# ============================================================
# Data structures
# ============================================================

@dataclass
class ScanResult:
    base_path: str
    found: List[str]
    error: Optional[str] = None


# ============================================================
# Helpers
# ============================================================

def open_browser(url: str, delay: float = 0.5):
    """
    Open the default web browser after a short delay.
    The delay ensures Flask is already listening.
    """
    def _open():
        time.sleep(delay)
        webbrowser.open_new_tab(url)

    threading.Thread(target=_open, daemon=True).start()


def normalize_path(p: str) -> str:
    """
    Normalize a user-supplied path for the current OS.
    Expands ~ and environment variables, and normalizes separators.
    """
    p = (p or "").strip()
    if not p:
        return ""
    p = os.path.expandvars(p)
    p = os.path.expanduser(p)
    p = os.path.normpath(p)
    return p


def is_safe_base_path(p: str) -> Tuple[bool, str]:
    """
    Basic guardrails: path must exist and be a directory.
    We do NOT block scanning root, but we warn by message.
    """
    if not p:
        return False, "Base path is empty."
    if not os.path.exists(p):
        return False, f"Path does not exist: {p}"
    if not os.path.isdir(p):
        return False, f"Path is not a directory: {p}"
    return True, ""


def find_venv_dirs(base_path: str, limit: int = MAX_RESULTS) -> ScanResult:
    """
    Recursively search for directories named exactly 'venv' under base_path.
    Skips symlinked directories to reduce risk.
    """
    base_path = normalize_path(base_path)
    ok, msg = is_safe_base_path(base_path)
    if not ok:
        return ScanResult(base_path=base_path, found=[], error=msg)

    found: List[str] = []
    try:
        for root, dirs, files in os.walk(base_path, topdown=True, followlinks=False):
            # Remove symlinked dirs from traversal
            pruned = []
            for d in dirs:
                full = os.path.join(root, d)
                try:
                    if os.path.islink(full):
                        continue
                except OSError:
                    continue
                pruned.append(d)
            dirs[:] = pruned

            # If a directory named 'venv' is present in this level, record its full path.
            # IMPORTANT: exact match, case-sensitive.
            if "venv" in dirs:
                venv_path = os.path.join(root, "venv")
                found.append(os.path.normpath(venv_path))
                if len(found) >= limit:
                    break

        found.sort()
        return ScanResult(base_path=base_path, found=found, error=None)
    except Exception as e:
        return ScanResult(base_path=base_path, found=[], error=f"Scan error: {e}")


def delete_dirs(selected: List[str]) -> Tuple[int, List[Tuple[str, str]]]:
    """
    Delete selected directories using shutil.rmtree.
    Returns (deleted_count, errors_list) where errors_list is (path, error_message).
    """
    deleted = 0
    errors: List[Tuple[str, str]] = []

    for p in selected:
        p = normalize_path(p)

        # Safety: only delete if basename is exactly 'venv'
        if os.path.basename(p) != "venv":
            errors.append((p, "Skipped: not named 'venv'"))
            continue

        # Safety: must exist and be a directory
        if not os.path.exists(p):
            errors.append((p, "Skipped: does not exist"))
            continue
        if not os.path.isdir(p):
            errors.append((p, "Skipped: not a directory"))
            continue

        # Safety: skip symlinks
        if os.path.islink(p):
            errors.append((p, "Skipped: is a symlink"))
            continue

        try:
            shutil.rmtree(p)
            deleted += 1
        except Exception as e:
            errors.append((p, str(e)))

    return deleted, errors


# ============================================================
# UI (single embedded template)
# ============================================================

TEMPLATE = r"""
<!doctype html>
<html lang="en" data-bs-theme="dark">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{{ app_name }} v{{ version }}</title>

  <!-- Bootstrap 5 (CDN). If you want fully offline, we can embed CSS later. -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">

  <style>
    body { min-height: 100vh; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }

    /* Progress overlay */
    #progressOverlay {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.55);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      backdrop-filter: blur(2px);
    }
    #progressCard {
      width: min(680px, 92vw);
    }

    /* Always-present progress bar container (shows idle state) */
    .progress-idle {
      opacity: .65;
    }

    .path-chip {
      word-break: break-all;
    }
  </style>
</head>

<body>
  <div id="progressOverlay">
    <div class="card shadow" id="progressCard">
      <div class="card-body">
        <div class="d-flex align-items-center justify-content-between mb-2">
          <div class="fw-semibold">Processing…</div>
          <div class="small text-secondary">Please don’t close this tab.</div>
        </div>
        <div class="progress" role="progressbar" aria-label="Processing">
          <div class="progress-bar progress-bar-striped progress-bar-animated" style="width: 100%"></div>
        </div>
      </div>
    </div>
  </div>

  <div class="container py-4">
    <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
      <div>
        <div class="h3 mb-0">{{ app_name }} <span class="text-secondary fs-6">v{{ version }}</span></div>
        <div class="text-secondary">Find and delete <span class="mono">venv</span> folders safely-ish (with guardrails).</div>
      </div>

      <div class="d-flex align-items-center gap-2">
        <div class="form-check form-switch">
          <input class="form-check-input" type="checkbox" role="switch" id="themeToggle">
          <label class="form-check-label" for="themeToggle">Light mode</label>
        </div>
      </div>
    </div>

    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        <div class="mb-3">
          {% for cat, msg in messages %}
            <div class="alert alert-{{ 'warning' if cat=='warn' else ('danger' if cat=='err' else 'success') }} mb-2">
              {{ msg }}
            </div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}

    <div class="card shadow-sm mb-3">
      <div class="card-body">
        <form method="GET" action="/" onsubmit="showProgressOverlay();">
          <div class="d-flex flex-column flex-lg-row gap-2 align-items-lg-end">
            <div class="flex-grow-1">
              <label class="form-label">
                Base path to scan
                <button type="button" class="btn btn-sm btn-outline-secondary ms-1" data-bs-toggle="modal" data-bs-target="#helpModal" title="Examples / Info">
                  <span class="fw-semibold">i</span>
                </button>
              </label>
              <input class="form-control mono" name="path" placeholder="e.g. /home/<user>/projects   or   C:\Users\<user>\Projects" value="{{ base_path or '' }}">
              <div class="form-text">
                Scans recursively for directories named exactly: <span class="mono">venv</span>
              </div>
            </div>

            <div class="d-grid">
              <button class="btn btn-primary px-4" type="submit">Scan</button>
            </div>
          </div>
        </form>

        <hr class="my-3">

        <!-- Always-on progress bar area (idle vs active) -->
        <div class="d-flex align-items-center justify-content-between mb-2">
          <div class="small text-secondary">Status</div>
          <div class="small text-secondary" id="statusText">Idle</div>
        </div>
        <div class="progress progress-idle" role="progressbar" aria-label="Status">
          <div id="statusBar" class="progress-bar" style="width: 100%"></div>
        </div>
      </div>
    </div>

    {% if scanned %}
      <div class="card shadow-sm">
        <div class="card-body">
          <div class="d-flex flex-wrap gap-2 align-items-center justify-content-between mb-2">
            <div>
              <div class="fw-semibold">Scan results</div>
              <div class="text-secondary small">
                Base path:
                <span class="badge text-bg-secondary path-chip mono">{{ base_path }}</span>
              </div>
            </div>
            <div class="text-secondary small">
              Found: <span class="fw-semibold">{{ results|length }}</span>
            </div>
          </div>

          {% if scan_error %}
            <div class="alert alert-danger">{{ scan_error }}</div>
          {% endif %}

          {% if results|length == 0 and not scan_error %}
            <div class="alert alert-warning mb-0">
              No directories named <span class="mono">venv</span> found under that path.
            </div>
          {% elif results|length > 0 %}
            <form method="POST" action="/delete" onsubmit="return confirmDelete();">
              <input type="hidden" name="base_path" value="{{ base_path }}"/>

              <div class="d-flex flex-wrap gap-2 align-items-center mb-3">
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="toggleAll(true)">Select all</button>
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="toggleAll(false)">Select none</button>

                <div class="ms-auto d-flex gap-2">
                  <button type="submit" class="btn btn-danger btn-sm px-3">
                    Delete selected
                  </button>
                </div>
              </div>

              <div class="table-responsive" style="max-height: 50vh;">
                <table class="table table-hover align-middle">
                  <thead class="sticky-top">
                    <tr>
                      <th style="width: 56px;">Del</th>
                      <th>venv path</th>
                    </tr>
                  </thead>
                  <tbody>
                    {% for p in results %}
                      <tr>
                        <td>
                          <input class="form-check-input venvCheck" type="checkbox" name="selected" value="{{ p }}">
                        </td>
                        <td class="mono">{{ p }}</td>
                      </tr>
                    {% endfor %}
                  </tbody>
                </table>
              </div>

              <div class="small text-secondary mt-3">
                Guardrail: only items whose final folder name is exactly <span class="mono">venv</span> will be deleted.
              </div>
            </form>
          {% endif %}
        </div>
      </div>
    {% endif %}

    <div class="text-secondary small mt-3">
      Tip: scanning huge roots can be slow. Aim at a projects directory rather than scanning your entire disk.
    </div>
  </div>

  <!-- Help / Info Modal -->
  <div class="modal fade" id="helpModal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-lg modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">Path examples and scanning info</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body">
          <p class="mb-2">
            Enter a <span class="fw-semibold">base folder</span> and PyCleaner will recursively search beneath it for directories named
            <span class="mono">venv</span>.
          </p>

          <div class="row g-3">
            <div class="col-md-4">
              <div class="border rounded p-3 h-100">
                <div class="fw-semibold mb-1">Linux</div>
                <div class="mono small">{{ examples.linux }}</div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="border rounded p-3 h-100">
                <div class="fw-semibold mb-1">macOS</div>
                <div class="mono small">{{ examples.mac }}</div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="border rounded p-3 h-100">
                <div class="fw-semibold mb-1">Windows</div>
                <div class="mono small">{{ examples.win }}</div>
              </div>
            </div>
          </div>

          <hr>

          <ul class="mb-0">
            <li>Symlinked directories are skipped (safer).</li>
            <li>Only folders named exactly <span class="mono">venv</span> appear in results.</li>
            <li>Deleting uses <span class="mono">shutil.rmtree()</span> (permanent).</li>
          </ul>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Close</button>
        </div>
      </div>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
  <script>
    // Theme: persisted via localStorage
    const THEME_KEY = "pycleaner_theme";
    const themeToggle = document.getElementById("themeToggle");

    function applyTheme(theme) {
      // Bootstrap 5.3 theme switcher
      document.documentElement.setAttribute("data-bs-theme", theme);
      const isLight = (theme === "light");
      themeToggle.checked = isLight;
      themeToggle.nextElementSibling.textContent = isLight ? "Light mode" : "Dark mode";
    }

    (function initTheme(){
      const saved = localStorage.getItem(THEME_KEY) || "dark";
      applyTheme(saved);
    })();

    themeToggle.addEventListener("change", () => {
      const theme = themeToggle.checked ? "light" : "dark";
      localStorage.setItem(THEME_KEY, theme);
      applyTheme(theme);
    });

    // Progress overlay
    function showProgressOverlay() {
      document.getElementById("progressOverlay").style.display = "flex";
      // status bar text
      const statusText = document.getElementById("statusText");
      const statusBar = document.getElementById("statusBar");
      if (statusText) statusText.textContent = "Working…";
      if (statusBar) {
        statusBar.classList.add("progress-bar-striped", "progress-bar-animated");
      }
    }

    function hideProgressOverlay() {
      document.getElementById("progressOverlay").style.display = "none";
      const statusText = document.getElementById("statusText");
      const statusBar = document.getElementById("statusBar");
      if (statusText) statusText.textContent = "Idle";
      if (statusBar) {
        statusBar.classList.remove("progress-bar-striped", "progress-bar-animated");
      }
    }

    // Hide overlay on load (in case of back/forward cache or weirdness)
    window.addEventListener("load", () => hideProgressOverlay());

    // Checkbox helpers
    function toggleAll(on) {
      document.querySelectorAll(".venvCheck").forEach(cb => cb.checked = on);
    }

    function confirmDelete() {
      const checked = Array.from(document.querySelectorAll(".venvCheck")).filter(cb => cb.checked).length;
      if (checked === 0) {
        alert("No items selected.");
        return false;
      }
      const ok = confirm("Are you sure you want to permanently delete the selected venv folders? (" + checked + " selected)");
      if (!ok) return false;
      showProgressOverlay();
      return true;
    }
  </script>
</body>
</html>
"""


# ============================================================
# Routes
# ============================================================

@app.route("/", methods=["GET"])
def index():
    base_path = normalize_path(request.args.get("path", ""))

    scanned = False
    results: List[str] = []
    scan_error: Optional[str] = None

    if base_path:
        scanned = True
        # tiny delay so UI overlay is perceptible on fast scans
        time.sleep(UI_DELAY_SECONDS)
        r = find_venv_dirs(base_path)
        results = r.found
        scan_error = r.error
        if not scan_error and os.path.abspath(base_path) in (os.path.abspath(os.sep), os.path.abspath(os.path.expanduser("~"))):
            flash("Heads up: scanning very large roots can be slow. Consider narrowing to a projects folder.", "warn")

        if len(results) >= MAX_RESULTS:
            flash(f"Result limit reached ({MAX_RESULTS}). Narrow your scan path for more precise results.", "warn")

    return render_template_string(
        TEMPLATE,
        app_name=APP_NAME,
        version=VERSION,
        base_path=base_path,
        scanned=scanned,
        results=results,
        scan_error=scan_error,
        examples=DEFAULT_EXAMPLE_PATHS,
    )


@app.route("/delete", methods=["POST"])
def delete():
    base_path = normalize_path(request.form.get("base_path", ""))
    selected = request.form.getlist("selected")

    if not base_path:
        flash("Missing base path. Please scan again.", "err")
        return redirect(url_for("index"))

    if not selected:
        flash("No items selected.", "warn")
        return redirect(url_for("index", path=base_path))

    # tiny delay so UI overlay is perceptible on fast deletes
    time.sleep(UI_DELAY_SECONDS)

    deleted, errors = delete_dirs(selected)

    if deleted > 0:
        flash(f"Deleted {deleted} venv folder(s).", "ok")
    if errors:
        # show up to a few to avoid giant walls of text
        preview = errors[:8]
        details = "; ".join([f"{p} -> {e}" for p, e in preview])
        extra = "" if len(errors) <= 8 else f" (+{len(errors)-8} more)"
        flash(f"Some items were not deleted: {details}{extra}", "warn")

    # Refresh results by redirecting back to scan view
    return redirect(url_for("index", path=base_path))


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"

    print(f"[+] {APP_NAME} v{VERSION}")
    print(f"[+] Launching on {url}")
    print("[+] Press CTRL+C to stop.")

    open_browser(url)

    app.run(host=HOST, port=PORT, debug=False)


