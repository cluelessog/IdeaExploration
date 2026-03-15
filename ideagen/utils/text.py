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

    # Bracket-counting scan: handles arbitrary nesting depth and arrays
    try:
        return _extract_json_bracket_scan(text)
    except ValueError:
        pass

    raise ValueError(f"No valid JSON found in text: {text[:200]}...")


def _extract_json_bracket_scan(text: str) -> str:
    """Fallback: scan for balanced braces/brackets and try json.loads.

    Correctly skips characters inside JSON strings so that braces or brackets
    within quoted values do not confuse the bracket counter.
    """
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in '{[':
            close = '}' if ch == '{' else ']'
            depth = 0
            j = i
            in_string = False
            escape_next = False
            while j < n:
                c = text[j]
                if escape_next:
                    escape_next = False
                elif c == '\\' and in_string:
                    escape_next = True
                elif c == '"':
                    in_string = not in_string
                elif not in_string:
                    if c == ch:
                        depth += 1
                    elif c == close:
                        depth -= 1
                    if depth == 0:
                        candidate = text[i:j + 1]
                        try:
                            json.loads(candidate)
                            return candidate
                        except json.JSONDecodeError:
                            break
                j += 1
        i += 1
    raise ValueError("No valid JSON found")
