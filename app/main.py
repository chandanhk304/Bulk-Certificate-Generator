"""Application entrypoint: builds the FastAPI app, wires routers and error handlers."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import certificates, jobs
from app.database import Base, engine
from app.services.errors import NotFoundError, NotReadyError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables on startup (no-op if they exist). Use Alembic for real schema migrations.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Bulk Certificate Generator",
    description="Submit recipients in bulk, track generation progress, download certificates.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs.router, prefix="/api")
app.include_router(certificates.router, prefix="/api")


# Map domain errors to HTTP status codes in one place, keeping routes free of try/except.
@app.exception_handler(NotFoundError)
def _not_found(_request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(NotReadyError)
def _not_ready(_request: Request, exc: NotReadyError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
