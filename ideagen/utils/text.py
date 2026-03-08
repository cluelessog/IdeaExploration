from __future__ import annotations
import json
import re


def extract_json(text: str) -> str:
    """Strip markdown code fences and extract JSON from LLM output.

    Handles: ```json ... ```, bare ``` ... ```, leading/trailing whitespace.
    Returns the first valid JSON block found.
    """
    text = text.strip()

    # Try stripping markdown fences: ```json ... ``` or ``` ... ```
    fence_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    matches = re.findall(fence_pattern, text, re.DOTALL)

    for match in matches:
        candidate = match.strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            continue

    # No fenced block found or none valid — try raw text
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Try to find JSON object or array in text
    for pattern in [r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', r'(\[.*\])']:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            candidate = match.group(1)
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No valid JSON found in text: {text[:200]}...")
