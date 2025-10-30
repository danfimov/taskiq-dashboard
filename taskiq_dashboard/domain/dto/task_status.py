import enum


class TaskStatus(enum.IntEnum):
    IN_PROGRESS = 0
    COMPLETED = 1
    FAILURE = 2
    QUEUED = 3
    ABANDONED = 4
