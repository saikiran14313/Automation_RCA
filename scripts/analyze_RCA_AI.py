#!/usr/bin/env python3

import os
import sys
import glob
import json
import re
import subprocess
from datetime import datetime

from dotenv import load_dotenv

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich import box


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")

SCRIPTS_DIR = os.path.join(
    BASE_DIR,
    "scripts",
)

EVIDENCE_DIR = os.path.join(
    BASE_DIR,
    "logs",
    "evidence",
)

REPORT_DIR = os.path.join(
    BASE_DIR,
    "reports",
)

ENV_FILE = os.path.join(
    BASE_DIR,
    ".env",
)

os.makedirs(REPORT_DIR, exist_ok=True)

load_dotenv(ENV_FILE)

console = Console()


# ============================================================
# COLORS
# ============================================================

GREEN = "green"
RED = "red"
YELLOW = "yellow"
CYAN = "cyan"
BLUE = "blue"


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if value is None:
        return ""

    return str(value).strip()


def run_command(command, timeout=300):

    try:

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return (
            result.stdout
            + result.stderr
        )

    except subprocess.TimeoutExpired:

        return (
            "ERROR: command timed out"
        )

    except Exception as exc:

        return (
            f"ERROR: {exc}"
        )


def find_latest(pattern):

    files = glob.glob(pattern)

    if not files:
        return None

    return max(
        files,
        key=os.path.getmtime,
    )


def get_server():

    hostname = run_command(
        "hostname"
    ).strip()

    return hostname or "UNKNOWN"


# ============================================================
# HEADER
# ============================================================

console.print()

console.print(
    Panel.fit(
        "[bold cyan]LINUX AI REBOOT RCA ENGINE[/bold cyan]\n"
        "[white]Evidence → Local Rules → AI Explanation → RCA → Health[/white]\n"
        "[dim]Local Rule Engine is the authoritative RCA source[/dim]",
        border_style="cyan",
        padding=(1, 5),
    )
)

console.print()


# ============================================================
# SERVER
# ============================================================

server = get_server()


# ============================================================
# FIND EVIDENCE
# ============================================================

latest_evidence = find_latest(
    os.path.join(
        EVIDENCE_DIR,
        "ai_evidence_*.txt",
    )
)


if not latest_evidence:

    console.print(
        Panel(
            "[bold red]No evidence file found.[/bold red]\n\n"
            "Run:\n"
            "[cyan]python3 scripts/collect_evidence.py[/cyan]",
            title="ERROR",
            border_style="red",
        )
    )

    sys.exit(1)


with open(
    latest_evidence,
    "r",
    errors="ignore",
) as f:

    evidence = f.read()


evidence_size = len(evidence)


# ============================================================
# EVIDENCE PANEL
# ============================================================

table = Table(
    box=box.ROUNDED,
    show_header=False,
    border_style="cyan",
)

table.add_column(
    "FIELD",
    style="bold cyan",
)

table.add_column(
    "VALUE",
)

table.add_row(
    "Status",
    "[bold green]✓ Evidence Loaded[/bold green]",
)

table.add_row(
    "File",
    os.path.basename(latest_evidence),
)

table.add_row(
    "Server",
    server,
)

table.add_row(
    "Evidence Size",
    f"{evidence_size:,} characters",
)


console.print(
    Panel(
        table,
        title="EVIDENCE",
        border_style="cyan",
    )
)

console.print()


# ============================================================
# EVIDENCE LOADING UI
# ============================================================

categories = [
    "Previous Boot Logs",
    "Kernel Events",
    "Reboot / Shutdown",
    "Manual Reboot",
    "Cron Activity",
    "OOM / Memory",
    "Kernel Panic / OOPS",
    "Hardware / MCE / ECC",
    "Storage / I/O",
    "Filesystem",
    "Watchdog / Lockup",
    "Systemd",
    "Disk / Filesystem State",
    "Kdump Service",
    "Kdump Configuration",
    "Crashkernel",
    "Kdump Kernel / Initrd",
    "VMcore / Crash Files",
    "Boot History",
    "Reboot Timeline",
]


