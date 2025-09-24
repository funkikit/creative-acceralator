from __future__ import annotations

from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, JSON, ForeignKey, DateTime, func

Base = declarative_base()


class PromptRun(Base):
    __tablename__ = "prompt_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    base_prompt: Mapped[str] = mapped_column(String)
    k: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())


class Variation(Base):
    __tablename__ = "variations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_run_id: Mapped[str] = mapped_column(ForeignKey("prompt_runs.id"))
    prompt: Mapped[str] = mapped_column(String)
    trace: Mapped[dict] = mapped_column(JSON)


class GeneratedImage(Base):
    __tablename__ = "generated_images"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    variation_id: Mapped[str] = mapped_column(ForeignKey("variations.id"))
    url: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON)


class Persona(Base):
    __tablename__ = "personas"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    attrs: Mapped[dict] = mapped_column(JSON)


class Evaluation(Base):
    __tablename__ = "evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str] = mapped_column(ForeignKey("personas.id"))
    image_id: Mapped[str] = mapped_column(ForeignKey("generated_images.id"))
    scores: Mapped[dict] = mapped_column(JSON)
    comment: Mapped[str] = mapped_column(String)
