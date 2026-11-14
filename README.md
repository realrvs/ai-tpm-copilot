# AI TPM Copilot

Automated status reporting from GitHub Issues/PRs with PII redaction and LLM analysis.

## Quick Start

```bash
pip install -e ".[dev]"
cp .env.example .env
# edit .env with your credentials
ai-tpm run --days 7 --deliver file
```

## Architecture

```
GitHub Fetcher → PII Redactor → Prompt Builder → YandexGPT → Report Validator → Report Generator
```

## CLI

```bash
ai-tpm run --days 14 --deliver both        # Run pipeline, deliver to file + Telegram
ai-tpm validate --config config.yaml       # Validate configuration
```

## License

Apache-2.0
