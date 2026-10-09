"""FastAPI dependency providers: the single place where concrete implementations are chosen.

Tests (or a future config switch) override these to inject a different DB, renderer or storage.
"""
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database import SessionLocal
from app.services.renderer import CertificateRenderer, PdfCertificateRenderer
from app.services.storage import FileStorage, LocalFileStorage


def get_session_factory() -> sessionmaker:
    return SessionLocal


def get_db(factory: Annotated[sessionmaker, Depends(get_session_factory)]) -> Iterator[Session]:
    """One DB session per request, always closed afterwards."""
    with factory() as db:
        yield db


@lru_cache
def get_renderer() -> CertificateRenderer:
    return PdfCertificateRenderer()


@lru_cache
def get_storage() -> FileStorage:
    return LocalFileStorage(settings.storage_dir)


# Short aliases used in route signatures.
DbSession = Annotated[Session, Depends(get_db)]
SessionFactory = Annotated[sessionmaker, Depends(get_session_factory)]
Renderer = Annotated[CertificateRenderer, Depends(get_renderer)]
Storage = Annotated[FileStorage, Depends(get_storage)]
