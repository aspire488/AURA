from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    valid: bool
    warnings: list[str] = field(default_factory=list)
    corrected_text: str = ""


def validate_response(
    answer: str,
    context_text: str = "",
    query: str = "",
) -> ValidationResult:
    """Deterministic response validation.

    ponytail: regex checks, no ML, no embedding similarity.
    Returns corrected_text if minor fixes applied.
    """
    warnings: list[str] = []
    text = answer.strip()

    # Empty output
    if not text:
        return ValidationResult(valid=False, warnings=["Empty response"], corrected_text="")

    # Hallucination indicators: model says it doesn't know
    uncertainty = (
        r"\bi don't (?:have|know|see|have access)\b",
        r"\bi (?:cannot|can't) (?:find|locate|access)\b",
        r"\bno (?:information|data|context)\b",
        r"\bnot (?:available|found|provided)\b",
    )
    for p in uncertainty:
        if re.search(p, text.lower()):
            warnings.append(f"Uncertainty pattern detected: {p}")
            break

    # Duplicate paragraphs
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    seen_paras: set[str] = set()
    dup_paras = []
    for p in paragraphs:
        normalized = re.sub(r"\s+", " ", p.lower())
        if normalized in seen_paras:
            dup_paras.append(p[:50])
        seen_paras.add(normalized)
    if dup_paras:
        warnings.append(f"Duplicate paragraphs: {dup_paras[:3]}")
        # Remove duplicates, keep first occurrence
        deduped: list[str] = []
        seen_dedup: set[str] = set()
        for p in paragraphs:
            normalized = re.sub(r"\s+", " ", p.lower())
            if normalized not in seen_dedup:
                deduped.append(p)
                seen_dedup.add(normalized)
        text = "\n\n".join(deduped)

    # Context leakage: response contains raw context artifacts
    if context_text:
        # Check if response is mostly verbatim from context
        context_words = set(context_text.lower().split())
        answer_words = set(text.lower().split())
        if context_words and answer_words:
            overlap = len(context_words & answer_words) / max(len(answer_words), 1)
            if overlap > 0.9:
                warnings.append("High context overlap — possible copy-paste")

    # Malformed markdown: unclosed code blocks
    code_blocks = re.findall(r"```", text)
    if len(code_blocks) % 2 != 0:
        warnings.append("Unclosed code block detected")
        text += "\n```"  # Close it

    # Malformed markdown: unclosed bold/italic
    bold_open = len(re.findall(r"\*\*(?!\*)", text))
    bold_close = len(re.findall(r"(?<!\*)\*\*(?!\*)", text))
    if bold_open > bold_close:
        warnings.append("Unclosed bold markdown")
        text += "**"

    return ValidationResult(
        valid=len(warnings) == 0 or all("Uncertainty" not in w for w in warnings),
        warnings=warnings,
        corrected_text=text,
    )
