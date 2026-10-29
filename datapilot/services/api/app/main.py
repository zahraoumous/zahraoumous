import logging
from contextlib import closing
from typing import Literal
from uuid import uuid4

import boto3
from botocore.config import Config
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis import Redis
from sqlalchemy import create_engine, text

from app.core.body_limit import BodyLimitMiddleware
from app.core.config import Settings, get_settings
from app.features.ai_mvp import router as ai_mvp_router
from app.features.data_mvp import router as data_mvp_router
from app.features.routes import router

logger = logging.getLogger("datapilot")
app = FastAPI(title="DataPilot API", version="0.3.0")
app.add_middleware(BodyLimitMiddleware)
app.include_router(router)
app.include_router(data_mvp_router)
app.include_router(ai_mvp_router)


class Liveness(BaseModel):
    status: Literal["ok"] = "ok"


class Readiness(BaseModel):
    status: Literal["ready", "unavailable"]
    checks: dict[str, bool]


@app.middleware("http")
async def request_id(request: Request, call_next):
    # Generate server-side IDs; never log caller-controlled identifiers or secrets.
    correlation_id = str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        logger.error("request_failed request_id=%s", correlation_id)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    response.headers["X-Request-ID"] = correlation_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def check_dependencies(settings: Settings) -> dict[str, bool]:
    checks = {"postgres": False, "redis": False, "object_store": False}
    engine = None
    try:
        engine = create_engine(
            settings.database_url.get_secret_value(),
            connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            # All additive MVP migrations must finish before traffic is accepted.
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            checks["postgres"] = revision == "0004_ai_mvp"
    except Exception:
        pass
    finally:
        if engine is not None:
            engine.dispose()
    try:
        with Redis.from_url(
            settings.redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
        ) as client:
            checks["redis"] = bool(client.ping())
    except Exception:
        pass
    try:
        with closing(
            boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                aws_access_key_id=settings.s3_access_key.get_secret_value(),
                aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
                region_name=settings.s3_region,
                config=Config(connect_timeout=3, read_timeout=3, retries={"max_attempts": 0}),
            )
        ) as client:
            client.list_buckets()
            checks["object_store"] = True
    except Exception:
        pass
    return checks


@app.get("/health/live", response_model=Liveness)
def live() -> Liveness:
    return Liveness()


@app.get("/health/ready", response_model=Readiness, responses={503: {"model": Readiness}})
def ready(response: Response) -> Readiness:
    try:
        checks = check_dependencies(get_settings())
    except Exception:
        checks = {"configuration": False}
    healthy = all(checks.values())
    response.status_code = 200 if healthy else 503
    return Readiness(status="ready" if healthy else "unavailable", checks=checks)
