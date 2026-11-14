# Context

## Threat Model
- **Методология:** STRIDE + OWASP Top 10 for LLM (комбинированно)
- **Обоснование:** `security_context` содержит `ai: ["LLM", "RAG", "Summarization"]`, `assets: ["PII", "Internal Project Data"]`, `regulatory: ["152-ФЗ"]`. Правило выбора №1 промпта предписывает комбинированную методологию.
- **Ключевые угрозы:** TM-06 (Critical, secrets leak), TM-01 (High, prompt injection), TM-02 (High, PII leak), TM-03 (High, hallucination), TM-09 (High, misinformation).

## Принятые ADR
- **ADR-001:** Стратегия PII Redaction (Accepted) — presidio + кастомные regex для СНИЛС/ИНН
- **ADR-002:** Паттерн изоляции промпта (Accepted) — XML-изоляция `<system-instructions>` / `<user-data>`
- **ADR-003:** Схема валидации вывода LLM (Accepted) — JSON Schema + fact-check по Issue ID + fuzzy matching
- **ADR-004:** Стратегия управления секретами (Accepted) — ENV → YC Secret Manager, gitleaks в CI

## Согласованные endpoints
- `POST /api/v1/reports` — генерация отчета (auth required)
- `GET /api/v1/reports/{report_id}` — получение отчета (auth required)
- `GET /health` — health check (no auth)

> **Примечание:** API-эндпоинты запланированы для future phase (FastAPI-обёртка над CLI). На MVP — только CLI + Telegram.

## Закрытые вопросы

| Вопрос | Решение | ADR |
|--------|---------|-----|
| Какой LLM-провайдер выбрать по умолчанию? | **YandexGPT** (YC Generative LLM API, model: YandexGPT Lite) | — |
| Нужна ли поддержка нескольких репозиториев? | **Да**, через `github.repos: list[str]` в конфиге | — |
| Формат Telegram-сообщения | Разбиение на чанки ≤4000 символов по `\n\n` | — |
| Интеграция с GitHub Projects v2 | **Нет**, вне scope MVP | — |

## Пропущенные артефакты
- (нет)
