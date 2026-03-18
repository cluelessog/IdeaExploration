"""Natural language interpreter for IdeaGen CLI commands.

Uses Claude CLI (`claude -p`) to interpret natural language queries
into structured IdeaGen actions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil

from pydantic import BaseModel, Field

from ideagen.core.exceptions import ProviderError

logger = logging.getLogger("ideagen")

# All available WTP segment IDs for the system prompt
_SEGMENT_IDS = (
    "parents, pet_owners, chronic_health, small_business, brides_grooms, "
    "hobbyists, remote_workers, fitness, creators, homeowners, elder_care, "
    "life_transitions, career_seekers, anxious_safety, luxury_status, "
    "neurodivergent, investors, immigrants, fertility, students, legal, "
    "knowledge_workers"
)

_SYSTEM_PROMPT = f"""\
You are a command interpreter for the IdeaGen CLI tool. Given a natural language query,
return a JSON object describing which IdeaGen command to execute.

Available commands and their options:

1. **run** - Run idea generation pipeline
   - domain: "software" (aliases: saas, tech, developer), "business" (aliases: startup, entrepreneur), "content" (aliases: media, creator)
   - source: list of sources to use. Valid: hackernews (aliases: hn, hacker news), reddit, producthunt (aliases: ph, product hunt), twitter (aliases: x, twitter/x)
   - segment: list of WTP segment IDs to target. Valid: {_SEGMENT_IDS}
   - dry_run: boolean - preview without AI calls
   - cached: boolean - reuse last scrape data
   - count: integer - number of ideas to generate (default 10)
   - format: "rich", "json", or "markdown"

2. **history_list** - Show past runs (no arguments)

3. **history_show** - Show details of a specific run
   - run_id: string (run ID or "latest" for most recent)

4. **history_prune** - Delete old runs
   - older_than: string (e.g. "30d")

5. **sources_list** - Show available data sources (no arguments)

6. **sources_test** - Health check all sources (no arguments)

7. **config_show** - Show current configuration (no arguments)

8. **config_init** - Create default configuration file (no arguments)

9. **compare** - Compare two runs
   - run1: string (run ID)
   - run2: string (run ID)

Respond with ONLY a JSON object (no markdown fences, no explanation):
{{
  "command": "<command_name>",
  "args": {{}},
  "explanation": "<brief human-readable description of what will be done>",
  "confidence": <float 0.0-1.0>
}}

Rules:
- Map aliases to canonical values (e.g. "hn" -> "hackernews", "saas" -> "software")
- If the user says "last run" or "most recent run", use history_show with run_id="latest"
- If the user says "last two runs" or "compare recent", use compare with run1="latest" and run2="previous"
- Default domain is "software" if not specified
- confidence should reflect how certain you are about the interpretation
- If the query is ambiguous or doesn't match any command, still give your best guess but with low confidence
"""


class NLAction(BaseModel):
    """Structured action parsed from natural language input."""

    command: str = Field(description="The IdeaGen command to execute")
    args: dict = Field(default_factory=dict, description="Command arguments")
    explanation: str = Field(description="Human-readable explanation of the action")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")


class NLInterpreter:
    """Interprets natural language queries into IdeaGen CLI actions.

    Uses the Claude CLI in piped mode (`claude -p --output-format json`)
    to parse user intent into structured NLAction objects.
    """

    def __init__(self, timeout: float = 60.0) -> None:
        self._timeout = timeout

    async def interpret(self, query: str) -> NLAction:
        """Interpret a natural language query into a structured action.

        Args:
            query: The user's natural language input.

        Returns:
            NLAction with the interpreted command and arguments.

        Raises:
            ProviderError: If the Claude CLI is not available or fails.
        """
        if not shutil.which("claude"):
            raise ProviderError(
                "Claude CLI not found. Install Claude Code: "
                "https://docs.anthropic.com/en/docs/claude-code"
            )

        cmd = [
            "claude",
            "-p",
            "--output-format", "json",
        ]

        full_prompt = f"{_SYSTEM_PROMPT}\n\nUser query: {query}"

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode("utf-8")),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass
            raise ProviderError(f"Claude CLI timed out after {self._timeout}s")
        except Exception as e:
            raise ProviderError(f"Claude CLI subprocess error: {e}")

        if proc.returncode != 0:
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            raise ProviderError(
                f"Claude CLI exited with code {proc.returncode}: {stderr_text[:500]}"
            )

        stdout_text = stdout_bytes.decode("utf-8")

        # Claude --output-format json wraps response in a JSON envelope
        try:
            envelope = json.loads(stdout_text)
            if isinstance(envelope, dict) and "result" in envelope:
                raw_text = envelope["result"]
            elif isinstance(envelope, dict) and "content" in envelope:
                raw_text = envelope["content"]
            else:
                raw_text = stdout_text
        except json.JSONDecodeError:
            raw_text = stdout_text

        # Extract JSON from the response text
        raw_text = raw_text.strip()

        # Strip markdown code fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw_text = "\n".join(lines)

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ProviderError(f"Failed to parse NL interpretation response: {e}")

        try:
            return NLAction.model_validate(data)
        except Exception as e:
            raise ProviderError(f"Invalid NL action structure: {e}")
