"""
bot.py — Main entry point for the PC Automation Telegram Bot.

Starts the Telegram bot, loads all task modules from the /tasks folder,
and routes incoming commands to the appropriate handler.
Only responds to the authorized Telegram user ID defined in config.
"""

import asyncio
import logging
import importlib
import pkgutil
import os
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ── Local imports ──────────────────────────────────────────────────────────────
from config.settings import BOT_TOKEN, AUTHORIZED_USER_ID, LOG_FILE
import tasks  # tasks package — all modules are auto-discovered
from login_watcher import send_login_alert, watch_login_events

# ── Logging setup ──────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("bot")


# ── Auth guard decorator ───────────────────────────────────────────────────────
def authorized_only(handler):
    """Decorator that silently drops any message not from AUTHORIZED_USER_ID."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else None
        if user_id != AUTHORIZED_USER_ID:
            logger.warning("Unauthorized access attempt from user_id=%s", user_id)
            return  # Silently ignore
        return await handler(update, context)
    wrapper.__name__ = handler.__name__
    return wrapper


# ── Built-in commands ──────────────────────────────────────────────────────────
@authorized_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message listing all available commands."""
    lines = [
        "✅ *PC Automation Bot is running.*",
        "",
        "Available commands:",
        "/start — Show this help message",
        "/status — Check bot health",
        "",
        "*Automation tasks:*",
    ]
    for name, meta in TASK_REGISTRY.items():
        lines.append(f"/{name} — {meta['description']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    logger.info("User %s ran /start", update.effective_user.id)


@authorized_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Report that the bot is alive."""
    await update.message.reply_text("🟢 Bot is online and ready.")
    logger.info("User %s ran /status", update.effective_user.id)


@authorized_only
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unrecognized commands."""
    await update.message.reply_text(
        "❓ Unknown command. Use /start to see available commands."
    )


# ── Task auto-discovery ────────────────────────────────────────────────────────
def discover_tasks() -> dict:
    """
    Scan the `tasks/` package for modules that expose:
        COMMAND     : str   — the /command name (no slash)
        DESCRIPTION : str   — one-line description shown in /start
        run(update, context) : async coroutine — the handler

    Returns a dict: { command_name: {"description": ..., "handler": ...} }
    """
    registry = {}
    for finder, module_name, _ in pkgutil.iter_modules(tasks.__path__):
        if module_name.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"tasks.{module_name}")
            command = getattr(module, "COMMAND", None)
            description = getattr(module, "DESCRIPTION", "No description provided.")
            handler = getattr(module, "run", None)

            if command and callable(handler):
                registry[command] = {"description": description, "handler": handler}
                logger.info("Registered task: /%s — %s", command, description)
            else:
                logger.warning(
                    "Skipping tasks/%s — missing COMMAND or run() function", module_name
                )
        except Exception as exc:
            logger.error("Failed to load tasks/%s: %s", module_name, exc, exc_info=True)
    return registry


# ── Application bootstrap ──────────────────────────────────────────────────────
TASK_REGISTRY: dict = {}


def build_app():
    """Build and configure the Telegram Application."""
    global TASK_REGISTRY
    TASK_REGISTRY = discover_tasks()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Built-in handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))

    # Dynamically register every discovered task
    for command, meta in TASK_REGISTRY.items():
        raw_handler = meta["handler"]

        # Wrap handler with auth guard
        @authorized_only
        async def _handler(
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            _fn=raw_handler,
            _cmd=command,
        ):
            logger.info("User %s triggered /%s", update.effective_user.id, _cmd)
            await update.message.reply_text(f"⚙️ Running `/{_cmd}`…", parse_mode="Markdown")
            try:
                result = await _fn(update, context)
                if result is None:
                    # Task handled its own reply (e.g. sent a photo); nothing to do
                    return
                msg = result if isinstance(result, str) else f"✅ `/{_cmd}` completed."
            except Exception as exc:
                logger.error("Task /%s failed: %s", _cmd, exc, exc_info=True)
                msg = f"❌ `/{_cmd}` failed: {exc}"
            await update.message.reply_text(msg, parse_mode="Markdown")

        app.add_handler(CommandHandler(command, _handler))

    # Fallback for unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # ── Login alert: startup notification + background watcher ─────────────────
    async def on_startup(application):
        """Fires once after the bot connects to Telegram."""
        logger.info("Sending startup login alert…")
        await send_login_alert(application.bot, logon_type="2")
        asyncio.create_task(watch_login_events(application.bot))
        logger.info("Background login watcher task launched.")

    app.post_init = on_startup

    return app


def main():
    logger.info("Starting PC Automation Bot…")
    app = build_app()
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
