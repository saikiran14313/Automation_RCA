#!/usr/bin/env python3

import os
import re
import subprocess
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

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


# ============================================================
# COMMAND EXECUTOR
# ============================================================

def run(command):

    try:

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        output = (
            result.stdout
            + result.stderr
        )

        return output.strip()

    except subprocess.TimeoutExpired:

        return "ERROR: Command timed out"

    except Exception as exc:

        return f"ERROR: {exc}"


# ============================================================
# WRITE SECTION
# ============================================================

def write_section(file, title, content):

    file.write(
        f"\n### {title} ###\n"
    )

    file.write(
        "-" * 80
        + "\n"
    )

    if content and content.strip():

        file.write(
            content.strip()
        )

    else:

        file.write(
            "NO EVENTS FOUND"
        )

    file.write("\n")


# ============================================================
# HEADER
# ============================================================

print()
print("=" * 70)
print("LINUX REBOOT INTELLIGENCE EVIDENCE COLLECTOR")
print("=" * 70)
print()

print(
    "Collecting Linux system, reboot, kernel, "
    "hardware, storage, kdump and crash evidence..."
)

print()


# ============================================================
# BASIC SYSTEM INFORMATION
# ============================================================

hostname = run(
    "hostname"
)

uname = run(
    "uname -a"
)

os_release = run(
    "cat /etc/os-release"
)

uptime = run(
    "uptime"
)

who = run(
    "who"
)

date_info = run(
    "date"
)

kernel_version = run(
    "uname -r"
)


# ============================================================
# MEMORY
# ============================================================

memory = run(
    "free -h"
)

memory_details = run(
    "cat /proc/meminfo"
)


# ============================================================
# DISK / FILESYSTEM
# ============================================================

disk = run(
    "df -hT"
)

disk_inode = run(
    "df -ih"
)

mounts = run(
    "mount"
)

block_devices = run(
    "lsblk -f"
)

fstab = run(
    "cat /etc/fstab"
)


# ============================================================
# KERNEL COMMAND LINE
# ============================================================

cmdline = run(
    "cat /proc/cmdline"
)


# ============================================================
# BOOT HISTORY
# ============================================================

boot_history = run(
    "journalctl --list-boots --no-pager"
)

last_reboots = run(
    "last -x | head -40"
)

last_logins = run(
    "last -20"
)


# ============================================================
# PREVIOUS BOOT JOURNAL
# ============================================================

previous_boot = run(
    "journalctl -b -1 --no-pager"
)


# ============================================================
# PREVIOUS KERNEL LOG
# ============================================================

previous_kernel = run(
    "journalctl -k -b -1 --no-pager"
)


# ============================================================
# PREVIOUS BOOT WARNINGS / ERRORS
# ============================================================

previous_errors = run(
    "journalctl -b -1 "
    "-p warning..alert "
    "--no-pager"
)


# ============================================================
# CURRENT BOOT WARNINGS / ERRORS
# ============================================================

current_errors = run(
    "journalctl -b 0 "
    "-p warning..alert "
    "--no-pager"
)


# ============================================================
# KERNEL PANIC / OOPS
# ============================================================

kernel_panic = run(
    "journalctl -k -b -1 --no-pager "
    "| grep -Ei "
    "'kernel panic|not syncing|"
    "kernel oops|oops|BUG:' "
    "|| true"
)


# ============================================================
# OOM / MEMORY
# ============================================================

oom = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'out of memory|"
    "out-of-memory|"
    "oom-killer|"
    "oom_reaper|"
    "killed process|"
    "memory cgroup' "
    "|| true"
)


# ============================================================
# HARDWARE / MCE / ECC / EDAC
# ============================================================

hardware = run(
    "journalctl -k -b -1 --no-pager "
    "| grep -Ei "
    "'hardware error|"
    "machine check|"
    "\\bmce\\b|"
    "\\becc\\b|"
    "\\bedac\\b|"
    "corrected error|"
    "uncorrected error' "
    "|| true"
)