console.print(
    Panel(
        "[bold]The collected evidence is being prepared "
        "for deterministic RCA.[/bold]\n\n"
        "The local rule engine remains the source of truth.",
        title="EVIDENCE PROCESSING",
        border_style="blue",
    )
)


with Progress(
    SpinnerColumn(),
    TextColumn(
        "[progress.description]{task.description}"
    ),
    BarColumn(),
    TextColumn("{task.completed}/{task.total}"),
    TimeElapsedColumn(),
    console=console,
) as progress:

    task = progress.add_task(
        "Loading evidence...",
        total=len(categories),
    )

    for category in categories:

        progress.update(
            task,
            description=f"Loading {category}...",
        )

        progress.advance(task)


console.print(
    "[bold green]✓ Evidence preparation completed[/bold green]"
)

console.print()


# ============================================================
# LOCAL RULE ENGINE
# ============================================================

local_script = os.path.join(
    SCRIPTS_DIR,
    "local_rule_rca.py",
)


if not os.path.isfile(local_script):

    console.print(
        Panel(
            f"[bold red]local_rule_rca.py not found[/bold red]\n\n"
            f"Expected:\n{local_script}",
            title="ERROR",
            border_style="red",
        )
    )

    sys.exit(1)


console.print(
    Panel(
        "[bold green]LOCAL RULE ENGINE[/bold green]\n\n"
        "The deterministic rule engine will now perform "
        "the primary RCA.\n\n"
        "[bold]Important:[/bold] AI cannot override this result.",
        title="RCA ENGINE",
        border_style="green",
    )
)

console.print()


# ============================================================
# EXECUTE LOCAL RULE ENGINE
# ============================================================

local_process = subprocess.run(
    [
        sys.executable,
        local_script,
    ],
    capture_output=True,
    text=True,
    timeout=300,
)


local_output = (
    local_process.stdout
    + local_process.stderr
)


if local_process.returncode != 0:

    console.print(
        Panel(
            "[bold red]Local Rule Engine failed.[/bold red]\n\n"
            f"{local_output[-5000:]}",
            title="RCA ERROR",
            border_style="red",
        )
    )

    sys.exit(1)


console.print(
    Panel(
        "[bold green]✓ Local RCA completed[/bold green]\n\n"
        "Primary RCA, root-cause matrix, health score, "
        "Kdump and VMcore status were determined by "
        "the local rule engine.",
        title="LOCAL RCA COMPLETE",
        border_style="green",
    )
)

console.print()


# ============================================================
# FIND LOCAL RCA REPORT
# ============================================================

rule_reports = glob.glob(
    os.path.join(
        REPORT_DIR,
        "RCA_RULE_*.txt",
    )
)

if rule_reports:

    latest_rule_report = max(
        rule_reports,
        key=os.path.getmtime,
    )

else:

    latest_rule_report = None


# ============================================================
# DISPLAY LOCAL ENGINE OUTPUT
# ============================================================

console.print(
    Panel(
        local_output[-12000:],
        title="LOCAL RULE ENGINE RESULT",
        border_style="green",
    )
)

console.print()


# ============================================================
# READ RULE REPORT
# ============================================================

if latest_rule_report:

    with open(
        latest_rule_report,
        "r",
        errors="ignore",
    ) as f:

        rule_report = f.read()

else:

    rule_report = local_output


# ============================================================
# EXTRACT IMPORTANT RCA VALUES
# ============================================================

def extract_value(label, text):

    pattern = (
        rf"^\s*{re.escape(label)}\s*:\s*(.+)$"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE |
        re.MULTILINE,
    )

    if match:

        return clean(
            match.group(1)
        )

    return "UNKNOWN"


root_cause = extract_value(
    "Probable Root Cause",
    rule_report,
)


health_score = extract_value(
    "Health Score",
    rule_report,
)


confidence = extract_value(
    "Confidence",
    rule_report,
)


kdump_status = "UNKNOWN"


if re.search(
    r"ready to kdump|KDUMP.*READY|Kdump.*READY",
    rule_report,
    re.IGNORECASE,
):

    kdump_status = "READY"

