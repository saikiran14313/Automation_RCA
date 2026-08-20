#!/usr/bin/env python3

import subprocess
import os
from datetime import datetime

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")
LOG_DIR = os.path.join(BASE_DIR, "logs")

os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = os.path.join(
    LOG_DIR,
    f"reboot_evidence_{timestamp}.txt"
)


def run_command(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        return result.stdout + result.stderr

    except Exception as e:
        return f"ERROR: {e}"


commands = {
    "HOSTNAME": "hostname",
    "OS": "cat /etc/os-release",
    "UPTIME": "uptime",
    "LAST_REBOOTS": "last -x | head -30",
    "BOOT_HISTORY": "journalctl --list-boots",

    "PREVIOUS_BOOT_ERRORS":
        "journalctl -b -1 -p 0..3",

    "PREVIOUS_KERNEL_LOGS":
        "journalctl -k -b -1",

    "OOM":
        "journalctl -b -1 | grep -Ei 'oom|out of memory|killed process'",

    "KERNEL_PANIC":
        "journalctl -b -1 | grep -Ei 'panic|not syncing|kernel oops|BUG:'",

    "HARDWARE":
        "journalctl -b -1 | grep -Ei 'hardware|mce|machine check|ecc|hardware error'",

    "STORAGE":
        "journalctl -b -1 | grep -Ei 'I/O error|scsi|nvme|xfs|ext4|filesystem error'",

    "WATCHDOG":
        "journalctl -b -1 | grep -Ei 'watchdog|soft lockup|hard lockup'",

    "REBOOT_SHUTDOWN":
        "journalctl -b -1 | grep -Ei 'shutdown|reboot|poweroff'",

    "MEMORY":
        "free -h",

    "DISK":
        "df -hT",

    "CRASH_FILES":
        "find /var/crash -type f -ls 2>/dev/null || true",

    "KDUMP_SERVICE":
        "systemctl status kdump 2>&1 || true",

    "KDUMP_CONFIG":
        "ls -l /etc/default/kdump-tools 2>&1 || true",

    "KDUMP_STATUS":
        "kdump-config show 2>&1 || true",
}


with open(output_file, "w") as f:

    f.write("LINUX REBOOT RCA EVIDENCE\n")
    f.write("=" * 80 + "\n")
    f.write(f"Collection Time: {datetime.now()}\n")
    f.write(f"Hostname: {run_command('hostname').strip()}\n")
    f.write("=" * 80 + "\n")

    for name, command in commands.items():

        f.write(f"\n\n### {name} ###\n")
        f.write(f"COMMAND: {command}\n")
        f.write("-" * 80 + "\n")

        output = run_command(command)

        f.write(output)


print("\nEvidence collection completed.")
print(f"Evidence file: {output_file}")
