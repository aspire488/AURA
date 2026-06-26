from __future__ import annotations

import re

from app.memory.memory import MemoryType
from app.observation.observation import Observation, ObservationType


def classify(observation: Observation) -> tuple[MemoryType, float]:
    """Classify an observation into memory type and importance.

    ponytail: deterministic heuristics, no LLM, no embeddings.
    Returns (memory_type, importance 0.0-1.0).
    """
    obs_type = observation.observation_type
    content = observation.summary + " " + str(observation.payload)
    lower = content.lower()
    word_count = len(content.split())

    # --- Importance scoring (adapted from old memory_ranker, normalized to 0.0-1.0) ---
    score = 0.0

    # Observation type signal
    if obs_type == ObservationType.USER_MESSAGE:
        score += 0.15
    elif obs_type == ObservationType.ASSISTANT_RESPONSE:
        score += 0.10
    elif obs_type == ObservationType.TASK:
        score += 0.12
    elif obs_type == ObservationType.REASONING:
        score += 0.10

    # Length signal
    length = len(content)
    if length > 500:
        score += 0.20
    elif length > 200:
        score += 0.15
    elif length > 50:
        score += 0.10
    elif length > 10:
        score += 0.05

    # Question = someone needs an answer
    if "?" in content or re.search(r"\b(what|how|why|when|where|who|can|is|do|does)\b", lower):
        score += 0.15

    # Code block = technical knowledge
    if "```" in content or re.search(r"\b(def |class |import |from |function |const |let |var )\b", content):
        score += 0.15

    # URL = reference material
    if re.search(r"https?://\S+", content):
        score += 0.10

    # Confidence signal from observation
    score += observation.confidence * 0.05

    importance = min(round(score, 2), 1.0)

    # --- Memory type classification ---
    memory_type = _classify_type(obs_type, lower, word_count, importance)

    return memory_type, importance


def _classify_type(
    obs_type: ObservationType,
    lower: str,
    word_count: int,
    importance: float,
) -> MemoryType:
    """Map observation to canonical memory type. ponytail: flat if/elif."""

    # Working: recent conversational turns, low-substance
    if obs_type in (ObservationType.USER_MESSAGE, ObservationType.ASSISTANT_RESPONSE):
        ephemeral_patterns = (
            "hello", "hi", "hey", "ok", "okay", "thanks", "thank you",
            "bye", "goodbye", "sure", "yes", "no", "got it", "understood",
        )
        if word_count <= 3 or lower.rstrip("!.?") in ephemeral_patterns:
            return MemoryType.WORKING
        # Substantive conversation → episodic
        if importance >= 0.3:
            return MemoryType.EPISODIC
        return MemoryType.WORKING

    # Task completion → episodic
    if obs_type == ObservationType.TASK:
        return MemoryType.EPISODIC

    # Reasoning, reflection → semantic
    if obs_type in (ObservationType.REASONING, ObservationType.REFLECTION):
        return MemoryType.SEMANTIC

    # Code, browser, provider execution → semantic if important, historical otherwise
    if obs_type in (ObservationType.CODE_EXECUTION, ObservationType.BROWSER_ACTION, ObservationType.PROVIDER):
        if importance >= 0.4:
            return MemoryType.SEMANTIC
        return MemoryType.HISTORICAL

    # Memory observations → semantic
    if obs_type == ObservationType.MEMORY:
        return MemoryType.SEMANTIC

    # Default: historical
    return MemoryType.HISTORICAL
