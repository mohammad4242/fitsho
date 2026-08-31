"""Structured, privacy-preserving request logging for the agent service."""

import json
import logging
from collections.abc import Mapping
from typing import Any

_LOGGER = logging.getLogger("fitsho.agent_service")
_ALLOWED_FIELDS = frozenset(
    {
        "request_id",
        "agent",
        "model",
        "endpoint",
        "task_kind",
        "duration_ms",
        "status",
        "error_code",
        "input_bytes",
        "image_count",
        "input_tokens",
        "output_tokens",
    }
)


def build_log_record(**fields: Any) -> dict[str, Any]:
    """Return a record containing only the explicitly approved telemetry fields."""

    return {key: value for key, value in fields.items() if key in _ALLOWED_FIELDS}


def emit_log(fields: Mapping[str, Any], *, logger: logging.Logger = _LOGGER) -> None:
    """Write one JSON object after applying the telemetry allowlist."""

    record = build_log_record(**dict(fields))
    logger.info(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
