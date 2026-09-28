from __future__ import annotations

import os

from langchain_openai import ChatOpenAI


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0,
        api_key=os.getenv("OPENAI_API_KEY"),
        max_retries=2,
        timeout=30,
    )