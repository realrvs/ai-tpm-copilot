# ADR-004: Стратегия управления секретами

| Field        | Value                                        |
|-------------|----------------------------------------------|
| Status      | **Accepted**                                 |
| Date        | 2026-11-14                                   |
| Related TM  | TM-06, TM-08                                 |
| Related NFR | NFR-SEC-003                                  |

## Context

Система работает с тремя типами секретов: GitHub token, YandexGPT API credentials, Telegram bot token. Секреты не должны попадать в код, репозиторий или логи.

## Decision

Принимаем **трёхуровневую стратегию**:

1. **Приоритет 1 — Переменные окружения (ENV)**:
   - Все секреты загружаются через `pydantic-settings` из `os.environ`.
   - `.env` файл загружается через `python-dotenv` (только локальная разработка).
   - В CI/CD секреты передаются через GitHub Actions Secrets.

2. **Приоритет 2 — Secret Manager (future)**:
   - Для production: интеграция с Yandex Cloud Secret Manager.
   - Абстракция через `SecretProvider` protocol — замена на YC SM без изменения кода.

3. **Приоритет 3 — Защита от утечек**:
   - `.env` в `.gitignore` (жестко).
   - `gitleaks` в pre-commit hook и в CI.
   - Секреты **никогда** не логируются (маскирование через `logging` config).
   - Конфигурационный файл `config.yaml` не содержит секретов (только non-sensitive settings).

## Consequences

- **Плюсы:**
  - Простая модель для MVP (ENV).
  - Масштабируемая для production (YC Secret Manager).
  - Автоматическая защита от коммита секретов (gitleaks).
- **Минусы:**
  - ENV-переменные видны в `/proc` на Linux.
  - YC Secret Manager требует дополнительного IAM-настраивания.

## References

- TM-06 (Secrets leak)
- NFR-SEC-003
