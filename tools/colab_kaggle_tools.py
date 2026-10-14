"""
Colab & Kaggle Automation Tools for Jarvis.
Opens and executes Google Colab notebooks on Monitor 2 in headed mode,
and provides complete Kaggle API integration for datasets, competitions, and kernels.
"""

import os
import subprocess
import time
from pathlib import Path
from typing import Optional
from tools.browser_session import get_or_create_page
import config

def run_colab_notebook_on_display2(notebook_url: str, run_all_cells: bool = True) -> str:
    """
    Opens a Google Colab notebook on Monitor 2 and triggers execution of all cells.

    Args:
        notebook_url: Full URL to the Google Colab notebook (e.g. https://colab.research.google.com/drive/...).
        run_all_cells: If True, triggers 'Run all' (Ctrl+F9) and monitors progress.

    Returns:
        Status report of the Colab execution.
    """
    if not notebook_url.startswith("http"):
        notebook_url = f"https://colab.research.google.com/drive/{notebook_url}"

    try:
        page = get_or_create_page("colab.research.google.com")
        page.goto(notebook_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)

        # Bring window into focus
        page.bring_to_front()

        # Handle Colab warning modal if opening external/shared notebook
        # E.g. "Warning: This notebook was not authored by Google." -> Click "Run anyway"
        try:
            warning_button = page.locator(
                'mwc-button:has-text("Run anyway"), button:has-text("Run anyway"), colab-dialog button#ok'
            ).first
            if warning_button.is_visible(timeout=3000):
                warning_button.click()
                time.sleep(1)
        except Exception:
            pass

        if run_all_cells:
            # Method 1: Send Ctrl+F9 (or Meta+F9)
            page.keyboard.press("Control+F9")
            time.sleep(1)

            # Method 2: Fallback click via Runtime Menu
            try:
                runtime_menu = page.locator('#runtime-menu-button, div[id="runtime-menu-button"], span:has-text("Runtime")').first
                if runtime_menu.is_visible(timeout=2000):
                    runtime_menu.click()
                    time.sleep(0.5)
                    run_all_item = page.locator('div[command="runall"], div:has-text("Run all")').first
                    if run_all_item.is_visible(timeout=2000):
                        run_all_item.click()
            except Exception:
                pass

            # Handle possible "Run anyway" dialog after shortcut
            time.sleep(1.5)
            try:
                run_anyway = page.locator('button:has-text("Run anyway"), mwc-button:has-text("Run anyway")').first
                if run_anyway.is_visible(timeout=2000):
                    run_anyway.click()
            except Exception:
                pass

            # Give cells time to spin up
            time.sleep(3)

            # Check execution indicators
            executing = False
            status_text = "Execution triggered."
            try:
                spinner = page.locator('colab-run-indicator, paper-spinner-lite[active], div.cell-execution-indicator').first
                if spinner.is_visible(timeout=2000):
                    executing = True
                    status_text = "Cells are currently running actively."
            except Exception:
                pass

            return (
                f"🚀 **Google Colab Notebook Launched on Monitor 2!**\n"
                f"- **Notebook URL**: {notebook_url}\n"
                f"- **Action**: Triggered 'Run all cells' (Ctrl+F9)\n"
                f"- **Status**: {status_text}\n"
                f"- **Display**: Pinned to Right Half of Monitor 2 (X={config.BROWSER_WINDOW_X}, Y={config.BROWSER_WINDOW_Y})"
            )
        else:
            return (
                f"📂 **Google Colab Notebook Opened on Monitor 2**\n"
                f"- **URL**: {notebook_url}\n"
                f"- **Status**: Loaded in persistent browser. Ready for manual interaction."
            )

    except Exception as e:
        return f"⚠️ Error automating Colab notebook on Monitor 2: {str(e)}"


def _has_kaggle_credentials() -> bool:
    """Verifies if Kaggle credentials are set in environment or ~/.kaggle/kaggle.json."""
    if os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"):
        return True
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    return kaggle_json.exists()


