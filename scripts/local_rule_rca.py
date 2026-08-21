#!/usr/bin/env python3

import os
import re
import glob
from datetime import datetime

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")

EVIDENCE_DIR = os.path.join(
    BASE_DIR,
    "logs",
    "evidence",
)

REPORT_DIR = os.path.join(
    BASE_DIR,
    "reports",
)

os.makedirs(REPORT_DIR, exist_ok=True)

console = Console(highlight=False)


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    """
    Escape Rich markup characters from log content.
    """
    if value is None:
        return ""

    return (
        str(value)
        .replace("[", "\\[")
        .replace("]", "\\]")
    )


def read_latest_evidence():

    files = glob.glob(
        os.path.join(
            EVIDENCE_DIR,
            "ai_evidence_*.txt",
        )
    )

    if not files:

        console.print(
            Panel(
                "[bold red]No evidence file found.[/bold red]\n\n"
                "Run:\n"
                "[cyan]python3 collect_evidence.py[/cyan]",
                title="ERROR",
                border_style="red",
            )
        )

        raise SystemExit(1)

    latest = max(
        files,
        key=os.path.getmtime,
    )

    with open(
        latest,
        "r",
        errors="ignore",
    ) as f:

        content = f.read()

    return latest, content


def get_hostname(evidence):

    match = re.search(
        r"Hostname:\s*(.+)",
        evidence,
        re.IGNORECASE,
    )

    if match:
        return match.group(1).strip()

    return os.uname().nodename


def get_section(evidence, section_name):

    pattern = (
        r"###\s+"
        + re.escape(section_name)
        + r"\s+###"
        r"(.*?)(?=\n###|\Z)"
    )

    match = re.search(
        pattern,
        evidence,
        re.IGNORECASE | re.DOTALL,
    )

    if match:
        return match.group(1).strip()

    return ""


def has_real_event(text, patterns):

    if not text:
        return False

    for pattern in patterns:

        if re.search(
            pattern,
            text,
            re.IGNORECASE,
        ):
            return True

    return False


# ============================================================
# LOAD EVIDENCE
# ============================================================

evidence_file, evidence = read_latest_evidence()

server = get_hostname(evidence)

evidence_size = len(evidence)


# ============================================================
# HEADER
# ============================================================

console.print()

console.print(
    Panel.fit(
        "[bold cyan]LINUX REBOOT INTELLIGENCE CENTER[/bold cyan]\n"
        "[white]Local Rule-Based RCA & Server Health Platform[/white]\n\n"
        "[dim]Evidence → Rules → Timeline → RCA → Health[/dim]",
        border_style="cyan",
        padding=(1, 5),
    )
)

console.print()


# ============================================================
# EVIDENCE
# ============================================================

evidence_table = Table(
    show_header=False,
    box=None,
)

evidence_table.add_column(
    "Field",
    style="bold cyan",
    width=24,
)

evidence_table.add_column(
    "Value",
    overflow="fold",
)

evidence_table.add_row(
    "Status",
    "[bold green]✓ Evidence Loaded[/bold green]",
)

evidence_table.add_row(
    "Evidence File",
    clean(os.path.basename(evidence_file)),
)

evidence_table.add_row(
    "Server",
    clean(server),
)

evidence_table.add_row(
    "Evidence Size",
    f"{evidence_size:,} characters",
)

console.print(
    Panel(
        evidence_table,
        title="EVIDENCE",
        border_style="green",
    )
)

console.print()


# ============================================================
# EXTRACT EVIDENCE SECTIONS
# ============================================================

kernel_section = get_section(
    evidence,
    "KERNEL PANIC / OOPS",
)

oom_section = get_section(
    evidence,
    "OOM / MEMORY",
)

hardware_section = get_section(
    evidence,
    "HARDWARE",
)

storage_section = get_section(
    evidence,
    "STORAGE / I/O",
)

filesystem_section = get_section(
    evidence,
    "FILESYSTEM",
)

