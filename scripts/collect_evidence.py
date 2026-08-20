#!/usr/bin/env python3

import os
import re
import subprocess
from datetime import datetime

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")
LOG_DIR = os.path.join(BASE_DIR, "logs")
RAW_DIR = os.path.join(LOG_DIR, "raw")
EVIDENCE_DIR = os.path.join(LOG_DIR, "evidence")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(EVIDENCE_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

raw_file = os.path.join(
    RAW_DIR,
    f"previous_boot_{timestamp}.log"
)

evidence_file = os.path.join(
    EVIDENCE_DIR,
    f"ai_evidence_{timestamp}.txt"
)


def run(command):
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


def write_section(file, title, content):
    file.write(f"\n### {title} ###\n")
    file.write("-" * 70 + "\n")

    if content.strip():
        file.write(content.strip())
    else:
        file.write("NO EVENTS FOUND")

    file.write("\n")


print("Collecting Linux reboot evidence...")

hostname = run("hostname").strip()
boot_history = run("journalctl --list-boots")

# Previous boot journal
previous_boot = run(
    "journalctl -b -1 --no-pager"
)

# Kernel messages from previous boot
previous_kernel = run(
    "journalctl -k -b -1 --no-pager"
)

# Save RAW logs for detailed investigation
with open(raw_file, "w") as f:
    f.write("RAW PREVIOUS BOOT LOG\n")
    f.write("=" * 80 + "\n")
    f.write(f"Hostname: {hostname}\n")
    f.write(f"Collection time: {datetime.now()}\n")
    f.write("=" * 80 + "\n\n")
    f.write(previous_boot)

# Patterns for important RCA events
patterns = {
    "OOM / MEMORY": r"oom|out of memory|out-of-memory|killed process",
    "KERNEL PANIC / OOPS": r"kernel panic|not syncing|kernel oops|oops|BUG:",
    "HARDWARE": r"hardware error|machine check|mce|ecc|edac",
    "STORAGE / I/O": r"I/O error|i/o error|scsi|nvme|blk_update_request|buffer i/o",
    "FILESYSTEM": r"xfs.*error|ext4.*error|filesystem error|remounting.*read-only",
    "WATCHDOG / LOCKUP": r"watchdog|soft lockup|hard lockup|hung task",
    "SEGFAULT": r"segfault|general protection fault",
    "NETWORK": r"link is down|link down|network.*error|nic.*error",
    "REBOOT / SHUTDOWN": r"reboot|shutdown|poweroff|systemd.*reboot",
    "SYSTEMD FAILURE": r"failed to start|dependency failed|start job failed",
}

# Extract matching lines
sections = {}

combined_logs = previous_boot + "\n" + previous_kernel

for category, pattern in patterns.items():

    matches = []

    regex = re.compile(pattern, re.IGNORECASE)

    for line in combined_logs.splitlines():

        if regex.search(line):
            matches.append(line)

    # Remove duplicates while preserving order
    unique_matches = list(dict.fromkeys(matches))

    # Keep evidence manageable
    sections[category] = "\n".join(unique_matches[-100:])


# System state information
memory = run("free -h")
disk = run("df -hT")
uptime = run("uptime")
last_reboots = run("last -x | head -20")

# Kdump checks for Ubuntu
kdump_service = run(
    "systemctl is-active kdump-tools 2>&1 || true"
)

kdump_config = run(
    "kdump-config show 2>&1 || true"
)

crash_files = run(
    "find /var/crash -type f -ls 2>/dev/null || true"
)

# Create concise AI evidence
with open(evidence_file, "w") as f:

    f.write("LINUX REBOOT AI EVIDENCE\n")
    f.write("=" * 80 + "\n")

    f.write(f"Hostname: {hostname}\n")
    f.write(f"Collection Time: {datetime.now()}\n")

    f.write("\nIMPORTANT:\n")
    f.write(
        "Evidence below is extracted from the previous boot. "
        "Raw logs are preserved separately.\n"
    )

    f.write("\n### BOOT HISTORY ###\n")
    f.write("-" * 70 + "\n")
    f.write(boot_history)

    f.write("\n### UPTIME ###\n")
    f.write("-" * 70 + "\n")
    f.write(uptime)

    f.write("\n### LAST REBOOTS ###\n")
    f.write("-" * 70 + "\n")
    f.write(last_reboots)

    for category, content in sections.items():
        write_section(f, category, content)

    write_section(
        f,
        "MEMORY STATUS AFTER BOOT",
        memory
    )

    write_section(
        f,
        "DISK STATUS AFTER BOOT",
        disk
    )

    write_section(
        f,
        "KDUMP SERVICE",
        kdump_service
    )

    write_section(
        f,
        "KDUMP CONFIGURATION",
        kdump_config
    )

    write_section(
        f,
        "CRASH / VMCORE FILES",
        crash_files
    )

print("\n======================================")
print("COLLECTION COMPLETED")
print("======================================")
print(f"Raw previous boot log:")
print(raw_file)
print()
print(f"AI evidence file:")
print(evidence_file)
