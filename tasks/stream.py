"""
tasks/stream.py — Command to launch a local Flask stream server and a Cloudflare Tunnel instantly.

Registered bot command : /stream

Usage:
  /stream      -> Runs for 2 mins
  /stream 5    -> Runs for 5 mins

What it does:
  1. Starts `stream_server.py` on port 5050 in a background thread.
  2. Spawns `cloudflared.exe tunnel --url http://127.0.0.1:5050` in a subprocess.
  3. Tails the subprocess output to extract the generated `https://...trycloudflare.com` URL.
  4. Replies to the user with the URL.
  5. Schedules an asyncio task to shut everything down after the requested time limit.
"""

import asyncio
import logging
import re
import subprocess
import threading
import time

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

COMMAND = "stream"
DESCRIPTION = "Start a high-FPS live browser stream of the screen (default 2 mins)"

# Global state to track active stream/tunnel across commands
ACTIVE_STREAM = {
    "flask_thread": None,
    "cloudflared_proc": None,
    "shutdown_task": None
}

def _start_flask_server():
    """Runs the Flask server in the current thread."""
    from stream_server import run_server
    try:
        run_server(port=5050)
    except Exception as exc:
        logger.error("Flask server exited: %s", exc)

async def _shutdown_services():
    """Kills the cloudflared process. (Flask gets killed since it's a daemon thread)."""
    proc = ACTIVE_STREAM["cloudflared_proc"]
    if proc and proc.poll() is None:
        logger.info("Terminating cloudflared process...")
        try:
            # Taskkill is more reliable for whole process trees on Windows
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        except Exception:
            try: proc.kill()
            except: pass
    
    ACTIVE_STREAM["cloudflared_proc"] = None
    logger.info("Live stream shutdown complete.")

async def _delayed_shutdown(duration_min: float, bot, chat_id: int):
    """Waits, then shuts down services and notifies the user."""
    seconds = int(duration_min * 60)
    logger.info("Stream will auto-shutdown in %d seconds", seconds)
    await asyncio.sleep(seconds)
    
    await _shutdown_services()
    try:
        await bot.send_message(
            chat_id=chat_id,
            text="⏹️ Live stream auto-terminated to save resources. Use `/stream` to start again.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /stream."""
    global ACTIVE_STREAM
    
    # Check if already running
    if ACTIVE_STREAM["cloudflared_proc"] and ACTIVE_STREAM["cloudflared_proc"].poll() is None:
        return "⚠️ A live stream is already running! Use /stop_stream first."

    # Parse duration
    try:
        duration_min = float(context.args[0]) if context.args else 2.0
    except ValueError:
        return "⚠️ Invalid time. Use `/stream 5` for 5 minutes."
    
    # 1. Start Flask thread if not already running
    # (Daemon thread means it closes when the main bot process exits)
    if not ACTIVE_STREAM["flask_thread"] or not ACTIVE_STREAM["flask_thread"].is_alive():
        logger.info("Starting Flask MJPEG server on port 5050...")
        t = threading.Thread(target=_start_flask_server, daemon=True)
        t.start()
        ACTIVE_STREAM["flask_thread"] = t
        # Give it a moment to bind
        await asyncio.sleep(1)

    # 2. Start Cloudflare Tunnel targeting port 5050
    # cloudflared outputs its generated URL to stderr!
    logger.info("Starting cloudflared tunnel...")
    try:
        proc = subprocess.Popen(
            ["cloudflared.exe", "tunnel", "--url", "http://127.0.0.1:5050"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True
        )
        ACTIVE_STREAM["cloudflared_proc"] = proc
    except FileNotFoundError:
        return "❌ `cloudflared.exe` not found in the bot directory! Please download it."
    except Exception as exc:
        return f"❌ Failed to start tunnel: {exc}"

    # 3. Read stderr to find the URL
    await update.message.reply_text("⏳ Generating secure stream URL... (takes about 5-10s)")
    
    tunnel_url = None
    start_time = time.time()
    
    # cloudflared prints lines like: "|  https://random-words.trycloudflare.com  |"
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    
    while time.time() - start_time < 15: # Timeout after 15s
        # Non-blocking read would be better, but small blocking readline on startup is OK here
        # since cloudflared prints it very quickly.
        line = proc.stderr.readline()
        if line:
            logger.debug("cloudflared: %s", line.strip())
            match = url_pattern.search(line)
            if match:
                tunnel_url = match.group(0)
                break
        
        # Check if proc died
        if proc.poll() is not None:
            err = proc.stderr.read()
            logger.error("cloudflared exited early: %s", err)
            break
            
        await asyncio.sleep(0.1)

    if not tunnel_url:
        await _shutdown_services()
        return "❌ Failed to generate tunnel URL. Is Cloudflare down?"

    # 4. Schedule auto-shutdown
    if ACTIVE_STREAM["shutdown_task"] and not ACTIVE_STREAM["shutdown_task"].done():
        ACTIVE_STREAM["shutdown_task"].cancel()
        
    ACTIVE_STREAM["shutdown_task"] = asyncio.create_task(
        _delayed_shutdown(duration_min, context.bot, update.effective_chat.id)
    )

    # Send result
    return (
        f"🟢 **Live Stream is Ready!**\n\n"
        f"🔗 [Tap here to watch live]({tunnel_url})\n\n"
        f"_This secure link will auto-expire in {duration_min} minutes._\n"
        f"To kill it early, send /stop\\_stream"
    )
