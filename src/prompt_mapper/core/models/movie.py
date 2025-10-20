"""Movie-related data models."""

from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .llm_response import LLMResponse


class MovieInfo(BaseModel):
    """Basic movie information."""

    title: str = Field(..., description="Movie title")
    year: Optional[int] = Field(None, description="Release year")
    tmdb_id: Optional[int] = Field(None, description="TMDb ID")
    imdb_id: Optional[str] = Field(None, description="IMDb ID")
    overview: Optional[str] = Field(None, description="Movie overview/plot")
    poster_path: Optional[str] = Field(None, description="Poster image path")
    backdrop_path: Optional[str] = Field(None, description="Backdrop image path")
    original_title: Optional[str] = Field(None, description="Original title")
    original_language: Optional[str] = Field(None, description="Original language")
    release_date: Optional[date] = Field(None, description="Release date")
    runtime: Optional[int] = Field(None, description="Runtime in minutes")
    genres: List[str] = Field(default_factory=list, description="Movie genres")
    popularity: Optional[float] = Field(None, description="TMDb popularity score")
    vote_average: Optional[float] = Field(None, description="Average rating")
    vote_count: Optional[int] = Field(None, description="Number of votes")


class MovieCandidate(BaseModel):
    """Movie candidate from search results."""

    movie_info: MovieInfo = Field(..., description="Movie information")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Match confidence score")
    score_breakdown: Dict[str, float] = Field(
        default_factory=dict, description="Score component breakdown"
    )
    search_query: str = Field(..., description="Query that found this candidate")


class MovieMatch(BaseModel):
    """Final movie match result."""

    movie_info: MovieInfo = Field(..., description="Matched movie information")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    candidates: List[MovieCandidate] = Field(
        default_factory=list, description="All candidates considered"
    )
    selected_automatically: bool = Field(..., description="Whether selection was automatic")
    user_confirmed: bool = Field(default=False, description="Whether user confirmed the match")
    rationale: Optional[str] = Field(None, description="Reasoning for the match")
    llm_response: Optional["LLMResponse"] = Field(None, description="Original LLM response")