mce_current = run(
    "dmesg -T 2>/dev/null "
    "| grep -Ei "
    "'hardware error|"
    "machine check|"
    "\\bmce\\b|"
    "\\becc\\b|"
    "\\bedac\\b' "
    "|| true"
)


# ============================================================
# STORAGE / I/O
# ============================================================

storage = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'I/O error|"
    "i/o error|"
    "blk_update_request|"
    "buffer I/O|"
    "nvme.*error|"
    "scsi.*error|"
    "ata.*error|"
    "resetting link|"
    "device offline|"
    "read error|"
    "write error' "
    "|| true"
)


# ============================================================
# FILESYSTEM
# ============================================================

filesystem = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'EXT4-fs error|"
    "XFS.*error|"
    "filesystem error|"
    "remount.*read-only|"
    "read-only filesystem|"
    "journal aborted|"
    "I/O failure' "
    "|| true"
)


# ============================================================
# WATCHDOG / LOCKUP / HUNG TASK
# ============================================================

watchdog = run(
    "journalctl -k -b -1 --no-pager "
    "| grep -Ei "
    "'watchdog|"
    "soft lockup|"
    "hard lockup|"
    "hung task|"
    "rcu.*stall|"
    "blocked for more than|"
    "task blocked' "
    "|| true"
)


# ============================================================
# SEGFAULT / PROCESS CRASH
# ============================================================

segfault = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'segfault|"
    "general protection fault|"
    "core dumped|"
    "trap invalid opcode' "
    "|| true"
)


# ============================================================
# NETWORK
# ============================================================

network = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'link is down|"
    "link down|"
    "network.*error|"
    "NIC.*error|"
    "carrier lost|"
    "carrier down|"
    "transmit timeout' "
    "|| true"
)


# ============================================================
# SYSTEMD FAILURE
# ============================================================

systemd_failure = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'failed to start|"
    "dependency failed|"
    "start job failed|"
    "failed with result|"
    "entered failed state' "
    "|| true"
)


# ============================================================
# REBOOT / SHUTDOWN
# ============================================================

reboot_logs = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'reboot|"
    "shutdown|"
    "poweroff|"
    "systemd.*reboot|"
    "system is rebooting|"
    "system will reboot' "
    "|| true"
)


# ============================================================
# MANUAL REBOOT
# ============================================================

manual_reboot = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'sudo.*reboot|"
    "COMMAND=.*reboot|"
    "COMMAND=/usr/sbin/reboot|"
    "COMMAND=/sbin/reboot|"
    "sudo.*shutdown|"
    "COMMAND=.*shutdown' "
    "|| true"
)


# ============================================================
# SUDO COMMAND HISTORY FROM JOURNAL
# ============================================================

sudo_commands = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'sudo\\[|sudo:' "
    "|| true"
)


# ============================================================
# CRON LOGS
# ============================================================

cron_logs = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'cron|CRON' "
    "|| true"
)


# ============================================================
# CRON REBOOT
# ============================================================

cron_reboot = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'cron.*reboot|"
    "cron.*shutdown|"
    "CRON.*reboot|"
    "CRON.*shutdown' "
    "|| true"
)


# ============================================================
# SYSTEMD REBOOT
# ============================================================

systemd_reboot = run(
    "journalctl -b -1 --no-pager "
    "| grep -Ei "
    "'reached target reboot|"
    "systemd-reboot.service|"
    "system is rebooting|"
    "system will reboot|"
    "systemd-shutdown' "
    "|| true"
)


# ============================================================
# SYSTEMD TIMERS
# ============================================================

systemd_timers = run(
    "systemctl list-timers --all --no-pager"
)


# ============================================================
# ROOT CRONTAB
# ============================================================

root_crontab = run(
    "crontab -l 2>&1 || true"
)


# ============================================================
# UBUNTU CRONTAB
# ============================================================

ubuntu_crontab = run(
    "sudo -u ubuntu crontab -l 2>&1 || true"
)


# ============================================================
# SYSTEM CRON CONFIGURATION
# ============================================================

