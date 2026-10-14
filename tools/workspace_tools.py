"""
Workspace Tools module for Jarvis.
Integrates Google Calendar, Google Tasks, Gmail, and Google Drive APIs.
"""

import os
import base64
import mimetypes
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Optional

from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config

def _get_google_credentials() -> Optional[Credentials]:
    """
    Loads and refreshes OAuth credentials from token.json.
    Returns Credentials or None if token does not exist.
    """
    token_file = config.GOOGLE_TOKEN_FILE
    if not token_file.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(token_file), config.GOOGLE_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"[!] Error refreshing Google token: {e}")
            return None
    return creds


def get_todays_tasks_and_schedule() -> str:
    """
    Fetches today's primary Google Calendar events and all pending Google Tasks.

    Returns:
        Clean markdown summary of schedule and incomplete tasks.
    """
    creds = _get_google_credentials()
    if not creds:
        return (
            "⚠️ Google Workspace authorization not found. "
            "Please run `python setup_google_oauth.py` once to authorize Calendar and Tasks."
        )

    output = ["### 📅 Today's Schedule & Tasks Overview\n"]
    now = datetime.now()
    start_of_day = datetime.combine(now.date(), time.min).isoformat() + "Z"
    end_of_day = datetime.combine(now.date(), time.max).isoformat() + "Z"

    # 1. Fetch Calendar Events
    try:
        cal_service = build("calendar", "v3", credentials=creds)
        events_result = (
            cal_service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        output.append("#### 🗓️ Scheduled Calendar Events:")
        if not events:
            output.append("• No events scheduled for today. Your calendar is clear!\n")
        else:
            for event in events:
                summary = event.get("summary", "Untitled Event")
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))
                loc = event.get("location")
                loc_str = f" (📍 {loc})" if loc else ""
                output.append(f"• **{start} - {end}**: {summary}{loc_str}")
            output.append("")
    except Exception as e:
        output.append(f"⚠️ Error retrieving Calendar events: {e}\n")

    # 2. Fetch Google Tasks
    try:
        tasks_service = build("tasks", "v1", credentials=creds)
        task_lists = tasks_service.tasklists().list(maxResults=10).execute().get("items", [])
        output.append("#### ✅ Incomplete Google Tasks:")
        pending_count = 0
        for tlist in task_lists:
            tlist_title = tlist.get("title", "Tasks")
            tasks = (
                tasks_service.tasks()
                .list(tasklist=tlist["id"], showCompleted=False, maxResults=20)
                .execute()
                .get("items", [])
            )
            for t in tasks:
                title = t.get("title", "").strip()
                if not title:
                    continue
                due = t.get("due")
                due_str = f" [Due: {due[:10]}]" if due else ""
                notes = t.get("notes")
                notes_str = f" - _{notes}_" if notes else ""
                output.append(f"• [{tlist_title}] {title}{due_str}{notes_str}")
                pending_count += 1

        if pending_count == 0:
            output.append("• No pending tasks found. All caught up!")
    except Exception as e:
        output.append(f"⚠️ Error retrieving Google Tasks: {e}")

    return "\n".join(output)


def get_yesterdays_email_replies(sender_or_query: str = "") -> str:
    """
    Retrieves recent emails and replies from Gmail from the last 24-48 hours.

    Args:
        sender_or_query: Optional sender name, email address, or keyword to filter.

    Returns:
        Structured summary of sender, subject, date, and key body snippet.
    """
    creds = _get_google_credentials()
    if not creds:
        return (
            "⚠️ Google Workspace authorization not found. "
            "Please run `python setup_google_oauth.py` to authorize Gmail."
        )

    try:
        service = build("gmail", "v1", credentials=creds)
        
        # Build search query: newer_than:2d
        query_parts = ["newer_than:2d"]
        if sender_or_query:
            query_parts.append(f"({sender_or_query})")
        query = " ".join(query_parts)

        results = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = results.get("messages", [])

        if not messages:
            return f"📭 No emails found matching the criteria '{query}' from the last 48 hours."

        summaries = [f"### 📬 Recent Emails & Replies ({len(messages)} found)\n"]

        for msg_meta in messages:
            msg = service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
            payload = msg.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
            
            subject = headers.get("subject", "(No Subject)")
            sender = headers.get("from", "Unknown Sender")
            date_str = headers.get("date", "Unknown Date")
            snippet = msg.get("snippet", "")
            
            is_reply = subject.lower().startswith("re:") or "in-reply-to" in headers
            reply_tag = "💬 [REPLY]" if is_reply else "✉️ [NEW MESSAGE]"

            summaries.append(
                f"**{reply_tag} {subject}**\n"
                f"- **From**: `{sender}`\n"
                f"- **Date**: {date_str}\n"
                f"- **Preview**: {snippet}\n"
                f"- **Message ID**: `{msg_meta['id']}`\n"
            )

        return "\n".join(summaries)
    except Exception as e:
        return f"⚠️ Error fetching email replies from Gmail: {str(e)}"


