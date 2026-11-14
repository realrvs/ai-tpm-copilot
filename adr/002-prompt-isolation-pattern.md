# ADR-002: Паттерн изоляции промпта

| Field        | Value                                        |
|-------------|----------------------------------------------|
| Status      | **Accepted**                                 |
| Date        | 2026-11-14                                   |
| Related TM  | TM-01                                        |
| Related NFR | NFR-SEC-002                                  |

## Context

Данные из GitHub (Issues, комментарии) передаются в LLM. Злоумышленник может внедрить prompt injection через комментарий (например, "Ignore previous instructions..."). Необходимо изолировать пользовательские данные от системных инструкций.

## Decision

Принимаем **XML-изоляцию** с обёрткой пользовательских данных:

```xml
<system-instructions>
{system_prompt_content}
</system-instructions>

<user-data>
{sanitized_issues_json}
</user-data>
```

Системный промпт размещается в отдельном XML-теге `<system-instructions>`, пользовательские данные — в `<user-data>`. LLM-провайдер (YandexGPT) получает инструкцию обрабатывать содержимое `<user-data>` исключительно как данные, а не как инструкции.

Дополнительно:
- Системный промпт хранится в отдельном файле `system_prompt.md` (не в коде).
- Специальные символы в пользовательских данных экранируются.

## Consequences

- **Плюсы:**
  - XML-теги создают чёткую границу между инструкциями и данными.
  - YandexGPT корректно обрабатывает XML-структуру в промпте.
  - Системный промпт можно обновлять без пересборки.
- **Минусы:**
  - XML-структура увеличивает размер промпта.
  - Не 100% защита от advanced prompt injection (но mitigates most common attacks).

## References

- OWASP LLM Top 10 — LLM01: Prompt Injection
- [YandexGPT Prompt Engineering Guide](https://cloud.yandex.ru/docs/yandexgpt)
