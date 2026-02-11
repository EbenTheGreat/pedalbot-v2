# Prompts Module
# Centralized location for all PedalBot prompts

from backend.prompts.manual_prompts import (
    PEDALBOT_IDENTITY,
    CONTEXT_TEMPLATE,
    SYSTEM_PROMPT_RESPONSE,
    SYSTEM_PROMPT_PATTERNS,
    is_system_prompt_question,
)

__all__ = [
    "PEDALBOT_IDENTITY",
    "CONTEXT_TEMPLATE", 
    "SYSTEM_PROMPT_RESPONSE",
    "SYSTEM_PROMPT_PATTERNS",
    "is_system_prompt_question",
]
