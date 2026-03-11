"""
setup_autostart.py — Register the bot to start automatically on Windows login.

Run this script ONCE (as your normal user, no admin required) after setting
up the project.  It creates a Task Scheduler entry that:
  • Triggers when YOUR user account logs in
  • Runs silently in the background (hidden window, no UAC prompt)
  • Restarts automatically if it crashes
  • Uses the Python interpreter that is running this script

Usage:
    python setup_autostart.py          # install / update
    python setup_autostart.py remove   # uninstall
"""

import os
import sys
import subprocess
import argparse
import textwrap

TASK_NAME = "PCAutomationBot"


def get_paths() -> tuple[str, str]:
    """Return (python_exe, bot_script_path)."""
    python_exe = sys.executable
    if python_exe.lower().endswith("python.exe"):
        pythonw = python_exe[:-10] + "pythonw.exe"
        if os.path.exists(pythonw):
            python_exe = pythonw
            
    bot_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
    if not os.path.isfile(bot_script):
        print(f"ERROR: bot.py not found at {bot_script}")
        sys.exit(1)
    return python_exe, bot_script


def install():
    python_exe, bot_script = get_paths()
    project_dir = os.path.dirname(bot_script)

    # schtasks XML approach — more reliable than command-line flags
    xml = textwrap.dedent(f"""\
    <?xml version="1.0" encoding="UTF-16"?>
    <Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <RegistrationInfo>
        <Description>PC Automation Telegram Bot — starts on user login</Description>
      </RegistrationInfo>
      <Triggers>
        <LogonTrigger>
          <Enabled>true</Enabled>
          <UserId>{os.environ.get('USERNAME', '')}</UserId>
        </LogonTrigger>
      </Triggers>
      <Principals>
        <Principal id="Author">
          <LogonType>InteractiveToken</LogonType>
          <RunLevel>LeastPrivilege</RunLevel>
        </Principal>
      </Principals>
      <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
        <RestartOnFailure>
          <Interval>PT1M</Interval>
          <Count>999</Count>
        </RestartOnFailure>
        <Enabled>true</Enabled>
        <Hidden>true</Hidden>
      </Settings>
      <Actions>
        <Exec>
          <Command>{python_exe}</Command>
          <Arguments>"{bot_script}"</Arguments>
          <WorkingDirectory>{project_dir}</WorkingDirectory>
        </Exec>
      </Actions>
    </Task>
    """)

    xml_path = os.path.join(os.environ.get("TEMP", "."), "pc_bot_task.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(xml)

    result = subprocess.run(
        ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", xml_path, "/F"],
        capture_output=True, text=True
    )
    os.remove(xml_path)

    if result.returncode == 0:
        print(f"[+] Task '{TASK_NAME}' created successfully.")
        print(f"   Python : {python_exe}")
        print(f"   Script : {bot_script}")
        print(f"\nThe bot will start automatically next time you log in.")
        print(f"To start it right now without logging out:")
        print(f"   schtasks /Run /TN {TASK_NAME}")
    else:
        print("[-] Failed to create scheduled task:")
        print(result.stderr)
        print("\nAlternative: manually add a shortcut to bot.py in:")
        print(r"  %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")


def remove():
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[+] Task '{TASK_NAME}' removed.")
    else:
        print("[-] Could not remove task (may not exist).")
        print(result.stderr)


if __name__ == "__main__":
    if sys.platform != "win32":
        print("This script is for Windows only.")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Install/remove PC Automation Bot autostart")
    parser.add_argument("action", nargs="?", default="install", choices=["install", "remove"])
    args = parser.parse_args()

    if args.action == "remove":
        remove()
    else:
        install()
