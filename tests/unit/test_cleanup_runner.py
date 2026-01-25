import asyncio
from unittest.mock import AsyncMock

from taskiq_dashboard.domain.services.cleanup_service import CleanupResult
from taskiq_dashboard.infrastructure.services.cleanup_service import PeriodicCleanupRunner


class TestPeriodicCleanupRunner:
    async def test_when_start_called__then_background_task_created(self) -> None:
        # Given
        mock_cleanup_service = AsyncMock()
        runner = PeriodicCleanupRunner(
            cleanup_service=mock_cleanup_service,
            interval_hours=1,
        )

        # When
        await runner.start()

        # Then
        assert runner._task is not None
        assert not runner._task.done()

        # Cleanup
        await runner.stop()

    async def test_when_stop_called_after_start__then_background_task_cancelled(self) -> None:
        # Given
        mock_cleanup_service = AsyncMock()
        runner = PeriodicCleanupRunner(
            cleanup_service=mock_cleanup_service,
            interval_hours=1,
        )
        await runner.start()

        # When
        await runner.stop()

        # Then
        assert runner._stop_event.is_set()
        assert runner._task is not None
        assert runner._task.done()

    async def test_when_stop_called_without_start__then_no_error_raised(self) -> None:
        # Given
        mock_cleanup_service = AsyncMock()
        runner = PeriodicCleanupRunner(
            cleanup_service=mock_cleanup_service,
            interval_hours=1,
        )

        # When & Then - should not raise
        await runner.stop()

    async def test_when_interval_elapsed__then_cleanup_called(self) -> None:
        # Given
        mock_cleanup_service = AsyncMock()
        mock_cleanup_service.cleanup = AsyncMock(return_value=CleanupResult())

        runner = PeriodicCleanupRunner(
            cleanup_service=mock_cleanup_service,
            interval_hours=1,
        )
        # Override interval for faster testing
        runner._interval_seconds = 0.1

        # When
        await runner.start()
        await asyncio.sleep(0.3)  # Wait for at least 2 intervals
        await runner.stop()

        # Then
        assert mock_cleanup_service.cleanup.call_count >= 1

    async def test_when_cleanup_raises_exception__then_runner_continues_working(self) -> None:
        # Given
        mock_cleanup_service = AsyncMock()
        mock_cleanup_service.cleanup = AsyncMock(side_effect=Exception('Database error'))

        runner = PeriodicCleanupRunner(
            cleanup_service=mock_cleanup_service,
            interval_hours=1,
        )
        runner._interval_seconds = 0.1

        # When
        await runner.start()
        await asyncio.sleep(0.3)  # Wait for cleanup to be attempted
        await runner.stop()

        # Then
        assert mock_cleanup_service.cleanup.call_count >= 1

    async def test_when_runner_created_with_hours__then_interval_converted_to_seconds(self) -> None:
        # Given
        mock_cleanup_service = AsyncMock()

        # When
        runner = PeriodicCleanupRunner(
            cleanup_service=mock_cleanup_service,
            interval_hours=24,
        )

        # Then
        assert runner._interval_seconds == 24 * 3600
