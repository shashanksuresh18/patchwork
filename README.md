# Patchwork

> Observability-first orchestrator for AI coding assistants - routes tasks across Claude, Codex,
> and Gemini, traces every model call with Langfuse, and gates patches before they touch code.

## Quick start

```bash
# Install with uv
uv pip install -e .

# Copy env template
cp .env.example .env
# Default mode uses local CLIs, so log in to Claude Code, Codex, and Gemini first.

# Initialize Patchwork in a project
patchwork init

# Check local tools and git setup
patchwork doctor

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

## Local CLI mode

Patchwork defaults to local agent CLI mode so you can use existing Claude Code, Codex,
and Gemini subscriptions instead of paying separately for API keys.

Install and log in to the tools you want Patchwork to use:

```bash
claude
codex
gemini
```

Patchwork calls them through these defaults:

```env
PATCHWORK_USE_CLI_BACKENDS=true
PATCHWORK_CLAUDE_CLI_COMMAND=claude -p
PATCHWORK_CODEX_CLI_COMMAND=codex exec
PATCHWORK_GEMINI_CLI_COMMAND=gemini -p
```

If your local command syntax is different, change the matching `PATCHWORK_*_CLI_COMMAND`
value in `.env`.

## Project setup

Run this once inside each codebase you want Patchwork to work on:

```bash
patchwork init
```

It creates:

```text
.env
.patchwork/
.patchwork/plans/
.patchwork/config.toml
```

Existing `.env` and `.patchwork/config.toml` files are preserved. To recreate them:

```bash
patchwork init --force
```

Check whether the current project is ready:

```bash
patchwork doctor
```

`doctor` checks for `git`, whether you are inside a Git repo, and either local agent CLIs
or API keys depending on `PATCHWORK_USE_CLI_BACKENDS`.

To use SDK/API keys instead, set:

```env
PATCHWORK_USE_CLI_BACKENDS=false
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
```

## Routing rules

| Keywords | Backend |
|---|---|
| ui, component, react, css, tailwind, frontend, jsx, tsx | Gemini |
| api, database, sql, fastapi, auth, backend, server, endpoint | Codex |
| *(everything else)* | Claude |

## Requirements

- Python 3.11+
- `git` on PATH
- Claude Code, Codex, and Gemini CLIs for default local CLI mode
- API keys only if `PATCHWORK_USE_CLI_BACKENDS=false`

## Project structure

```
patchwork/
  cli.py           # typer CLI: plan, exec
  config.py        # pydantic-settings config
  agent_cli.py     # local Claude/Codex/Gemini CLI runner
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
