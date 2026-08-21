#!/usr/bin/env python3
"""
LINUX AI REBOOT RCA ENGINE
Enterprise-style Rich UI for evidence -> AI -> local fallback -> RCA -> health.

Usage:
    python3 scripts/analyze_RCA_AI.py

Requirements:
    pip install rich python-dotenv google-genai
"""

import os
import re
import json
import glob
import time
import textwrap
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.columns import Columns
from rich.text import Text
from rich import box

# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

BASE_DIR = os.path.expanduser("~/linux-rcc-ai")
EVIDENCE_DIR = os.path.join(BASE_DIR, "logs", "evidence")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(REPORT_DIR, exist_ok=True)

load_dotenv(os.path.join(BASE_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

console = Console()

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def clean_rich(value):
    """Prevent evidence text containing [tags] from breaking Rich markup."""
    return str(value).replace("[", "\\[").replace("]", "\\]")


def safe_read(path):
    try:
        with open(path, "r", errors="ignore") as f:
            return f.read()
    except Exception as exc:
        return f"ERROR READING FILE: {exc}"


def latest_evidence():
    files = glob.glob(os.path.join(EVIDENCE_DIR, "ai_evidence_*.txt"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def get_hostname(evidence):
    m = re.search(r"^Hostname:\s*(.+)$", evidence, re.MULTILINE)
    return m.group(1).strip() if m else os.uname().nodename


def section(evidence, title):
    """Extract a named evidence section with flexible heading formatting."""
    pattern = (
        rf"###\s*{re.escape(title)}\s*###"
        rf"(?:\s*\n-+)?\s*\n"
        rf"(.*?)(?=\n###|\Z)"
    )
    m = re.search(pattern, evidence, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def status_from_text(text, positive_patterns):
    low = text.lower()
    return any(re.search(p, low) for p in positive_patterns)


def first_match(text, patterns):
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return ""


def wrap(text, width=88):
    return "\n".join(textwrap.wrap(str(text), width=width))


def detect_local_facts(evidence):
    """
    Deterministic observations used only to prepare the AI explanation.

    IMPORTANT:
    The production Local Rule Engine (local_rule_rca.py) remains the
    authoritative RCA source. These facts are deliberately conservative:
    a missing evidence section is NOT treated as evidence that an event
    occurred.
    """
    facts = {}

    # -------------------------------------------------------------
    # Reboot commands
    # -------------------------------------------------------------
    reboot_block = (
        section(evidence, "REBOOT / SHUTDOWN")
        or section(evidence, "REBOOT")
        or evidence
    )

    facts["manual_reboot"] = bool(re.search(
        r"(?:sudo|audit).*COMMAND\s*=\s*"
        r"(?:/usr/sbin/reboot|/sbin/reboot|/usr/bin/reboot|"
        r"/usr/sbin/shutdown\s+(?:-r|--reboot)|"
        r"/sbin/shutdown\s+(?:-r|--reboot)|"
        r"/usr/bin/shutdown\s+(?:-r|--reboot)|"
        r"/usr/bin/systemctl\s+reboot|/bin/systemctl\s+reboot)\b",
        reboot_block,
        re.IGNORECASE,
    ))

    # Do NOT search the entire evidence for the words "cron" and "reboot".
    # That creates false positives from explanations/configuration text.
    cron_block = (
        section(evidence, "CRON")
        or section(evidence, "CRON REBOOT")
        or ""
    )

    facts["cron_reboot"] = bool(re.search(
        r"(?:COMMAND\s*=\s*)?"
        r"(?:/usr/sbin/reboot|/sbin/reboot|/usr/bin/reboot|"
        r"/usr/sbin/shutdown\s+(?:-r|--reboot)|"
        r"/sbin/shutdown\s+(?:-r|--reboot)|"
        r"/usr/bin/shutdown\s+(?:-r|--reboot)|"
        r"/usr/bin/systemctl\s+reboot|/bin/systemctl\s+reboot)\b",
        cron_block,
        re.IGNORECASE,
    ))

    # If there is no dedicated CRON section, only accept a same-line
    # cron + explicit command evidence. Never accept prose such as
    # "cron reboot" from an AI/report section.
    if not facts["cron_reboot"]:
        facts["cron_reboot"] = bool(re.search(
            r"(?m)^(?!.*(?:AI|INTERPRETATION|SUMMARY|REPORT)).*"
            r"\bcron(?:d)?\b.*COMMAND\s*=\s*"
            r"(?:/usr/sbin/reboot|/sbin/reboot|/usr/bin/reboot|"
            r"/usr/sbin/shutdown\s+(?:-r|--reboot)|"
            r"/sbin/shutdown\s+(?:-r|--reboot)|"
            r"/usr/bin/shutdown\s+(?:-r|--reboot)|"
            r"/usr/bin/systemctl\s+reboot|/bin/systemctl\s+reboot)\b",
            evidence,
            re.IGNORECASE,
        ))

    # -------------------------------------------------------------
    # Kernel panic / OOPS
    # -------------------------------------------------------------
    panic_block = (
        section(evidence, "KERNEL PANIC / OOPS")
        or section(evidence, "FILTERED KERNEL PANIC / OOPS")
        or ""
    )

    facts["panic"] = bool(re.search(
        r"kernel panic\s*[-:]|not syncing:|panic:\s*not syncing|panic occurred",
        panic_block,
        re.IGNORECASE,
    ))

    facts["oops"] = bool(re.search(
        r"\bOops:\s+\d+|kernel oops|BUG:\s+unable to handle|BUG:\s+kernel",
        panic_block,
        re.IGNORECASE,
    ))

    # -------------------------------------------------------------
    # Specific failure categories
    # -------------------------------------------------------------
    facts["oom"] = bool(re.search(
        r"out of memory|out-of-memory|oom-killer|"
        r"killed process\s+\d+.*(?:out of memory|oom)|oom_reaper",
        section(evidence, "OOM / MEMORY"),
        re.IGNORECASE,
    ))

    facts["hardware"] = bool(re.search(
        r"hardware error|machine check exception|\bmce:\s|"
        r"edac.*error|ecc.*error|uncorrected.*error",
        section(evidence, "HARDWARE"),
        re.IGNORECASE,
    ))

    facts["storage"] = bool(re.search(
        r"I/O error|I/O failure|blk_update_request.*error|"
        r"buffer I/O error|nvme.*error|scsi.*error",
        section(evidence, "STORAGE / I/O"),
        re.IGNORECASE,
    ))

    facts["filesystem"] = bool(re.search(
        r"filesystem error|EXT4-fs error|XFS.*error|remounting.*read-only",
        section(evidence, "FILESYSTEM"),
        re.IGNORECASE,
    ))

    facts["watchdog"] = bool(re.search(
        r"soft lockup|hard lockup|hung task|watchdog.*lockup",
        section(evidence, "WATCHDOG / LOCKUP"),
        re.IGNORECASE,
    ))

    facts["systemd_failure"] = bool(re.search(
        r"failed to start|dependency failed|start job failed",
        section(evidence, "SYSTEMD FAILURE"),
        re.IGNORECASE,
    ))

    # -------------------------------------------------------------
    # Kdump
    # -------------------------------------------------------------
    kdump = (
        section(evidence, "KDUMP SERVICE")
        + "\n"
        + section(evidence, "KDUMP CONFIGURATION")
    )

    facts["kdump_ready"] = bool(re.search(
        r"ready to kdump|current state:\s*ready",
        kdump,
        re.IGNORECASE,
    ))

    # Ubuntu kdump-tools commonly uses dump.<timestamp> and dmesg.<timestamp>.
    crash = (
        section(evidence, "VMCORE / CRASH FILES")
        or section(evidence, "CRASH / VMCORE FILES")
        or ""
    )

    vmcore_patterns = [
        r"/var/crash/.*/vmcore(?:\s|$)",
        r"/var/crash/.*/vmcore\.[0-9]+(?:\s|$)",
        r"/var/crash/.*/vmcore-dmesg(?:\s|$)",
        r"/var/crash/.*/dump\.[0-9]+(?:\s|$)",
        r"/var/crash/.*/dmesg\.[0-9]+(?:\s|$)",
    ]

    facts["vmcore"] = any(
        re.search(p, crash, re.IGNORECASE | re.MULTILINE)
        for p in vmcore_patterns
    )

    # Very narrow fallback for collectors that changed the section heading.
    if not facts["vmcore"]:
        facts["vmcore"] = bool(re.search(
            r"/var/crash/[^ \n]+/(?:dump|dmesg)\.[0-9]+(?:\s|$)",
            evidence,
            re.IGNORECASE,
        ))

    facts["kdump_crash_dump"] = facts["vmcore"]

    # A generated crash dump is strong evidence of a crash path even when
    # the original panic string was not preserved in the text logs.
    if facts["kdump_crash_dump"]:
        facts["panic"] = True

    facts["recurring"] = detect_recurring_reboot(evidence)

    return facts

def detect_recurring_reboot(evidence):
    block = section(evidence, "LAST REBOOTS")
    times = []

    for line in block.splitlines():
        # Common `last -x` format:
        # reboot system boot ... Thu Aug 20 15:02
        m = re.search(
            r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
            r"\d{1,2}\s+(\d{2}:\d{2})",
            line,
        )
        if m:
            times.append(m.group(1))

    # Conservative: only report recurring if there are several reboot entries.
    return len(times) >= 3


def health_score(facts):
    score = 100
    impacts = []

    penalties = [
        ("panic", 30, "Kernel panic detected"),
        ("oops", 25, "Kernel OOPS detected"),
        ("oom", 20, "OOM / memory exhaustion detected"),
        ("hardware", 30, "Hardware / MCE / ECC error detected"),
        ("storage", 25, "Storage / I/O error detected"),
        ("filesystem", 20, "Filesystem error detected"),
        ("watchdog", 25, "Watchdog / lockup detected"),
        ("systemd_failure", 15, "Systemd failure detected"),
    ]

    for key, points, label in penalties:
        if facts.get(key):
            score -= points
            impacts.append((label, points))

    if facts.get("manual_reboot") or facts.get("cron_reboot"):
        score -= 5
        impacts.append(("Recent reboot detected", 5))

    if facts.get("recurring"):
        score -= 10
        impacts.append(("Recurring reboot pattern", 10))

    if not facts.get("kdump_ready"):
        score -= 5
        impacts.append(("Kdump not ready", 5))

    if facts.get("panic") and not facts.get("vmcore"):
        score -= 5
        impacts.append(("Kernel panic occurred but VMcore unavailable", 5))

    score = max(0, min(100, score))

    if score >= 90:
        status = "HEALTHY"
    elif score >= 75:
        status = "GOOD"
    elif score >= 50:
        status = "WARNING"
    elif score >= 25:
        status = "CRITICAL"
    else:
        status = "SEVERE"

    return score, status, impacts


def local_rca(facts):
    # A crash dump is strong evidence that the previous boot entered
    # the Kdump crash path. Prefer an explicit panic signature when
    # available; otherwise classify the event as a kernel crash only
    # when the local evidence proves a crash dump was generated.
    if facts["panic"] or facts.get("kdump_crash_dump"):
        cause = "Kernel Panic"
        detail = (
            "The reboot is associated with a kernel panic signature in the "
            "previous-boot evidence."
        )
        confidence = "HIGH"
    elif facts["hardware"]:
        cause = "Hardware Error"
        detail = (
            "The evidence contains hardware/MCE/ECC/EDAC error signatures "
            "before the reboot."
        )
        confidence = "HIGH"
    elif facts["oom"]:
        cause = "OOM / Memory Exhaustion"
        detail = (
            "The previous boot contains an out-of-memory condition or OOM-killer "
            "activity associated with the incident."
        )
        confidence = "HIGH"
    elif facts["storage"]:
        cause = "Storage / I/O Error"
        detail = (
            "The evidence contains storage or I/O error signatures associated "
            "with the previous boot."
        )
        confidence = "HIGH"
    elif facts["filesystem"]:
        cause = "Filesystem Error"
        detail = (
            "The evidence contains filesystem error signatures associated "
            "with the reboot."
        )
        confidence = "HIGH"
    elif facts["watchdog"]:
        cause = "Watchdog / Lockup"
        detail = (
            "The evidence contains watchdog, lockup, or hung-task signatures "
            "associated with the incident."
        )
        confidence = "HIGH"
    elif facts["cron_reboot"]:
        cause = "Cron Scheduled Reboot"
        detail = (
            "The evidence contains a cron execution path that explicitly "
            "invoked a reboot command."
        )
        confidence = "HIGH"
    elif facts["manual_reboot"]:
        cause = "Manual / Planned Reboot"
        detail = (
            "The evidence contains a sudo/user-session reboot command, "
            "followed by a normal systemd reboot sequence."
        )
        confidence = "HIGH"
    elif facts["systemd_failure"]:
        cause = "Systemd / Service Failure"
        detail = (
            "The evidence contains systemd service/dependency failures, "
            "but the reboot cause cannot be established with the same "
            "confidence as a direct reboot command."
        )
        confidence = "MEDIUM"
    else:
        cause = "Unknown"
        detail = (
            "The exact cause of the reboot could not be determined from "
            "the available evidence."
        )
        confidence = "LOW"

    if facts["cron_reboot"]:
        reboot_type = "CRON"
    elif facts["manual_reboot"]:
        reboot_type = "MANUAL"
    else:
        reboot_type = "UNKNOWN"

    return {
        "probable_root_cause": cause,
        "cause_of_reboot": detail,
        "reboot_type": reboot_type,
        "confidence": confidence,
    }


def extract_json(text):
    """Extract the first JSON object from an AI response."""
    text = text.strip()

    # Remove fenced JSON if present.
    text = re.sub(r"^```json\s*", "", text, flags=re.I)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None

    return None


def ask_gemini(evidence, facts, authoritative_rca):
    """
    Gemini is an explanation/correlation layer only.

    The local rule engine supplies the authoritative RCA. Gemini is
    explicitly prohibited from changing it or inventing an exact
    subsystem/root cause that the evidence does not prove.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Give the model compact, high-value evidence instead of relying on
    # it to discover the RCA inside a large raw file.
    evidence_sections = {
        "kernel_panic_oops": section(evidence, "KERNEL PANIC / OOPS"),
        "filtered_kernel_panic_oops": section(evidence, "FILTERED KERNEL PANIC / OOPS"),
        "reboot_shutdown": section(evidence, "REBOOT / SHUTDOWN"),
        "kdump_service": section(evidence, "KDUMP SERVICE"),
        "kdump_configuration": section(evidence, "KDUMP CONFIGURATION"),
        "crash_vmcore_files": (
            section(evidence, "VMCORE / CRASH FILES")
            or section(evidence, "CRASH / VMCORE FILES")
        ),
        "hardware": section(evidence, "HARDWARE"),
        "storage_io": section(evidence, "STORAGE / I/O"),
        "filesystem": section(evidence, "FILESYSTEM"),
        "oom_memory": section(evidence, "OOM / MEMORY"),
        "watchdog": section(evidence, "WATCHDOG / LOCKUP"),
        "systemd": section(evidence, "SYSTEMD FAILURE"),
    }

    prompt = f"""
You are an evidence-based Linux incident RCA explanation analyst.

CRITICAL AUTHORITY RULE:
The Local Rule Engine is the authoritative RCA source.
You MUST NOT change, downgrade, or replace its primary RCA.

AUTHORITATIVE LOCAL RCA:
{json.dumps(authoritative_rca, indent=2)}

DETERMINISTIC FACTS:
{json.dumps(facts, indent=2)}

Your job is ONLY to explain and correlate the authoritative result.

Accuracy requirements:
1. Use only facts supported by the supplied evidence.
2. Never invent a kernel subsystem, driver, hardware component, process,
   user, command, timestamp, or failure mechanism.
3. Do not call warnings/noise a root cause.
4. Distinguish:
   - direct evidence,
   - strong correlation,
   - possible contributing factor.
5. If the exact underlying subsystem is not proven, explicitly say:
   "The exact failing subsystem is not established by the available evidence."
6. If Kdump generated dump.<timestamp> or vmcore, call it a crash dump.
   Do NOT claim a literal file named vmcore exists unless the evidence
   actually shows that filename.
7. Kdump READY means the capture mechanism is configured/ready.
   VMCORE AVAILABLE means a crash dump file was found.
8. Do not infer that Kdump caused the reboot. It captures the crash.
9. Do not infer a planned/manual reboot from normal shutdown/startup text.
10. Do not treat words appearing in this prompt, report formatting, or
    explanatory text as incident evidence.
11. Do not claim a cron reboot unless an explicit cron-triggered reboot
    command is present in the supplied evidence.
12. Do not claim a watchdog/lockup unless an actual soft-lockup, hard-lockup,
    hung-task, or equivalent watchdog event is present in the supplied
    evidence.
13. Do not claim a literal "vmcore" filename when Ubuntu evidence shows
    dump.<timestamp>/dmesg.<timestamp>; call those files a crash dump.
14. The primary RCA MUST exactly match the Local Rule Engine's
    authoritative root cause.

Return ONLY valid JSON:

{{
  "final_summary": "3-5 sentences suitable for an incident ticket",
  "primary_rca": "{authoritative_rca.get('probable_root_cause', 'Unknown')}",
  "why": "2-4 sentences explaining why the authoritative RCA is supported",
  "confidence_note": "What is proven and what remains unproven",
  "supporting_evidence": [
    "up to 5 concise evidence statements; quote/paraphrase only supplied evidence"
  ],
  "contributing_factors": [
    "0-3 items; use an empty list when none are supported"
  ],
  "kdump_vmcore_summary": "Accurate Kdump/VMcore status and what it means",
  "recommended_investigation": [
    "up to 4 concrete SA investigation steps"
  ]
}}

AUTHORITATIVE RCA MUST REMAIN:
{authoritative_rca.get('probable_root_cause', 'Unknown')}

SELECTED EVIDENCE:
{json.dumps(evidence_sections, indent=2)}

Do not output markdown fences.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    parsed = extract_json(response.text)

    if not parsed:
        raise RuntimeError("Gemini returned non-JSON RCA explanation")

    # Hard validation: AI cannot override the local RCA.
    parsed["primary_rca"] = authoritative_rca.get(
        "probable_root_cause",
        "Unknown",
    )

    return parsed


# ---------------------------------------------------------------------
# Deterministic supporting evidence / summary fallback
# ---------------------------------------------------------------------

def build_supporting_evidence(evidence, facts, rca):
    """Build ticket-ready evidence without relying on Gemini."""
    items = []
    cause = rca.get("probable_root_cause", "Unknown")

    if cause == "Kernel Panic":
        if facts.get("panic"):
            items.append("Previous-boot kernel evidence contains a kernel panic / not-syncing signature.")
        if facts.get("kdump_ready"):
            items.append("Kdump service is READY and configured with a crash kernel.")
        if facts.get("vmcore"):
            crash = section(evidence, "VMCORE / CRASH FILES") or section(evidence, "CRASH / VMCORE FILES")
            m = re.search(r"(/var/crash/[^\s]+/(?:dump|dmesg)\.[0-9]+)", crash, re.I)
            if m:
                items.append(f"Kdump crash-dump evidence was found: {m.group(1)}.")
            else:
                items.append("A Kdump crash-dump file was found under /var/crash.")
        if not facts.get("hardware"):
            items.append("No hardware MCE/ECC/EDAC error was detected by the local rules.")
        if not facts.get("oom"):
            items.append("No OOM / memory-exhaustion event was detected by the local rules.")

    elif cause == "Hardware Error":
        items.append("Hardware/MCE/ECC/EDAC error signatures were detected in the evidence.")
        if facts.get("kdump_ready"):
            items.append("Kdump is READY for crash capture.")
    elif cause == "OOM / Memory Exhaustion":
        items.append("OOM-killer or out-of-memory evidence was detected before the reboot.")
    elif cause == "Storage / I/O Error":
        items.append("Storage/I/O error signatures were detected in the evidence.")
    elif cause == "Filesystem Error":
        items.append("Filesystem error signatures were detected in the evidence.")
    elif cause == "Watchdog / Lockup":
        items.append("Actual soft-lockup, hard-lockup, hung-task, or watchdog evidence was detected.")
    elif cause == "Cron Scheduled Reboot":
        items.append("An explicit cron execution path invoked a reboot/shutdown command.")
    elif cause == "Manual / Planned Reboot":
        items.append("A sudo/user-session reboot command was detected in the evidence.")
    elif cause == "Systemd / Service Failure":
        items.append("Systemd service/dependency failure signatures were detected.")

    if facts.get("recurring"):
        items.append("Multiple reboot entries indicate a recurring reboot pattern.")

    return items[:5]


def deterministic_summary(facts, rca):
    """Accurate fallback summary when Gemini is unavailable."""
    cause = rca.get("probable_root_cause", "Unknown")
    if cause == "Kernel Panic":
        s = "The server reboot is associated with a kernel panic detected in the previous-boot evidence."
        if facts.get("vmcore"):
            s += " Kdump captured the crash state and a crash-dump file is available for post-mortem analysis."
        elif facts.get("kdump_ready"):
            s += " Kdump is configured and ready, but no crash-dump file was found for this incident."
        s += " The available evidence does not establish the exact failing kernel subsystem or driver."
        return s
    return rca.get("cause_of_reboot", "The exact cause could not be determined from the available evidence.")

# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------

console.clear()

console.print(
    Panel.fit(
        "[bold cyan]LINUX AI REBOOT RCA ENGINE[/bold cyan]\n"
        "[white]Enterprise Linux Incident Investigation Platform[/white]\n\n"
        "[dim]Evidence → Timeline → AI Correlation → RCA → Health[/dim]",
        border_style="cyan",
        padding=(1, 5),
    )
)

console.print()

evidence_file = latest_evidence()

if not evidence_file:
    console.print(
        Panel(
            "[bold red]No evidence file found.[/bold red]\n\n"
            "Run collect_evidence.py first.",
            title="ERROR",
            border_style="red",
        )
    )
    raise SystemExit(1)

evidence = safe_read(evidence_file)
server = get_hostname(evidence)
facts = detect_local_facts(evidence)

# ---------------------------------------------------------------------
# Evidence inventory
# ---------------------------------------------------------------------

inventory = [
    ("System Information", True, "Hostname / OS / system state"),
    ("Previous Boot Journal", bool(section(evidence, "BOOT HISTORY") or evidence), "Previous boot evidence"),
    ("Kernel Events", bool(section(evidence, "KERNEL PANIC / OOPS")), "Kernel crash signatures"),
    ("OOM / Memory", bool(section(evidence, "OOM / MEMORY")), "Memory exhaustion"),
    ("Hardware / MCE / ECC", bool(section(evidence, "HARDWARE")), "Hardware events"),
    ("Storage / I/O", bool(section(evidence, "STORAGE / I/O")), "Disk and controller events"),
    ("Filesystem", bool(section(evidence, "FILESYSTEM")), "Filesystem errors"),
    ("Watchdog / Lockup", bool(section(evidence, "WATCHDOG / LOCKUP")), "Lockups and hung tasks"),
    ("Network", bool(section(evidence, "NETWORK")), "Network events"),
    ("Systemd", bool(section(evidence, "SYSTEMD FAILURE")), "Service/dependency events"),
    ("Reboot / Shutdown", bool(section(evidence, "REBOOT / SHUTDOWN")), "Reboot sequence"),
    ("Kdump Service", bool(section(evidence, "KDUMP SERVICE")), "Kdump state"),
    ("Kdump Configuration", bool(section(evidence, "KDUMP CONFIGURATION")), "Crashkernel/kexec state"),
    ("VMcore / Crash Files", bool(section(evidence, "VMCORE / CRASH FILES") or section(evidence, "CRASH / VMCORE FILES")), "Crash dump availability"),
    ("Memory / Disk State", bool(section(evidence, "MEMORY STATUS AFTER BOOT") or section(evidence, "DISK STATUS AFTER BOOT")), "Current resource state"),
]

# Animated collection display
console.print(
    Panel(
        "[bold]Scanning collected evidence categories...[/bold]",
        title="EVIDENCE COLLECTION",
        border_style="blue",
    )
)

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    console=console,
) as progress:
    task = progress.add_task("Validating evidence", total=len(inventory))
    for name, available, desc in inventory:
        time.sleep(0.04)
        progress.update(
            task,
            description=f"[cyan]Checking[/cyan] {name}",
        )
        progress.advance(task)

console.print()

evidence_table = Table(
    title="COLLECTED LINUX EVIDENCE",
    box=box.ROUNDED,
    header_style="bold cyan",
    expand=True,
)

evidence_table.add_column("#", justify="right", width=3)
evidence_table.add_column("Evidence Source")
evidence_table.add_column("Status", width=18)
evidence_table.add_column("Purpose")

for idx, (name, available, desc) in enumerate(inventory, 1):
    status = "[green]✓ COLLECTED[/green]" if available else "[yellow]⚠ UNAVAILABLE[/yellow]"
    evidence_table.add_row(str(idx), name, status, desc)

console.print(evidence_table)
console.print()

# ---------------------------------------------------------------------
# Kdump dashboard
# ---------------------------------------------------------------------

kdump_status = "READY" if facts["kdump_ready"] else "NOT READY"
vmcore_status = "AVAILABLE" if facts["vmcore"] else "NOT AVAILABLE"

kdump_color = "green" if facts["kdump_ready"] else "yellow"
vmcore_color = "green" if facts["vmcore"] else "yellow"

kdump_table = Table(
    title="KDUMP / CRASH ANALYSIS",
    box=box.ROUNDED,
    header_style="bold cyan",
    expand=True,
)
kdump_table.add_column("Component")
kdump_table.add_column("Status")
kdump_table.add_column("Interpretation")

kdump_table.add_row(
    "Kdump Service",
    f"[bold {kdump_color}]{kdump_status}[/bold {kdump_color}]",
    "Crash capture framework state",
)
kdump_table.add_row(
    "Crashkernel",
    "[green]CONFIGURED[/green]" if "crashkernel=" in evidence else "[yellow]NOT DETECTED[/yellow]",
    "Reserved crash kernel memory",
)
kdump_table.add_row(
    "Kdump Kernel",
    "[green]AVAILABLE[/green]" if "/var/lib/kdump/vmlinuz" in evidence else "[yellow]NOT AVAILABLE[/yellow]",
    "Capture kernel",
)
kdump_table.add_row(
    "Kdump Initrd",
    "[green]AVAILABLE[/green]" if "/var/lib/kdump/initrd.img" in evidence else "[yellow]NOT AVAILABLE[/yellow]",
    "Capture initramfs",
)
kdump_table.add_row(
    "VMcore",
    f"[bold {vmcore_color}]{vmcore_status}[/bold {vmcore_color}]",
    (
        "Crash dump found for analysis"
        if facts["vmcore"]
        else "No VMcore found for this incident"
    ),
)

if facts["kdump_ready"] and facts["vmcore"]:
    kdump_explanation = (
        "[bold green]Kdump is READY.[/bold green] A crash-dump file was "
        "found for this incident. The dump should be analyzed to identify "
        "the exact failing kernel path or subsystem."
    )
elif facts["kdump_ready"]:
    kdump_explanation = (
        "[bold green]Kdump is READY.[/bold green] No crash dump was found "
        "for this incident."
    )
else:
    kdump_explanation = (
        "[bold yellow]Kdump is NOT READY.[/bold yellow] Crash-dump capture "
        "may not be available for a future kernel crash."
    )

console.print(
    Columns(
        [
            kdump_table,
            Panel(
                kdump_explanation,
                title="INTERPRETATION",
                border_style=kdump_color,
                padding=(1, 2),
            ),
        ],
        expand=True,
    )
)
console.print()

# ---------------------------------------------------------------------
# Local deterministic facts
# ---------------------------------------------------------------------

fact_table = Table(
    title="ROOT CAUSE SIGNAL MATRIX",
    box=box.SIMPLE_HEAVY,
    header_style="bold cyan",
    expand=True,
)
fact_table.add_column("Check")
fact_table.add_column("Result")
fact_table.add_column("Meaning")

checks = [
    ("Kernel Panic", facts["panic"], "Crash signature"),
    ("Kernel OOPS", facts["oops"], "Kernel exception"),
    ("OOM", facts["oom"], "Memory exhaustion"),
    ("Hardware", facts["hardware"], "MCE/ECC/EDAC"),
    ("Storage / I/O", facts["storage"], "Disk/controller errors"),
    ("Filesystem", facts["filesystem"], "Filesystem failure"),
    ("Watchdog", facts["watchdog"], "Lockup/hung task"),
    ("Systemd Failure", facts["systemd_failure"], "Service/dependency failure"),
    ("Manual Reboot", facts["manual_reboot"], "Direct reboot command"),
    ("Cron Reboot", facts["cron_reboot"], "Scheduled reboot command"),
]

for name, detected, meaning in checks:
    result = "[bold red]DETECTED[/bold red]" if detected else "[green]CLEAR[/green]"
    fact_table.add_row(name, result, meaning)

console.print(fact_table)
console.print()

# ---------------------------------------------------------------------
# AI analysis
# ---------------------------------------------------------------------

console.print(
    Panel(
        "[bold]Gemini will correlate evidence, timestamps, reboot commands, "
        "kernel events, hardware, memory, storage, systemd, cron, kdump "
        "and crash-dump state.[/bold]\n\n"
        f"Model: [cyan]{clean_rich(GEMINI_MODEL)}[/cyan]\n"
        f"Evidence: [cyan]{len(evidence):,} characters[/cyan]\n"
        "Local Rule Engine remains authoritative; Gemini only explains its result.",
        title="AI INVESTIGATION",
        border_style="magenta",
    )
)

ai_result = None
ai_error = None

if GEMINI_API_KEY:
    with console.status(
        "[bold magenta]Gemini AI is correlating Linux evidence...[/bold magenta]",
        spinner="dots",
    ):
        try:
            # Build deterministic RCA first so Gemini receives the
            # authoritative classification as an immutable input.
            _authoritative_for_ai = local_rca(facts)
            ai_result = ask_gemini(
                evidence,
                facts,
                _authoritative_for_ai,
            )
        except Exception as exc:
            ai_error = str(exc)
            if "429" in ai_error or "RESOURCE_EXHAUSTED" in ai_error or "quota" in ai_error.lower():
                ai_error = (
                    "Gemini API quota exhausted. The Local Rule Engine remains authoritative; "
                    "deterministic supporting evidence and the final incident summary are still generated."
                )
else:
    ai_error = "GEMINI_API_KEY is not configured"

console.print()

# The Local Rule Engine ALWAYS owns the RCA.
authoritative_rca = local_rca(facts)
rca = authoritative_rca

if ai_result:
    analysis_mode = "LOCAL RCA + GEMINI EXPLANATION"
    ai_explanation = ai_result
    console.print(
        Panel(
            "[bold green]✓ Gemini explanation completed[/bold green]\n\n"
            f"Model: {clean_rich(GEMINI_MODEL)}\n"
            "Role: Explanation / Correlation only\n"
            "RCA Authority: Local Rule Engine",
            title="AI STATUS",
            border_style="green",
        )
    )
else:
    analysis_mode = "LOCAL RULE ENGINE"
    ai_explanation = {}

    console.print(
        Panel(
            "[bold yellow]⚠ Gemini unavailable — local RCA remains authoritative[/bold yellow]\n\n"
            f"Reason: {clean_rich(ai_error)}\n\n"
            "The deterministic local rule engine analyzed the evidence.",
            title="AI STATUS",
            border_style="yellow",
        )
    )

# ---------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------

score, health_status, impacts = health_score(facts)

status_style = {
    "HEALTHY": "green",
    "GOOD": "green",
    "WARNING": "yellow",
    "CRITICAL": "dark_orange",
    "SEVERE": "red",
}.get(health_status, "yellow")

bar_len = 42
filled = round(score / 100 * bar_len)
health_bar = "█" * filled + "░" * (bar_len - filled)

console.print(
    Panel(
        f"[bold white]{score} / 100[/bold white]\n\n"
        f"[bold {status_style}]{health_bar}[/bold {status_style}]\n\n"
        f"[bold {status_style}]● {health_status}[/bold {status_style}]",
        title="SERVER HEALTH",
        border_style=status_style,
        padding=(1, 4),
    )
)

if impacts:
    impact_table = Table(
        title="HEALTH IMPACT",
        box=box.ROUNDED,
        header_style="bold cyan",
        expand=True,
    )
    impact_table.add_column("Issue")
    impact_table.add_column("Impact", justify="right")

    for issue, points in impacts:
        impact_table.add_row(
            issue,
            f"[bold red]-{points}[/bold red]",
        )

    console.print(impact_table)
else:
    console.print(
        Panel(
            "[bold green]✓ No health-impacting events detected.[/bold green]",
            title="HEALTH IMPACT",
            border_style="green",
        )
    )

console.print()

# ---------------------------------------------------------------------
# Supporting evidence
# ---------------------------------------------------------------------

supporting = build_supporting_evidence(evidence, facts, rca)

# AI may add evidence, but it cannot replace deterministic evidence.
if ai_result and isinstance(ai_explanation, dict):
    for item in ai_explanation.get("supporting_evidence", []):
        item = str(item).strip()
        if item and item not in supporting and len(supporting) < 5:
            supporting.append(item)

support_table = Table(
    title="SUPPORTING EVIDENCE",
    box=box.ROUNDED,
    header_style="bold cyan",
    expand=True,
)
support_table.add_column("#", width=4, justify="right")
support_table.add_column("Evidence")

if supporting:
    for i, line in enumerate(supporting[:5], 1):
        support_table.add_row(str(i), clean_rich(line))
else:
    support_table.add_row("1", "No concise supporting evidence returned.")

console.print(support_table)
console.print()

# ---------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------

timeline_lines = []

for line in evidence.splitlines():
    if re.search(
        r"COMMAND=.*reboot|system will reboot|system is rebooting|"
        r"shutdown\.target|reboot\.target|systemd-reboot",
        line,
        re.IGNORECASE,
    ):
        timeline_lines.append(line.strip())

timeline_table = Table(
    title="REBOOT TIMELINE",
    box=box.ROUNDED,
    header_style="bold cyan",
    expand=True,
)
timeline_table.add_column("Time", width=12)
timeline_table.add_column("Event")
timeline_table.add_column("Type", width=12)

for line in timeline_lines[-12:]:
    tm = re.search(r"\b(\d{2}:\d{2}:\d{2})\b", line)
    tm_value = tm.group(1) if tm else "--:--:--"

    if re.search(r"COMMAND=.*reboot|sudo.*reboot", line, re.I):
        typ = "MANUAL"
    elif re.search(r"cron", line, re.I):
        typ = "CRON"
    else:
        typ = "SYSTEMD"

    timeline_table.add_row(
        tm_value,
        clean_rich(line),
        typ,
    )

if timeline_lines:
    console.print(timeline_table)
    console.print()

# ---------------------------------------------------------------------
# RCA and recommendations
# ---------------------------------------------------------------------

cause = rca.get(
    "cause_of_reboot",
    "The exact cause could not be determined from the available evidence.",
)

root_cause = rca.get(
    "probable_root_cause",
    "Unknown",
)

confidence = rca.get("confidence", "UNKNOWN")

if ai_result:
    recs = ai_explanation.get("recommended_investigation", [])
    recommendation = (
        " ".join(str(x) for x in recs[:4])
        if recs
        else "Validate the authoritative Local Rule Engine RCA and investigate the supporting evidence."
    )
else:
    if root_cause == "Manual / Planned Reboot":
        recommendation = (
            "Verify the reboot against the approved change or maintenance "
            "window and confirm it was authorized."
        )
    elif root_cause == "Cron Scheduled Reboot":
        recommendation = (
            "Review root/user crontabs and confirm the scheduled reboot "
            "was authorized."
        )
    elif root_cause == "Kernel Panic":
        recommendation = (
            "Review kernel logs and VMcore if available; verify kdump "
            "configuration for future crash analysis."
        )
    else:
        recommendation = (
            "Review the supporting evidence and validate the probable RCA "
            "before updating or closing the incident."
        )

final_summary = (
    clean_rich(ai_explanation.get("final_summary", "")).strip()
    if ai_result and isinstance(ai_explanation, dict)
    else ""
)

# Never leave the incident without a useful summary when Gemini is unavailable.
if not final_summary:
    final_summary = clean_rich(deterministic_summary(facts, rca))

console.print(
    Panel(
        wrap(final_summary, 100),
        title="AI FINAL SUMMARY — EXPLANATION ONLY" if ai_result else "FINAL INCIDENT SUMMARY — LOCAL FALLBACK",
        border_style="magenta" if ai_result else "blue",
        padding=(1, 2),
    )
)
console.print()

console.print(
    Panel(
        f"[bold]Probable Root Cause:[/bold] {clean_rich(root_cause)}\n"
        f"[bold]Confidence:[/bold] {clean_rich(confidence)}\n"
        f"[bold]Analysis Mode:[/bold] {clean_rich(analysis_mode)}\n\n"
        f"{wrap(clean_rich(cause), 100)}",
        title="FINAL RCA",
        border_style="red" if root_cause != "Manual / Planned Reboot" else "green",
        padding=(1, 2),
    )
)

console.print(
    Panel(
        wrap(clean_rich(recommendation), 100),
        title="RECOMMENDED ACTION",
        border_style="blue",
    )
)

# ---------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
report_prefix = "RCA_AI" if ai_result else "RCA_RULE"
report_file = os.path.join(
    REPORT_DIR,
    f"{report_prefix}_{timestamp}.txt",
)

report = f"""LINUX REBOOT RCA REPORT
========================================

Server: {server}
Analysis Time: {datetime.now()}
Analysis Mode: {analysis_mode}
Gemini Model: {GEMINI_MODEL if ai_result else "N/A"}
Evidence File: {os.path.basename(evidence_file)}
Evidence Size: {len(evidence):,} characters

PROBABLE ROOT CAUSE
-------------------
{root_cause}

CAUSE OF REBOOT
---------------
{cause}

REBOOT TYPE
-----------
{rca.get("reboot_type", "UNKNOWN")}

CONFIDENCE
----------
{confidence}

SERVER HEALTH
-------------
{score}/100
{health_status}

KDUMP
-----
{"READY" if facts["kdump_ready"] else "NOT READY"}

VMCORE
------
{"AVAILABLE" if facts["vmcore"] else "NOT AVAILABLE"}

SUPPORTING EVIDENCE
-------------------
{chr(10).join("- " + str(x) for x in supporting[:5])}

RECOMMENDED ACTION
------------------
{recommendation}

AI FINAL SUMMARY
----------------
{final_summary}

AI PRIMARY RCA (VALIDATED)
--------------------------
{root_cause}

RAW EVIDENCE
------------
{evidence_file}
"""

with open(report_file, "w") as f:
    f.write(report)

console.print(
    Panel(
        "[bold green]✓ RCA REPORT GENERATED[/bold green]\n\n"
        f"Report: {clean_rich(report_file)}\n"
        f"Engine: {clean_rich(analysis_mode)}\n"
        f"Health Score: {score}/100\n"
        f"Status: {health_status}\n"
        f"Confidence: {clean_rich(confidence)}\n"
        f"Kdump: {kdump_status}\n"
        f"VMcore: {vmcore_status}",
        title="FINAL REPORT",
        border_style="green",
    )
)

console.print()

console.print(
    Panel.fit(
        "[bold cyan]LINUX REBOOT INTELLIGENCE CENTER[/bold cyan]  |  "
        f"{clean_rich(analysis_mode)}  |  "
        "Evidence-Based RCA",
        border_style="cyan",
    )
)