elif re.search(
    r"not ready",
    rule_report,
    re.IGNORECASE,
):

    kdump_status = "NOT READY"

elif re.search(
    r"not configured",
    rule_report,
    re.IGNORECASE,
):

    kdump_status = "NOT CONFIGURED"


if re.search(
    r"VMcore.*NOT AVAILABLE|VMCORE.*NOT AVAILABLE",
    rule_report,
    re.IGNORECASE,
):

    vmcore_status = "NOT AVAILABLE"

elif re.search(
    r"VMcore.*AVAILABLE|VMCORE.*AVAILABLE",
    rule_report,
    re.IGNORECASE,
):

    vmcore_status = "AVAILABLE"

else:

    vmcore_status = "UNKNOWN"


# ============================================================
# AI SECTION
# ============================================================

console.print()

console.print(
    Panel(
        "[bold]Gemini AI will NOT determine the primary RCA.[/bold]\n\n"
        "It will receive the local RCA result and provide:\n"
        "• Incident explanation\n"
        "• Evidence interpretation\n"
        "• Possible contributing factors\n"
        "• Recommended investigation\n"
        "• Kdump / VMcore explanation\n\n"
        "[green]Local Rule Engine remains authoritative.[/green]",
        title="AI ANALYSIS",
        border_style="magenta",
    )
)

console.print()


# ============================================================
# GEMINI IMPORT
# ============================================================

gemini_available = False
gemini_reason = ""

try:

    from google import genai

    gemini_available = True

except Exception as exc:

    gemini_available = False

    gemini_reason = str(exc)


api_key = os.getenv(
    "GEMINI_API_KEY"
)


if not api_key:

    gemini_available = False

    gemini_reason = (
        "GEMINI_API_KEY not found"
    )


# ============================================================
# AI RESPONSE
# ============================================================

ai_response = ""

if gemini_available:

    try:

        client = genai.Client(
            api_key=api_key
        )


        # Use the model from environment if supplied.
        model = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.6-flash",
        )


        prompt = f"""
You are the AI explanation layer of a Linux
Reboot Root Cause Analysis platform.

IMPORTANT:
The LOCAL RULE ENGINE is authoritative.

You MUST NOT change or override the primary RCA.

SERVER:
{server}

PRIMARY RCA FROM LOCAL RULE ENGINE:
{root_cause}

LOCAL HEALTH SCORE:
{health_score}

LOCAL CONFIDENCE:
{confidence}

KDUMP:
{kdump_status}

VMCORE:
{vmcore_status}

LOCAL RULE REPORT:
{rule_report[:30000]}

EVIDENCE:
{evidence[:50000]}

Provide a concise professional analysis with exactly
these sections:

1. INCIDENT SUMMARY
2. PRIMARY RCA
3. WHY THIS RCA WAS SELECTED
4. SUPPORTING EVIDENCE
5. OTHER DETECTED EVENTS
6. KDUMP / VMCORE ANALYSIS
7. RECOMMENDED INVESTIGATION

Rules:

- Do not change the primary RCA.
- Do not invent evidence.
- Do not call something a reboot cause unless evidence
  supports it.
- Distinguish cause from background health events.
- If VMcore is unavailable, explicitly say so.
- If Kdump is READY, explain that it is prepared for
  future kernel crash capture.
- If evidence is insufficient, say so.
"""


        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )


        ai_response = clean(
            getattr(
                response,
                "text",
                "",
            )
        )


        if ai_response:

            console.print(
                Panel(
                    "[bold green]✓ Gemini analysis completed[/bold green]\n\n"
                    f"Model: {model}\n"
                    "Role: Explanation / Correlation only\n"
                    "RCA Authority: Local Rule Engine",
                    title="AI STATUS",
                    border_style="green",
                )
            )

        else:

            gemini_available = False

            gemini_reason = (
                "Gemini returned an empty response"
            )


    except Exception as exc:

        gemini_available = False

        gemini_reason = str(exc)


# ============================================================
# AI FALLBACK
# ============================================================

