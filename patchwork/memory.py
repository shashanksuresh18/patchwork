class MemoryStore:
    """Stub - not implemented in MVP."""

    def add(self, task_id: str, patch_content: str) -> None:
        raise NotImplementedError("MemoryStore not implemented in MVP")

    def query(self, description: str) -> list[str]:
        raise NotImplementedError("MemoryStore not implemented in MVP")