cron_directories = run(
    "find /etc/cron.d "
    "/etc/cron.daily "
    "/etc/cron.hourly "
    "/etc/cron.weekly "
    "/etc/cron.monthly "
    "-maxdepth 1 "
    "-type f "
    "-ls "
    "2>/dev/null || true"
)


# ============================================================
# FAILED SERVICES
# ============================================================

failed_services = run(
    "systemctl --failed --no-pager"
)


# ============================================================
# IMPORTANT SERVICES
# ============================================================

service_status = run(
    "systemctl --type=service "
    "--state=failed "
    "--no-pager"
)


# ============================================================
# PROCESS INFORMATION
# ============================================================

top_processes = run(
    "ps aux --sort=-%mem | head -30"
)


# ============================================================
# KERNEL MODULES
# ============================================================

loaded_modules = run(
    "lsmod"
)


# ============================================================
# KERNEL MESSAGES CURRENT BOOT
# ============================================================

current_kernel = run(
    "journalctl -k -b 0 --no-pager"
)


# ============================================================
# KDUMP SERVICE
# ============================================================

kdump_service = run(
    "systemctl is-active kdump-tools 2>&1 || true"
)

kdump_enabled = run(
    "systemctl is-enabled kdump-tools 2>&1 || true"
)

kdump_status = run(
    "kdump-config status 2>&1 || true"
)

kdump_config = run(
    "kdump-config show 2>&1 || true"
)

kdump_test = run(
    "kdump-config test 2>&1 || true"
)


# ============================================================
# CRASHKERNEL
# ============================================================

crashkernel_cmdline = run(
    "cat /proc/cmdline "
    "| grep -o "
    "'crashkernel=[^ ]*' "
    "|| true"
)

crashkernel_config = run(
    "grep -R "
    "'crashkernel' "
    "/etc/default/grub.d/ "
    "/etc/default/grub "
    "2>/dev/null || true"
)


# ============================================================
# KDUMP DIRECTORY
# ============================================================

kdump_directory = run(
    "ls -lah /var/lib/kdump/ "
    "2>&1 || true"
)


# ============================================================
# KDUMP KERNEL
# ============================================================

kdump_kernel = run(
    "readlink -f "
    "/var/lib/kdump/vmlinuz "
    "2>&1 || true"
)


# ============================================================
# KDUMP INITRD
# ============================================================

kdump_initrd = run(
    "readlink -f "
    "/var/lib/kdump/initrd.img "
    "2>&1 || true"
)


# ============================================================
# KDUMP CONFIG FILE
# ============================================================

kdump_defaults = run(
    "grep -v '^#' "
    "/etc/default/kdump-tools "
    "| grep -v '^$' "
    "2>/dev/null || true"
)


# ============================================================
# VMCORE / CRASH FILES
# ============================================================

crash_files = run(
    "find /var/crash "
    "-type f "
    "-ls "
    "2>/dev/null || true"
)

vmcore_files = run(
    "find /var/crash /var/lib/kdump "
    "-type f "
    "\\("
    "-name 'vmcore*' "
    "-o "
    "-name '*.dump' "
    "-o "
    "-name 'kdump*' "
    "\\) "
    "-ls "
    "2>/dev/null || true"
)


# ============================================================
# /VAR/CRASH DIRECTORY
# ============================================================

crash_directory = run(
    "ls -lah /var/crash "
    "2>&1 || true"
)


# ============================================================
# BOOT KERNEL FILES
# ============================================================

kernel_files = run(
    "ls -lh "
    "/boot/vmlinuz* "
    "/boot/initrd.img* "
    "2>/dev/null || true"
)


# ============================================================
# GRUB CONFIGURATION
# ============================================================

grub_config = run(
    "grep -R "
    "'GRUB_CMDLINE_LINUX' "
    "/etc/default/grub "
    "/etc/default/grub.d/ "
    "2>/dev/null || true"
)


# ============================================================
# JOURNAL STORAGE
# ============================================================

journal_disk = run(
    "journalctl --disk-usage"
)


# ============================================================
# JOURNAL BOOT AVAILABILITY
# ============================================================

