from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ParseStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ComparisonStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), default="application/pdf")
    extracted_text = Column(Text(16_000_000))  # LONGTEXT
    parsed_data = Column(JSON)
    parse_status = Column(
        Enum(ParseStatus),
        nullable=False,
        default=ParseStatus.PENDING,
    )
    parse_error = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # relationships
    comparisons_as_policy1 = relationship(
        "Comparison", foreign_keys="Comparison.policy1_id", back_populates="policy1"
    )
    comparisons_as_policy2 = relationship(
        "Comparison", foreign_keys="Comparison.policy2_id", back_populates="policy2"
    )


class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True, index=True)
    policy1_id = Column(Integer, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    policy2_id = Column(Integer, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    comparison_result = Column(JSON)
    status = Column(
        Enum(ComparisonStatus),
        nullable=False,
        default=ComparisonStatus.PENDING,
    )
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    policy1 = relationship("Policy", foreign_keys=[policy1_id], back_populates="comparisons_as_policy1")
    policy2 = relationship("Policy", foreign_keys=[policy2_id], back_populates="comparisons_as_policy2")
    upload_session = relationship("UploadSession", back_populates="comparison", uselist=False)


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, nullable=False, index=True)
    policy1_filename = Column(String(255))
    policy2_filename = Column(String(255))
    policy1_id = Column(Integer, ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    policy2_id = Column(Integer, ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    comparison_id = Column(Integer, ForeignKey("comparisons.id", ondelete="SET NULL"), nullable=True)
    status = Column(
        Enum("uploading", "processing", "completed", "failed", name="session_status"),
        nullable=False,
        default="uploading",
    )
    error_message = Column(Text)
    ip_address = Column(String(45))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    comparison = relationship("Comparison", back_populates="upload_session")
