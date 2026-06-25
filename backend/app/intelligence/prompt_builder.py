from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.context_builder import ContextBundle


SYSTEM_PROMPTS = {
    "question": "You are AURA, a helpful assistant. Answer the user's question using the provided context. If the context doesn't contain enough information, say so. Be concise and accurate.",
    "search": "You are AURA, a search assistant. Present the search results clearly. Highlight the most relevant information from the context.",
    "summarize": "You are AURA, a summarization assistant. Provide a clear, concise summary of the information in the context. Focus on key points.",
    "recall": "You are AURA, a memory assistant. Help the user recall past conversations and information. Reference the provided context.",
    "conversation": "You are AURA, a friendly and helpful assistant. Have a natural conversation. Use the context if relevant.",
    "command": "You are AURA, an assistant that executes commands. Acknowledge the command and explain what you will do. Use the context if needed.",
    "unknown": "You are AURA, a helpful assistant. Do your best to understand and respond to the user's message. Use the provided context if relevant.",
}


@dataclass
class PromptBundle:
    system_prompt: str
    context_text: str
    user_prompt: str
    citations: list[str]
    estimated_tokens: int


def _estimate_tokens(text: str) -> int:
    """~4 chars per token. ponytail: same as context_builder."""
    return max(len(text) // 4, 0)


def build_prompt(
    query: str,
    context: ContextBundle,
    intent: str,
) -> PromptBundle:
    """Assemble prompt from query, context, and intent.

    ponytail: string formatting only. No templates, no Jinja, no DSL.
    """
    system = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["unknown"])

    context_parts: list[str] = []
    if context.chunks:
        context_parts.append("## Retrieved Context")
        for i, chunk in enumerate(context.chunks, 1):
            context_parts.append(f"[{i}] {chunk.text}")
        context_parts.append("")
        context_parts.append("## Citations")
        context_parts.append(", ".join(context.citations))

    context_text = "\n".join(context_parts)
    user_prompt = f"Context:\n{context_text}\n\nQuestion: {query}" if context_text else f"Question: {query}"

    total = _estimate_tokens(system) + _estimate_tokens(user_prompt)

    return PromptBundle(
        system_prompt=system,
        context_text=context_text,
        user_prompt=user_prompt,
        citations=context.citations,
        estimated_tokens=total,
    )
