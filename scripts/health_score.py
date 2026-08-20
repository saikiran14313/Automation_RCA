#!/usr/bin/env python3

import os
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")
EVIDENCE_DIR = os.path.join(BASE_DIR, "logs", "evidence")
REPORT_DIR = os.path.join(BASE_DIR, "reports")


# ============================================================
# FIND LATEST RCA REPORT
# ============================================================

reports = [
    os.path.join(REPORT_DIR, f)
    for f in os.listdir(REPORT_DIR)
    if f.startswith("RCA_") and f.endswith(".txt")
]

if not reports:
    console.print(
        Panel(
            "[bold red]No RCA report found.[/bold red]\n\n"
            "Run analyze_rca.py first.",
            border_style="red",
        )
    )
    raise SystemExit(1)

latest_report = max(
    reports,
    key=os.path.getmtime
)

with open(
    latest_report,
    "r",
    errors="ignore"
) as f:
    rca = f.read()


# ============================================================
# GET VALUE FROM RCA
# ============================================================

def get_status(label):

    for line in rca.splitlines():

        line = line.strip()

        if line.lower().startswith(
            label.lower() + ":"
        ):
            return line.split(
                ":", 1
            )[1].strip()

    return "Unknown"


# ============================================================
# SERVER
# ============================================================

server = get_status("Server")

if server == "Unknown":
    server = os.uname().nodename


# ============================================================
# START SCORE
# ============================================================

score = 100
issues = []


def deduct(points, description):

    global score

    score -= points

    issues.append(
        (
            description,
            points
        )
    )


# ============================================================
# READ ACTUAL RCA STATUS
# ============================================================

kernel_panic = get_status(
    "Kernel Panic"
)

kernel_oops = get_status(
    "Kernel OOPS"
)

oom = get_status(
    "OOM"
)

hardware = get_status(
    "Hardware Error"
)

storage = get_status(
    "Storage / I/O Error"
)

filesystem = get_status(
    "Filesystem Error"
)

watchdog = get_status(
    "Watchdog / Lockup"
)

systemd = get_status(
    "Systemd Failure"
)

manual_reboot = get_status(
    "Manual / Planned Reboot"
)

cron_reboot = get_status(
    "Cron Scheduled Reboot"
)

kdump = get_status(
    "Kdump"
)

vmcore = get_status(
    "VMcore"
)


# ============================================================
# APPLY HEALTH PENALTIES
# ONLY WHEN ACTUALLY DETECTED
# ============================================================

if kernel_panic.lower() == "detected":
    deduct(
        30,
        "Kernel panic detected"
    )


if kernel_oops.lower() == "detected":
    deduct(
        25,
        "Kernel OOPS detected"
    )


if oom.lower() == "detected":
    deduct(
        20,
        "OOM / memory exhaustion detected"
    )


if hardware.lower() == "detected":
    deduct(
        30,
        "Hardware / MCE / ECC error detected"
    )


if storage.lower() == "detected":
    deduct(
        25,
        "Storage / I/O error detected"
    )


if filesystem.lower() == "detected":
    deduct(
        20,
        "Filesystem error detected"
    )


if watchdog.lower() == "detected":
    deduct(
        25,
        "Watchdog / lockup detected"
    )


if systemd.lower() == "detected":
    deduct(
        15,
        "Systemd failure detected"
    )


# ============================================================
# REBOOT
# ============================================================

if (
    manual_reboot.lower() == "detected"
    or
    cron_reboot.lower() == "detected"
):

    deduct(
        5,
        "Recent reboot detected"
    )


# ============================================================
# KDUMP
# ============================================================

if kdump.lower() == "not configured":

    deduct(
        5,
        "Kdump not configured"
    )


# ============================================================
# VMCORE
# ============================================================

if (
    kernel_panic.lower() == "detected"
    and
    vmcore.lower() == "not available"
):

    deduct(
        5,
        "Kernel panic occurred but VMcore unavailable"
    )


# ============================================================
# LIMIT SCORE
# ============================================================

score = max(
    0,
    min(
        100,
        score
    )
)


# ============================================================
# HEALTH STATUS
# ============================================================

if score >= 90:

    status = "HEALTHY"
    status_color = "green"

elif score >= 75:

    status = "GOOD"
    status_color = "green"

elif score >= 50:

    status = "WARNING"
    status_color = "yellow"

elif score >= 25:

    status = "CRITICAL"
    status_color = "dark_orange"

else:

    status = "SEVERE"
    status_color = "red"


# ============================================================
# DISPLAY
# ============================================================

console.print()

console.print(
    Panel.fit(
        "[bold cyan]LINUX SERVER HEALTH ENGINE[/bold cyan]\n"
        "[white]RCA-based server health scoring[/white]",
        border_style="cyan",
        padding=(1, 4),
    )
)

console.print()


# ============================================================
# SERVER PANEL
# ============================================================

console.print(
    Panel(
        f"[bold]Server:[/bold] {server}\n"
        f"[bold]RCA Report:[/bold] "
        f"{os.path.basename(latest_report)}\n"
        f"[bold]Analysis Time:[/bold] "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        title="SERVER",
        border_style="blue",
    )
)

console.print()


# ============================================================
# HEALTH SCORE
# ============================================================

console.print(
    Panel(
        f"[bold white]Health Score: "
        f"{score} / 100[/bold white]\n\n"
        f"[bold {status_color}]Status: "
        f"{status}[/bold {status_color}]",
        title="SERVER HEALTH",
        border_style=status_color,
        padding=(1, 4),
    )
)

console.print()


# ============================================================
# IMPACT TABLE
# ============================================================

if issues:

    table = Table(
        title="HEALTH IMPACT",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )

    table.add_column(
        "Issue"
    )

    table.add_column(
        "Impact",
        justify="right"
    )

    for issue, points in issues:

        table.add_row(
            issue,
            f"[bold red]-{points}[/bold red]"
        )

    console.print(table)

else:

    console.print(
        Panel(
            "[bold green]✓ No health-impacting "
            "events detected.[/bold green]",
            title="HEALTH CHECK",
            border_style="green",
        )
    )


console.print()


# ============================================================
# RCA STATUS TABLE
# ============================================================

table = Table(
    title="RCA HEALTH INPUTS",
    show_header=True,
    header_style="bold cyan",
    border_style="cyan",
)

table.add_column("Check")
table.add_column("Status")


checks = {
    "Kernel Panic": kernel_panic,
    "Kernel OOPS": kernel_oops,
    "OOM": oom,
    "Hardware Error": hardware,
    "Storage / I/O": storage,
    "Filesystem": filesystem,
    "Watchdog / Lockup": watchdog,
    "Systemd Failure": systemd,
    "Manual Reboot": manual_reboot,
    "Cron Reboot": cron_reboot,
    "Kdump": kdump,
    "VMcore": vmcore,
}


for name, value in checks.items():

    if value.lower() == "detected":

        display = (
            f"[bold red]{value}[/bold red]"
        )

    elif value.lower() in [
        "not detected",
        "not configured",
        "not available",
    ]:

        display = (
            f"[green]{value}[/green]"
        )

    else:

        display = (
            f"[yellow]{value}[/yellow]"
        )

    table.add_row(
        name,
        display
    )


console.print(table)

console.print()


# ============================================================
# FINAL
# ============================================================

console.print(
    Panel(
        "[bold]Health score is calculated from "
        "the validated RCA results rather than "
        "simple keyword matching.[/bold]",
        title="HEALTH ENGINE",
        border_style="green",
    )
)

console.print()
