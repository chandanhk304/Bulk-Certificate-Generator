"""Database tables: a Job owns many Certificates (one row per recipient)."""
import uuid
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class JobStatus(StrEnum):
    PENDING = "PENDING"                              # accepted, waiting for the worker
    PROCESSING = "PROCESSING"                        # worker is generating certificates
    COMPLETED = "COMPLETED"                          # every recipient succeeded
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"  # some succeeded, some failed
    FAILED = "FAILED"                                # nothing succeeded, or the job crashed


class CertificateStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    event_name: Mapped[str] = mapped_column(String(150))
    issued_by: Mapped[str] = mapped_column(String(100), default="")
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=32), default=JobStatus.PENDING
    )
    # Denormalized counters so status checks don't have to count rows.
    total: Mapped[int] = mapped_column(Integer, default=0)
    succeeded: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Certificate.position"
    )


class Certificate(Base):
    __tablename__ = "certificates"
    # Speeds up "pending/failed certificates of job X" queries.
    __table_args__ = (Index("ix_certificates_job_status", "job_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)  # index in the request, to map results back to input rows
    # Nullable: invalid input may lack these, but we still record the failed row.
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[CertificateStatus] = mapped_column(
        Enum(CertificateStatus, native_enum=False, length=16), default=CertificateStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)
    file_key: Mapped[str | None] = mapped_column(String(255))  # storage key, not an absolute path
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped[Job] = relationship(back_populates="certificates")
