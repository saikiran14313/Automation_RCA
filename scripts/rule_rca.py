#!/usr/bin/env python3

import os
import re
from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")
EVIDENCE_DIR = os.path.join(BASE_DIR, "logs", "evidence")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(REPORT_DIR, exist_ok=True)


# ============================================================
# HEADER
# ============================================================

console.clear()

console.print(
    Panel.fit(
        "[bold cyan]LINUX REBOOT INTELLIGENCE CENTER[/bold cyan]\n"
        "[white]Automated RCA & Server Health Platform[/white]\n"
        "[dim]Evidence → Timeline → Correlation → RCA → Health[/dim]",
        border_style="cyan",
        padding=(1, 5),
    )
)

console.print()


# ============================================================
# FIND LATEST EVIDENCE
# ============================================================

files = [
    os.path.join(EVIDENCE_DIR, f)
    for f in os.listdir(EVIDENCE_DIR)
    if f.startswith("ai_evidence_") and f.endswith(".txt")
]

if not files:
    console.print(
        Panel(
            "[bold red]No evidence file found.[/bold red]\n\n"
            "Run collect_evidence.py first.",
            title="ERROR",
            border_style="red",
        )
    )
    raise SystemExit(1)

evidence_file = max(files, key=os.path.getmtime)

with open(evidence_file, "r", errors="ignore") as f:
    evidence = f.read()

server = os.uname().nodename
evidence_size = len(evidence)
analysis_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# LOADING
# ============================================================

with Progress(
    SpinnerColumn(),
    TextColumn("[cyan]Analyzing Linux evidence and reboot timeline..."),
    console=console,
) as progress:

    task = progress.add_task("analysis", total=None)

    evidence_lines = evidence.splitlines()

    progress.update(task, completed=True)


# ============================================================
# SECTION EXTRACTION
# ============================================================

def get_section(start_marker, end_markers=None):

    lines = evidence.splitlines()

    start = None

    for i, line in enumerate(lines):

        if line.strip().lower() == start_marker.lower():
            start = i + 1
            break

    if start is None:
        return []

    end = len(lines)

    if end_markers:

        for i in range(start, len(lines)):

            if lines[i].strip().lower() in [
                x.lower() for x in end_markers
            ]:
                end = i
                break

    return lines[start:end]


oom_section = get_section(
    "### OOM / MEMORY ###",
    [
        "### KERNEL PANIC / OOPS ###",
        "### WATCHDOG / LOCKUP ###",
        "### REBOOT / SHUTDOWN ###",
    ],
)

panic_section = get_section(
    "### KERNEL PANIC / OOPS ###",
    [
        "### WATCHDOG / LOCKUP ###",
        "### REBOOT / SHUTDOWN ###",
    ],
)

watchdog_section = get_section(
    "### WATCHDOG / LOCKUP ###",
    [
        "### REBOOT / SHUTDOWN ###",
    ],
)

reboot_section = get_section(
    "### REBOOT / SHUTDOWN ###",
    [],
)


# ============================================================
# TIMESTAMP PARSER
# ============================================================

timestamp_regex = re.compile(
    r"([A-Z][a-z]{2}\s+\d{1,2}\s+"
    r"\d{2}:\d{2}:\d{2})"
)


def extract_timestamps(lines):

    results = []

    year = datetime.now().year

    for line in lines:

        match = timestamp_regex.search(line)

        if not match:
            continue

        value = match.group(1)

        try:
            dt = datetime.strptime(
                f"{year} {value}",
                "%Y %b %d %H:%M:%S"
            )

            results.append(
                (dt, line)
            )

        except ValueError:
            pass

    return results


all_timestamped_events = extract_timestamps(
    evidence_lines
)


# ============================================================
# FIND ACTUAL REBOOT EVENTS
# ============================================================

reboot_events = []

for dt, line in all_timestamped_events:

    lower = line.lower()

    # Actual user reboot command
    if (
        "command=/usr/sbin/reboot" in lower
        or
        "command=/sbin/reboot" in lower
        or
        "command=/usr/bin/systemctl reboot" in lower
    ):

        reboot_events.append(
            {
                "time": dt,
                "type": "MANUAL",
                "line": line,
            }
        )

    # Cron actually executing reboot/shutdown
    elif (
        ("cron" in lower or "crond" in lower)
        and
        re.search(
            r"\b(reboot|shutdown|systemctl\s+reboot)\b",
            lower
        )
        and
        "@reboot" not in lower
    ):

        reboot_events.append(
            {
                "time": dt,
                "type": "CRON",
                "line": line,
            }
        )


