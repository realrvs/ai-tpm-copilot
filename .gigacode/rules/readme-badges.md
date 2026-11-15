---
apply: ALWAYS
mode: AGENT
---

# Поддержка бейджей CI и Codecov в README

При редактировании файла `README.md` или при настройке CI/CD необходимо убедиться, что в файле `README.md` присутствуют два обязательных бейджа, отображающих статус проекта.

## 1. Бейдж статуса GitHub Actions (CI)

Бейдж должен ссылаться на файл workflow `.github/workflows/ci-cd.yml` (или актуальный файл workflow) текущего репозитория.

Формат Markdown:
`[![CI](https://github.com/realrvs/ai-tpm-copilot/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/realrvs/ai-tpm-copilot/actions/workflows/ci-cd.yml)`

## 2. Бейдж статуса Codecov (покрытие тестами)

Бейдж должен ссылаться на сервис Codecov для текущего репозитория.

Формат Markdown:
`[![codecov](https://codecov.io/gh/realrvs/ai-tpm-copilot/branch/main/graph/badge.svg)](https://codecov.io/gh/realrvs/ai-tpm-copilot)`
*(Замените `main` на вашу основную ветку, если это необходимо).*

## Инструкции для агента:
1. Проверь наличие этих двух бейджей в `README.md` (обычно они располагаются сразу под заголовком проекта).
2. Если какого-то бейджа нет, добавь его.
3. Если в репозитории изменилось имя владельца (сейчас `realrvs`), имя репозитория (сейчас `ai-tpm-copilot`) или имя файла workflow, автоматически обнови URL в бейджах.
4. Если статус бейджа отображается как `unknown` или `failing`, сообщи пользователю, что необходимо проверить настройки GitHub Actions (шаг загрузки в Codecov) и наличие секрета `CODECOV_TOKEN`.