import fastapi
from dishka.integrations import fastapi as dishka_fastapi
from pydantic import BaseModel


router = fastapi.APIRouter(tags=['System'], route_class=dishka_fastapi.DishkaRoute)


class HealthCheckResponse(BaseModel):
    status: str
    app_name: str



@router.get('/liveness', name='liveness', summary='Проверка работоспособности сервиса')
async def get_liveness() -> HealthCheckResponse:
    return HealthCheckResponse(
        status='alive',
        app_name='taskiq dashboard',
    )


@router.get('/readiness', name='readiness', summary='Проверка готовности обслуживать входящие запросы')
async def get_readiness() -> HealthCheckResponse:
    # TODO: maybe add "select 1" to database
    return HealthCheckResponse(
        status='ready',
        app_name='taskiq dashboard',
    )