# ============================================================
# SYSTEMD REBOOT CONFIRMATION
# ============================================================

systemd_reboot_events = []

for dt, line in all_timestamped_events:

    lower = line.lower()

    if (
        "systemd-logind" in lower
        and
        (
            "system will reboot now" in lower
            or
            "system is rebooting" in lower
        )
    ):

        systemd_reboot_events.append(
            {
                "time": dt,
                "line": line,
            }
        )


# ============================================================
# REBOOT HISTORY
# ============================================================

history_reboots = []

for line in evidence_lines:

    # Example:
    # reboot system boot ... Thu Aug 20 15:02
    match = re.search(
        r"^reboot\s+system boot.*"
        r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"([A-Z][a-z]{2})\s+"
        r"(\d{1,2})\s+"
        r"(\d{2}:\d{2})",
        line,
        re.IGNORECASE,
    )

    if match:

        month = match.group(2)
        day = match.group(3)
        clock = match.group(4)

        try:

            dt = datetime.strptime(
                f"{datetime.now().year} "
                f"{month} {day} {clock}",
                "%Y %b %d %H:%M",
            )

            history_reboots.append(dt)

        except ValueError:
            pass


history_reboots.sort()


# ============================================================
# RECURRING REBOOT DETECTION
# ============================================================

recurring_reboot = False
reboot_intervals = []

if len(history_reboots) >= 3:

    for i in range(1, len(history_reboots)):

        previous = history_reboots[i - 1]
        current = history_reboots[i]

        minutes = (
            current - previous
        ).total_seconds() / 60

        reboot_intervals.append(
            minutes
        )

    # Detect repeated short reboot intervals.
    short_intervals = [
        x for x in reboot_intervals
        if 0 < x <= 10
    ]

    if len(short_intervals) >= 2:

        recurring_reboot = True


# ============================================================
# ROOT CAUSE CHECKS
# ============================================================

checks = {
    "Kernel Panic": "Not detected",
    "Kernel OOPS": "Not detected",
    "OOM": "Not detected",
    "Hardware Error": "Not detected",
    "Storage / I/O": "Not detected",
    "Filesystem": "Not detected",
    "Watchdog / Lockup": "Not detected",
    "Systemd Failure": "Not detected",
    "Cron Reboot": "Not detected",
    "Manual Reboot": "Not detected",
    "Recurring Reboot": (
        "Detected" if recurring_reboot
        else "Not detected"
    ),
    "Kdump": "Unknown",
    "VMcore": "Not available",
}


# ============================================================
# ACTUAL KERNEL PANIC
# IMPORTANT:
# Do NOT match "panic=-1"
# ============================================================

for line in panic_section:

    lower = line.lower()

    if (
        "panic - not syncing" in lower
        or
        "kernel panic" in lower
        or
        re.search(
            r"\bpanic:\s",
            lower
        )
    ):

        checks["Kernel Panic"] = "Detected"
        break


# ============================================================
# KERNEL OOPS
# ============================================================

for line in panic_section:

    lower = line.lower()

    if (
        re.search(
            r"\boops:",
            lower
        )
        or
        "kernel oops" in lower
    ):

        checks["Kernel OOPS"] = "Detected"
        break


# ============================================================
# OOM
# ============================================================

for line in oom_section:

    lower = line.lower()

    if (
        "out of memory" in lower
        or
        "oom-killer" in lower
        or
        "oom_reaper" in lower
        or
        "killed process" in lower
    ):

        checks["OOM"] = "Detected"
        break


# ============================================================
# HARDWARE
# ============================================================

for line in evidence_lines:

    lower = line.lower()

    if (
        "machine check error" in lower
        or
        "mce error" in lower
        or
        "hardware error" in lower
        or
        "ecc error" in lower
        or
        "edac.*error" in lower
    ):

        checks["Hardware Error"] = "Detected"
        break


# ============================================================
# STORAGE
# ============================================================

for line in evidence_lines:

    lower = line.lower()

    if (
        "i/o error" in lower
        or
        "buffer i/o error" in lower
        or
        "blk_update_request" in lower
        or
        "scsi error" in lower
        or
        "medium error" in lower
    ):

        checks["Storage / I/O"] = "Detected"
        break


# ============================================================
# FILESYSTEM
# ============================================================

