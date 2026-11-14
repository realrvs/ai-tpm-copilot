# ADR-003: Схема валидации вывода LLM

| Field        | Value                                        |
|-------------|----------------------------------------------|
| Status      | **Accepted**                                 |
| Date        | 2026-11-14                                   |
| Related TM  | TM-03, TM-09, TM-04                          |
| Related NFR | NFR-SEC-004                                  |

## Context

LLM (YandexGPT) может генерировать галлюцинирующие статусы, несуществующие Issue ID или недостоверную информацию. Необходим слой валидации перед доставкой отчёта.

## Decision

Принимаем **трёхуровневую валидацию**:

1. **JSON Schema validation** (если LLM возвращает JSON):
   - Строгая схема с обязательными полями: `sections.completed[]`, `sections.in_progress[]`, `sections.blocked[]`, `sections.risks[]`.
   - Каждый элемент содержит `issue_id` (int), `title` (str), `reason` (str).

2. **Fact-check по Issue ID**:
   - Для каждого `issue_id` в отчёте проверяем наличие в исходном наборе собранных Issues.
   - Если ID не найден — пункт помечается как `unverified` и исключается из финального отчёта (при `ENABLE_FACT_CHECK_STRICT=true`).

3. **Fuzzy matching** (опционально, при `ENABLE_FUZZY_MATCHING=true`):
   - Если точное совпадение не найдено, ищем по частичному совпадению номера (`#123` vs `123`).
   - При совпадении — исправляем ID, при отсутствии — исключаем.

Финальный Markdown-отчёт генерируется из валидированных данных, а не из сырого вывода LLM.

## Consequences

- **Плюсы:**
  - 100% пунктов отчёта имеют верифицированный Issue ID.
  - Галлюцинации не попадают в финальный отчёт.
  - Fuzzy matching снижает false negatives.
- **Минусы:**
  - Дополнительная задержка (fact-check ~100-200ms для 100 Issues).
  - LLM не может добавить контекстные рекомендации по несобранным Issues.

## References

- TM-03 (Excessive Agency), TM-09 (Misinformation)
- NFR-SEC-004