journal_boots = run(
    "journalctl --list-boots --no-pager"
)


# ============================================================
# RAW PREVIOUS BOOT LOG
# ============================================================

with open(
    raw_file,
    "w",
    errors="ignore"
) as file:

    file.write(
        "LINUX RAW PREVIOUS BOOT LOG\n"
    )

    file.write(
        "=" * 80
        + "\n"
    )

    file.write(
        f"Hostname: {hostname}\n"
    )

    file.write(
        f"Collection Time: "
        f"{datetime.now()}\n"
    )

    file.write(
        "=" * 80
        + "\n\n"
    )

    file.write(
        previous_boot
    )


# ============================================================
# FILTER IMPORTANT EVENTS
# ============================================================

patterns = {

    "OOM / MEMORY":
        r"oom|out of memory|"
        r"out-of-memory|"
        r"oom-killer|"
        r"killed process",

    "KERNEL PANIC / OOPS":
        r"kernel panic|"
        r"not syncing|"
        r"kernel oops|"
        r"\boops\b|"
        r"BUG:",

    "HARDWARE":
        r"hardware error|"
        r"machine check|"
        r"\bmce\b|"
        r"\becc\b|"
        r"\bedac\b|"
        r"corrected error|"
        r"uncorrected error",

    "STORAGE / I/O":
        r"I/O error|"
        r"i/o error|"
        r"blk_update_request|"
        r"buffer I/O|"
        r"nvme.*error|"
        r"scsi.*error|"
        r"ata.*error|"
        r"resetting link",

    "FILESYSTEM":
        r"EXT4-fs error|"
        r"XFS.*error|"
        r"filesystem error|"
        r"remount.*read-only|"
        r"read-only filesystem",

    "WATCHDOG / LOCKUP":
        r"watchdog|"
        r"soft lockup|"
        r"hard lockup|"
        r"hung task|"
        r"rcu.*stall",

    "SEGFAULT":
        r"segfault|"
        r"general protection fault|"
        r"core dumped",

    "NETWORK":
        r"link is down|"
        r"link down|"
        r"network.*error|"
        r"NIC.*error|"
        r"carrier lost",

    "SYSTEMD FAILURE":
        r"failed to start|"
        r"dependency failed|"
        r"start job failed|"
        r"failed with result",

    "REBOOT / SHUTDOWN":
        r"reboot|"
        r"shutdown|"
        r"poweroff|"
        r"systemd.*reboot",
}


combined_logs = (
    previous_boot
    + "\n"
    + previous_kernel
)


filtered_sections = {}


for category, pattern in patterns.items():

    matches = []

    regex = re.compile(
        pattern,
        re.IGNORECASE
    )

    for line in combined_logs.splitlines():

        if regex.search(line):

            matches.append(line)

    # Remove duplicate lines
    unique_matches = list(
        dict.fromkeys(matches)
    )

    # Keep evidence manageable
    filtered_sections[
        category
    ] = "\n".join(
        unique_matches[-200:]
    )


# ============================================================
# CREATE EVIDENCE FILE
# ============================================================