watchdog_section = get_section(
    evidence,
    "WATCHDOG / LOCKUP",
)

systemd_section = get_section(
    evidence,
    "SYSTEMD FAILURE",
)

reboot_section = get_section(
    evidence,
    "REBOOT / SHUTDOWN",
)

kdump_service_section = get_section(
    evidence,
    "KDUMP SERVICE",
)

kdump_config_section = get_section(
    evidence,
    "KDUMP CONFIGURATION",
)

kdump_section = (
    kdump_service_section
    + "\n"
    + kdump_config_section
)

crash_section = get_section(
    evidence,
    "CRASH / VMCORE FILES",
)


# ============================================================
# KERNEL PANIC
# ============================================================

kernel_panic = has_real_event(
    kernel_section,
    [
        r"kernel panic\s*[-:]",
        r"kernel panic - not syncing",
        r"not syncing:",
        r"panic: not syncing",
    ],
)


# ============================================================
# KERNEL OOPS
# ============================================================

kernel_oops = has_real_event(
    kernel_section,
    [
        r"\bOops:\s+\d+",
        r"kernel oops",
        r"BUG:\s+unable to handle",
        r"BUG:\s+kernel",
    ],
)


# ============================================================
# OOM
# ============================================================

oom = has_real_event(
    oom_section,
    [
        r"out of memory",
        r"out-of-memory",
        r"oom-killer",
        r"killed process\s+\d+",
        r"oom_reaper",
    ],
)


# ============================================================
# HARDWARE
# ============================================================

hardware = has_real_event(
    hardware_section,
    [
        r"hardware error",
        r"machine check exception",
        r"\bmce:\s",
        r"edac.*error",
        r"ecc.*error",
        r"uncorrected.*error",
    ],
)


# ============================================================
# STORAGE / I/O
# ============================================================

storage = has_real_event(
    storage_section,
    [
        r"I/O error",
        r"I/O failure",
        r"blk_update_request.*error",
        r"buffer I/O error",
        r"nvme.*error",
        r"scsi.*error",
        r"ata.*error",
    ],
)


# ============================================================
# FILESYSTEM
# ============================================================

filesystem = has_real_event(
    filesystem_section,
    [
        r"EXT4-fs error",
        r"XFS.*error",
        r"filesystem error",
        r"remount.*read-only",
        r"read-only filesystem",
    ],
)


# ============================================================
# WATCHDOG / LOCKUP
# ============================================================

watchdog = has_real_event(
    watchdog_section,
    [
        r"soft lockup",
        r"hard lockup",
        r"hung task",
        r"watchdog.*timeout",
        r"rcu.*stall",
    ],
)


# ============================================================
# SYSTEMD FAILURE
# ============================================================

systemd_failure = has_real_event(
    systemd_section,
    [
        r"failed to start .*service",
        r"dependency failed",
        r"start job failed",
        r"failed with result",
    ],
)


# ============================================================
# MANUAL / USER-INITIATED REBOOT
# ============================================================

manual_reboot_lines = []

