#!/usr/bin/env python3

import os
import json
import time
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import errors

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)

load_dotenv()

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
        "[bold cyan]LINUX AI REBOOT RCA ENGINE[/bold cyan]\n"
        "[white]Automated Linux Incident Root Cause Analysis[/white]\n"
        "[dim]Evidence → Correlation → AI → RCA[/dim]",
        border_style="cyan",
        padding=(1, 4),
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
            "[bold red]No AI evidence file found.[/bold red]",
            border_style="red",
        )
    )
    raise SystemExit(1)

evidence_file = max(files, key=os.path.getmtime)

with open(evidence_file, "r", errors="ignore") as f:
    evidence = f.read()


console.print(
    Panel(
        f"[bold green]✓ Evidence loaded[/bold green]\n\n"
        f"[bold]File:[/bold] {os.path.basename(evidence_file)}\n"
        f"[bold]Server:[/bold] {os.uname().nodename}\n"
        f"[bold]Evidence size:[/bold] {len(evidence):,} characters",
        title="EVIDENCE",
        border_style="green",
    )
)

console.print()


# ============================================================
# API KEY
# ============================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    console.print(
        Panel(
            "[bold red]GEMINI_API_KEY not found in .env[/bold red]",
            border_style="red",
        )
    )
    raise SystemExit(1)

client = genai.Client(api_key=api_key)


# ============================================================
# AI PROMPT
# ============================================================

prompt = f"""
You are a senior Linux production support engineer.

Analyze the following Ubuntu Linux reboot evidence.

Determine the MOST PROBABLE ROOT CAUSE.

IMPORTANT RULES:

1. Use ONLY the supplied evidence.
2. Do not invent facts.
3. Correlate timestamps whenever possible.
4. Give priority to events BEFORE the reboot.
5. A reboot command alone does not prove the original incident was planned.
6. Distinguish between confirmed cause, probable cause, and insufficient evidence.
7. If evidence is insufficient, use UNKNOWN.
8. Do not blame hardware, storage, OOM, panic, etc. without supporting evidence.
9. Look for cron/systemd/AWS/external reboot indicators.
10. Identify the earliest relevant failure before the reboot.

Possible causes:

- Manual / Planned reboot
- Cron scheduled reboot
- OOM / Memory exhaustion
- Kernel panic
- Kernel OOPS
- Hardware / MCE / ECC
- Storage / I/O
- Filesystem
- Watchdog / Lockup
- Hung task
- Systemd / Service
- Network
- Unknown

Return ONLY valid JSON.

Use exactly these fields:

{{
  "server": "hostname",
  "incident": "short description",
  "probable_root_cause": "one clear cause",
  "confidence": "HIGH",
  "timeline": [
    "timestamp - event",
    "timestamp - event",
    "timestamp - event"
  ],
  "key_evidence": [
    "evidence 1",
    "evidence 2",
    "evidence 3"
  ],
  "kernel_panic": "Detected / Not detected / Unknown",
  "kernel_oops": "Detected / Not detected / Unknown",
  "oom": "Detected / Not detected / Unknown",
  "hardware_error": "Detected / Not detected / Unknown",
  "storage_error": "Detected / Not detected / Unknown",
  "filesystem_error": "Detected / Not detected / Unknown",
  "watchdog_lockup": "Detected / Not detected / Unknown",
  "systemd_failure": "Detected / Not detected / Unknown",
  "manual_reboot": "Detected / Not detected / Unknown",
  "cron_reboot": "Detected / Not detected / Unknown",
  "kdump": "Configured / Not configured / Unknown",
  "vmcore": "Available / Not available / Unknown",
  "final_rca": "2-4 sentence professional RCA",
  "recommended_action": "short Linux SA action",
  "cause_of_reboot": "ONE clear sentence explaining the most probable cause"
}}

Rules for cause_of_reboot:

- Exactly ONE sentence.
- Must clearly state the most probable cause.
- Must be based ONLY on supplied evidence.
- Do not invent a cause.
- If the cause cannot be determined, use exactly:
  "The exact cause of the reboot could not be determined from the available evidence."

Evidence:

{evidence}
"""


# ============================================================
# AI ANALYSIS WITH RETRY
# ============================================================

console.print(
    Panel.fit(
        "[bold yellow]AI ANALYSIS STARTED[/bold yellow]\n"
        "Correlating Linux reboot evidence...",
        border_style="yellow",
    )
)

start_time = time.time()

response = None

# Retry delays
retry_delays = [5, 10, 20]

