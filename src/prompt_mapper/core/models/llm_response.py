"""LLM response data models."""

from typing import List, Optional

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """Response from LLM for movie resolution."""

    canonical_title: str = Field(..., description="Canonical movie title")
    year: Optional[int] = Field(None, description="Release year")
    aka_titles: List[str] = Field(default_factory=list, description="Alternative titles")
    language_hints: List[str] = Field(default_factory=list, description="Language hints")
    confidence: float = Field(..., ge=0.0, le=1.0, description="LLM confidence score")
    rationale: str = Field(..., description="Reasoning for the resolution")

    # Optional additional metadata
    director: Optional[str] = Field(None, description="Director name if identified")
    genre_hints: List[str] = Field(default_factory=list, description="Genre hints")
    edition_notes: Optional[str] = Field(None, description="Special edition notes")

    @property
    def all_titles(self) -> List[str]:
        """Get all titles including canonical and alternatives."""
        titles = [self.canonical_title]
        titles.extend(self.aka_titles)
        return list(set(titles))  # Remove duplicates