manual_reboot_pattern = re.compile(
    r"""
    (?:sudo|audit).*COMMAND\s*=\s*
    (?:
        /usr/sbin/reboot\b
        |
        /sbin/reboot\b
        |
        /usr/bin/reboot\b
        |
        /usr/sbin/shutdown\s+(?:-r|--reboot)(?:\s+now)?\b
        |
        /sbin/shutdown\s+(?:-r|--reboot)(?:\s+now)?\b
        |
        /usr/bin/shutdown\s+(?:-r|--reboot)(?:\s+now)?\b
        |
        /usr/bin/systemctl\s+reboot\b
        |
        /bin/systemctl\s+reboot\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

for line in evidence.splitlines():

    if manual_reboot_pattern.search(line):

        manual_reboot_lines.append(
            line.strip()
        )


manual_reboot = bool(
    manual_reboot_lines
)


# ============================================================
# CRON REBOOT
# ============================================================

cron_reboot_lines = []

cron_reboot_pattern = re.compile(
    r"""
    CRON.*(?:COMMAND|CMD).*
    (?:
        /usr/sbin/reboot\b
        |
        /sbin/reboot\b
        |
        /usr/bin/reboot\b
        |
        /usr/sbin/shutdown\s+(?:-r|--reboot)
        |
        /sbin/shutdown\s+(?:-r|--reboot)
        |
        /usr/bin/shutdown\s+(?:-r|--reboot)
        |
        /usr/bin/systemctl\s+reboot\b
        |
        /bin/systemctl\s+reboot\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

for line in evidence.splitlines():

    if cron_reboot_pattern.search(line):

        cron_reboot_lines.append(
            line.strip()
        )


cron_reboot = bool(
    cron_reboot_lines
)


# ============================================================
# KDUMP
# ============================================================

kdump_ready = has_real_event(
    kdump_section,
    [
        r"current state:\s*ready to kdump",
        r"ready to kdump",
        r"loaded kdump kernel",
    ],
)

kdump_not_ready = has_real_event(
    kdump_section,
    [
        r"current state:\s*not ready to kdump",
        r"not ready to kdump",
        r"no crashkernel=.*parameter",
    ],
)

kdump_not_configured = has_real_event(
    kdump_section,
    [
        r"kdump-config:\s*command not found",
        r"unit kdump-tools\.service could not be found",
        r"not configured",
    ],
)


if kdump_ready:

    kdump_status = "READY"

elif kdump_not_ready:

    kdump_status = "NOT READY"

elif kdump_not_configured:

    kdump_status = "NOT CONFIGURED"

else:

    kdump_status = "UNKNOWN"


# ============================================================
# VMCORE
# ============================================================

vmcore_status = "NOT AVAILABLE"

vmcore_real_patterns = [
    r"^\s*.*\/vmcore(?:\s|$)",
    r"^\s*.*vmcore-dmesg(?:\s|$)",
    r"^\s*.*vmcore\.[0-9]+",
]

for pattern in vmcore_real_patterns:

    if re.search(
        pattern,
        crash_section,
        re.IGNORECASE | re.MULTILINE,
    ):

        vmcore_status = "AVAILABLE"
        break


# ============================================================
# REBOOT TIMELINE
# ============================================================

timeline = []

timeline_pattern = re.compile(
    r"""
    (?:
        COMMAND\s*=.*
        (?:
            reboot\b
            |
            shutdown\s+(?:-r|--reboot)
            |
            systemctl\s+reboot\b
        )
        |
        System will reboot now
        |
        System is rebooting
        |
        systemd-reboot\.service
        |
        Reached target reboot\.target
        |
        Reached target shutdown\.target
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

for line in evidence.splitlines():

    if timeline_pattern.search(line):

        timeline.append(
            line.strip()
        )


timeline = list(
    dict.fromkeys(timeline)
)

timeline = timeline[-15:]


# ============================================================
# RCA DECISION
# ============================================================

root_cause = "Unknown"

cause = (
    "The exact cause of the reboot could not be "
    "determined from the available evidence."
)

confidence = "LOW"

reboot_type = "UNKNOWN"

recommended_action = (
    "Review the raw previous-boot logs and correlate "
    "the reboot with the approved change or maintenance "
    "window."
)


# ============================================================
# CRASH EVENTS
# ============================================================

crash_events = (
    kernel_panic
    or kernel_oops
    or oom
    or hardware
    or storage
    or filesystem
    or watchdog
)


# ============================================================
# MANUAL / PLANNED REBOOT
# ============================================================

if manual_reboot and not crash_events:

    root_cause = "Manual / Planned Reboot"

    if manual_reboot_lines:

        cause = (
            "The server was manually/planned rebooted by a "
            "user through a user-initiated reboot command.\n\n"
            "Evidence:\n"
            + manual_reboot_lines[0]
        )

    else:

        cause = (
            "The server was manually/planned rebooted by "
            "a user through a user-initiated reboot command."
        )

    confidence = "HIGH"

    reboot_type = "MANUAL"

    recommended_action = (
        "Verify the reboot against the approved change "
        "or maintenance window."
    )


# ============================================================
# CRON REBOOT
# ============================================================

elif cron_reboot and not crash_events:

    root_cause = "Cron Scheduled Reboot"

    if cron_reboot_lines:

        cause = (
            "The server reboot was initiated by a scheduled "
            "cron command.\n\n"
            "Evidence:\n"
            + cron_reboot_lines[0]
        )

    else:

        cause = (
            "The server reboot was initiated by a scheduled "
            "cron command executing a reboot operation."
        )

    confidence = "HIGH"

    reboot_type = "CRON"

    recommended_action = (
        "Review the relevant crontab and verify the "
        "scheduled reboot against an approved change."
    )


# ============================================================
# KERNEL PANIC
# ============================================================

elif kernel_panic:

    root_cause = "Kernel Panic"

    cause = (
        "The server rebooted following a kernel panic "
        "detected in the previous-boot kernel logs."
    )

    confidence = "HIGH"

    reboot_type = "KERNEL"

    recommended_action = (
        "Review kernel panic messages and verify "
        "kdump/VMcore availability."
    )


# ============================================================
# HARDWARE
# ============================================================

elif hardware:

    root_cause = "Hardware Error"

    cause = (
        "Hardware-related errors were detected before "
        "the reboot, including MCE/ECC/EDAC evidence."
    )

    confidence = "HIGH"

    reboot_type = "HARDWARE"

    recommended_action = (
        "Review hardware error logs and coordinate "
        "with the hardware or cloud platform team."
    )


# ============================================================
# OOM
# ============================================================

elif oom:

    root_cause = "OOM / Memory Exhaustion"

    cause = (
        "The Linux kernel reported an out-of-memory "
        "condition before the reboot."
    )

    confidence = "HIGH"

    reboot_type = "OOM"

    recommended_action = (
        "Review memory utilization and identify the "
        "process affected by the OOM killer."
    )


# ============================================================
# STORAGE
# ============================================================

elif storage:

    root_cause = "Storage / I/O Error"

    cause = (
        "Storage or I/O errors were detected in the "
        "previous-boot logs."
    )

    confidence = "HIGH"

    reboot_type = "STORAGE"

    recommended_action = (
        "Review disk, NVMe/SCSI and filesystem I/O "
        "errors and coordinate with the storage team."
    )


# ============================================================
# FILESYSTEM
# ============================================================

elif filesystem:

    root_cause = "Filesystem Error"

    cause = (
        "Filesystem errors were detected before "
        "the reboot."
    )

    confidence = "HIGH"

    reboot_type = "FILESYSTEM"

    recommended_action = (
        "Review filesystem errors and verify "
        "filesystem health."
    )


# ============================================================
# WATCHDOG
# ============================================================

elif watchdog:

    root_cause = "Watchdog / Lockup"

    cause = (
        "Watchdog, lockup or hung-task evidence was "
        "detected before the reboot."
    )

    confidence = "HIGH"

    reboot_type = "WATCHDOG"

    recommended_action = (
        "Review watchdog and kernel lockup messages "
        "and verify kdump configuration."
    )


# ============================================================
# SYSTEMD
# ============================================================

elif systemd_failure:

    root_cause = "Systemd / Service Failure"

    cause = (
        "Systemd service or dependency failures were "
        "detected before the reboot."
    )

    confidence = "MEDIUM"

    reboot_type = "SYSTEMD"

    recommended_action = (
        "Review failed systemd units and correlate "
        "their timestamps with the reboot."
    )


# ============================================================
# DETECTED EVENTS
# ============================================================

detected_events = []

if kernel_panic:

    detected_events.append(
        ("Kernel Panic", "HIGH")
    )

if kernel_oops:

    detected_events.append(
        ("Kernel OOPS", "HIGH")
    )

if oom:

    detected_events.append(
        ("OOM / Memory", "HIGH")
    )

if hardware:

    detected_events.append(
        ("Hardware Error", "HIGH")
    )

if storage:

    detected_events.append(
        ("Storage / I/O", "HIGH")
    )

if filesystem:

    detected_events.append(
        ("Filesystem Error", "HIGH")
    )

if watchdog:

    detected_events.append(
        ("Watchdog / Lockup", "HIGH")
    )

if systemd_failure:

    detected_events.append(
        ("Systemd Failure", "MEDIUM")
    )

if cron_reboot:

    detected_events.append(
        ("Cron Scheduled Reboot", "HIGH")
    )

if manual_reboot:

    detected_events.append(
        ("Manual / Planned Reboot", "HIGH")
    )


# ============================================================
# HEALTH SCORE
# ============================================================

score = 100

health_issues = []


def deduct(points, description):

    global score

    score -= points

    health_issues.append(
        (
            description,
            points,
        )
    )


if kernel_panic:

    deduct(
        30,
        "Kernel panic detected",
    )


if kernel_oops:

    deduct(
        25,
        "Kernel OOPS detected",
    )


if oom:

    deduct(
        20,
        "OOM / memory exhaustion detected",
    )


if hardware:

    deduct(
        30,
        "Hardware / MCE / ECC error detected",
    )


if storage:

    deduct(
        25,
        "Storage / I/O error detected",
    )


if filesystem:

    deduct(
        20,
        "Filesystem error detected",
    )


if watchdog:

    deduct(
        25,
        "Watchdog / lockup detected",
    )


if systemd_failure:

    deduct(
        15,
        "Systemd failure detected",
    )


if manual_reboot or cron_reboot:

    deduct(
        5,
        "Recent reboot detected",
    )


if kdump_status == "NOT READY":

    deduct(
        5,
        "Kdump not ready",
    )


if kernel_panic and vmcore_status != "AVAILABLE":

    deduct(
        5,
        "Kernel panic occurred but VMcore unavailable",
    )


score = max(
    0,
    min(
        100,
        score,
    ),
)


# ============================================================
# HEALTH STATUS
# ============================================================

if score >= 90:

    health_status = "HEALTHY"
    health_color = "green"

elif score >= 75:

    health_status = "GOOD"
    health_color = "green"

elif score >= 50:

    health_status = "WARNING"
    health_color = "yellow"

elif score >= 25:

    health_status = "CRITICAL"
    health_color = "dark_orange"

else:

    health_status = "SEVERE"
    health_color = "red"


# ============================================================
# ANALYSIS COMPLETE
# ============================================================

console.print(
    Panel(
        "[bold green]✓ Local rule analysis completed[/bold green]\n\n"
        "Analysis Mode: [cyan]LOCAL / NO AI / NO EXTERNAL API[/cyan]\n"
        "Rules Evaluated: [bold]15[/bold]\n"
        f"RCA Confidence: [bold]{clean(confidence)}[/bold]",
        title="ANALYSIS COMPLETE",
        border_style="green",
    )
)

console.print()


# ============================================================
# INCIDENT SUMMARY
# ============================================================

summary = Table(
    show_header=False,
    box=None,
)

summary.add_column(
    "Field",
    style="bold cyan",
    width=25,
)

summary.add_column(
    "Result",
    overflow="fold",
)

summary.add_row(
    "Server",
    clean(server),
)

summary.add_row(
    "Probable Root Cause",
    clean(root_cause),
)

summary.add_row(
    "Cause of Reboot",
    clean(cause),
)

summary.add_row(
    "Reboot Type",
    reboot_type,
)

summary.add_row(
    "Confidence",
    confidence,
)

summary.add_row(
    "Evidence Size",
    f"{evidence_size:,} characters",
)

summary.add_row(
    "Analysis Mode",
    "LOCAL RULE ENGINE",
)

console.print(
    Panel(
        summary,
        title="INCIDENT SUMMARY",
        border_style="blue",
    )
)

console.print()


# ============================================================
# HEALTH SCORE
# ============================================================

bar_length = 40

filled = int(
    bar_length * score / 100
)

empty = bar_length - filled

bar = (
    "█" * filled
    +
    "░" * empty
)

health_group = Group(
    Text(
        f"Health Score: {score} / 100",
        style="bold white",
    ),
    Text(""),
    Text(
        bar,
        style=health_color,
    ),
    Text(""),
    Text(
        f"● {health_status}",
        style=f"bold {health_color}",
    ),
)

console.print(
    Panel(
        health_group,
        title="SERVER HEALTH",
        border_style=health_color,
        padding=(1, 4),
    )
)

console.print()


# ============================================================
# ROOT CAUSE MATRIX
# ============================================================

matrix = Table(
    title="ROOT CAUSE MATRIX",
    show_header=True,
    header_style="bold cyan",
    border_style="cyan",
)

matrix.add_column(
    "CHECK",
)

matrix.add_column(
    "STATUS",
    justify="center",
)

matrix_checks = [
    ("Kernel Panic", kernel_panic),
    ("Kernel OOPS", kernel_oops),
    ("OOM", oom),
    ("Hardware Error", hardware),
    ("Storage / I/O", storage),
    ("Filesystem", filesystem),
    ("Watchdog / Lockup", watchdog),
    ("Systemd Failure", systemd_failure),
    ("Manual Reboot", manual_reboot),
    ("Cron Reboot", cron_reboot),
]


for name, detected in matrix_checks:

    if detected:

        status = (
            "[bold red]● DETECTED[/bold red]"
        )

    else:

        status = (
            "[green]✓ NOT DETECTED[/green]"
        )

    matrix.add_row(
        name,
        status,
    )


# Kdump

if kdump_status == "READY":

    matrix.add_row(
        "Kdump",
        "[bold green]✓ READY[/bold green]",
    )

elif kdump_status == "NOT READY":

    matrix.add_row(
        "Kdump",
        "[yellow]⚠ NOT READY[/yellow]",
    )

elif kdump_status == "NOT CONFIGURED":

    matrix.add_row(
        "Kdump",
        "[yellow]⚠ NOT CONFIGURED[/yellow]",
    )

else:

    matrix.add_row(
        "Kdump",
        "[yellow]? UNKNOWN[/yellow]",
    )


# VMcore

if vmcore_status == "AVAILABLE":

    matrix.add_row(
        "VMcore",
        "[bold green]✓ AVAILABLE[/bold green]",
    )

else:

    matrix.add_row(
        "VMcore",
        "[green]✓ NOT AVAILABLE[/green]",
    )


console.print(matrix)

console.print()


# ============================================================
# REBOOT TIMELINE
# ============================================================

timeline_table = Table(
    title="REBOOT TIMELINE",
    show_header=True,
    header_style="bold cyan",
    border_style="blue",
)

timeline_table.add_column(
    "TIME",
    width=10,
)

timeline_table.add_column(
    "EVENT",
    overflow="fold",
)

timeline_table.add_column(
    "TYPE",
    width=12,
    justify="center",
)


for line in timeline:

    time_match = re.search(
        r"\b(\d{2}:\d{2}:\d{2})\b",
        line,
    )

    event_time = (
        time_match.group(1)
        if time_match
        else "--:--:--"
    )


    # --------------------------------------------------------
    # MANUAL
    # --------------------------------------------------------

    if re.search(
        r"""
        COMMAND\s*=.*
        (?:
            reboot\b
            |
            shutdown\s+(?:-r|--reboot)
            |
            systemctl\s+reboot\b
        )
        """,
        line,
        re.IGNORECASE | re.VERBOSE,
    ):

        event_type = (
            "[bold yellow]MANUAL[/bold yellow]"
        )


    # --------------------------------------------------------
    # CRON
    # --------------------------------------------------------

    elif re.search(
        r"CRON",
        line,
        re.IGNORECASE,
    ):

        event_type = (
            "[bold magenta]CRON[/bold magenta]"
        )


    # --------------------------------------------------------
    # SYSTEMD
    # --------------------------------------------------------

    else:

        event_type = (
            "[cyan]SYSTEMD[/cyan]"
        )


    timeline_table.add_row(
        clean(event_time),
        clean(line),
        event_type,
    )


if timeline:

    console.print(
        timeline_table
    )

else:

    console.print(
        Panel(
            "[yellow]No reboot timeline events found.[/yellow]",
            title="REBOOT TIMELINE",
            border_style="yellow",
        )
    )


console.print()


# ============================================================
# DETECTED EVENTS
# ============================================================

if detected_events:

    events_table = Table(
        title="DETECTED EVENTS",
        show_header=True,
        header_style="bold cyan",
        border_style="yellow",
    )

    events_table.add_column(
        "Priority",
        justify="center",
        width=10,
    )

    events_table.add_column(
        "Condition",
    )

    events_table.add_column(
        "Confidence",
        justify="center",
    )


    for index, (
        event,
        event_confidence,
    ) in enumerate(
        detected_events,
        start=1,
    ):

        events_table.add_row(
            str(index),
            clean(event),
            event_confidence,
        )


    console.print(
        events_table
    )

    console.print()


# ============================================================
# HEALTH IMPACT
# ============================================================

if health_issues:

    impact = Table(
        title="HEALTH IMPACT",
        show_header=True,
        header_style="bold cyan",
        border_style="red",
    )

    impact.add_column(
        "Issue",
    )

    impact.add_column(
        "Impact",
        justify="right",
    )


    for issue, points in health_issues:

        impact.add_row(
            clean(issue),
            f"[bold red]-{points}[/bold red]",
        )


    console.print(
        impact
    )

else:

    console.print(
        Panel(
            "[bold green]✓ No health-impacting events detected.[/bold green]",
            title="HEALTH IMPACT",
            border_style="green",
        )
    )


console.print()


# ============================================================
# FINAL RCA
# ============================================================

console.print(
    Panel(
        clean(cause),
        title="FINAL RCA",
        border_style="magenta",
        padding=(1, 2),
    )
)

console.print()


# ============================================================
# RECOMMENDED ACTION
# ============================================================

console.print(
    Panel(
        clean(recommended_action),
        title="RECOMMENDED ACTION",
        border_style="yellow",
        padding=(1, 2),
    )
)

console.print()


# ============================================================
# RULE ENGINE DETAILS
# ============================================================

rules_table = Table(
    title="RULE ENGINE DETAILS",
    show_header=True,
    header_style="bold cyan",
    border_style="cyan",
)

rules_table.add_column(
    "Rule",
    width=30,
)

rules_table.add_column(
    "Detection Logic",
    overflow="fold",
)

rules_table.add_column(
    "Result",
    width=18,
    justify="center",
)


rule_details = [

    (
        "Manual Reboot",
        "sudo/audit reboot, shutdown -r, or systemctl reboot",
        manual_reboot,
    ),

    (
        "Cron Reboot",
        "CRON command explicitly executes reboot/shutdown -r",
        cron_reboot,
    ),

    (
        "Kernel Panic",
        "Actual panic/not-syncing event",
        kernel_panic,
    ),

    (
        "Kernel OOPS",
        "Actual OOPS/BUG event",
        kernel_oops,
    ),

    (
        "OOM",
        "OOM killer/out-of-memory event",
        oom,
    ),

    (
        "Hardware",
        "Actual MCE/ECC/EDAC error",
        hardware,
    ),

    (
        "Storage",
        "Actual I/O/NVMe/SCSI error",
        storage,
    ),

    (
        "Filesystem",
        "Actual EXT4/XFS/read-only error",
        filesystem,
    ),

    (
        "Watchdog",
        "Actual lockup/hung-task event",
        watchdog,
    ),

    (
        "Systemd",
        "Actual service/dependency failure",
        systemd_failure,
    ),
]


for (
    name,
    logic,
    result,
) in rule_details:

    result_text = (
        "[bold red]DETECTED[/bold red]"
        if result
        else "[green]CLEAR[/green]"
    )

    rules_table.add_row(
        clean(name),
        clean(logic),
        result_text,
    )


console.print(
    rules_table
)

console.print()


# ============================================================
# GENERATE REPORT
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

report_file = os.path.join(
    REPORT_DIR,
    f"RCA_RULE_{timestamp}.txt",
)


with open(
    report_file,
    "w",
) as report:

    report.write(
        "LINUX REBOOT LOCAL RULE ENGINE RCA REPORT\n"
    )

    report.write(
        "=" * 80 + "\n\n"
    )

    report.write(
        f"Server: {server}\n"
    )

    report.write(
        f"Evidence: {os.path.basename(evidence_file)}\n"
    )

    report.write(
        f"Analysis Time: {datetime.now()}\n"
    )

    report.write(
        "Analysis Mode: LOCAL RULE ENGINE\n"
    )

    report.write(
        f"Confidence: {confidence}\n"
    )

    report.write(
        f"Health Score: {score}/100\n"
    )

    report.write(
        f"Health Status: {health_status}\n\n"
    )


    report.write(
        "PROBABLE ROOT CAUSE\n"
        + "-" * 80
        + "\n"
        + root_cause
        + "\n\n"
    )


    report.write(
        "CAUSE OF REBOOT\n"
        + "-" * 80
        + "\n"
        + cause
        + "\n\n"
    )


    report.write(
        "REBOOT TYPE\n"
        + "-" * 80
        + "\n"
        + reboot_type
        + "\n\n"
    )


    report.write(
        "ROOT CAUSE MATRIX\n"
        + "-" * 80
        + "\n"
    )


    for (
        name,
        detected,
    ) in matrix_checks:

        report.write(
            f"{name}: "
            f"{'DETECTED' if detected else 'NOT DETECTED'}\n"
        )


    report.write(
        f"Kdump: {kdump_status}\n"
    )

    report.write(
        f"VMcore: {vmcore_status}\n\n"
    )


    report.write(
        "HEALTH IMPACT\n"
        + "-" * 80
        + "\n"
    )


    if health_issues:

        for issue, points in health_issues:

            report.write(
                f"{issue}: -{points}\n"
            )

    else:

        report.write(
            "No health-impacting events detected.\n"
        )


    report.write(
        "\nREBOOT TIMELINE\n"
        + "-" * 80
        + "\n"
    )


    if timeline:

        for line in timeline:

            report.write(
                line + "\n"
            )

    else:

        report.write(
            "No reboot timeline events found.\n"
        )


    report.write(
        "\nRECOMMENDED ACTION\n"
        + "-" * 80
        + "\n"
        + recommended_action
        + "\n"
    )


# ============================================================
# REPORT
# ============================================================

console.print(
    Panel(
        "[bold green]✓ RCA REPORT GENERATED[/bold green]\n\n"
        f"Report: {clean(report_file)}\n"
        f"Evidence: {clean(evidence_file)}\n\n"
        "[cyan]Engine:[/cyan] Local Rule Engine\n"
        "[cyan]AI:[/cyan] Disabled\n"
        "[cyan]External API:[/cyan] None\n"
        "[cyan]Health Score:[/cyan] "
        f"{score}/100\n"
        "[cyan]Confidence:[/cyan] "
        f"{clean(confidence)}",
        title="REPORT",
        border_style="green",
        padding=(1, 2),
    )
)

console.print()

console.print(
    Panel.fit(
        "[bold cyan]LINUX REBOOT INTELLIGENCE CENTER[/bold cyan]"
        "  |  Rule Engine v6.0  |  LOCAL / NO AI / NO API",
        border_style="cyan",
    )
)

console.print()
