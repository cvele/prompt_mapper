"""LLM service implementations."""

import json
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from ...config.models import Config
from ...infrastructure.logging import LoggerMixin
from ...utils import (
    LLMServiceError,
    clean_filename,
    extract_language_hints,
    extract_year_from_filename,
)
from ..interfaces import ILLMService
from ..models import FileInfo, LLMResponse


class BaseLLMService(ILLMService, LoggerMixin, ABC):
    """Base LLM service with common functionality."""

    def __init__(self, config: Config):
        """Initialize LLM service.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._llm_config = config.llm

    async def resolve_movies_batch(
        self, movies_data: List[Dict[str, Any]], user_prompt: str
    ) -> List[LLMResponse]:
        """Resolve movie information for multiple movies in a single LLM request.

        Args:
            movies_data: List of movie data dictionaries, each containing:
                - file_info: List[FileInfo] - File information objects
                - context: str - Additional context information
            user_prompt: User-provided prompt for resolution guidance.

        Returns:
            List of LLM responses with movie resolutions, one per input movie.

        Raises:
            LLMServiceError: If LLM request fails.
        """
        try:
            if not movies_data:
                return []

            # Create system prompt for batch processing
            system_prompt = self._create_batch_system_prompt()

            # Create user prompt with all movies
            full_user_prompt = self._create_batch_user_prompt(movies_data, user_prompt)

            # Make LLM request
            response_text = await self._make_llm_request(system_prompt, full_user_prompt)

            # Parse batch response
            llm_responses = self._parse_batch_response(response_text, len(movies_data))

            self.logger.info(f"LLM resolved {len(llm_responses)} movies in batch")
            return llm_responses

        except Exception as e:
            error_msg = f"LLM batch resolution failed: {e}"
            self.logger.error(error_msg)
            raise LLMServiceError(error_msg) from e

    def validate_response(self, response: str) -> bool:
        """Validate LLM response format.

        Args:
            response: Raw LLM response.

        Returns:
            True if response is valid, False otherwise.
        """
        try:
            self._parse_response(response)
            return True
        except Exception:
            return False

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

    def _prepare_input_data(self, file_info: List[FileInfo], context: str) -> Dict[str, Any]:
        """Prepare input data for LLM.

        Args:
            file_info: List of file information.
            context: Additional context.

        Returns:
            Prepared input data.
        """
        # Get main video file (largest)
        main_file = max(file_info, key=lambda f: f.size_bytes) if file_info else None

        input_data: Dict[str, Any] = {"context": context, "files": []}

        for file in file_info:
            # Clean filename for analysis
            clean_name = clean_filename(file.name)

            file_data = {
                "name": file.name,
                "clean_name": clean_name,
                "directory": file.directory_name,
                "size_mb": round(file.size_mb, 1),
                "is_main": file == main_file,
                "extracted_year": extract_year_from_filename(file.name),
                "language_hints": extract_language_hints(file.name),
            }
            input_data["files"].append(file_data)

        return input_data

    def _create_batch_system_prompt(self) -> str:
        """Create system prompt for batch LLM processing.

        Returns:
            System prompt text for batch processing.
        """
        return """You are a movie identification expert. Analyze the provided file information for multiple movies and extract canonical movie details for each.

IMPORTANT: You must respond with valid JSON array containing movie objects in exactly this format:
[
    {
        "canonical_title": "string",
        "year": integer_or_null,
        "aka_titles": ["string_array"],
        "language_hints": ["string_array"],
        "confidence": float_between_0_and_1,
        "rationale": "string",
        "director": "string_or_null",
        "genre_hints": ["string_array"],
        "edition_notes": "string_or_null"
    },
    ...
]

