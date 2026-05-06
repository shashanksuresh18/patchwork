# Agent Responsibilities

This diagram separates what Patchwork owns from what each assistant owns.

Patchwork is the orchestrator. It does not ask agents to edit the worktree directly. It asks
them for patches, then runs review and Git validation gates before applying anything.

Use this when explaining operational control:

- Patchwork owns planning, routing, execution, validation, and status.
- Claude owns planning and review, and can also handle general tasks.
- Codex is preferred for backend/API/database-shaped work.
- Gemini is preferred for frontend/UI-shaped work.
- The Git validation gate decides whether an approved patch can touch the repository.

```mermaid
flowchart TB
    classDef user fill:#e8f4ff,stroke:#2563eb,color:#0f172a
    classDef patchwork fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef claude fill:#f5f3ff,stroke:#7c3aed,color:#0f172a
    classDef codex fill:#ecfeff,stroke:#0891b2,color:#0f172a
    classDef gemini fill:#f0fdf4,stroke:#16a34a,color:#0f172a
    classDef guard fill:#fef2f2,stroke:#dc2626,color:#0f172a

    U[Developer]:::user --> PW[Patchwork]:::patchwork

    subgraph O[Patchwork responsibilities]
        P[Create and save plans]:::patchwork
        R[Route tasks]:::patchwork
        E[Run backends]:::patchwork
        S[Persist task status]:::patchwork
    end

    subgraph A[Agent responsibilities]
        CL[Claude: planning, fallback generation, review]:::claude
        CX[Codex: backend, API, database, auth patches]:::codex
        GM[Gemini: UI, component, frontend patches]:::gemini
    end

    subgraph G[Guardrails]
        RV[Review generated patches]:::guard
        GA[Validate with git apply --check]:::guard
        RJ[Reject unsafe or invalid diffs]:::guard
    end

    PW --> P
    PW --> R
    R --> CL
    R --> CX
    R --> GM
    CL --> RV
    CX --> RV
    GM --> RV
    RV --> GA
    RV --> RJ
    GA --> S
    RJ --> S
```
