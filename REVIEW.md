# REVIEW.md — Patchwork Implementation Review

Reviewed against `BUILD_PLAN.md`. All 19 source/test/example files present. Tracing
coverage confirmed. Below are all findings, sorted by severity.

---

## Summary

| Severity | Count | Files |
|---|---|---|
| HIGH | 1 | `cli.py` |
| MEDIUM | 1 | `cli.py` |
| LOW | 2 | `cli.py` |

No critical bugs. `patch.py`, all three backends, `reviewer.py`, `tracing.py`,
`config.py`, `router.py`, `models.py`, and all test files are clean.

---

## HIGH

### H-1 · `cli.py:33–39` — `plan` command silently produces nonsense tasks when `ANTHROPIC_API_KEY` is missing

**What the code does**

When `settings.anthropic_api_key` is falsy, the command does not exit. Instead it
injects three hardcoded task descriptions about a `/healthz` route — regardless of
what feature the user asked for — and continues as if the API call succeeded.

```python
# cli.py:33–39
    if not settings.anthropic_api_key:
        # TODO: clarify whether the planner should require Claude auth during local smoke tests.
        task_dicts = [
            {"description": f"Add the /healthz route for this feature: {feature}."},
            {"description": "Return a simple successful health response from the new endpoint."},
            {"description": "Ensure the endpoint is registered with the FastAPI application."},
        ]
```

**Why this is wrong**

The plan (§2.13) is explicit:

> If `not settings.anthropic_api_key`: `console.print("[red]Error: ANTHROPIC_API_KEY
> not set[/red]"); raise typer.Exit(1)`.

A user running `patchwork plan "add rate limiting"` with no key set will receive a
saved plan for health-check routes. That plan is then fed to `exec`, which either hits
real backends with nonsensical tasks or silently fails. The companion `exec_plan`
command already implements the correct pattern (lines 119–121), so there is a
consistency asymmetry as well.

**Suggested fix**

```diff
-    task_dicts: list[dict[str, str]]
-    if not settings.anthropic_api_key:
-        # TODO: clarify whether the planner should require Claude auth during local smoke tests.
-        task_dicts = [
-            {"description": f"Add the /healthz route for this feature: {feature}."},
-            {"description": "Return a simple successful health response from the new endpoint."},
-            {"description": "Ensure the endpoint is registered with the FastAPI application."},
-        ]
-    else:
-        client = Anthropic(api_key=settings.anthropic_api_key)
+    if not settings.anthropic_api_key:
+        console.print("[red]Error: ANTHROPIC_API_KEY not set[/red]")
+        raise typer.Exit(1)
+    client = Anthropic(api_key=settings.anthropic_api_key)
```

Remove the dangling `else:` indent from the block that follows (lines 41–79 shift
left by one level).

---

## MEDIUM

### M-1 · `cli.py:150` — `except (BackendError, Exception)` is logically dead; `BackendError` is unreachable in the tuple

**What the code does**

```python
# cli.py:148–154
        try:
            generated_patch = backend.generate_patch(task, repo_context)
        except (BackendError, Exception) as e:
            task.status = TaskStatus.failed
            task.rejection_reason = str(e)
            console.print(f"  [red]x Generation failed[/red]: {e}")
            continue
```

**Why this is wrong**

`BackendError` is a subclass of `Exception`. Python evaluates `except` clauses in
order and matches the first one that fits, but in a single `except (A, B)` tuple, if
`B` is a supertype of `A`, then `A` is never the reason for the match — `B` catches
everything `A` would have caught and more. The tuple is therefore equivalent to
`except Exception`. A linter (`flake8-bugbear` rule B025 or Ruff `B029`) will flag
this.

The practical consequence: unexpected internal bugs in a backend — `AttributeError`
when `response.content` is `None`, `TypeError` from a model API change — are silently
converted to task-failure messages rather than propagating as program errors. During
development this makes backend bugs very hard to spot.

The plan spec (§2.13) did prescribe "BackendError or other exception", but clean
Python expresses that as two separate except clauses:

**Suggested fix**

```diff
-        except (BackendError, Exception) as e:
+        except BackendError as e:
             task.status = TaskStatus.failed
             task.rejection_reason = str(e)
-            console.print(f"  [red]x Generation failed[/red]: {e}")
+            console.print(f"  [red]✗ Generation failed[/red]: {e}")
             continue
+        except Exception as e:
+            task.status = TaskStatus.failed
+            task.rejection_reason = f"Unexpected error: {e}"
+            console.print(f"  [red]✗ Unexpected error[/red]: {e}")
+            raise  # re-raise so the caller sees the bug during dev
```

The `raise` on the unexpected-exception branch is optional but strongly recommended
for a development tool; remove it if you prefer silent resilience in all cases.

---

## LOW

### L-1 · `cli.py:29` — `@traced` applied to a Typer CLI command (undocumented, potential Typer+Langfuse incompatibility)

**What the code does**

```python
# cli.py:28–30
@app.command()
@traced
def plan(feature: Annotated[str, typer.Argument(help="Feature description")]) -> None:
```

**Why this is a concern**