for line in evidence_lines:

    lower = line.lower()

    if (
        re.search(
            r"\b(ext4|xfs).*\berror\b",
            lower
        )
        or
        "read-only filesystem" in lower
        or
        "filesystem error" in lower
    ):

        checks["Filesystem"] = "Detected"
        break


# ============================================================
# WATCHDOG
# IMPORTANT:
# "NMI watchdog permanently disabled"
# is NOT a lockup.
# ============================================================

for line in watchdog_section:

    lower = line.lower()

    if (
        "soft lockup" in lower
        or
        "hard lockup" in lower
        or
        "watchdog timeout" in lower
        or
        "watchdog: BUG" in lower
        or
        "hung task" in lower
    ):

        checks["Watchdog / Lockup"] = "Detected"
        break


# ============================================================
# SYSTEMD FAILURE
# ============================================================

for line in evidence_lines:

    lower = line.lower()

    if (
        "failed to start" in lower
        or
        "dependency failed" in lower
    ):

        checks["Systemd Failure"] = "Detected"
        break


# ============================================================
# REBOOT SOURCE
# ============================================================

manual_reboot = any(
    x["type"] == "MANUAL"
    for x in reboot_events
)

cron_reboot = any(
    x["type"] == "CRON"
    for x in reboot_events
)

if manual_reboot:

    checks["Manual Reboot"] = "Detected"

elif cron_reboot:

    checks["Cron Reboot"] = "Detected"


# ============================================================
# KDUMP
# ============================================================

if re.search(
    r"kdump.*not configured|"
    r"kdump.*disabled|"
    r"kdump.*inactive",
    evidence,
    re.IGNORECASE,
):

    checks["Kdump"] = "Not configured"

elif re.search(
    r"kdump.*active|"
    r"kdump.*running",
    evidence,
    re.IGNORECASE,
):

    checks["Kdump"] = "Configured"


# ============================================================
# VMCORE
# ============================================================

if re.search(
    r"/vmcore\b|vmcore-dmesg",
    evidence,
    re.IGNORECASE,
):

    checks["VMcore"] = "Available"


# ============================================================
# FIND LATEST ACTUAL REBOOT
# ============================================================

latest_reboot = None

if reboot_events:

    latest_reboot = max(
        reboot_events,
        key=lambda x: x["time"]
    )


# ============================================================
# RCA PRIORITY
# ============================================================

# Failure events get priority over reboot mechanism,
# BUT only if they are actual events.

failure_candidates = []

if checks["Kernel Panic"] == "Detected":
    failure_candidates.append(
        ("Kernel Panic", 1)
    )

if checks["Kernel OOPS"] == "Detected":
    failure_candidates.append(
        ("Kernel OOPS", 2)
    )

if checks["OOM"] == "Detected":
    failure_candidates.append(
        ("OOM / Memory Exhaustion", 3)
    )

if checks["Hardware Error"] == "Detected":
    failure_candidates.append(
        ("Hardware / MCE / ECC Error", 4)
    )

if checks["Storage / I/O"] == "Detected":
    failure_candidates.append(
        ("Storage / I/O Error", 5)
    )

if checks["Filesystem"] == "Detected":
    failure_candidates.append(
        ("Filesystem Error", 6)
    )

if checks["Watchdog / Lockup"] == "Detected":
    failure_candidates.append(
        ("Watchdog / System Lockup", 7)
    )


# ============================================================
# ROOT CAUSE
# ============================================================

if failure_candidates:

    failure_candidates.sort(
        key=lambda x: x[1]
    )

    root_cause = failure_candidates[0][0]
    confidence = "HIGH"

elif manual_reboot:

    root_cause = "Manual / Planned Reboot"
    confidence = "HIGH"

elif cron_reboot:

    root_cause = "Scheduled Cron Reboot"
    confidence = "HIGH"

else:

    root_cause = "Unknown"
    confidence = "UNKNOWN"


# ============================================================
# CAUSE SENTENCE
# ============================================================

if root_cause == "Manual / Planned Reboot":

    if latest_reboot:

        reboot_time = latest_reboot["time"].strftime(
            "%H:%M:%S"
        )

        cause_of_reboot = (
            f"The server was manually rebooted by the "
            f"ubuntu user using /usr/sbin/reboot at "
            f"{reboot_time}."
        )

    else:

        cause_of_reboot = (
            "The server was manually rebooted using "
            "a user-issued reboot command."
        )


elif root_cause == "Scheduled Cron Reboot":

    cause_of_reboot = (
        "The server was rebooted by an automated "
        "cron-scheduled reboot command."
    )


