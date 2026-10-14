"""
Telegram Remote Worker for Jarvis.
Allows texting and sending voice notes to the laptop from any phone.
Locked to ALLOWED_TELEGRAM_USER_ID for security.
"""

import os
import sys
import asyncio
import tempfile
import threading
from pathlib import Path
from typing import Optional

import config
from agent_core import execute_agent_command, telemetry_buffer, get_gemini_client
from google.genai import types

def _is_user_authorized(user_id: int) -> bool:
    """Verifies that the incoming message sender matches ALLOWED_TELEGRAM_USER_ID."""
    if not config.ALLOWED_TELEGRAM_USER_ID:
        # If no ID specified, permit all or notify in console
        return True
    return user_id == config.ALLOWED_TELEGRAM_USER_ID


async def _handle_start(update, context):
    """Handles the /start command."""
    user = update.effective_user
    if not _is_user_authorized(user.id):
        await update.message.reply_text(
            f"⛔ Unauthorized Access. Your Telegram User ID is `{user.id}`.\n"
            f"Add this ID to `ALLOWED_TELEGRAM_USER_ID` in your `.env` file to grant access.",
            parse_mode="Markdown"
        )
        return

    welcome_text = (
        f"👋 **Greetings, {user.first_name}! JARVIS is online.**\n\n"
        "I am connected to your laptop and ready to execute commands remotely:\n"
        "• 📅 _'Show me today's tasks'_\n"
        "• 📬 _'Tell me about my yesterday's mail reply'_\n"
        "• 💬 _'Send a WhatsApp message to [Name] that [Message]'_\n"
        "• ✉️ _'Compose a mail to [Person] about [Topic]'_\n"
        "• 💻 _'Search this file in my system and send to xyz.com'_\n"
        "• 🚀 _'Run colab notebook [URL]'_\n\n"
        "You can send text commands or record voice notes directly here."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


async def _handle_text(update, context):
    """Processes incoming text messages and delegates to Jarvis agent core."""
    user = update.effective_user
    if not _is_user_authorized(user.id):
        await update.message.reply_text(
            f"⛔ Unauthorized. Add `ALLOWED_TELEGRAM_USER_ID={user.id}` to your `.env` to unlock.",
            parse_mode="Markdown"
        )
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    telemetry_buffer.add_event(
        event_type="telegram",
        message=f"Received Telegram command from {user.first_name} (ID: {user.id}): '{user_text}'",
        status="running"
    )

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Execute in executor to avoid blocking the asyncio Telegram loop
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, execute_agent_command, user_text)

    response_text = result.get("response", "No response generated.")

    # Split message into chunks if it exceeds Telegram's 4096 character limit
    max_len = 4000
    for i in range(0, len(response_text), max_len):
        chunk = response_text[i:i + max_len]
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            # Fallback to plain text if Markdown parsing fails
            await update.message.reply_text(chunk)


async def _handle_voice(update, context):
    """Downloads voice notes, transcribes via Gemini multimodal audio, and executes."""
    user = update.effective_user
    if not _is_user_authorized(user.id):
        await update.message.reply_text(f"⛔ Unauthorized User ID: {user.id}")
        return

    voice = update.message.voice or update.message.audio
    if not voice:
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Download voice file
        voice_file = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_audio:
            tmp_path = Path(tmp_audio.name)

        await voice_file.download_to_drive(str(tmp_path))

        # Transcribe audio using Gemini multimodal capabilities
        gemini_client = get_gemini_client()
        transcribed_text = ""

        if gemini_client:
            with open(tmp_path, "rb") as af:
                audio_bytes = af.read()
            
            trans_resp = gemini_client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                    "Accurately transcribe this user voice note into plain text. Return ONLY the transcribed words, without any preamble."
                ]
            )
            transcribed_text = trans_resp.text.strip() if trans_resp and trans_resp.text else ""

        # Cleanup audio file
        try:
            tmp_path.unlink()
        except Exception:
            pass

        if not transcribed_text:
            await update.message.reply_text("⚠️ Could not transcribe the voice note. Please try speaking again or send text.")
            return

        await update.message.reply_text(f"🎙️ *Heard:* \"_{transcribed_text}_\"", parse_mode="Markdown")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, execute_agent_command, transcribed_text)

        resp = result.get("response", "Action completed.")
        for i in range(0, len(resp), 4000):
            try:
                await update.message.reply_text(resp[i:i + 4000], parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(resp[i:i + 4000])

    except Exception as e:
        await update.message.reply_text(f"⚠️ Error handling voice note: {str(e)}")


def start_telegram_bot_thread():
    """
    Launches the Telegram bot in a standalone background daemon thread.
    Does nothing if TELEGRAM_BOT_TOKEN is not configured.
    """
    if not config.TELEGRAM_BOT_TOKEN:
        print("[*] Telegram Bot: TELEGRAM_BOT_TOKEN is not configured. Remote phone interface disabled.")
        return None

    def _runner():
        print(f"[+] Starting Telegram Bot listener (Authorized User ID: {config.ALLOWED_TELEGRAM_USER_ID or 'ANY'})...")
        try:
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
            
            # Create a dedicated event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", _handle_start))
            app.add_handler(CommandHandler("help", _handle_start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_text))
            app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, _handle_voice))

            telemetry_buffer.add_event(
                event_type="system",
                message="Telegram Remote Interface connected and listening for incoming messages.",
                status="success"
            )
            app.run_polling(close_loop=False)
        except Exception as e:
            print(f"[!] Telegram bot runner encountered an error: {e}")
            telemetry_buffer.add_event(
                event_type="system",
                message=f"Telegram bot error: {str(e)}",
                status="error"
            )

    t = threading.Thread(target=_runner, daemon=True, name="TelegramBotThread")
    t.start()
    return t

if __name__ == "__main__":
    if not config.TELEGRAM_BOT_TOKEN:
        print("Please configure TELEGRAM_BOT_TOKEN in .env")
        sys.exit(1)
    t = start_telegram_bot_thread()
    if t:
        t.join()
