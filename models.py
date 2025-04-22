from datetime import datetime
from typing import List, Dict, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, conint, HttpUrl, validator


class ResearchQuestion(BaseModel):
    """Model representing a research question."""
    question: str
    sources: List[str] = Field(default_factory=list, min_items=0, max_items=5)


class ResearchPlan(BaseModel):
    """Model representing a structured research plan."""
    questions: List[ResearchQuestion] = Field(min_items=1, max_items=10)
    depth: conint(ge=1, le=3) = 1  # 1=superficial, 3=approfondita


class ResearchTask(BaseModel):
    """Model representing a research task."""
    task_id: UUID = Field(default_factory=uuid4)
    objective: str
    sources: List[str] = Field(default_factory=list)
    depth: conint(ge=1, le=3) = 1
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

    class Config:
        validate_assignment = True


class ContentMetadata(BaseModel):
    """Model representing metadata for extracted content."""
    title: Optional[str] = None
    author: Optional[str] = None
    date: Optional[datetime] = None
    url: Optional[str] = None
    content_type: Optional[str] = None  # e.g., "text", "pdf", "table"


class KeyPoint(BaseModel):
    """Model representing a key point extracted from content."""
    text: str
    confidence: float = Field(ge=0.0, le=1.0)


class ContentFinding(BaseModel):
    """Model representing findings from a single source."""
    source: str
    metadata: ContentMetadata
    key_points: List[KeyPoint] = Field(default_factory=list)
    summary: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    raw_content: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.now)


class Connection(BaseModel):
    """Model representing a connection between two findings."""
    source: str  # Source identifier
    target: str  # Target identifier
    relation: str  # Type of relation: "contrasto", "supporto", "correlazione", etc.
    strength: float = Field(ge=0.0, le=1.0, default=0.5)
    description: Optional[str] = None


class ResearchOutput(BaseModel):
    """Model representing the complete output of a research task."""
    task_id: UUID
    objective: str
    findings: List[ContentFinding] = Field(default_factory=list)
    connections: List[Connection] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = "completed"