elif root_cause == "Kernel Panic":

    cause_of_reboot = (
        "The server rebooted following an actual "
        "kernel panic event detected before the reboot."
    )


elif root_cause == "Kernel OOPS":

    cause_of_reboot = (
        "The server rebooted following a kernel OOPS "
        "event detected before the reboot."
    )


elif root_cause == "OOM / Memory Exhaustion":

    cause_of_reboot = (
        "The server rebooted following memory exhaustion "
        "and an OOM event detected before the reboot."
    )


elif root_cause == "Hardware / MCE / ECC Error":

    cause_of_reboot = (
        "The server rebooted after a hardware or "
        "MCE/ECC error was detected before the reboot."
    )


elif root_cause == "Storage / I/O Error":

    cause_of_reboot = (
        "The server rebooted following storage or "
        "I/O errors detected before the reboot."
    )


elif root_cause == "Filesystem Error":

    cause_of_reboot = (
        "The server rebooted following filesystem "
        "errors detected before the reboot."
    )


elif root_cause == "Watchdog / System Lockup":

    cause_of_reboot = (
        "The server rebooted following watchdog or "
        "system lockup activity detected before the reboot."
    )


else:

    cause_of_reboot = (
        "The exact cause of the reboot could not be "
        "determined from the available evidence."
    )


# ============================================================
# HEALTH SCORE
# ============================================================

health_score = 100
health_impact = []


def deduct(points, reason):

    global health_score

    health_score -= points

    health_impact.append(
        (reason, points)
    )


if checks["Kernel Panic"] == "Detected":
    deduct(30, "Kernel panic")


if checks["Kernel OOPS"] == "Detected":
    deduct(25, "Kernel OOPS")


if checks["OOM"] == "Detected":
    deduct(20, "OOM / Memory exhaustion")


if checks["Hardware Error"] == "Detected":
    deduct(30, "Hardware error")


if checks["Storage / I/O"] == "Detected":
    deduct(25, "Storage / I/O error")


if checks["Filesystem"] == "Detected":
    deduct(20, "Filesystem error")


if checks["Watchdog / Lockup"] == "Detected":
    deduct(25, "Watchdog / Lockup")


if checks["Systemd Failure"] == "Detected":
    deduct(15, "Systemd failure")


if (
    checks["Manual Reboot"] == "Detected"
    or
    checks["Cron Reboot"] == "Detected"
):

    deduct(5, "Recent reboot")


if checks["Recurring Reboot"] == "Detected":

    deduct(
        15,
        "Recurring reboot pattern"
    )


if checks["Kdump"] == "Not configured":

    deduct(
        5,
        "Kdump not configured"
    )


if (
    checks["Kernel Panic"] == "Detected"
    and
    checks["VMcore"] == "Not available"
):

    deduct(
        5,
        "VMcore unavailable after panic"
    )


health_score = max(
    0,
    min(
        100,
        health_score
    )
)


# ============================================================
# HEALTH STATUS
# ============================================================

if health_score >= 90:

    health_status = "HEALTHY"
    health_color = "green"

elif health_score >= 75:

    health_status = "GOOD"
    health_color = "green"

elif health_score >= 50:

    health_status = "WARNING"
    health_color = "yellow"

elif health_score >= 25:

    health_status = "CRITICAL"
    health_color = "dark_orange"

else:

    health_status = "SEVERE"
    health_color = "red"


# ============================================================
# HEALTH BAR
# ============================================================

bar_length = 35

filled = int(
    bar_length * health_score / 100
)

empty = bar_length - filled

health_bar = (
    "█" * filled +
    "░" * empty
)


# ============================================================
# REBOOT PATTERN
# ============================================================

if recurring_reboot and reboot_intervals:

    rounded = [
        round(x, 1)
        for x in reboot_intervals
        if 0 < x <= 10
    ]

    if rounded:

        avg_interval = round(
            sum(rounded) / len(rounded),
            1
        )

        pattern_text = (
            f"Recurring reboot pattern detected. "
            f"Recent reboot interval is approximately "
            f"{avg_interval} minutes."
        )

    else:

        pattern_text = (
            "Recurring reboot pattern detected."
        )

else:

    pattern_text = (
        "No recurring short-interval reboot pattern detected."
    )


# ============================================================
# REPORT
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

report_file = os.path.join(
    REPORT_DIR,
    f"RCA_RULE_{timestamp}.txt"
)