for attempt, delay in enumerate(retry_delays, start=1):

    try:

        console.print(
            f"[cyan]AI attempt {attempt}/3...[/cyan]"
        )

        with Progress(
            SpinnerColumn(),
            TextColumn(
                "[magenta]Gemini is analyzing reboot evidence..."
            ),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            task = progress.add_task(
                "Analyzing",
                total=100,
            )

            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
            )

            progress.update(
                task,
                completed=100,
            )

        break

    except errors.ServerError as e:

        console.print(
            f"[yellow]Gemini returned server error "
            f"(503).[/yellow]"
        )

        if attempt == len(retry_delays):

            console.print(
                Panel(
                    "[bold red]Gemini AI is currently unavailable.[/bold red]\n\n"
                    "The Linux evidence was collected successfully, "
                    "but AI analysis could not be completed.\n\n"
                    "No reboot or evidence collection is required again.\n"
                    "Run this script later to retry the existing evidence.",
                    title="AI SERVICE ERROR",
                    border_style="red",
                )
            )

            raise SystemExit(1)

        console.print(
            f"[yellow]Retrying in {delay} seconds...[/yellow]"
        )

        time.sleep(delay)

    except Exception as e:

        console.print(
            Panel(
                f"[bold red]Unexpected AI error[/bold red]\n\n"
                f"{str(e)}",
                title="AI ERROR",
                border_style="red",
            )
        )

        raise SystemExit(1)


if response is None:
    console.print(
        Panel(
            "[bold red]No response received from Gemini.[/bold red]",
            border_style="red",
        )
    )
    raise SystemExit(1)


elapsed = time.time() - start_time


# ============================================================
# GET AI RESPONSE
# ============================================================

raw_response = response.text.strip()

# Remove Markdown JSON fences if Gemini returns them
if raw_response.startswith("```"):

    raw_response = raw_response.replace(
        "```json",
        ""
    )

    raw_response = raw_response.replace(
        "```",
        ""
    )

    raw_response = raw_response.strip()


# ============================================================
# PARSE JSON
# ============================================================

try:

    rca = json.loads(raw_response)

except json.JSONDecodeError:

    console.print(
        Panel(
            "[bold red]Gemini returned invalid JSON.[/bold red]\n\n"
            f"{raw_response}",
            title="AI RESPONSE ERROR",
            border_style="red",
        )
    )

    raise SystemExit(1)


# ============================================================
# HELPER
# ============================================================

def get_value(key, default="UNKNOWN"):

    value = rca.get(key, default)

    if value is None:
        return default

    return str(value)


# ============================================================
# SAVE REPORT
# ============================================================

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

report_file = os.path.join(
    REPORT_DIR,
    f"RCA_{timestamp}.txt",
)


with open(report_file, "w") as f:

    f.write("========================================\n")
    f.write("LINUX REBOOT RCA\n")
    f.write("========================================\n\n")

    f.write(
        f"Server:\n"
        f"{get_value('server')}\n\n"
    )

    f.write(
        f"Incident:\n"
        f"{get_value('incident')}\n\n"
    )

    f.write(
        f"Probable Root Cause:\n"
        f"{get_value('probable_root_cause')}\n\n"
    )

    f.write(
        f"Confidence:\n"
        f"{get_value('confidence')}\n\n"
    )

    f.write("Timeline:\n")

    for item in rca.get("timeline", []):
        f.write(f"- {item}\n")

    f.write("\nKey Evidence:\n")

    for index, item in enumerate(
        rca.get("key_evidence", []),
        1
    ):
        f.write(
            f"{index}. {item}\n"
        )

    f.write("\nRoot Cause Checks:\n")

    checks = {
        "Kernel Panic": "kernel_panic",
        "Kernel OOPS": "kernel_oops",
        "OOM": "oom",
        "Hardware Error": "hardware_error",
        "Storage / I/O Error": "storage_error",
        "Filesystem Error": "filesystem_error",
        "Watchdog / Lockup": "watchdog_lockup",
        "Systemd Failure": "systemd_failure",
        "Manual / Planned Reboot": "manual_reboot",
        "Cron Scheduled Reboot": "cron_reboot",
        "Kdump": "kdump",
        "VMcore": "vmcore",
    }

    for label, key in checks.items():

        f.write(
            f"{label}: "
            f"{get_value(key)}\n"
        )

    f.write(
        f"\nFinal RCA:\n"
        f"{get_value('final_rca')}\n"
    )

    f.write(
        f"\nRecommended Action:\n"
        f"{get_value('recommended_action')}\n"
    )

    f.write(
        f"\nEvidence File:\n"
        f"{os.path.basename(evidence_file)}\n"
    )

    f.write(
        f"\nCause of Reboot:\n"
        f"{get_value('cause_of_reboot')}\n"
    )


