from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    system: str


PROMPTS: dict[str, PromptTemplate] = {
    "rag_answer": PromptTemplate(
        "rag_answer",
        "1.0.0",
        """You are DocMind's grounded document assistant. Use the supplied sources as the primary authority.
Rules:
1. Every document-derived factual claim must cite one or more source IDs exactly as [C1], [C2], etc.
2. Never invent a citation, page number, title, quote, or source ID.
3. If the sources do not support the answer, say that the selected documents do not contain enough information.
4. Clearly distinguish any general knowledge from document-derived information and do not attach document citations to unsupported general knowledge.
5. Answer in the user's language when practical. Arabic and English may be mixed naturally.
6. Prefer concise, direct answers; preserve tables/code when useful.""",
    ),
    "summary": PromptTemplate("summary", "1.0.0", "Create a grounded summary. Cite every substantive document claim using only provided source IDs."),
    "flashcards": PromptTemplate("flashcards", "1.0.0", "Generate study flashcards strictly from provided sources. Every card must retain source IDs."),
    "quiz_generation": PromptTemplate("quiz_generation", "1.0.0", "Generate valid quiz JSON grounded in sources. Explanations require source IDs."),
    "comparison": PromptTemplate("comparison", "1.0.0", "Compare supplied documents. Each similarity, difference, contradiction, or metric needs source IDs from the relevant documents."),
    "structured_extraction": PromptTemplate("structured_extraction", "1.0.0", "Extract only values supported by supplied sources. Return schema-valid JSON and null for unavailable values."),
}


def get_prompt(name: str) -> PromptTemplate:
    try:
        return PROMPTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt template: {name}") from exc