with open(
    report_file,
    "w"
) as f:

    f.write("=" * 70 + "\n")
    f.write("LINUX REBOOT INTELLIGENCE CENTER\n")
    f.write("=" * 70 + "\n\n")

    f.write(f"Server: {server}\n")
    f.write(f"Analysis Time: {analysis_time}\n")
    f.write(
        f"Evidence File: "
        f"{os.path.basename(evidence_file)}\n\n"
    )

    f.write(
        f"Probable Root Cause: {root_cause}\n"
    )

    f.write(
        f"Confidence: {confidence}\n\n"
    )

    f.write(
        "Cause of Reboot:\n"
        f"{cause_of_reboot}\n\n"
    )

    f.write(
        "Reboot Pattern:\n"
        f"{pattern_text}\n\n"
    )

    f.write(
        f"Health Score: {health_score}/100\n"
    )

    f.write(
        f"Health Status: {health_status}\n\n"
    )

    f.write("ROOT CAUSE CHECKS\n")
    f.write("-" * 40 + "\n")

    for name, status in checks.items():

        f.write(
            f"{name}: {status}\n"
        )

    f.write("\nHEALTH IMPACT\n")
    f.write("-" * 40 + "\n")

    for reason, points in health_impact:

        f.write(
            f"{reason}: -{points}\n"
        )

    f.write("\n")


# ============================================================
# UI - STATUS
# ============================================================

status_table = Table(
    show_header=False,
    box=None,
    padding=(0, 2),
)

status_table.add_column(
    "SERVER",
    justify="center"
)

status_table.add_column(
    "STATUS",
    justify="center"
)

status_table.add_column(
    "HEALTH",
    justify="center"
)

status_table.add_column(
    "CONFIDENCE",
    justify="center"
)

status_table.add_row(
    f"[bold]SERVER[/bold]\n"
    f"[cyan]{server}[/cyan]",

    f"[bold]STATUS[/bold]\n"
    f"[{health_color}]● {health_status}[/{health_color}]",

    f"[bold]HEALTH SCORE[/bold]\n"
    f"[bold {health_color}]"
    f"{health_score}/100"
    f"[/bold {health_color}]",

    f"[bold]RCA CONFIDENCE[/bold]\n"
    f"[bold yellow]{confidence}[/bold yellow]",
)

console.print(
    Panel(
        status_table,
        border_style="blue"
    )
)

console.print()


# ============================================================
# INCIDENT SUMMARY
# ============================================================

summary = Table(
    show_header=False,
    box=None,
    padding=(0, 1)
)

summary.add_column(
    "Field",
    style="bold cyan",
    width=24
)

summary.add_column(
    "Value"
)

summary.add_row(
    "Reboot Investigation",
    "Linux server reboot detected"
)

summary.add_row(
    "Probable Root Cause",
    f"[bold yellow]{root_cause}[/bold yellow]"
)

summary.add_row(
    "Cause of Reboot",
    cause_of_reboot
)

summary.add_row(
    "Evidence Size",
    f"{evidence_size:,} characters"
)

summary.add_row(
    "Analysis Mode",
    "LOCAL RULE-BASED ENGINE"
)

console.print(
    Panel(
        summary,
        title="[bold cyan]INCIDENT SUMMARY[/bold cyan]",
        border_style="cyan"
    )
)

console.print()


# ============================================================
# HEALTH
# ============================================================