with open(
    evidence_file,
    "w",
    errors="ignore"
) as file:

    file.write(
        "LINUX REBOOT INTELLIGENCE EVIDENCE\n"
    )

    file.write(
        "=" * 80
        + "\n"
    )

    file.write(
        f"Hostname: {hostname}\n"
    )

    file.write(
        f"Collection Time: "
        f"{datetime.now()}\n"
    )

    file.write(
        "\nIMPORTANT:\n"
    )

    file.write(
        "This evidence contains system state, "
        "previous/current boot logs, reboot events, "
        "kernel errors, hardware/storage events, "
        "cron information, kdump configuration and "
        "crash dump information.\n"
    )


    # ========================================================
    # SYSTEM
    # ========================================================

    write_section(
        file,
        "SYSTEM INFORMATION",
        uname
    )

    write_section(
        file,
        "KERNEL VERSION",
        kernel_version
    )

    write_section(
        file,
        "OS RELEASE",
        os_release
    )

    write_section(
        file,
        "DATE",
        date_info
    )

    write_section(
        file,
        "UPTIME",
        uptime
    )

    write_section(
        file,
        "CURRENT USERS",
        who
    )


    # ========================================================
    # MEMORY / DISK
    # ========================================================

    write_section(
        file,
        "MEMORY STATUS",
        memory
    )

    write_section(
        file,
        "MEMORY DETAILS",
        memory_details
    )

    write_section(
        file,
        "DISK STATUS",
        disk
    )

    write_section(
        file,
        "INODE STATUS",
        disk_inode
    )

    write_section(
        file,
        "BLOCK DEVICES",
        block_devices
    )

    write_section(
        file,
        "MOUNT INFORMATION",
        mounts
    )

    write_section(
        file,
        "FILESYSTEM CONFIGURATION",
        fstab
    )


    # ========================================================
    # KERNEL
    # ========================================================

    write_section(
        file,
        "KERNEL CMDLINE",
        cmdline
    )

    write_section(
        file,
        "LOADED KERNEL MODULES",
        loaded_modules
    )


    # ========================================================
    # BOOT HISTORY
    # ========================================================

    write_section(
        file,
        "BOOT HISTORY",
        boot_history
    )

    write_section(
        file,
        "LAST REBOOTS",
        last_reboots
    )

    write_section(
        file,
        "LAST LOGINS",
        last_logins
    )


    # ========================================================
    # JOURNAL
    # ========================================================

    write_section(
        file,
        "PREVIOUS BOOT ERRORS",
        previous_errors
    )

    write_section(
        file,
        "CURRENT BOOT ERRORS",
        current_errors
    )

    write_section(
        file,
        "JOURNAL DISK USAGE",
        journal_disk
    )

    write_section(
        file,
        "AVAILABLE JOURNAL BOOTS",
        journal_boots
    )


    # ========================================================
    # KERNEL CURRENT / PREVIOUS
    # ========================================================

    write_section(
        file,
        "PREVIOUS KERNEL LOG",
        previous_kernel
    )

    write_section(
        file,
        "CURRENT KERNEL LOG",
        current_kernel
    )


    # ========================================================
    # RCA EVENTS
    # ========================================================

    write_section(
        file,
        "KERNEL PANIC / OOPS",
        kernel_panic
    )

    write_section(
        file,
        "OOM / MEMORY EVENTS",
        oom
    )

    write_section(
        file,
        "HARDWARE EVENTS",
        hardware
    )

    write_section(
        file,
        "MCE / ECC / EDAC",
        mce_current
    )

    write_section(
        file,
        "STORAGE / I/O EVENTS",
        storage
    )

    write_section(
        file,
        "FILESYSTEM EVENTS",
        filesystem
    )

    write_section(
        file,
        "WATCHDOG / LOCKUP EVENTS",
        watchdog
    )

    write_section(
        file,
        "SEGFAULT / PROCESS CRASH",
        segfault
    )

    write_section(
        file,
        "NETWORK EVENTS",
        network
    )

    write_section(
        file,
        "SYSTEMD FAILURES",
        systemd_failure
    )


    # ========================================================
    # REBOOT
    # ========================================================

    write_section(
        file,
        "REBOOT / SHUTDOWN",
        reboot_logs
    )

    write_section(
        file,
        "MANUAL / SUDO REBOOT",
        manual_reboot
    )

    write_section(
        file,
        "SUDO COMMANDS",
        sudo_commands
    )

    write_section(
        file,
        "CRON LOGS",
        cron_logs
    )

    write_section(
        file,
        "CRON REBOOT",
        cron_reboot
    )

    write_section(
        file,
        "SYSTEMD REBOOT",
        systemd_reboot
    )


    # ========================================================
    # CRON / AUTOMATION
    # ========================================================

    write_section(
        file,
        "SYSTEMD TIMERS",
        systemd_timers
    )

    write_section(
        file,
        "ROOT CRONTAB",
        root_crontab
    )

    write_section(
        file,
        "UBUNTU CRONTAB",
        ubuntu_crontab
    )

    write_section(
        file,
        "SYSTEM CRON CONFIGURATION",
        cron_directories
    )


    # ========================================================
    # SERVICES / PROCESSES
    # ========================================================

    write_section(
        file,
        "FAILED SYSTEMD SERVICES",
        failed_services
    )

    write_section(
        file,
        "SERVICE FAILURE STATUS",
        service_status
    )

    write_section(
        file,
        "TOP PROCESSES",
        top_processes
    )


    # ========================================================
    # KDUMP
    # ========================================================

    write_section(
        file,
        "KDUMP SERVICE",
        kdump_service
    )

    write_section(
        file,
        "KDUMP ENABLED",
        kdump_enabled
    )

    write_section(
        file,
        "KDUMP STATUS",
        kdump_status
    )

    write_section(
        file,
        "KDUMP CONFIGURATION",
        kdump_config
    )

    write_section(
        file,
        "KDUMP TEST",
        kdump_test
    )

    write_section(
        file,
        "KDUMP DEFAULT CONFIGURATION",
        kdump_defaults
    )


    # ========================================================
    # CRASHKERNEL
    # ========================================================

    write_section(
        file,
        "CRASHKERNEL CMDLINE",
        crashkernel_cmdline
    )

    write_section(
        file,
        "CRASHKERNEL CONFIGURATION",
        crashkernel_config
    )

    write_section(
        file,
        "GRUB CONFIGURATION",
        grub_config
    )


    # ========================================================
    # KDUMP FILES
    # ========================================================

    write_section(
        file,
        "KDUMP DIRECTORY",
        kdump_directory
    )

    write_section(
        file,
        "KDUMP KERNEL",
        kdump_kernel
    )

    write_section(
        file,
        "KDUMP INITRD",
        kdump_initrd
    )


    # ========================================================
    # VMCORE
    # ========================================================

    write_section(
        file,
        "VMCORE / CRASH FILES",
        vmcore_files
    )

    write_section(
        file,
        "CRASH DIRECTORY",
        crash_directory
    )

    write_section(
        file,
        "CRASH FILES",
        crash_files
    )


    # ========================================================
    # BOOT FILES
    # ========================================================

    write_section(
        file,
        "KERNEL / INITRD FILES",
        kernel_files
    )


    # ========================================================
    # FILTERED RCA EVIDENCE
    # ========================================================

    for category, content in filtered_sections.items():

        write_section(
            file,
            f"FILTERED {category}",
            content
        )


