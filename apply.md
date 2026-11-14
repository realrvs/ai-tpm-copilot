## Миграции

- [ ] `migration-001-initial-schema`: Создание схемы БД для хранения метаданных отчетов (report_id, repo, generated_at, token_usage, pii_redacted_count) (`alembic/versions/001_initial.py`)
- [ ] Rollback: `alembic downgrade base` — удаление всех таблиц

- [ ] `migration-002-reports-index`: Добавление индекса на `reports.generated_at` (`alembic/versions/002_reports_index.py`)
- [ ] Rollback: `alembic downgrade -1` — удаление индекса

> **Примечание:** На MVP-фазе допустимо использовать SQLite (локально) и PostgreSQL (production). Миграции через Alembic.

## Feature Flags

| Flag | Default | TTL | Связанный FR | Связанный TM |
|---|---|---|---|---|
| `ENABLE_TELEGRAM_DELIVERY` | `false` | 30 дней | FR-004 | TM-04 |
| `ENABLE_FACT_CHECK_STRICT` | `true` | бессрочно | NFR-SEC-004 | TM-03, TM-09 |
| `ENABLE_LLM_PROVIDER_YANDEXGPT` | `false` | 60 дней | FR-003 | — |
| `ENABLE_FUZZY_MATCHING` | `true` | бессрочно | NFR-SEC-004 | TM-03 |
| `ENABLE_PII_REDACTION_PRESIDIO` | `true` | бессрочно | NFR-SEC-001 | TM-02 |

> **Обоснование флагов:**
> - `ENABLE_TELEGRAM_DELIVERY` — включается после тестирования TC-005.
> - `ENABLE_FACT_CHECK_STRICT` — по умолчанию `true`, риск галлюцинаций критичен.
> - `ENABLE_LLM_PROVIDER_YANDEXGPT` — опциональный провайдер (Phase 4).
> - `ENABLE_FUZZY_MATCHING` — смягчает false negatives в fact-check.
> - `ENABLE_PII_REDACTION_PRESIDIO` — fallback на regex-only, если presidio не установлен.

## Canary Deployment

1. **Стадия 1 (dev):** 1 тестовый репозиторий (`realrvs/ai-tax-assistant`), `ENABLE_TELEGRAM_DELIVERY=false`, `deliver_to=file`. Проверка: отчет корректен, PII не утекли.
2. **Стадия 2 (staging):** 3 репозитория, `ENABLE_TELEGRAM_DELIVERY=true`, `deliver_to=both`. Проверка: Telegram доставлен, Markdown не ломается, OTel-трейсы в Jaeger.
3. **Стадия 3 (production, 10%):** Cron раз в неделю на `realrvs/regulated-llm-eval-framework`. Мониторинг: latency ≤ 120с, token_usage ≤ 32K, `pii_redacted_count > 0`.
4. **Стадия 4 (production, 100%):** Все репозитории TPM. Мониторинг Grafana: `llm.generate` p95, `report.deliver` success rate, `unverified_items_count` < 5%.

> **Критерий отката:** Если `report.deliver` success rate < 95% или `pii_redacted_count = 0` при наличии PII — немедленный откат.

## Rollback Plan

1. **Откат feature flags:** `ENABLE_TELEGRAM_DELIVERY=false`, `ENABLE_LLM_PROVIDER_YANDEXGPT=false` через GitHub Secrets / ENV.
2. **Откат миграций:** `alembic downgrade -1`.
3. **Откат кода:** `git revert <commit>` или переключение на tag `v0.1.0`.
4. **Откат OTel-конфигурации:** Убрать OTLP exporter из `config.yaml`.
5. **Уведомление:** Сообщение в Telegram-канал `#ai-tpm-copilot-alerts` с описанием инцидента.
6. **Пост-мортем:** В течение 48 часов — обновить `threat-model.md` (если инцидент связан с безопасностью) и добавить регрессионный тест.

> **Важно:** Откат `threat-model.md` запрещён — TM является источником истины для security-требований. При изменении архитектуры — повторный прогон `threat-model`.