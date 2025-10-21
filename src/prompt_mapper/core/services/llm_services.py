"""LLM service implementations."""

import json
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import LLMServiceError
from ..interfaces import ILLMService
from ..models import MovieCandidate


class BaseLLMService(ILLMService, LoggerMixin, ABC):
    """Base LLM service with common functionality."""

    def __init__(self, config: Config):
        """Initialize LLM service.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._llm_config = config.llm

    async def select_movie_from_candidates(
        self,
        candidates: List[MovieCandidate],
        original_filename: str,
        movie_name: str,
        movie_year: Optional[int],
        user_prompt: str,
    ) -> Tuple[Optional[MovieCandidate], float]:
        """Select the best movie match from TMDB candidates using LLM.

        Args:
            candidates: List of movie candidates from TMDB search.
            original_filename: Original filename for context.
            movie_name: Cleaned movie name extracted from filename.
            movie_year: Extracted year from filename (if any).
            user_prompt: User-provided prompt for selection guidance.

        Returns:
            Tuple of (selected_candidate, confidence_score).
            Returns (None, 0.0) if no suitable match found.

        Raises:
            LLMServiceError: If LLM request fails.
        """
        try:
            if not candidates:
                return None, 0.0

            # Create system prompt for movie selection
            system_prompt = self._create_selection_system_prompt()

            # Create user prompt with candidates
            full_user_prompt = self._create_selection_user_prompt(
                candidates, original_filename, movie_name, movie_year, user_prompt
            )

            # Make LLM request
            response_text = await self._make_llm_request(system_prompt, full_user_prompt)

            # Parse response
            selected_index, confidence = self._parse_selection_response(
                response_text, len(candidates)
            )

            if selected_index is None:
                self.logger.info("LLM did not select any candidate")
                return None, 0.0

            selected_candidate = candidates[selected_index]
            self.logger.info(
                f"LLM selected: {selected_candidate.movie_info.title} "
                f"({selected_candidate.movie_info.year}) with confidence {confidence:.2f}"
            )

            return selected_candidate, confidence

        except Exception as e:
            error_msg = f"LLM selection failed: {e}"
            self.logger.error(error_msg)
            raise LLMServiceError(error_msg) from e

    @abstractmethod
    async def _make_llm_request(self, system_prompt: str, user_prompt: str) -> str:
        """Make request to LLM service.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.

        Returns:
            LLM response text.
        """
        pass

    def _create_selection_system_prompt(self) -> str:
        """Create system prompt for movie selection.

        Returns:
            System prompt text.
        """
        return """You are a movie identification expert. Given a filename and a list of candidate movies from TMDb, select the best match.

IMPORTANT: You must respond with valid JSON in exactly this format:
{
    "selected_index": integer_or_null,
    "confidence": float_between_0_and_1,
    "rationale": "string"
}

Rules:
- selected_index: The 0-based index of the best matching candidate from the list, or null if no good match
- confidence: Your confidence in the selection (0.0-1.0). Use 0.95+ for very confident matches
- rationale: Brief explanation of your reasoning

Consider:
- Title similarity (exact matches are best)
- Year match (if year is available from filename)
- Original title vs English title
- Alternative titles and regional variations
- Release date proximity