The plan spec (§2.13) does not list `@traced` on CLI commands. The decorator is
specified only for `backend.generate_patch` and `reviewer.review` (§2.4).

When `traced = _noop_decorator` (Langfuse keys absent), this is harmless because
`_noop_decorator` uses `@wraps` and preserves the function signature Typer inspects.

When `traced = langfuse.observe` (Langfuse keys present), Langfuse wraps the function
in its own span context manager. Typer resolves CLI argument types by calling
`inspect.signature` on the registered callable. While Langfuse also uses `@wraps`,
there is no test coverage for the `observe`-active case, so any future Langfuse
version that changes how it wraps callables could silently break CLI argument parsing.

Additionally, applying `observe` to the entire CLI entry point means every
`patchwork plan` invocation opens a Langfuse root trace that spans the full runtime,
which is not what the spec intended — the plan says traces are for model calls, not
CLI invocations.

**Suggested fix**

```diff
-@app.command()
-@traced
-def plan(feature: Annotated[str, typer.Argument(help="Feature description")]) -> None:
+@app.command()
+def plan(feature: Annotated[str, typer.Argument(help="Feature description")]) -> None:
```

Tracing of the underlying Claude call is already covered by `ClaudeBackend.generate_patch`
having `@traced`.

---

### L-2 · `cli.py:128, 153, 160, 167, 171, 175` — ASCII stand-ins for Unicode symbols

The spec (§2.13) uses Unicode punctuation throughout the exec output; the
implementation uses ASCII equivalents. This is cosmetic but makes the terminal output
look different from the documented UX and the example in `examples/hello_feature.md`.

| Line | Actual | Spec |
|---|---|---|
| 128 | `"  -> routing to ..."` | `"  → routing to ..."` |
| 153 | `"  [red]x Generation failed[/red]"` | `"  [red]✗ Generation failed[/red]"` |
| 160 | `"  [red]x Review error[/red]"` | `"  [red]✗ Review error[/red]"` |
| 167 | `"  [green]Applied[/green]"` | `"  [green]✓ Applied[/green]"` |
| 171 | `"  [red]x Patch error[/red]"` | `"  [red]✗ Patch error[/red]"` |
| 175 | `"  [yellow]x Rejected[/yellow]"` | `"  [yellow]✗ Rejected[/yellow]"` |

**Suggested fix** (one diff, all six lines):

```diff
-        console.print(f"  -> routing to [cyan]{task.backend}[/cyan]")
+        console.print(f"  → routing to [cyan]{task.backend}[/cyan]")
 
-            console.print(f"  [red]x Generation failed[/red]: {e}")
+            console.print(f"  [red]✗ Generation failed[/red]: {e}")
 
-            console.print(f"  [red]x Review error[/red]: {e}")
+            console.print(f"  [red]✗ Review error[/red]: {e}")
 
-                console.print("  [green]Applied[/green]")
+                console.print("  [green]✓ Applied[/green]")
 
-                console.print(f"  [red]x Patch error[/red]: {e}")
+                console.print(f"  [red]✗ Patch error[/red]: {e}")
 
-            console.print(f"  [yellow]x Rejected[/yellow]: {review_result.reasoning[:80]}")
+            console.print(f"  [yellow]✗ Rejected[/yellow]: {review_result.reasoning[:80]}")
```

---

## Confirmed Clean

Everything below was checked against the plan and passes:

| File | Checks |
|---|---|
| `patch.py` | `delete=False` on NamedTemporaryFile ✓, `finally: os.unlink` in both functions ✓, empty-content guard runs before temp file creation ✓ |
| `tracing.py` | `@wraps` applied ✓, module-level `traced = _make_tracer()` ✓, no-op falls back silently on `ImportError` ✓ |
| `config.py` | `AliasChoices` on all fields ✓, `populate_by_name=True` ✓, `@lru_cache` without parentheses ✓ |
| `models.py` | `slugify` both `re.sub` passes correct ✓, `created_at` uses `timezone.utc` ✓ |
| `router.py` | `re.split` tokenization ✓, frontend checked before backend ✓ |
| `backends/base.py` | System prompt verbatim ✓, `_extract_diff` fence-strip loop correct ✓ |
| `backends/claude.py` | `@traced` on `generate_patch` ✓, `APIError` wrapped as `BackendError` ✓ |
| `backends/codex.py` | `@traced` on `generate_patch` ✓, `APIError` wrapped ✓ |
| `backends/gemini.py` | `@traced` on `generate_patch` ✓, `genai.Client(api_key=...)` not `configure()` ✓ |
| `reviewer.py` | `@traced` on `review` ✓, `APIError` returns rejection not raises ✓, `_parse_response` regex uses `re.DOTALL` ✓ |
| `tests/test_models.py` | All 14 named test cases present ✓ |
| `tests/test_router.py` | All 10 named test cases present ✓ |
| `tests/test_patch.py` | All 8 named test cases present ✓, both cleanup tests assert `os.unlink` called ✓ |
| `pyproject.toml` | All 9 deps, `scripts` entry, `requires-python = ">=3.11"` ✓ |
| `memory.py` / `eval.py` | Stubs raise `NotImplementedError` ✓, not imported anywhere ✓ |
