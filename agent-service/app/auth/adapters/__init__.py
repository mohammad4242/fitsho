from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from ..base import ParsedAuthUpdate
from ..schemas import AuthSafeErrorMessage

_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_URL_PATTERN = re.compile(r"(?i)\b(?:https?|ftp)://[^\s<>\"]+")
_CODE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:user|device|verification|authorization)\s+code\s*[:=]\s*"
        r"([A-Za-z0-9][A-Za-z0-9._-]{3,63})\b"
    ),
    re.compile(
        r"(?i)\b(?:enter|use|copy)\s+(?:this\s+)?"
        r"(?:user\s+|device\s+|verification\s+|authorization\s+)?code\s*[:=]\s*"
        r"([A-Za-z0-9][A-Za-z0-9._-]{3,63})\b"
    ),
)
_SAFE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{3,63}$")
_SUCCESS_PATTERN = re.compile(
    r"(?i)\b(?:login|authentication)\s+successful\b|"
    r"\bsuccessfully\s+(?:logged|signed)\s+in\b"
)
_INPUT_PROMPT_PATTERN = re.compile(
    r"(?i)\b(?:enter|paste|input|provide)\s+(?:the\s+)?"
    r"(?:authorization\s+|verification\s+|device\s+|user\s+)?code\b"
)
_FAILURE_PATTERN = re.compile(
    r"(?i)\b(?:login|authentication|authorization)\s+(?:failed|cancelled|canceled)\b|"
    r"\bnot\s+(?:logged|authenticated)\s+in\b"
)

CODEX_AUTH_HOSTS = frozenset({"auth.openai.com"})
CLAUDE_AUTH_HOSTS = frozenset({"claude.com"})


def strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE.sub("", text)


def parse_browser_handoff(
    text: str,
    *,
    allowed_hosts: frozenset[str],
    include_user_code: bool,
    input_label: str | None = None,
) -> ParsedAuthUpdate:
    clean_text = strip_ansi(text)
    verification_url: str | None = None
    invalid_url = False
    for raw_url in _URL_PATTERN.findall(clean_text):
        candidate = raw_url.rstrip(".,);]}")
        try:
            parsed = urlsplit(candidate)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            invalid_url = True
            continue
        if (
            parsed.scheme.lower() != "https"
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or len(candidate) > 4096
            or (port is not None and not 1 <= port <= 65535)
            or hostname.lower() not in {host.lower() for host in allowed_hosts}
        ):
            invalid_url = True
            continue
        verification_url = candidate
        break

    if invalid_url:
        return _safe_failure()

    user_code = _extract_user_code(clean_text, verification_url) if include_user_code else None
    if _SUCCESS_PATTERN.search(clean_text):
        return ParsedAuthUpdate(authenticated=True)
    if _FAILURE_PATTERN.search(clean_text):
        return _safe_failure()
    if input_label is not None and verification_url is not None and _INPUT_PROMPT_PATTERN.search(
        clean_text
    ):
        return ParsedAuthUpdate(
            verification_url=verification_url,
            user_code=user_code,
            needs_input=True,
            input_label=input_label,
        )
    if verification_url is not None or user_code is not None:
        return ParsedAuthUpdate(verification_url=verification_url, user_code=user_code)
    return ParsedAuthUpdate()


def _extract_user_code(text: str, verification_url: str | None) -> str | None:
    if verification_url is not None:
        try:
            query = parse_qs(urlsplit(verification_url).query, keep_blank_values=False)
        except ValueError:
            query = {}
        for key in ("user_code", "device_code", "verification_code"):
            for value in query.get(key, ()):
                if _SAFE_CODE.fullmatch(value):
                    return value
    for pattern in _CODE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            value = match.group(1)
            if _SAFE_CODE.fullmatch(value):
                return value
    return None


def _safe_failure() -> ParsedAuthUpdate:
    return ParsedAuthUpdate(
        failed=True,
        safe_error_message=AuthSafeErrorMessage.FAILED.value,
    )


__all__ = [
    "CLAUDE_AUTH_HOSTS",
    "CODEX_AUTH_HOSTS",
    "parse_browser_handoff",
    "strip_ansi",
]