If no candidate is a good match (wrong movie entirely), return selected_index: null with confidence 0.0."""

    def _create_selection_user_prompt(
        self,
        candidates: List[MovieCandidate],
        original_filename: str,
        movie_name: str,
        movie_year: Optional[int],
        user_prompt: str,
    ) -> str:
        """Create user prompt for movie selection.

        Args:
            candidates: List of movie candidates.
            original_filename: Original filename.
            movie_name: Cleaned movie name.
            movie_year: Extracted year.
            user_prompt: User guidance.

        Returns:
            Complete user prompt.
        """
        prompt_parts = []

        # Add user guidance
        if user_prompt:
            prompt_parts.append(f"User guidance: {user_prompt}")
            prompt_parts.append("")

        # Add file information
        prompt_parts.append("File to identify:")
        prompt_parts.append(f"  Original filename: {original_filename}")
        prompt_parts.append(f"  Cleaned name: {movie_name}")
        if movie_year:
            prompt_parts.append(f"  Extracted year: {movie_year}")
        prompt_parts.append("")

        # Add candidates
        prompt_parts.append(f"TMDb candidates ({len(candidates)} found):")
        for i, candidate in enumerate(candidates):
            movie = candidate.movie_info
            prompt_parts.append(f"\nCandidate {i}:")
            prompt_parts.append(f"  Title: {movie.title}")
            if movie.year:
                prompt_parts.append(f"  Year: {movie.year}")
            if movie.original_title and movie.original_title != movie.title:
                prompt_parts.append(f"  Original Title: {movie.original_title}")
            prompt_parts.append(f"  TMDb ID: {movie.tmdb_id}")
            if movie.overview:
                overview = (
                    movie.overview[:150] + "..." if len(movie.overview) > 150 else movie.overview
                )
                prompt_parts.append(f"  Overview: {overview}")
            prompt_parts.append(f"  Match Score: {candidate.match_score:.3f}")

        prompt_parts.append("")
        prompt_parts.append(
            "Please select the best matching candidate and respond with the required JSON format."
        )

        return "\n".join(prompt_parts)

    def _parse_selection_response(
        self, response_text: str, num_candidates: int
    ) -> Tuple[Optional[int], float]:
        """Parse LLM selection response.

        Args:
            response_text: Raw LLM response.
            num_candidates: Number of candidates provided.

        Returns:
            Tuple of (selected_index, confidence).

        Raises:
            LLMServiceError: If parsing fails.
        """
        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = response_text

            # Parse JSON
            data = json.loads(json_text)

            selected_index = data.get("selected_index")
            confidence = data["confidence"]

            # Validate selected_index
            if selected_index is not None:
                if not isinstance(selected_index, int):
                    raise LLMServiceError("selected_index must be an integer or null")
                if not (0 <= selected_index < num_candidates):
                    raise LLMServiceError(
                        f"selected_index {selected_index} out of range [0, {num_candidates-1}]"
                    )

            # Validate confidence
            if not isinstance(confidence, (int, float)):
                raise LLMServiceError("confidence must be a number")
            if not (0.0 <= confidence <= 1.0):
                raise LLMServiceError("confidence must be between 0.0 and 1.0")

            return selected_index, float(confidence)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LLMServiceError(f"Failed to parse LLM selection response: {e}")


class OpenAILLMService(BaseLLMService):
    """OpenAI LLM service implementation."""

    async def _make_llm_request(self, system_prompt: str, user_prompt: str) -> str:
        """Make request to OpenAI API.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.

        Returns:
            LLM response text.
        """
        try:
            import openai
        except ImportError:
            raise LLMServiceError("OpenAI package not installed. Install with: pip install openai")

        try:
            # Disable SSL verification for OpenAI client
            import httpx

            http_client = httpx.AsyncClient(verify=False)
            client = openai.AsyncOpenAI(api_key=self._llm_config.api_key, http_client=http_client)

            response = await client.chat.completions.create(
                model=self._llm_config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self._llm_config.max_tokens,
                temperature=self._llm_config.temperature,
                timeout=self._llm_config.timeout,
            )

            content = response.choices[0].message.content
            if content is None:
                raise LLMServiceError("OpenAI API returned empty content")
            return content

        except Exception as e:
            raise LLMServiceError(f"OpenAI API request failed: {e}")


class AnthropicLLMService(BaseLLMService):
    """Anthropic (Claude) LLM service implementation."""

    async def _make_llm_request(self, system_prompt: str, user_prompt: str) -> str:
        """Make request to Anthropic API.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.

        Returns:
            LLM response text.
        """
        try:
            import anthropic
        except ImportError:
            raise LLMServiceError(
                "Anthropic package not installed. Install with: pip install anthropic"
            )

        try:
            # Disable SSL verification for Anthropic client
            import httpx

            http_client = httpx.AsyncClient(verify=False)
            client = anthropic.AsyncAnthropic(
                api_key=self._llm_config.api_key, http_client=http_client
            )

            response = await client.messages.create(
                model=self._llm_config.model,
                max_tokens=self._llm_config.max_tokens,
                temperature=self._llm_config.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                timeout=self._llm_config.timeout,
            )

            content_block = response.content[0]
            if hasattr(content_block, "text"):
                return content_block.text
            else:
                raise LLMServiceError("Anthropic API returned unexpected content type")

        except Exception as e:
            raise LLMServiceError(f"Anthropic API request failed: {e}")