def compose_or_send_email(
    recipient: str,
    subject: str,
    body: str,
    attachment_path: str = "",
    send_now: bool = False
) -> str:
    """
    Composes a Gmail draft or sends an email directly, with optional file attachment.

    Args:
        recipient: Destination email address (e.g. user@example.com).
        subject: Email subject line.
        body: Text content of the email.
        attachment_path: Absolute or relative local path to a file to attach.
        send_now: If True, sends the email immediately. If False, saves as a draft.

    Returns:
        Status message with draft or message ID.
    """
    creds = _get_google_credentials()
    if not creds:
        return (
            "⚠️ Google Workspace authorization not found. "
            "Please run `python setup_google_oauth.py` to authorize Gmail."
        )

    try:
        service = build("gmail", "v1", credentials=creds)

        message = MIMEMultipart()
        message["to"] = recipient
        message["subject"] = subject
        message.attach(MIMEText(body, "plain"))

        # Process attachment if requested
        if attachment_path:
            attach_file = Path(attachment_path).resolve()
            if attach_file.exists() and attach_file.is_file():
                content_type, encoding = mimetypes.guess_type(str(attach_file))
                if content_type is None or encoding is not None:
                    content_type = "application/octet-stream"
                main_type, sub_type = content_type.split("/", 1)

                with open(attach_file, "rb") as fp:
                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(fp.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename=\"{attach_file.name}\""
                )
                message.attach(part)
            else:
                return f"⚠️ Warning: Specified attachment path does not exist: {attachment_path}"

        raw_msg = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        if send_now:
            sent_resp = service.users().messages().send(userId="me", body={"raw": raw_msg}).execute()
            msg_id = sent_resp.get("id")
            return (
                f"✅ **Email successfully sent!**\n"
                f"- **To**: `{recipient}`\n"
                f"- **Subject**: {subject}\n"
                f"- **Message ID**: `{msg_id}`\n"
                f"- **Attachment**: `{attachment_path or 'None'}`"
            )
        else:
            draft_resp = service.users().drafts().create(userId="me", body={"message": {"raw": raw_msg}}).execute()
            draft_id = draft_resp.get("id")
            return (
                f"📝 **Email draft created in Gmail!**\n"
                f"- **To**: `{recipient}`\n"
                f"- **Subject**: {subject}\n"
                f"- **Draft ID**: `{draft_id}`\n"
                f"- **Attachment**: `{attachment_path or 'None'}`\n"
                f"_You can review and click Send from your Gmail client, or request Jarvis to send it._"
            )
    except Exception as e:
        return f"⚠️ Error processing email operation: {str(e)}"


def search_or_upload_google_drive(query: str = "", upload_local_path: str = "") -> str:
    """
    Searches Google Drive for matching files or uploads a local file to Drive.

    Args:
        query: Search term for filename.
        upload_local_path: Local path of file to upload.

    Returns:
        Markdown description with file names and webViewLinks.
    """
    creds = _get_google_credentials()
    if not creds:
        return (
            "⚠️ Google Workspace authorization not found. "
            "Please run `python setup_google_oauth.py` to authorize Google Drive."
        )

    try:
        service = build("drive", "v3", credentials=creds)

        # Mode 1: Upload File
        if upload_local_path:
            local_path = Path(upload_local_path).resolve()
            if not local_path.exists() or not local_path.is_file():
                return f"⚠️ File to upload not found: {upload_local_path}"

            file_metadata = {"name": local_path.name}
            media = MediaFileUpload(str(local_path), resumable=True)
            uploaded = (
                service.files()
                .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
                .execute()
            )
            return (
                f"☁️ **File Uploaded to Google Drive Successfully!**\n"
                f"- **Filename**: `{uploaded.get('name')}`\n"
                f"- **File ID**: `{uploaded.get('id')}`\n"
                f"- **View Link**: {uploaded.get('webViewLink')}"
            )

        # Mode 2: Search Files
        search_q = "trashed = false"
        if query:
            clean_q = query.replace("'", "\\'")
            search_q += f" and name contains '{clean_q}'"

        results = (
            service.files()
            .list(q=search_q, pageSize=10, fields="files(id, name, mimeType, webViewLink, modifiedTime, size)")
            .execute()
        )
        files = results.get("files", [])

        if not files:
            return f"🔍 No Google Drive files found matching '{query}'."

        res = [f"### 📂 Google Drive Search Results ({len(files)} files found)\n"]
        for f in files:
            name = f.get("name", "Untitled")
            link = f.get("webViewLink", "#")
            fid = f.get("id")
            mtype = f.get("mimeType", "")
            res.append(f"• **[{name}]({link})** (`{mtype}`) — ID: `{fid}`")

        return "\n".join(res)
    except Exception as e:
        return f"⚠️ Error with Google Drive operation: {str(e)}"