if not gemini_available:

    console.print(
        Panel(
            "[bold yellow]⚠ Gemini AI unavailable[/bold yellow]\n\n"
            f"Reason:\n{gemini_reason}\n\n"
            "The local RCA remains fully functional.\n"
            "No RCA decision will be lost.",
            title="AI STATUS",
            border_style="yellow",
        )
    )

    ai_response = (
        "Gemini AI was unavailable.\n\n"
        "The Local Rule Engine remains the authoritative "
        "RCA source. No AI conclusion was used."
    )


# ============================================================
# FINAL RCA VALIDATION
# ============================================================

console.print()

console.print(
    Panel(
        f"[bold cyan]Primary RCA:[/bold cyan] "
        f"{root_cause}\n\n"
        f"[bold cyan]Health Score:[/bold cyan] "
        f"{health_score}\n\n"
        f"[bold cyan]Confidence:[/bold cyan] "
        f"{confidence}\n\n"
        f"[bold cyan]Kdump:[/bold cyan] "
        f"{kdump_status}\n\n"
        f"[bold cyan]VMcore:[/bold cyan] "
        f"{vmcore_status}",
        title="FINAL RCA — LOCAL RULE AUTHORITY",
        border_style="cyan",
    )
)


# ============================================================
# AI EXPLANATION
# ============================================================

console.print()

console.print(
    Panel(
        ai_response,
        title="AI EXPLANATION",
        border_style="magenta",
        padding=(1, 2),
    )
)


# ============================================================
# FINAL REPORT
# ============================================================

timestamp = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

final_report = os.path.join(
    REPORT_DIR,
    f"RCA_AI_{timestamp}.txt",
)


report_content = f"""
LINUX REBOOT INTELLIGENCE CENTER
=================================

Server:
{server}

Analysis Time:
{datetime.now()}

Evidence:
{latest_evidence}

Evidence Size:
{evidence_size:,} characters


PRIMARY RCA
===========

Root Cause:
{root_cause}

Confidence:
{confidence}

Health Score:
{health_score}

Kdump:
{kdump_status}

VMcore:
{vmcore_status}


RCA AUTHORITY
=============

Primary RCA Engine:
LOCAL RULE ENGINE

AI Role:
EXPLANATION / CORRELATION ONLY

AI MAY NOT OVERRIDE LOCAL RCA.


LOCAL RULE REPORT
=================

{rule_report}


AI ANALYSIS
===========

{ai_response}


FINAL DECISION
==============

The Local Rule Engine is the authoritative source
for the primary reboot RCA.

Gemini AI is used only to provide additional
explanation and contextual analysis.

Evidence was preserved separately.
"""


with open(
    final_report,
    "w",
) as f:

    f.write(
        report_content.strip()
    )


# ============================================================
# REPORT UI
# ============================================================

console.print()

report_table = Table(
    box=box.ROUNDED,
    show_header=False,
    border_style="green",
)

report_table.add_column(
    "FIELD",
    style="bold cyan",
)

report_table.add_column(
    "VALUE",
)


report_table.add_row(
    "Status",
    "[bold green]✓ FINAL RCA REPORT GENERATED[/bold green]",
)

report_table.add_row(
    "Report",
    final_report,
)

report_table.add_row(
    "Evidence",
    latest_evidence,
)

report_table.add_row(
    "Primary Engine",
    "LOCAL RULE ENGINE",
)

report_table.add_row(
    "AI",
    "Gemini Explanation Layer",
)

report_table.add_row(
    "RCA Authority",
    "LOCAL RULE ENGINE",
)

report_table.add_row(
    "Kdump",
    kdump_status,
)

report_table.add_row(
    "VMcore",
    vmcore_status,
)


console.print(
    Panel(
        report_table,
        title="FINAL REPORT",
        border_style="green",
    )
)


# ============================================================
# FOOTER
# ============================================================

console.print()

console.print(
    Panel.fit(
        "[bold cyan]LINUX REBOOT INTELLIGENCE CENTER[/bold cyan]\n"
        "[white]AI + Deterministic Local RCA[/white]\n"
        "[dim]LOCAL RULES = SOURCE OF TRUTH | AI = EXPLANATION[/dim]",
        border_style="cyan",
        padding=(1, 4),
    )
)

console.print()
