# Patchwork

> Observability-first orchestrator for AI coding assistants - routes tasks across Claude, Codex,
> and Gemini, traces every model call with Langfuse, and gates patches before they touch code.

## Quick start

```bash
# Install with uv
uv pip install -e .

# Copy env template
cp .env.example .env
# Edit .env with your API keys

# Plan a feature
patchwork plan "add a /health endpoint to the FastAPI app"

# Execute the plan
patchwork exec .patchwork/plans/add-a-health-endpoint-20250101-120000.json
```

## How it works

1. **Plan**: Claude decomposes a feature into 3-7 tasks and saves a JSON plan.
2. **Route**: Each task is routed to the best backend based on keywords.
3. **Generate**: The assigned backend produces a unified diff patch.
4. **Review**: Claude inspects the patch and approves or rejects it.
5. **Apply**: Approved patches are validated with `git apply --check` then applied.
6. **Observe**: Every model call is traced in Langfuse (optional).

## Routing rules

| Keywords | Backend |
|---|---|
| ui, component, react, css, tailwind, frontend, jsx, tsx | Gemini |
| api, database, sql, fastapi, auth, backend, server, endpoint | Codex |
| *(everything else)* | Claude |

## Requirements

- Python 3.11+
- `git` on PATH
- API keys for the backends you want to use

## Project structure

```
patchwork/
  cli.py           # typer CLI: plan, exec
  config.py        # pydantic-settings config
  models.py        # Task, Patch, Plan, ReviewResult
  router.py        # keyword-based backend routing
  reviewer.py      # Claude patch reviewer
  patch.py         # git apply --check + apply
  tracing.py       # Langfuse @traced / no-op
  backends/
    base.py        # Backend ABC
    claude.py      # Anthropic backend
    codex.py       # OpenAI backend
    gemini.py      # Google Gemini backend
```

## Inspiration

Architecture inspired by [ccg-workflow](https://github.com/ccg-workflow/ccg-workflow).

## License

MIT - see [LICENSE](LICENSE).
