from dataclasses import dataclass


@dataclass
class CleanupResult:
    deleted_by_ttl: int = 0
    deleted_by_count: int = 0
