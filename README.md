# PC Automation Bot — Setup & Developer Guide

A secure, modular Telegram bot that runs silently on your Windows PC
and lets you trigger automation tasks from your phone — globally, no
port-forwarding required. 

---

## Project Structure

```
pc_automation/
│
├── bot.py                   ← Main entry point; auto-discovers tasks
├── setup_autostart.py       ← One-time Windows Task Scheduler installer
├── requirements.txt         ← pip dependencies
│
├── config/
│   ├── __init__.py
│   └── settings.py          ← BOT_TOKEN, AUTHORIZED_USER_ID, paths
│
├── tasks/                   ← Drop new .py files here to add commands
│   ├── __init__.py
│   ├── _template.py         ← Copy this to build a new task
│   ├── uninstall_chrome_apps.py
│   ├── clear_chrome_history.py
│   └── logout_social_media.py
│
└── logs/
    └── bot.log              ← Auto-created at runtime
```

---

## Step 1 — Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts (choose any name & username).
3. BotFather replies with a **token** like `123456:ABC-DEF1234…` — copy it.
4. Find your own **numeric user ID**:
   - Search for **@userinfobot** or **@getmyid_bot** on Telegram.
   - Start a chat — it will reply with your user ID (a plain number, e.g. `987654321`).

---

## Step 2 — Configure the Bot

Open `config/settings.py` and fill in your credentials:

```python
BOT_TOKEN: str = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
AUTHORIZED_USER_ID: int = 987654321
```

> **Security tip**: Alternatively, set environment variables so the
> token never lives in a source file:
> ```
> set PC_BOT_TOKEN=123456:ABC-DEF...
> set PC_BOT_USER_ID=987654321
> ```
> The settings file reads these automatically.

---

## Step 3 — Install Python Dependencies

```bat
cd pc_automation
pip install -r requirements.txt
```

Requires **Python 3.10+**.

---

## Step 4 — Test the Bot

```bat
python bot.py
```

Open Telegram on your phone, find your bot, send `/start`.
You should see a list of available commands.  Try `/status` to confirm
the bot is responding.

Press `Ctrl+C` to stop.

---

## Step 5 — Enable Auto-Start on Windows Login

Run the installer **once** (no admin rights needed):

```bat
python setup_autostart.py
```

This creates a **Windows Task Scheduler** entry named `PCAutomationBot`
that:
- Triggers on **your** user login
- Runs the bot silently (no console window)
- Restarts automatically if it crashes

To verify:
```bat
schtasks /Query /TN PCAutomationBot /FO LIST
```

To start it immediately without logging out:
```bat
schtasks /Run /TN PCAutomationBot
```

To remove auto-start:
```bat
python setup_autostart.py remove
```

---

## Available Bot Commands

| Command | Description |
|---|---|
| `/start` | Show all available commands |
| `/status` | Check bot is alive |
| `/uninstall_chrome_apps` | Remove Chrome PWA shortcuts (Instagram, Snapchat) |
| `/clear_chrome_history` | Delete all Chrome history, cache, and visited links |
| `/logout_social_media` | Clear session cookies for social media sites in Chrome |

> **Important**: Chrome must be fully closed before running
> `/clear_chrome_history` or `/logout_social_media` — Chrome locks
> its database files while running.

---

## How to Add a New Task (5-Minute Guide)

1. **Copy the template**:
   ```bat
   copy tasks\_template.py tasks\my_new_task.py
   ```

2. **Edit the three required parts** in `tasks/my_new_task.py`:

   ```python
   # 1. Set the command name (no slash)
   COMMAND = "run_backup"

   # 2. Set a description shown in /start
   DESCRIPTION = "Back up Documents folder to D:\\Backup"

   # 3. Implement the logic
   async def run(update, context):
       import shutil, datetime
       stamp = datetime.date.today().isoformat()
       shutil.copytree(
           r"C:\Users\Me\Documents",
           rf"D:\Backup\Documents_{stamp}",
           dirs_exist_ok=True
       )
       return f"✅ Backup complete → D:\\Backup\\Documents_{stamp}"
   ```

3. **Restart the bot** — no other files need to change.
   `/run_backup` will appear in `/start` automatically.

---

## Security Model

| Threat | Mitigation |
|---|---|
| Unauthorized users | Every handler checks `update.effective_user.id == AUTHORIZED_USER_ID`; non-matching messages are silently dropped and logged. |
| Token exposure | Token stored in `settings.py` (gitignored) or environment variable — never hard-coded in task files. |
| Task failures | Each task runs inside a `try/except`; exceptions are logged and reported to you over Telegram without crashing the bot. |
| Plaintext logs | Logs contain timestamps and command names only — no tokens, no user data. |

Add `config/settings.py` (or the whole `config/` folder) to `.gitignore`
before committing to any repository.

---

## Troubleshooting

**Bot doesn't respond**
- Confirm `BOT_TOKEN` is correct.
- Confirm `AUTHORIZED_USER_ID` matches your actual Telegram ID.
- Check `logs/bot.log` for error messages.

**Chrome tasks say "database is locked"**
- Close Chrome completely (including background processes in Task Manager)
  before sending the command.

**Auto-start not working**
- Run `schtasks /Query /TN PCAutomationBot` to confirm the task exists.
- Check that the Python path in the task still matches your current install.
- Re-run `python setup_autostart.py` after updating Python.

---

## Future Ideas

Tasks you can add by following the template above:

- `/shutdown` / `/restart` — system power commands
- `/screenshot` — take a screenshot and send it to Telegram
- `/open_app` — launch a specific application
- `/delete_downloads` — clear the Downloads folder
- `/run_script` — execute an arbitrary `.bat` or `.py` file
- `/lock_screen` — lock the Windows session
- `/notify` — send yourself a reminder message