Rules:
- canonical_title: The most widely recognized English title
- year: Release year (prefer theatrical release)
- aka_titles: Alternative titles, translated titles, or regional variations
- language_hints: ISO language codes (en, es, fr, etc.)
- confidence: Your confidence in the identification (0.0-1.0)
- rationale: Brief explanation of your reasoning
- director: Director name if clearly identifiable
- genre_hints: Likely genres based on title/context
- edition_notes: Special edition info (Director's Cut, Extended, etc.)

The response array must contain exactly the same number of movie objects as provided in the input, in the same order.
Focus on accuracy over speed. If uncertain, lower the confidence score."""

    def _create_user_prompt(self, input_data: Dict[str, Any], user_prompt: str) -> str:
        """Create user prompt with file data.

        Args:
            input_data: Prepared input data.
            user_prompt: User-provided prompt.

        Returns:
            Complete user prompt.
        """
        prompt_parts = []

        # Add user guidance
        if user_prompt:
            prompt_parts.append(f"User guidance: {user_prompt}")
            prompt_parts.append("")

        # Add context if provided
        if input_data.get("context"):
            prompt_parts.append(f"Additional context: {input_data['context']}")
            prompt_parts.append("")

        # Add file information
        prompt_parts.append("Files to analyze:")
        for file_data in input_data["files"]:
            file_desc = f"- {file_data['name']}"
            if file_data["is_main"]:
                file_desc += " (main file)"
            file_desc += f" [{file_data['size_mb']}MB]"

            if file_data["directory"] != file_data["name"]:
                file_desc += f" in folder: {file_data['directory']}"

            if file_data["extracted_year"]:
                file_desc += f" (extracted year: {file_data['extracted_year']})"

            if file_data["language_hints"]:
                file_desc += f" (languages: {', '.join(file_data['language_hints'])})"

            prompt_parts.append(file_desc)

        prompt_parts.append("")
        prompt_parts.append("Please identify this movie and respond with the required JSON format.")

        return "\n".join(prompt_parts)

    def _create_batch_user_prompt(self, movies_data: List[Dict[str, Any]], user_prompt: str) -> str:
        """Create batch user prompt with multiple movies data.

        Args:
            movies_data: List of movie data dictionaries.
            user_prompt: User-provided prompt.

        Returns:
            Complete batch user prompt.
        """
        prompt_parts = []

        # Add user guidance
        if user_prompt:
            prompt_parts.append(f"User guidance: {user_prompt}")
            prompt_parts.append("")

        # Add movies information
        prompt_parts.append(f"Process these {len(movies_data)} movies:")
        prompt_parts.append("")

        for i, movie_data in enumerate(movies_data, 1):
            file_info = movie_data["file_info"]
            context = movie_data.get("context", "")

            # Prepare input data for this movie
            input_data = self._prepare_input_data(file_info, context)

            prompt_parts.append(f"Movie {i}:")

            # Add context if provided
            if input_data.get("context"):
                prompt_parts.append(f"  Context: {input_data['context']}")

            # Add file information
            prompt_parts.append("  Files:")
            for file_data in input_data["files"]:
                file_desc = f"    - {file_data['name']}"
                if file_data["is_main"]:
                    file_desc += " (main file)"
                file_desc += f" [{file_data['size_mb']}MB]"

                if file_data["directory"] != file_data["name"]:
                    file_desc += f" in folder: {file_data['directory']}"

                if file_data["extracted_year"]:
                    file_desc += f" (extracted year: {file_data['extracted_year']})"

                if file_data["language_hints"]:
                    file_desc += f" (languages: {', '.join(file_data['language_hints'])})"

                prompt_parts.append(file_desc)

            prompt_parts.append("")

        prompt_parts.append(
            "Please identify each movie and respond with a JSON array containing movie objects in the required format, maintaining the same order as the input."
        )

        return "\n".join(prompt_parts)

    def _parse_response(self, response_text: str) -> LLMResponse:
        """Parse LLM response into structured format.

        Args:
            response_text: Raw LLM response.

        Returns:
            Parsed LLM response.

        Raises:
            LLMServiceError: If parsing fails.
        """
        try:
            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = response_text

            # Parse JSON
            data = json.loads(json_text)

            # Create LLMResponse with validation
            return LLMResponse(
                canonical_title=data["canonical_title"],
                year=data.get("year"),
                aka_titles=data.get("aka_titles", []),
                language_hints=data.get("language_hints", []),
                confidence=data["confidence"],
                rationale=data["rationale"],
                director=data.get("director"),
                genre_hints=data.get("genre_hints", []),
                edition_notes=data.get("edition_notes"),
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LLMServiceError(f"Failed to parse LLM response: {e}")

    def _parse_batch_response(self, response_text: str, expected_count: int) -> List[LLMResponse]:
        """Parse batch LLM response into structured format.

        Args:
            response_text: Raw LLM response containing JSON array.
            expected_count: Expected number of movie responses.

        Returns:
            List of parsed LLM responses.

        Raises:
            LLMServiceError: If parsing fails.
        """
        try:
            # Extract JSON array from response (in case there's extra text)
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                json_text = response_text

            # Parse JSON array
            data_array = json.loads(json_text)

            if not isinstance(data_array, list):
                raise LLMServiceError("Expected JSON array in batch response")

            if len(data_array) != expected_count:
                raise LLMServiceError(
                    f"Expected {expected_count} movies in response, got {len(data_array)}"
                )

            # Create LLMResponse objects with validation
            responses = []
            for i, data in enumerate(data_array):
                try:
                    response = LLMResponse(
                        canonical_title=data["canonical_title"],
                        year=data.get("year"),
                        aka_titles=data.get("aka_titles", []),
                        language_hints=data.get("language_hints", []),
                        confidence=data["confidence"],
                        rationale=data["rationale"],
                        director=data.get("director"),
                        genre_hints=data.get("genre_hints", []),
                        edition_notes=data.get("edition_notes"),
                    )
                    responses.append(response)
                except (KeyError, TypeError) as e:
                    raise LLMServiceError(f"Failed to parse movie {i+1} in batch response: {e}")

            return responses

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise LLMServiceError(f"Failed to parse batch LLM response: {e}")


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
