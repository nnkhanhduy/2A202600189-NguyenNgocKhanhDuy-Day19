from __future__ import annotations

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL


class LLMNotConfiguredError(RuntimeError):
    pass


def generate_answer(question: str, context: str, mode: str) -> str:
    if not OPENAI_API_KEY or OPENAI_API_KEY == "your_openai_api_key_here":
        raise LLMNotConfiguredError("Missing OPENAI_API_KEY. Add it to .env before running LLM generation.")

    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You answer questions using only the provided context. "
                    "If the context does not contain enough information, say so. "
                    "Be concise and include the key entities or graph path when relevant."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Mode: {mode}\n\n"
                    f"Question:\n{question}\n\n"
                    f"Context:\n{context}\n\n"
                    "Final answer:"
                ),
            },
        ],
    )
    return response.choices[0].message.content.strip()
