from __future__ import annotations

import re

from app.knowledge.knowledge import Knowledge
from app.memory.memory import Memory

# ponytail: regex-based extraction. No LLM, no embeddings, deterministic only.
# Each pattern captures (subject, predicate, object) from memory content.

_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # "I use Python" → (identity, uses, Python)
    (re.compile(r"\b(?:I|i)\s+(use|uses|am using)\s+(.+)", re.I), "uses", "identity"),
    # "I am a developer" → (identity, is, developer)
    (re.compile(r"\b(?:I|i)\s+(?:am|'m)\s+(?:a|an|the)\s+(.+)", re.I), "is", None),
    # "X uses Y" → (X, uses, Y)
    (re.compile(r"(.+?)\s+(use|uses|using)\s+(.+)", re.I), "uses", None),
    # "X is a Y" → (X, is, Y)
    (re.compile(r"(.+?)\s+(?:is|are)\s+(?:a|an|the)\s+(.+)", re.I), "is", None),
    # "X has Y" → (X, has, Y)
    (re.compile(r"(.+?)\s+(?:has|have)\s+(.+)", re.I), "has", None),
    # "X was Y" → (X, was, Y)
    (re.compile(r"(.+?)\s+(?:was|were)\s+(.+)", re.I), "was", None),
    # "X can Y" → (X, can, Y)
    (re.compile(r"(.+?)\s+can\s+(.+)", re.I), "can", None),
    # "X needs Y" → (X, needs, Y)
    (re.compile(r"(.+?)\s+(?:needs?|require)s?\s+(.+)", re.I), "needs", None),
]

# ponytail: ignore these subjects — too vague to be useful facts
_IGNORE_SUBJECTS = {"it", "this", "that", "there", "what", "which", "who", "i"}

# ponytail: strip trailing punctuation from extracted values
_STRIP = re.compile(r"[.,;:!?]+$")


def extract(memory: Memory) -> list[Knowledge]:
    """Extract knowledge triples from memory content. ponytail: regex only, no LLM."""
    text = f"{memory.summary}\n{memory.content}".strip()
    if not text:
        return []

    results: list[Knowledge] = []
    seen: set[tuple[str, str, str]] = set()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        _extract_from_line(line, memory.identity_id, memory.memory_id, results, seen)

    return results


def _extract_from_line(
    line: str,
    identity_id: str,
    memory_id: str,
    results: list[Knowledge],
    seen: set[tuple[str, str, str]],
) -> None:
    matched = False
    for pattern, predicate, identity_marker in _PATTERNS:
        match = pattern.search(line)
        if not match:
            continue
        matched = True
        groups = match.groups()
        if identity_marker == "identity":
            subject = identity_id or "self"
            obj = groups[1] if len(groups) > 1 else groups[0]
        elif identity_marker is None:
            subject = groups[0].strip()
            obj = groups[1].strip() if len(groups) > 1 else ""
        else:
            continue
        subject = _clean(subject)
        obj = _clean(obj)
        if not subject or not obj:
            continue
        if subject.lower() in _IGNORE_SUBJECTS:
            continue
        key = (subject.lower(), predicate, obj.lower())
        if key in seen:
            continue
        seen.add(key)
        results.append(Knowledge(
            identity_id=identity_id,
            source_memory_ids=[memory_id],
            subject=subject,
            predicate=predicate,
            object=obj,
            metadata={"source": "extractor", "pattern": predicate},
        ))
    # ponytail: fallback – if no pattern matched, store the raw line as a statement
    if not matched:
        subject = identity_id or "self"
        predicate = "says"
        obj = _clean(line)
        if obj:
            key = (subject.lower(), predicate, obj.lower())
            if key not in seen:
                seen.add(key)
                results.append(Knowledge(
                    identity_id=identity_id,
                    source_memory_ids=[memory_id],
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    metadata={"source": "fallback"},
                ))

def _clean(value: str) -> str:
    """Strip leading/trailing noise. ponytail: minimal cleanup."""
    value = _STRIP.sub("", value).strip()
    # Remove surrounding quotes
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] in ('"', "'"):
        value = value[1:-1].strip()
    return value
