# Tasks: AI TPM Copilot

> **Репозиторий:** `realrvs/ai-tpm-copilot`
> **Дата старта:** 2026-11-16
> **Спринт:** 14 дней
> **1 SP = 0.5 человеко-дня**
> **Команда:** @sokolov-tl (Tech Lead), @ivanov-dev (Senior Backend), @petrov-dev (DevOps), @sidorova-qa (QA Automation)

---

## Сводная таблица трудоемкости

| Фаза | Описание | SP | Дни (0.5/SP) |
|------|----------|----:|-------------:|
| Phase 1 | MVP: CLI + GitHub Fetcher + PII + YandexGPT + File Writer | 20 | 10 |
| Phase 2 | Telegram + OTel + Report Validator | 13 | 6.5 |
| Phase 3 | Cron + Grafana | 8 | 4 |
| Phase 4 | FastAPI-обёртка + fallback LLM | 13 | 6.5 |
| **Итого** | | **54** | **27** |

По направлениям: Backend 36 SP, DevOps 10 SP, QA 8 SP

---

## Матрица RACI

| Роль | Username | Технологии |
|------|----------|-----------|
| Tech Lead / Security | @sokolov-tl | Архитектура, ADR, security, code review |
| Senior Backend | @ivanov-dev | Python, httpx, YandexGPT, presidio, aiogram |
| DevOps | @petrov-dev | CI/CD, Docker, Alembic, OTel, Grafana |
| QA Automation | @sidorova-qa | pytest, respx, security tests, performance |

---

## Phase 1: MVP (Sprint 1)

| ID | Задача | SP | Assignee | Зависимости | FR/NFR |
|----|--------|---:|----------|-------------|--------|
| T-001 | Инициализация проекта: pyproject.toml, структура, конфиги | 1 | @ivanov-dev | — | — |
| T-002 | GitHub Fetcher: httpx + pagination + retry | 3 | @ivanov-dev | T-001 | FR-001 |
| T-003 | PII Redactor: presidio + RU regex | 3 | @ivanov-dev | T-001 | FR-002, NFR-SEC-001 |
| T-004 | Prompt Builder: XML-изоляция | 2 | @ivanov-dev | T-003 | FR-003, NFR-SEC-002 |
| T-005 | YandexGPT Client: API integration | 3 | @ivanov-dev | T-004 | FR-003 |
| T-006 | Report Generator: Markdown output | 2 | @ivanov-dev | T-005 | FR-004 |
| T-007 | CLI: Typer entry point + config validation | 2 | @ivanov-dev | T-001 | FR-001 |
| T-008 | Feature Flags: pydantic-settings + ENV | 1 | @ivanov-dev | T-001 | NFR-SEC-003 |
| T-009 | Unit tests: GitHub Fetcher | 2 | @sidorova-qa | T-002 | TC-001, TC-002 |
| T-010 | Unit tests: PII Redactor | 2 | @sidorova-qa | T-003 | TC-SEC-001 |

## Phase 2: Telegram + OTel + Validator (Sprint 2)

| ID | Задача | SP | Assignee | Зависимости | FR/NFR |
|----|--------|---:|----------|-------------|--------|
| T-011 | Telegram Sender: aiogram + chunking | 3 | @ivanov-dev | T-006 | FR-004 |
| T-012 | Report Validator: fact-check + fuzzy | 3 | @ivanov-dev | T-005 | FR-003, NFR-SEC-004 |
| T-013 | OpenTelemetry: tracing pipeline | 3 | @petrov-dev | T-001 | FR-005 |
| T-014 | Pipeline Orchestrator: full integration | 2 | @ivanov-dev | T-011, T-012, T-013 | FR-001..FR-005 |
| T-015 | Integration tests: full pipeline | 3 | @sidorova-qa | T-014 | TC-003..TC-007 |
| T-016 | Performance test: latency ≤ 120s | 2 | @sidorova-qa | T-014 | NFR-001, TC-008 |
| T-017 | Security tests: prompt injection, fact-check | 3 | @sidorova-qa | T-012 | TC-SEC-002, TC-SEC-004 |

## Phase 3: Cron + Grafana (Sprint 3)

| ID | Задача | SP | Assignee | Зависимости | FR/NFR |
|----|--------|---:|----------|-------------|--------|
| T-018 | Alembic migration: initial schema | 2 | @petrov-dev | T-001 | apply.md |
| T-019 | Cron scheduler: scheduled runs | 3 | @petrov-dev | T-014 | — |
| T-020 | Grafana dashboard: OTel metrics | 3 | @petrov-dev | T-013 | — |
| T-021 | Canary deployment: staging setup | 2 | @petrov-dev | T-019 | apply.md |

## Phase 4: FastAPI + Fallback (Sprint 4)

| ID | Задача | SP | Assignee | Зависимости | FR/NFR |
|----|--------|---:|----------|-------------|--------|
| T-022 | FastAPI wrapper: POST /api/v1/reports | 4 | @ivanov-dev | T-014 | context.md |
| T-023 | FastAPI: GET /api/v1/reports/{id} | 3 | @ivanov-dev | T-022 | context.md |
| T-024 | Health endpoint: GET /health | 1 | @ivanov-dev | T-022 | context.md |
| T-025 | Docker: multi-stage build | 3 | @petrov-dev | T-022 | — |
| T-026 | CI/CD: GitHub Actions pipeline | 2 | @petrov-dev | T-001 | — |
| T-027 | End-to-end smoke tests | 2 | @sidorova-qa | T-022 | — |
| T-028 | Tech Lead: security audit + code review | 2 | @sokolov-tl | T-027 | NFR-SEC-001..007 |
| T-029 | Release v0.1.0: tagging + changelog | 1 | @sokolov-tl | T-027 | — |

---

## Зависимости (blockers)

```
T-001 ─┬─→ T-002 ──→ T-009
       ├─→ T-003 ──→ T-004 ──→ T-005 ──→ T-006 ──→ T-011 ──→ T-014 ──→ T-015
       │         │              │           │              │           │
       │         ↓              ↓           ↓              ↓           ↓
       │       T-010          T-012        T-017         T-016      T-022 ──→ T-027
       │                                                              │
       └─→ T-007 ─────────────────────────────────────────────────────┘
       └─→ T-008 ─────────────────────────────────────────────────────┘
       └─→ T-013 ─────────────────────────────────────────────────────┘
       
T-014 ──→ T-019 ──→ T-020 ──→ T-021
T-014 ──→ T-022 ──→ T-024
T-022 ──→ T-025
T-027 ──→ T-028 ──→ T-029
```

## Риски

| Риск | Вероятность | Влияние | Митигация |
|------|:-----------:|:-------:|-----------|
| YandexGPT API rate limits | Средняя | Высокое | Retry (tenacity), token budget (NFR-003) |
| Presidio NLTK не загружается | Низкая | Среднее | Fallback на regex-only (ADR-001) |
| Telegram API 429 (flood) | Средняя | Среднее | Чанки ≤4000 символов, backoff |
| LLM hallucination | Средняя | Высокое | Fact-check (ADR-003), strict mode |
| GitHub API rate limit (60/h unauth) | Высокая | Высокое | PAT token (5000/h), pagination |
