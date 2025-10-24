import abc


class AbstractSchemaService(abc.ABC):
    @abc.abstractmethod
    async def create_schema(self) -> None:
        """
        Create the database schema for task states.
        """
        ...