# ============================================================
# FINAL OUTPUT
# ============================================================

print()
print("=" * 70)
print("✓ EVIDENCE COLLECTION COMPLETED")
print("=" * 70)

print()

print(
    f"Server          : {hostname}"
)

print(
    f"Kernel          : {kernel_version}"
)

print(
    f"Evidence File   : {evidence_file}"
)

print(
    f"Raw Log         : {raw_file}"
)

print()

print(
    "Collected:"
)

print(
    "  ✓ System information"
)

print(
    "  ✓ Previous boot journal"
)

print(
    "  ✓ Kernel logs"
)

print(
    "  ✓ OOM / memory"
)

print(
    "  ✓ Hardware / MCE / ECC"
)

print(
    "  ✓ Storage / I/O"
)

print(
    "  ✓ Filesystem"
)

print(
    "  ✓ Watchdog / lockup"
)

print(
    "  ✓ Network"
)

print(
    "  ✓ Systemd failures"
)

print(
    "  ✓ Manual reboot evidence"
)

print(
    "  ✓ Cron / scheduled reboot evidence"
)

print(
    "  ✓ Systemd timers"
)

print(
    "  ✓ Kdump configuration"
)

print(
    "  ✓ Crashkernel configuration"
)

print(
    "  ✓ Kdump kernel/initrd"
)

print(
    "  ✓ VMcore / crash files"
)

print(
    "  ✓ Failed services"
)

print(
    "  ✓ Disk / filesystem state"
)

print()

print(
    "Next step:"
)

print(
    "python3 scripts/analyze_RCA_AI.py"
)

print()
