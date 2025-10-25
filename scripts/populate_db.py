import asyncio
import datetime as dt
import json
import random
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from taskiq_dashboard.domain.dto.task_status import TaskStatus
from taskiq_dashboard.infrastructure.database.schemas import Task
from taskiq_dashboard.infrastructure import Settings


# Константы для генерации данных
TASK_NAMES = [
    'extract_data',
    'transform_data',
    'load_data',
    'send_email',
    'generate_report',
    'process_image',
    'check_availability',
    'clean_database',
    'backup_data',
    'update_index',
    'analyze_metrics',
    'fetch_external_api',
]

WORKER_NAMES = [
    'worker-01',
    'worker-02',
    'worker-03',
    'analytics-worker',
    'email-worker',
    'image-processor',
    'data-worker',
]


async def create_random_tasks(session: AsyncSession, count: int) -> None:
    """Создает указанное количество случайных задач."""
    tasks = []

    for _ in range(count):
        # Генерируем базовые данные
        task_name = random.choice(TASK_NAMES)
        worker_name = random.choice(WORKER_NAMES)
        status = random.choice(list(TaskStatus))

        # Генерируем аргументы
        args = json.dumps([random.randint(1, 100) for _ in range(random.randint(0, 3))])
        kwargs = json.dumps(
            {f'param{i}': random.choice(['value', 123, True, None]) for i in range(random.randint(0, 3))}
        )

        # Генерируем время начала (от недели назад до сейчас)
        started_at = dt.datetime.now(dt.UTC) - dt.timedelta(
            days=random.randint(0, 7),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        # Генерируем результат в зависимости от статуса
        result = None
        error = None
        finished_at = None

        if status != TaskStatus.IN_PROGRESS:
            # Если задача не в процессе, то она завершена (успешно или с ошибкой)
            execution_time = dt.timedelta(
                seconds=random.randint(1, 300)  # от 1 секунды до 5 минут
            )
            finished_at = started_at + execution_time

            if status == TaskStatus.COMPLETED:
                result = json.dumps({'success': True, 'value': random.randint(1, 1000)})
            elif status == TaskStatus.FAILURE:
                error = random.choice(
                    [
                        'Connection timeout',
                        'ValueError: Invalid input data',
                        "KeyError: 'missing_key'",
                        'IndexError: list index out of range',
                        'Exception: External API unavailable',
                    ]
                )
            elif status == TaskStatus.QUEUED:
                error = random.choice(
                    [
                        'Timeout exceeded',
                        'Worker node crashed',
                        'Task was cancelled by user',
                        'Resource limits exceeded',
                        'Task was terminated due to system maintenance',
                    ]
                )
                finished_at = None

        # Создаем объект задачи
        task = Task(
            id=uuid.uuid4(),
            name=task_name,
            status=status,
            worker=worker_name,
            args=args,
            kwargs=kwargs,
            result=result,
            error=error,
            started_at=started_at,
            finished_at=finished_at,
        )

        tasks.append(task)

    # Добавляем все задачи в базу
    session.add_all(tasks)
    await session.commit()

    print(f'✅ Успешно добавлено {count} задач в базу данных')


async def main() -> None:
    """Основная функция для запуска скрипта."""
    # Загружаем настройки
    settings = Settings()

    # Создаем engine для SQLAlchemy
    engine = create_async_engine(
        settings.db.dsn.get_secret_value(),
        echo=True,
    )

    # Создаем фабрику сессий
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Запрашиваем количество задач для генерации
    try:
        task_count = int(input('Введите количество задач для генерации: '))
        if task_count <= 0:
            raise ValueError('Количество должно быть положительным')
    except ValueError:
        print('Ошибка: введите корректное число')
        return

    # Создаем задачи
    async with async_session() as session:
        await create_random_tasks(session, task_count)

    # Закрываем соединение
    await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
