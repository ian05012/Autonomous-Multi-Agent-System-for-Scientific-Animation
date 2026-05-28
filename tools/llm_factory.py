"""
tools/llm_factory.py
--------------------
Factory for creating LangChain ChatOpenAI instances that are compatible with
both standard models (gpt-4o, gpt-4.1) and newer reasoning models (gpt-5,
o1, o3, o4-series) which have different API parameter requirements.

Differences for reasoning models:
  - Use max_completion_tokens instead of max_tokens
  - Temperature must be 1 (fixed by API)
"""
from __future__ import annotations
import os
from langchain_openai import ChatOpenAI

# Model name prefixes that require reasoning-model API parameters
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def _is_reasoning_model(model: str) -> bool:
    return any(model.startswith(p) for p in _REASONING_PREFIXES)


def make_llm(temperature: float = 0) -> ChatOpenAI:
    """Create ChatOpenAI for the current LLM_MODEL env var."""
    model = os.getenv("LLM_MODEL", "gpt-4o")
    if _is_reasoning_model(model):
        return ChatOpenAI(
            model=model,
            temperature=1,
            model_kwargs={"max_completion_tokens": 8192},
        )
    return ChatOpenAI(model=model, temperature=temperature)


def make_animator_llm(temperature: float = 0.2) -> ChatOpenAI:
    """Create ChatOpenAI for the current ANIMATOR_MODEL env var."""
    model = os.getenv("ANIMATOR_MODEL") or os.getenv("LLM_MODEL", "gpt-4o")
    if _is_reasoning_model(model):
        return ChatOpenAI(
            model=model,
            temperature=1,
            model_kwargs={"max_completion_tokens": 8192},
        )
    return ChatOpenAI(model=model, temperature=temperature)
