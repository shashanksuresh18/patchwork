# Example: Hello Feature

This example walks through using Patchwork to add a `/hello` endpoint to a minimal FastAPI app.

## Setup

```bash
mkdir demo && cd demo && git init
printf 'from fastapi import FastAPI\napp = FastAPI()\n' > main.py
git add main.py && git commit -m "initial"

uv pip install -e /path/to/patchwork
cp /path/to/patchwork/.env.example .env
# Edit .env - add your ANTHROPIC_API_KEY at minimum
```

## Step 1: Plan

```bash
patchwork plan "add a /hello endpoint that returns {\"message\": \"hello world\"}"
```

Expected output:
```
Plan saved: .patchwork/plans/add-a-hello-endpoint-20250101-120000.json
 Task      Description
 task-001  Add GET /hello route returning {"message": "hello world"}
 task-002  Add pytest test for the /hello route
```

## Step 2: Execute

```bash
patchwork exec .patchwork/plans/add-a-hello-endpoint-20250101-120000.json
```

Expected output:
```
Task task-001: Add GET /hello route returning {"message": "hello world"}
  -> routing to codex
  Applied

Task task-002: Add pytest test for the /hello route
  -> routing to codex
  Applied
```

## Step 3: Verify

```bash
git diff HEAD~1    # review the applied patches
uvicorn main:app --reload
curl http://localhost:8000/hello
# {"message": "hello world"}
```

## Troubleshooting

**"API key not set"** - Edit `.env` and add the missing key for the routed backend.

**"git apply --check failed"** - The model didn't have enough context. Try running `exec` again, or add more detail to the task description in the plan JSON before re-running.

**"Rejected: ..."** - Claude's reviewer found an issue. Read the reasoning. Fix the plan JSON's task description to be more precise, then re-run `exec`.
