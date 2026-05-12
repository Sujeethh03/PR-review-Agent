import enum
from datetime import datetime
from sqlalchemy import String, Float, Integer, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class FindingStatus(enum.Enum):
    pending     = "pending"
    approved    = "approved"
    dismissed   = "dismissed"
    auto_posted = "auto_posted"
    digest      = "digest"


class Base(DeclarativeBase):
    pass


class PRReview(Base):
    __tablename__ = "pr_reviews"

    id:              Mapped[int]      = mapped_column(Integer, primary_key=True)
    owner:           Mapped[str]      = mapped_column(String(255))
    repo_name:       Mapped[str]      = mapped_column(String(255))
    pr_number:       Mapped[int]      = mapped_column(Integer)
    head_sha:        Mapped[str]      = mapped_column(String(40))
    collection_name: Mapped[str]      = mapped_column(String(255))
    created_at:      Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FindingRow(Base):
    __tablename__ = "findings"

    id:               Mapped[int]           = mapped_column(Integer, primary_key=True)
    finding_hash:     Mapped[str]           = mapped_column(String(64), unique=True)
    pr_review_id:     Mapped[int]           = mapped_column(Integer, ForeignKey("pr_reviews.id"))
    agent:            Mapped[str]           = mapped_column(String(20))
    file:             Mapped[str]           = mapped_column(String(500))
    line_start:       Mapped[int]           = mapped_column(Integer)
    line_end:         Mapped[int]           = mapped_column(Integer)
    severity:         Mapped[str]           = mapped_column(String(10))
    category:         Mapped[str]           = mapped_column(String(50))
    title:            Mapped[str]           = mapped_column(String(500))
    description:      Mapped[str]           = mapped_column(Text)
    suggestion:       Mapped[str]           = mapped_column(Text)
    specialist_conf:  Mapped[float]         = mapped_column(Float)
    critic_conf:      Mapped[float]         = mapped_column(Float)
    critic_reasoning: Mapped[str]           = mapped_column(Text)
    route:            Mapped[str]           = mapped_column(String(10))
    status:           Mapped[FindingStatus] = mapped_column(
                          Enum(FindingStatus), default=FindingStatus.pending
                      )
    created_at:       Mapped[datetime]      = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by:      Mapped[str | None]      = mapped_column(String(255), nullable=True)