console.print(
    Panel(
        f"[bold white]Health Score: "
        f"{health_score} / 100[/bold white]\n\n"
        f"[{health_color}]{health_bar}[/{health_color}]\n\n"
        f"[bold {health_color}]● {health_status}[/bold {health_color}]",
        title="[bold green]SERVER HEALTH[/bold green]",
        border_style=health_color,
        padding=(1, 3)
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
    border_style="blue"
)

matrix.add_column("CHECK")
matrix.add_column("STATUS", justify="center")


for name, status in checks.items():

    if status == "Detected":

        display = "[bold red]● DETECTED[/bold red]"

    elif status in [
        "Not detected",
        "Not configured",
        "Not available",
    ]:

        display = f"[green]✓ {status.upper()}[/green]"

    else:

        display = f"[yellow]? {status.upper()}[/yellow]"

    matrix.add_row(
        name,
        display
    )


console.print(matrix)

console.print()


# ============================================================
# REBOOT TIMELINE
# ============================================================

timeline = Table(
    title="REBOOT TIMELINE",
    show_header=True,
    header_style="bold cyan",
    border_style="magenta"
)

timeline.add_column(
    "TIME",
    justify="center"
)

timeline.add_column(
    "EVENT"
)

timeline.add_column(
    "TYPE",
    justify="center"
)


if latest_reboot:

    timeline.add_row(
        latest_reboot["time"].strftime(
            "%H:%M:%S"
        ),
        latest_reboot["line"].strip(),
        f"[bold yellow]{latest_reboot['type']}[/bold yellow]"
    )

for item in systemd_reboot_events[-3:]:

    timeline.add_row(
        item["time"].strftime("%H:%M:%S"),
        item["line"].strip(),
        "[cyan]SYSTEMD[/cyan]"
    )


if not latest_reboot:

    timeline.add_row(
        "-",
        "No explicit reboot command detected",
        "[yellow]UNKNOWN[/yellow]"
    )


console.print(timeline)

console.print()


# ============================================================
# RECURRING PATTERN
# ============================================================

pattern_color = (
    "yellow"
    if recurring_reboot
    else "green"
)

console.print(
    Panel(
        f"[bold]{pattern_text}[/bold]",
        title="[bold magenta]REBOOT PATTERN ANALYSIS[/bold magenta]",
        border_style=pattern_color
    )
)

console.print()


# ============================================================
# HEALTH IMPACT
# ============================================================

impact = Table(
    title="HEALTH IMPACT",
    show_header=True,
    header_style="bold cyan",
    border_style="yellow"
)

impact.add_column("Issue")
impact.add_column("Impact", justify="right")


if health_impact:

    for reason, points in health_impact:

        impact.add_row(
            reason,
            f"[bold red]-{points}[/bold red]"
        )

else:

    impact.add_row(
        "No health-impacting conditions",
        "[green]0[/green]"
    )


console.print(impact)

console.print()


# ============================================================
# CAUSE OF REBOOT
# ============================================================

console.print(
    Panel(
        f"[bold white]{cause_of_reboot}[/bold white]",
        title="[bold red]⚠ CAUSE OF REBOOT[/bold red]",
        border_style="red",
        padding=(1, 3)
    )
)

console.print()


# ============================================================
# RECOMMENDED ACTION
# ============================================================

if root_cause == "Manual / Planned Reboot":

    action = (
        "Verify the reboot against the approved "
        "change or maintenance window."
    )

elif root_cause == "Scheduled Cron Reboot":

    action = (
        "Verify the cron job and confirm whether "
        "the scheduled reboot was authorized."
    )

elif recurring_reboot:

    action = (
        "Investigate the recurring reboot pattern and "
        "review scheduled jobs, automation and system events."
    )

elif root_cause == "OOM / Memory Exhaustion":

    action = (
        "Review memory-consuming processes and "
        "application memory utilization."
    )

elif root_cause == "Hardware / MCE / ECC Error":

    action = (
        "Review hardware/MCE/ECC events and engage "
        "the hardware/vendor team if required."
    )

elif root_cause == "Storage / I/O Error":

    action = (
        "Investigate storage, disk, SAN and I/O errors "
        "with the relevant team."
    )

elif root_cause == "Kernel Panic":

    action = (
        "Review kernel logs and verify kdump configuration "
        "for future crash analysis."
    )

else:

    action = (
        "Perform additional investigation because the "
        "reboot cause could not be conclusively identified."
    )


console.print(
    Panel(
        f"[bold white]{action}[/bold white]",
        title="[bold yellow]RECOMMENDED ACTION[/bold yellow]",
        border_style="yellow",
        padding=(1, 3)
    )
)

console.print()


# ============================================================
# REPORT
# ============================================================

console.print(
    Panel(
        "[bold green]✓ RCA REPORT GENERATED[/bold green]\n\n"
        f"[cyan]{report_file}[/cyan]\n\n"
        "[dim]Rule Engine v3.0 | Local | No AI | No External API[/dim]",
        title="[bold green]REPORT[/bold green]",
        border_style="green",
        padding=(1, 3)
    )
)

console.print()


# ============================================================
# FOOTER
# ============================================================

console.print(
    Panel.fit(
        "[bold cyan]LINUX REBOOT INTELLIGENCE CENTER[/bold cyan]"
        "  [dim]|[/dim]  "
        "[white]Rule Engine v3.0[/white]"
        "  [dim]|[/dim]  "
        "[green]LOCAL / NO AI / NO EXTERNAL API[/green]",
        border_style="cyan"
    )
)

console.print()
