from enum import StrEnum


class ZenApiKind(StrEnum):
    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"
    MESSAGES = "messages"
    GEMINI = "gemini"
