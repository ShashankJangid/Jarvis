"""
System File Operations and Web Uploader Tools for Jarvis.
Searches local laptop directories for files and automates file uploads to websites on Monitor 2.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from tools.browser_session import get_or_create_page
import config

EXCLUDED_DIR_NAMES = {
    ".git",
    "node_modules",
    ".vscode",
    ".idea",
    "appdata",
    "library",
    ".cache",
    "__pycache__",
    "venv",
    ".env",
    "env",
    "site-packages",
    "dist",
    "build",
    ".gemini",
    ".system_generated",
}

def _human_readable_size(size_bytes: int) -> str:
    """Formats bytes into human readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def search_local_files_on_laptop(filename_query: str, search_root: str = "") -> str:
    """
    Recursively searches local laptop directories for files matching the given query,
    skipping hidden folders, virtual environments, and node_modules.

    Args:
        filename_query: Keyword or filename pattern to search for (e.g. 'invoice', 'report.pdf', 'resume').
        search_root: Optional directory to restrict search (defaults to user Documents, Downloads, Desktop, and Home).

    Returns:
        Structured list of matching absolute file paths with sizes and modification dates.
    """
    query_lower = filename_query.lower().strip()
    if not query_lower:
        return "⚠️ Please provide a filename or keyword to search for."

    search_paths: List[Path] = []
    if search_root:
        custom_root = Path(search_root).resolve()
        if custom_root.exists():
            search_paths.append(custom_root)
        else:
            return f"⚠️ Specified search root does not exist: `{search_root}`"
    else:
        home = Path.home()
        # Search high-priority directories first
        priority_dirs = [
            home / "Documents",
            home / "Downloads",
            home / "Desktop",
            home / "Projects",
            home / "Workspace",
            config.BASE_DIR,
        ]
        for p in priority_dirs:
            if p.exists() and p not in search_paths:
                search_paths.append(p)
        # Add Home directory as fallback
        if home not in search_paths:
            search_paths.append(home)

    matches = []
    max_matches = 15

    for root_dir in search_paths:
        if len(matches) >= max_matches:
            break

        try:
            for root, dirs, files in os.walk(str(root_dir)):
                # Prune excluded directories in-place
                dirs[:] = [
                    d for d in dirs
                    if d.lower() not in EXCLUDED_DIR_NAMES
                    and not d.startswith(".")
                ]

                # Prevent scanning too deep into arbitrary trees
                rel_depth = len(Path(root).relative_to(root_dir).parts)
                if rel_depth > 5:
                    dirs.clear()
                    continue

                for f in files:
                    if query_lower in f.lower():
                        full_path = Path(root) / f
                        try:
                            stat = full_path.stat()
                            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                            size_str = _human_readable_size(stat.st_size)
                            matches.append({
                                "name": f,
                                "path": str(full_path),
                                "size": size_str,
                                "mtime": mtime,
                            })
                            if len(matches) >= max_matches:
                                break
                        except Exception:
                            continue
                if len(matches) >= max_matches:
                    break
        except Exception:
            continue

    if not matches:
        return f"🔍 No local files found matching query '{filename_query}' across system directories."

    # Remove duplicates preserving order
    seen_paths = set()
    unique_matches = []
    for m in matches:
        if m["path"] not in seen_paths:
            seen_paths.add(m["path"])
            unique_matches.append(m)

    output = [f"### 💻 Found {len(unique_matches)} Local File(s) for '{filename_query}':\n"]
    for i, m in enumerate(unique_matches, 1):
        output.append(
            f"{i}. **`{m['name']}`**\n"
            f"   - **Path**: `{m['path']}`\n"
            f"   - **Size**: {m['size']} | **Modified**: {m['mtime']}\n"
        )

    return "\n".join(output)


def upload_local_file_to_website(
    target_url: str,
    local_file_path: str,
    additional_instructions: str = ""
) -> str:
    """
    Opens the target website on Monitor 2 using Playwright and uploads the local file into the file input.

    Args:
        target_url: Target website URL (e.g. 'https://xyz.com', 'https://dropmefiles.com').
        local_file_path: Absolute or relative path to the local file to upload.
        additional_instructions: Optional instructions such as form fields or upload button clicks.

    Returns:
        Status confirmation of the upload operation on Monitor 2.
    """
    file_path = Path(local_file_path).resolve()
    if not file_path.exists() or not file_path.is_file():
        return f"⚠️ File does not exist on laptop: `{local_file_path}`. Please verify the path or search for it first."

    # Ensure URL protocol
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = f"https://{target_url}"

    try:
        page = get_or_create_page(target_url)
        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(2)
        page.bring_to_front()

        # 1. Look for standard file inputs (including hidden ones which Playwright can set directly)
        file_inputs = page.locator('input[type="file"]')
        uploaded = False

        if file_inputs.count() > 0:
            try:
                file_inputs.first.set_input_files(str(file_path))
                uploaded = True
            except Exception:
                pass

        # 2. If not uploaded, look for clickable dropzone / upload buttons with file chooser listener
        if not uploaded:
            upload_buttons = [
                'button:has-text("Upload")',
                'button:has-text("Choose File")',
                'button:has-text("Browse")',
                'button:has-text("Select File")',
                'div[role="button"]:has-text("Upload")',
                'label:has-text("Upload")',
                'label:has-text("Choose")',
                'div[class*="dropzone"]',
                'div[class*="upload"]',
            ]
            for btn_sel in upload_buttons:
                btn = page.locator(btn_sel).first
                try:
                    if btn.is_visible(timeout=1500):
                        try:
                            with page.expect_file_chooser(timeout=4000) as fc_info:
                                btn.click()
                            file_chooser = fc_info.value
                            file_chooser.set_files(str(file_path))
                            uploaded = True
                            break
                        except Exception:
                            continue
                except Exception:
                    continue

        time.sleep(2)
        page_title = page.title()

        if uploaded:
            return (
                f"✅ **File Upload Triggered on Monitor 2!**\n"
                f"- **Target URL**: {target_url}\n"
                f"- **Local File**: `{file_path}` ({_human_readable_size(file_path.stat().st_size)})\n"
                f"- **Page Title**: \"{page_title}\"\n"
                f"- **Display**: Pinned to Monitor 2 right half. Window is active for verification."
            )
        else:
            return (
                f"ℹ️ **Website Opened on Monitor 2**: {target_url}\n"
                f"- **File Ready**: `{file_path}`\n"
                f"- **Note**: An automatic `input[type='file']` was not immediately triggered. "
                f"The page is open on Monitor 2 so you can drag and drop the file or click the upload element."
            )

    except Exception as e:
        return f"⚠️ Error automating file upload to `{target_url}`: {str(e)}"
