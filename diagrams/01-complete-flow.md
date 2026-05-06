# Complete Flow

This diagram is the client-facing overview of Patchwork.

Patchwork starts with a feature request, asks Claude to break it into small tasks, routes
each task to the best coding assistant, reviews the generated patch, validates it with
`git apply --check`, and only then applies approved changes to the repository.

Use this when explaining the core value proposition:

- Work is split into small, trackable tasks.
- Different assistants are used for the work they are best suited to.
- Every patch goes through a review and validation gate before touching code.
- Execution state is saved back to the plan file.
- Model calls can be traced in Langfuse for observability.

```mermaid
flowchart TD
    classDef user fill:#e8f4ff,stroke:#2563eb,color:#0f172a
    classDef patchwork fill:#fff7ed,stroke:#ea580c,color:#0f172a
    classDef agent fill:#f0fdf4,stroke:#16a34a,color:#0f172a
    classDef gate fill:#fef2f2,stroke:#dc2626,color:#0f172a
    classDef artifact fill:#f8fafc,stroke:#64748b,color:#0f172a

    U[Developer request]:::user --> P1[patchwork plan]:::patchwork
    P1 --> C1[Claude planner decomposes feature]:::agent
    C1 --> F1[Plan JSON in .patchwork/plans]:::artifact
    F1 --> P2[patchwork exec plan.json]:::patchwork
    P2 --> R1[Route each task by keywords]:::patchwork

    R1 -->|UI / frontend| G[Gemini generates patch]:::agent
    R1 -->|API / backend| X[Codex generates patch]:::agent
    R1 -->|General tasks| C2[Claude generates patch]:::agent

    G --> D[Unified diff patch]:::artifact
    X --> D
    C2 --> D

    D --> V[Claude patch review]:::gate
    V -->|approved| A[git apply --check]:::gate
    A -->|valid| B[Apply patch to repo]:::patchwork
    A -->|invalid| J[Reject with reason]:::gate
    V -->|rejected| J

    B --> S[Update plan task status]:::artifact
    J --> S
    S --> L[Optional Langfuse trace]:::artifact
```
