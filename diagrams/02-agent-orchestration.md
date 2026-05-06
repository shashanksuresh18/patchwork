# Agent Orchestration

Patchwork acts as the coordinator between multiple AI coding assistants.

The router looks at each task description and chooses a backend. Frontend-shaped work goes
to Gemini, backend/API-shaped work goes to Codex, and general planning or fallback work goes
to Claude. Claude also acts as the patch reviewer before changes are applied.

Use this when explaining why Patchwork is not tied to one model:

- It routes work by task type.
- It can use local CLI subscriptions by default.
- It keeps a consistent review gate even when generation comes from different agents.

```mermaid
flowchart LR
    classDef center fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef claude fill:#f5f3ff,stroke:#7c3aed,color:#0f172a
    classDef codex fill:#ecfeff,stroke:#0891b2,color:#0f172a
    classDef gemini fill:#f0fdf4,stroke:#16a34a,color:#0f172a
    classDef output fill:#f8fafc,stroke:#64748b,color:#0f172a

    T[Task from plan]:::output --> O[Patchwork orchestrator]:::center
    O --> K{Keyword router}:::center

    K -->|ui, component, react, css, tailwind| G[Gemini]:::gemini
    K -->|api, database, fastapi, auth, endpoint| C[Codex]:::codex
    K -->|fallback and planning| A[Claude]:::claude

    A --> P[Patch candidate]:::output
    C --> P
    G --> P

    P --> Q[Claude reviewer]:::claude
    Q -->|approve| OK[Validated patch]:::output
    Q -->|reject| NO[Reason saved on task]:::output
```
