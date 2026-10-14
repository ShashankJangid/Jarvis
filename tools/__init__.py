"""
Tools package for Jarvis Dual-Display Personal Agent.
Provides Workspace, WhatsApp Web, Colab & Kaggle, and System File operations.
"""

from .workspace_tools import (
    get_todays_tasks_and_schedule,
    get_yesterdays_email_replies,
    compose_or_send_email,
    search_or_upload_google_drive,
)
from .whatsapp_web_tool import (
    send_whatsapp_message,
    read_recent_whatsapp_messages,
)
from .colab_kaggle_tools import (
    run_colab_notebook_on_display2,
    manage_kaggle,
)
from .system_file_tools import (
    search_local_files_on_laptop,
    upload_local_file_to_website,
)

__all__ = [
    "get_todays_tasks_and_schedule",
    "get_yesterdays_email_replies",
    "compose_or_send_email",
    "search_or_upload_google_drive",
    "send_whatsapp_message",
    "read_recent_whatsapp_messages",
    "run_colab_notebook_on_display2",
    "manage_kaggle",
    "search_local_files_on_laptop",
    "upload_local_file_to_website",
]
