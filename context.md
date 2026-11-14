# Context

## Threat Model
- **Методология:** STRIDE + OWASP Top 10 for LLM (комбинированно)
- **Обоснование:** `security_context` содержит `ai: ["LLM", "RAG", "Summarization"]`, `assets: ["PII", "Internal Project Data"]`, `regulatory: ["152-ФЗ"]`. Правило выбора №1 промпта предписывает комбинированную методологию.
- **Ключевые угрозы:** TM-06 (Critical, secrets leak), TM-01 (High, prompt injection), TM-02 (High, PII leak), TM-03 (High, hallucination), TM-09 (High, misinformation).

## Принятые ADR
- ADR-001: Стратегия PII Redaction (Proposed) — связан с TM-02, NFR-SEC-001
- ADR-002: Паттерн изоляции промпта (Proposed) — связан с TM-01, NFR-SEC-002
- ADR-003: Схема валидации вывода LLM (Proposed) — связан с TM-03, TM-09, TM-04
- ADR-004: Стратегия управления секретами (Proposed) — связан с TM-06, TM-08

## Согласованные endpoints
- `POST /api/v1/reports` — генерация отчета (auth required)
- `GET /api/v1/reports/{report_id}` — получение отчета (auth required)
- `GET /health` — health check (no auth)

## Открытые вопросы
- [ ] Какой LLM-провайдер выбрать по умолчанию: GigaChat или YandexGPT?
- [ ] Нужна ли поддержка нескольких репозиториев в одном запуске?
- [ ] Формат Telegram-сообщения: единое длинное или несколько коротких?
- [ ] Нужна ли интеграция с GitHub Projects (v2)?

## Пропущенные артефакты
- (нет)