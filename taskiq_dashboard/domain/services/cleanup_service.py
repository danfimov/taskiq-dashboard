from abc import ABC, abstractmethod

from taskiq_dashboard.domain.dto.cleanup import CleanupResult


class AbstractCleanupService(ABC):
    """Abstract service for cleaning up old tasks."""

    @abstractmethod
    async def cleanup(self) -> CleanupResult:
        """
        Perform cleanup according to settings.

        Returns:
            CleanupResult with counts of deleted tasks.
        """
        ...

    @abstractmethod
    async def cleanup_by_ttl(self, ttl_days: int) -> int:
        """
        Delete tasks older than ttl_days.

        Args:
            ttl_days: Maximum age of tasks in days.

        Returns:
            Number of deleted tasks.
        """
        ...

    @abstractmethod
    async def cleanup_by_count(self, max_tasks: int) -> int:
        """
        Delete oldest tasks if total count exceeds max_tasks.

        Args:
            max_tasks: Maximum number of tasks to keep.

        Returns:
            Number of deleted tasks.
        """
        ...