def manage_kaggle(action: str, target: str = "", download_dir: str = "./downloads") -> str:
    """
    Manages Kaggle datasets, competitions, and kernels via the official Kaggle API/CLI.

    Args:
        action: One of 'list_datasets', 'download_dataset', 'list_competitions', 'download_competition', 'kernel_status'.
        target: Query string for search or identifier (e.g. 'owner/dataset-slug' or competition slug).
        download_dir: Target directory for downloads (defaults to ./downloads).

    Returns:
        Structured summary of results or confirmation of downloaded files.
    """
    if not _has_kaggle_credentials():
        return (
            "⚠️ **Kaggle API credentials not found!**\n"
            "Please provide `KAGGLE_USERNAME` and `KAGGLE_KEY` in your `.env` file, "
            "or place your `kaggle.json` inside `~/.kaggle/kaggle.json`.\n"
            "You can generate API credentials at: https://www.kaggle.com/settings -> 'Create New API Token'."
        )

    action = action.lower().strip()
    target_dir = Path(download_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Use Kaggle Python API when available
        from kaggle.api.kaggle_api_extended import KaggleApi
        api = KaggleApi()
        api.authenticate()

        if action == "list_datasets":
            search_query = target if target else None
            datasets = api.dataset_list(search=search_query, max_size=None, page=1)
            if not datasets:
                return f"🔍 No Kaggle datasets found matching '{target}'."
            
            output = [f"### 📊 Kaggle Datasets (Search: '{target or 'top'}'):\n"]
            for ds in datasets[:8]:
                output.append(
                    f"• **{ds.ref}**\n"
                    f"  - Title: {ds.title}\n"
                    f"  - Size: {ds.size}\n"
                    f"  - Usability: {ds.usabilityRating:.2f} | Upvotes: {ds.totalVotes}\n"
                )
            return "\n".join(output)

        elif action == "download_dataset":
            if not target:
                return "⚠️ Please specify the dataset identifier (e.g. 'zynicide/wine-reviews')."
            
            api.dataset_download_files(target, path=str(target_dir), unzip=True)
            files = [f.name for f in target_dir.iterdir() if f.is_file()]
            return (
                f"📥 **Kaggle Dataset Downloaded Successfully!**\n"
                f"- **Dataset**: `{target}`\n"
                f"- **Destination**: `{target_dir}`\n"
                f"- **Files in Directory**: {', '.join(files[:10])}{' ...' if len(files) > 10 else ''}"
            )

        elif action == "list_competitions":
            comps = api.competitions_list(search=target if target else None)
            if not comps:
                return f"🔍 No Kaggle competitions found matching '{target}'."
            
            output = [f"### 🏆 Kaggle Competitions (Search: '{target or 'all'}'):\n"]
            for c in comps[:8]:
                output.append(
                    f"• **{c.ref}**\n"
                    f"  - Title: {c.title}\n"
                    f"  - Category: {c.category} | Reward: {c.reward}\n"
                    f"  - Deadline: {c.deadline}\n"
                )
            return "\n".join(output)

        elif action == "download_competition":
            if not target:
                return "⚠️ Please specify the competition slug (e.g. 'titanic')."
            api.competition_download_files(target, path=str(target_dir))
            return (
                f"📥 **Competition Files Downloaded!**\n"
                f"- **Competition**: `{target}`\n"
                f"- **Location**: `{target_dir}`"
            )

        elif action == "kernel_status":
            if not target:
                return "⚠️ Please specify the kernel slug (e.g. 'username/notebook-name')."
            status = api.kernel_status(target)
            return (
                f"⚙️ **Kaggle Kernel Status for `{target}`**:\n"
                f"- **Status**: `{status.get('status', 'Unknown')}`\n"
                f"- **Message**: {status.get('message', 'No details available')}"
            )

        else:
            return f"⚠️ Unknown Kaggle action '{action}'. Supported: list_datasets, download_dataset, list_competitions, download_competition, kernel_status."

    except Exception as e:
        # Fallback to CLI subprocess
        try:
            cmd = ["kaggle"]
            if action == "list_datasets":
                cmd.extend(["datasets", "list", "-s", target] if target else ["datasets", "list"])
            elif action == "download_dataset":
                cmd.extend(["datasets", "download", "-d", target, "-p", str(target_dir), "--unzip"])
            elif action == "list_competitions":
                cmd.extend(["competitions", "list", "-s", target] if target else ["competitions", "list"])
            elif action == "download_competition":
                cmd.extend(["competitions", "download", "-c", target, "-p", str(target_dir)])
            elif action == "kernel_status":
                cmd.extend(["kernels", "status", target])
            else:
                return f"⚠️ Unsupported action '{action}'."

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                return f"### Kaggle CLI Output:\n```\n{proc.stdout[:1500]}\n```"
            else:
                return f"⚠️ Kaggle CLI Error: {proc.stderr or proc.stdout}"
        except Exception as cli_err:
            return f"⚠️ Error executing Kaggle command: {str(e)} | CLI Fallback: {str(cli_err)}"
