# Linux Reboot Intelligence Center – Automated RCA & Server Health Platform

## 📌 Project Overview

The **Linux Reboot Intelligence Center (RCA)** is an automation and AI-assisted platform designed to analyze Linux server reboot events and identify the possible root cause.

The project combines **rule-based Root Cause Analysis (RCA)** with **AI-based analysis** to reduce manual investigation time and provide clear, actionable insights for Linux infrastructure teams.

## 🎯 Objectives

* Automatically analyze Linux server reboot events
* Identify possible root causes of unexpected reboots
* Reduce manual log investigation and troubleshooting effort
* Provide evidence-based RCA findings
* Combine deterministic rules with AI-based analysis
* Improve incident response and troubleshooting efficiency

## 🏗️ How It Works

```text
Linux Server
     ↓
Collect System Logs & Events
     ↓
RCA Analysis Engine
     ↓
Rule-Based RCA
     ↓
AI-Assisted Analysis
     ↓
Root Cause + Evidence
     ↓
RCA Report
```

## 🔍 RCA Engine

The project uses a **rule-based RCA engine** to identify known reboot patterns from Linux logs and system information.

Example checks include:

* Kernel panic
* OOM (Out of Memory)
* Manual reboot/shutdown
* Hardware-related events
* Filesystem/storage issues
* System crashes
* Unexpected shutdown
* Watchdog events
* Scheduled reboot activity

The rule engine provides a deterministic result when the available evidence matches a known pattern.

## 🤖 AI-Assisted RCA

When the rule engine cannot confidently determine the root cause, the collected logs and system information can be analyzed using AI.

The AI layer helps:

* Analyze complex or unfamiliar log patterns
* Correlate multiple events
* Explain the probable root cause
* Summarize technical findings
* Provide recommended troubleshooting actions

### Rule Engine + AI Approach

```text
Known Pattern
     ↓
Rule Engine
     ↓
High Confidence RCA
```

```text
Unknown / Complex Pattern
     ↓
AI Analysis
     ↓
Probable Root Cause
     ↓
Evidence + Explanation
```

This hybrid approach combines the **accuracy and consistency of rules** with the **analysis capability of AI**.

## 🛠️ Technologies Used

* Linux / RHEL
* Python
* Shell Scripting
* Linux System Logs
* Rule-Based RCA
* AI / LLM Integration
* Git & GitHub
* Virtual Environment
* AWS EC2 for development/testing

## 📂 Project Structure

```text
Automation_RCA/
│
├── scripts/
│   └── rule_rca.py
│
├── logs/
│   └── sample logs
│
├── src/
│   └── RCA / AI components
│
├── tests/
│
├── requirements.txt
├── .gitignore
└── README.md
```

> Update the structure above to match the actual folders in your repository.

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/saikiran14313/Automation_RCA.git
cd Automation_RCA
```

Create a Python virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## ▶️ Running the Project

Example:

```bash
python3 scripts/rule_rca.py
```

The application analyzes the available Linux reboot information and generates RCA findings based on the configured rules and analysis logic.

## 🔐 Configuration & Security

Sensitive information such as API keys, credentials, tokens, and environment variables should **never be committed to GitHub**.

Use a local `.env` file for secrets and add it to `.gitignore`:

```text
.env
venv/
__pycache__/
*.pyc
```

Example:

```text
API_KEY=<your-api-key>
```

Do not commit real API keys or credentials to the repository.

## 📊 Key Benefits

* Automated Linux reboot investigation
* Faster RCA generation
* Reduced manual troubleshooting
* Consistent RCA methodology
* AI-assisted analysis for complex incidents
* Evidence-based root cause identification
* Useful for large-scale Linux infrastructure environments

## 🔮 Future Enhancements

* Automated server log collection
* Integration with ServiceNow
* Automated incident creation/update
* More RCA rules
* Historical RCA database
* Dashboard for reboot trends
* Confidence scoring
* Automated remediation recommendations
* Integration with monitoring platforms

## 👨‍💻 Author

**Sai Kiran**

Linux System Administrator | DevOps & Cloud Enthusiast

GitHub: https://github.com/saikiran14313
