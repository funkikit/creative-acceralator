from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


LLMName = Literal["openai", "gemini"]


class VariationTrace(BaseModel):
    motif: str = ""
    style: str = ""
    concept: str = ""
    constraints: List[str] = Field(default_factory=list)
    palette: Optional[str] = None
    target_audience: Optional[str] = None
    brand_tone: Optional[str] = None
    extras: Dict[str, str] = Field(default_factory=dict)


class VariationOut(BaseModel):
    id: str
    prompt: str
    trace: VariationTrace


class VariationSeed(BaseModel):
    motif: Optional[str] = None
    style: Optional[str] = None
    concept: Optional[str] = None
    palette: Optional[str] = None
    target_audience: Optional[str] = None
    brand_tone: Optional[str] = None
    extras: Dict[str, str] = Field(default_factory=dict)


class VariationVariablesRequest(BaseModel):
    goal: str
    constraints: List[str] = []
    llm: LLMName = "gemini"


class VariationVariablesResponse(BaseModel):
    goal: str
    llm: LLMName
    dynamic_variables: Dict[str, List[str]]
    fixed_constraints: List[str]
    used_fallback: bool = False


class VariationsRequest(BaseModel):
    goal: str
    constraints: List[str] = []
    dynamic_variables: Dict[str, List[str]] = Field(default_factory=dict)
    custom_variations: List[VariationSeed] = Field(default_factory=list)
    k: int = Field(10, ge=1, le=32)
    llm: LLMName = "gemini"


class VariationsResponse(BaseModel):
    prompt_run_id: str
    variations: List[VariationOut]


class ReferenceImagePayload(BaseModel):
    data: str
    mime_type: str


class ImagesRequest(BaseModel):
    variation_ids: List[str]
    reference_image: Optional[ReferenceImagePayload] = None


class ImageOut(BaseModel):
    id: str
    variation_id: str
    url: str
    provider_meta: Dict[str, str] = {}


class ImagesResponse(BaseModel):
    images: List[ImageOut]


class Scores(BaseModel):
    Appeal: float
    BrandFit: float
    Originality: float
    Clarity: float
    CulturalSensitivity: float
    overall: float


class PersonaConfig(BaseModel):
    id: str
    gender: str
    age_band: str
    region: str
    background: str
    familiarity: str
    summary: str
    extras: Dict[str, Any] = Field(default_factory=dict)


class PersonaSpec(BaseModel):
    id: str
    gender: str
    age_band: str
    region: str
    background: str
    familiarity: str
    summary: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class EvaluationOut(BaseModel):
    persona_id: str
    persona: PersonaConfig
    image_id: str
    scores: Scores
    comment: str
    flags: List[str] = []
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidateResponse(BaseModel):
    evaluations: List[EvaluationOut]


class ValidateRequest(BaseModel):
    image_ids: List[str]
    n_personas: int = Field(100, ge=1, le=300)
    llm: LLMName = "openai"
    personas: Optional[List[PersonaSpec]] = None


class ValidationProgress(BaseModel):
    status: Literal["idle", "initializing", "running", "complete", "error"] = "idle"
    total: int = 0
    completed: int = 0
    message: Optional[str] = None
