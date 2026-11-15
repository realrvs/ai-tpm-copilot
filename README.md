# AI TPM Copilot

> Automated status reporting from GitHub Issues/PRs with PII redaction and LLM analysis.

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Tests](https://github.com/realrvs/ai-tpm-copilot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/realrvs/ai-tpm-copilot/actions)
[![Coverage](https://codecov.io/gh/realrvs/ai-tpm-copilot/branch/main/graph/badge.svg)](https://codecov.io/gh/realrvs/ai-tpm-copilot)

## 📋 Overview

AI TPM Copilot is an AI-powered tool for Technical Program Managers that automates the generation of project status reports from GitHub Issues and Pull Requests. It combines GitHub API data with YandexGPT LLM analysis to produce structured reports with sections: **Completed**, **In Progress**, **Blocked**, and **Risks**.

### Key Features

- **GitHub Integration** — Fetches Issues/PRs with pagination, retry logic, and date filtering
- **PII Redaction** — Automatic detection and redaction of sensitive data (СНИЛС, ИНН, passports, emails) using Presidio + custom regex patterns
- **LLM Analysis** — YandexGPT-powered issue categorization and status summarization
- **Report Validation** — Fact-checking against source data with fuzzy matching support
- **Multi-channel Delivery** — File output + Telegram bot with message chunking
- **Scheduled Runs** — Cron-based or interval-based automated execution
- **REST API** — FastAPI endpoints for report generation and retrieval
- **Full Observability** — OpenTelemetry tracing across all pipeline stages
- **Security-First** — Prompt isolation, secrets management, gitleaks scanning

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Input Layer                              │
│  CLI (Typer)  │  REST API (FastAPI)  │  Scheduler (Cron)        │
└───────────────┬──────────────────────┬──────────────────────────┘
                │                      │
                ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Pipeline Orchestrator                       │
├──────────┬──────────┬────────────┬───────────┬──────────────────┤
│ GitHub   │ PII      │ Prompt     │ YandexGPT │ Report           │
│ Fetcher  │ Redactor │ Builder    │ Client    │ Validator        │
└──────────┴──────────┴────────────┴───────────┴──────────────────┘
                │                      │
                ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Output Layer                               │
│  File Writer  │  Telegram Sender  │  REST Response               │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Observability                                 │
│  OpenTelemetry Tracing  │  Grafana Dashboard  │  Console Spans   │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or 3.12
- GitHub Personal Access Token (repo scope)
- Yandex Cloud IAM Token
- (Optional) Telegram Bot Token

### Installation

```bash
# Clone repository
git clone https://github.com/realrvs/ai-tpm-copilot.git
cd ai-tpm-copilot

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### Basic Usage

```bash
# Generate report and save to file
ai-tpm run --days 7 --deliver file

# Generate and send to Telegram
ai-tpm run --days 14 --deliver telegram

# Run with both deliveries
ai-tpm run --days 7 --deliver both

# Validate configuration without running
ai-tpm validate
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Yes |
| `YC_FOLDER_ID` | Yandex Cloud Folder ID | Yes |
| `YC_IAM_TOKEN` | Yandex IAM Token | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | No |
| `TELEGRAM_CHAT_ID` | Target chat/channel ID | No |
| `ENABLE_TELEGRAM_DELIVERY` | Enable Telegram delivery | No (default: false) |
| `ENABLE_FACT_CHECK_STRICT` | Strict fact-checking mode | No (default: true) |
| `ENABLE_FUZZY_MATCHING` | Enable fuzzy ID matching | No (default: true) |
| `ENABLE_PII_REDACTION_PRESIDIO` | Use Presidio for PII | No (default: true) |

### GitHub Repositories

Configure multiple repositories in `.env`:

```bash
GITHUB_REPOS=org/repo1,org/repo2,org/repo3
```

## 📡 REST API

### Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/reports` | Generate status report | Required |
| `GET` | `/api/v1/reports/{id}` | Retrieve report by ID | Required |
| `GET` | `/health` | Health check | No |

### Example: Generate Report

```bash
curl -X POST http://localhost:8000/api/v1/reports \
  -H "Content-Type: application/json" \
  -d '{"days": 7, "repos": ["org/repo"]}'
```

Response:

```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "markdown": "# Статус проекта (7 дней)\n\n## Выполнено\n- #10 **Fixed login bug**\n\n...",
  "generated_at": "2026-11-15T08:00:00Z",
  "issues_count": 15,
  "duration_ms": 12345.6
}
```

### Start API Server

```bash
uvicorn ai_tpm_copilot.api:app --host 0.0.0.0 --port 8000
```

## ⏰ Scheduler

Run reports on a schedule:

```bash
# Every hour
ai-tpm schedule --interval 3600 --deliver file

# Every Monday at 9:00
ai-tpm schedule --cron "0 9 * * 1" --deliver both

# Every 30 minutes with Telegram
ai-tpm schedule --interval 1800 --deliver telegram --days 14
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=ai_tpm_copilot --cov-report=html

# Run specific test file
pytest tests/pipeline/test_github_fetcher.py -v
```

### Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| GitHub Fetcher | 8 | ✅ |
| PII Redactor | 13 | ✅ |
| Prompt Builder | 8 | ✅ |
| LLM Client | 8 | ✅ |
| Report Generator | 8 | ✅ |
| Report Validator | 7 | ✅ |
| OTel Instrumentation | 6 | ✅ |
| Scheduler | 6 | ✅ |
| API Endpoints | 5 | ✅ |
| E2E Smoke Tests | 5 | ✅ |
| Integration | 7 | ✅ |
| **Total** | **93** | **✅** |

## 🐳 Docker

### Build Image

```bash
docker build -t ai-tpm-copilot:latest .
```

### Run Container

```bash
docker run --env-file .env \
  -p 8000:8000 \
  ai-tpm-copilot:latest
```

### Health Check

```bash
curl http://localhost:8000/health
```

## 🔒 Security

### Threat Model

- **STRIDE + OWASP Top 10 for LLM** (combined methodology)
- **PII Redaction** — Presidio + custom regex for Russian-specific formats (СНИЛС, ИНН, passport)
- **Prompt Isolation** — XML-based separation of system instructions and user data
- **Secrets Management** — ENV variables → YC Secret Manager, gitleaks in CI

### Key Threats Addressed

| ID | Threat | Severity | Mitigation |
|----|--------|----------|------------|
| TM-06 | Secrets leak | Critical | gitleaks in CI, SecretStr fields |
| TM-01 | Prompt injection | High | XML isolation (`<system-instructions>`) |
| TM-02 | PII leak | High | Presidio + RU regex patterns |
| TM-03 | Hallucination | High | Fact-check validation + fuzzy matching |
| TM-09 | Misinformation | High | Strict mode + source verification |

## 📊 Observability

### OpenTelemetry

Pipeline stages are instrumented with spans:

- `github.fetch` — Issues fetched from GitHub API
- `pii.redact` — PII redaction count
- `prompt.build` — Prompt assembly
- `llm.generate` — LLM API call
- `report.validate` — Fact-check validation
- `report.generate` — Markdown generation
- `report.deliver` — Delivery to channels

### Grafana Dashboard

Import `grafana/dashboard.json` for real-time metrics visualization.

## 📁 Project Structure

```
ai-tpm-copilot/
├── src/ai_tpm_copilot/
│   ├── api.py              # FastAPI endpoints
│   ├── cli.py              # Typer CLI
│   ├── config/
│   │   └── settings.py     # Pydantic settings
│   ├── models/
│   │   ├── domain.py       # Domain models
│   │   └── database.py     # SQLAlchemy models
│   └── pipeline/
│       ├── github_fetcher.py
│       ├── pii_redactor.py
│       ├── prompt_builder.py
│       ├── llm_client.py   # YandexGPT client
│       ├── report_generator.py
│       ├── report_validator.py
│       ├── orchestrator.py
│       ├── observability.py
│       ├── output.py
│       └── scheduler.py
├── tests/
├── grafana/
│   └── dashboard.json
├── adr/                    # Architecture Decision Records
├── alembic/                # Database migrations
├── Dockerfile
├── pyproject.toml
└── .github/workflows/
    └── ci-cd.yml
```

## 📜 License

Apache-2.0 — See [LICENSE](LICENSE) for details.

## 👥 Team

| Role | Responsibilities |
|------|-----------------|
| Tech Lead / Security | Architecture, ADR, security, code review |
| Senior Backend | Python, httpx, YandexGPT, presidio, aiogram |
| DevOps | CI/CD, Docker, Alembic, OTel, Grafana |
| QA Automation | pytest, respx, security tests, performance |