# ============================================================
# SUCCESS DISPLAY
# ============================================================

console.print()

console.print(
    Panel.fit(
        "[bold green]✓ AI ANALYSIS COMPLETED[/bold green]\n"
        f"[dim]Analysis time: {elapsed:.2f} seconds[/dim]",
        border_style="green",
    )
)

console.print()


# ============================================================
# RCA SUMMARY TABLE
# ============================================================

table = Table(
    title="RCA SUMMARY",
    show_header=True,
    header_style="bold cyan",
    border_style="blue",
)

table.add_column(
    "FIELD",
    style="bold white",
)

table.add_column(
    "RESULT",
)


table.add_row(
    "Server",
    get_value("server"),
)


table.add_row(
    "Probable Root Cause",
    f"[bold yellow]"
    f"{get_value('probable_root_cause')}"
    f"[/bold yellow]",
)


confidence = get_value(
    "confidence"
).upper()


if confidence == "HIGH":

    confidence_display = (
        "[bold green]HIGH[/bold green]"
    )

elif confidence == "MEDIUM":

    confidence_display = (
        "[bold yellow]MEDIUM[/bold yellow]"
    )

elif confidence == "LOW":

    confidence_display = (
        "[bold red]LOW[/bold red]"
    )

else:

    confidence_display = (
        "[bold white]UNKNOWN[/bold white]"
    )


table.add_row(
    "Confidence",
    confidence_display,
)


console.print(table)

console.print()


# ============================================================
# CAUSE OF REBOOT
# ============================================================

console.print(
    Panel(
        f"[bold white]"
        f"{get_value('cause_of_reboot')}"
        f"[/bold white]",
        title="[bold red]⚠ CAUSE OF REBOOT[/bold red]",
        border_style="red",
        padding=(1, 2),
    )
)

console.print()


# ============================================================
# KEY EVIDENCE
# ============================================================

evidence_table = Table(
    title="KEY EVIDENCE",
    show_header=False,
    border_style="cyan",
)

evidence_table.add_column(
    "Evidence"
)

for item in rca.get(
    "key_evidence",
    []
):

    evidence_table.add_row(
        f"• {item}"
    )


console.print(evidence_table)

console.print()


# ============================================================
# RCA DETAILS
# ============================================================

details = Table(
    title="ROOT CAUSE CHECKS",
    show_header=True,
    header_style="bold cyan",
    border_style="blue",
)

details.add_column(
    "CHECK",
    style="white",
)

details.add_column(
    "STATUS",
)


for label, key in {
    "Kernel Panic": "kernel_panic",
    "Kernel OOPS": "kernel_oops",
    "OOM": "oom",
    "Hardware Error": "hardware_error",
    "Storage / I/O": "storage_error",
    "Filesystem": "filesystem_error",
    "Watchdog / Lockup": "watchdog_lockup",
    "Systemd Failure": "systemd_failure",
    "Manual Reboot": "manual_reboot",
    "Cron Reboot": "cron_reboot",
    "Kdump": "kdump",
    "VMcore": "vmcore",
}.items():

    value = get_value(key)

    if "Detected" in value:

        display = (
            f"[bold red]{value}[/bold red]"
        )

    elif (
        "Not detected" in value
        or "Not configured" in value
        or "Not available" in value
    ):

        display = (
            f"[green]{value}[/green]"
        )

    else:

        display = (
            f"[yellow]{value}[/yellow]"
        )

    details.add_row(
        label,
        display,
    )


console.print(details)

console.print()


# ============================================================
# FINAL RCA
# ============================================================

console.print(
    Panel(
        get_value("final_rca"),
        title="[bold cyan]FINAL RCA[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
)

console.print()


# ============================================================
# RECOMMENDED ACTION
# ============================================================

console.print(
    Panel(
        get_value("recommended_action"),
        title="[bold yellow]RECOMMENDED ACTION[/bold yellow]",
        border_style="yellow",
        padding=(1, 2),
    )
)

console.print()


# ============================================================
# REPORT LOCATION
# ============================================================

console.print(
    Panel(
        f"[bold green]RCA report saved successfully[/bold green]\n\n"
        f"[cyan]{report_file}[/cyan]",
        title="REPORT",
        border_style="green",
    )
)

console.print()

console.print(
    "[dim]Raw evidence is preserved separately "
    "for detailed SA investigation.[/dim]"
)

console.print()
