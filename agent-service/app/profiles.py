"""Allow-listed model/reasoning profiles exposed by Agent Service.

The public API deals in opaque profile IDs.  Runner implementations receive a
resolved model and effort only after this catalog has accepted the ID.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

from .schemas import AgentModelProfile, AgentName, AgentTaskKind, ReasoningEffort

__all__ = [
    "AgentModelProfile",
    "AgentName",
    "AgentTaskKind",
    "ReasoningEffort",
    "ProfileCatalog",
    "ResolvedProfile",
    "antigravity_profiles_from_output",
    "claude_profiles",
    "codex_profiles",
    "legacy_profile",
    "profile_id_for",
]


@dataclass(frozen=True)
class ResolvedProfile:
    profile: AgentModelProfile
    model_id: str
    effort: ReasoningEffort | None


def profile_id_for(
    agent: AgentName, model_id: str, effort: ReasoningEffort | str | None = None
) -> str:
    """Return a deterministic, shell-safe identifier for a profile."""

    model = re.sub(r"[^a-z0-9._-]+", "-", model_id.strip().lower()).strip("-")
    effort_value = effort.value if isinstance(effort, ReasoningEffort) else effort
    suffix = (
        f"-{effort_value}"
        if effort_value and not model.endswith(f"-{effort_value}")
        else ""
    )
    return f"{agent.value}-{model}{suffix}"


def legacy_profile(
    agent: AgentName,
    model_id: str,
    *,
    version: str | None = None,
    supports_text_input: bool = True,
    supports_image_input: bool = False,
    supports_structured_output: bool = True,
    supports_live_web: bool = False,
) -> AgentModelProfile:
    """Represent an old model-only client request during the contract transition."""

    return _profile(
        agent=agent,
        model_id=model_id,
        display_name=model_id,
        effort=None,
        version=version,
        supports_image_input=supports_image_input,
        supports_text_input=supports_text_input,
        supports_structured_output=supports_structured_output,
        task_kinds=tuple(
            kind for kind in AgentTaskKind if kind is not AgentTaskKind.FOOD_PRICE_SEARCH
        ),
        supports_live_web=supports_live_web,
    )


def _fingerprint(
    *,
    agent: AgentName,
    version: str | None,
    profile_id: str,
    model_id: str,
    effort: ReasoningEffort | None,
    task_kinds: Iterable[AgentTaskKind],
    supports_image_input: bool,
    supports_live_web: bool,
) -> str:
    material = "|".join(
        (
            agent.value,
            version or "unknown",
            profile_id,
            model_id,
            effort.value if effort else "none",
            ",".join(kind.value for kind in task_kinds),
            str(supports_image_input),
            str(supports_live_web),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _profile(
    *,
    agent: AgentName,
    model_id: str,
    display_name: str,
    effort: ReasoningEffort | None,
    version: str | None,
    supports_text_input: bool = True,
    supports_image_input: bool = False,
    supports_structured_output: bool = True,
    supports_live_web: bool = False,
    task_kinds: tuple[AgentTaskKind, ...] | None = None,
) -> AgentModelProfile:
    requested_kinds = task_kinds if task_kinds is not None else tuple(AgentTaskKind)
    kinds = tuple(
        kind
        for kind in requested_kinds
        if supports_live_web or kind is not AgentTaskKind.FOOD_PRICE_SEARCH
    )
    if not kinds:
        raise ValueError("a profile must support at least one task")
    identifier = profile_id_for(agent, model_id, effort)
    return AgentModelProfile(
        profile_id=identifier,
        agent=agent,
        display_name=display_name,
        model_id=model_id,
        effort=effort,
        task_kinds=kinds,
        fingerprint=_fingerprint(
            agent=agent,
            version=version,
            profile_id=identifier,
            model_id=model_id,
            effort=effort,
            task_kinds=kinds,
            supports_image_input=supports_image_input,
            supports_live_web=supports_live_web,
        ),
        supports_text_input=supports_text_input,
        supports_image_input=supports_image_input,
        supports_structured_output=supports_structured_output,
        supports_live_web=supports_live_web,
    )


_MODEL_ROW = re.compile(
    r"(?m)^\s*((?:gemini|claude|gpt)[a-z0-9._-]*)\s+([^\r\n]+?)\s*$",
    re.IGNORECASE,
)
_MODEL_ID = re.compile(r"^(?:gemini|claude|gpt)[a-z0-9._-]*$", re.IGNORECASE)


def antigravity_profiles_from_output(
    output: str,
    *,
    version: str | None,
    supports_image_input: bool = False,
) -> tuple[AgentModelProfile, ...]:
    """Parse only the simple model table emitted by ``agy models``."""

    parsed: list[AgentModelProfile] = []
    seen: set[str] = set()
    for match in _MODEL_ROW.finditer(output):
        model_id = match.group(1).strip()
        if not _MODEL_ID.fullmatch(model_id) or model_id in seen:
            continue
        seen.add(model_id)
        parsed.append(
            _profile(
                agent=AgentName.ANTIGRAVITY,
                model_id=model_id,
                display_name=match.group(2).strip()[:300],
                effort=_effort_from_model_id(model_id),
                version=version,
                supports_image_input=supports_image_input,
                supports_live_web=True,
            )
        )
    return tuple(parsed)


def _effort_from_model_id(model_id: str) -> ReasoningEffort | None:
    suffix = model_id.rsplit("-", 1)[-1].lower()
    return {
        "low": ReasoningEffort.LOW,
        "medium": ReasoningEffort.MEDIUM,
        "high": ReasoningEffort.HIGH,
        "thinking": ReasoningEffort.THINKING,
    }.get(suffix)


def codex_profiles(
    *, version: str | None, configured_models: tuple[str, ...], supports_image_input: bool
) -> tuple[AgentModelProfile, ...]:
    models = configured_models or ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
    return tuple(
        _profile(
            agent=AgentName.CODEX,
            model_id=model,
            display_name=f"Codex {model} ({effort.value.title()})",
            effort=effort,
            version=version,
            supports_image_input=supports_image_input,
            supports_live_web=True,
        )
        for model in models
        for effort in (ReasoningEffort.LOW, ReasoningEffort.MEDIUM, ReasoningEffort.HIGH)
    )


def claude_profiles(
    *, version: str | None, configured_models: tuple[str, ...], supports_image_input: bool
) -> tuple[AgentModelProfile, ...]:
    models = configured_models or ("claude-sonnet-4-6", "claude-opus-4-6-thinking")
    profiles: list[AgentModelProfile] = []
    for model in models:
        effort = ReasoningEffort.THINKING if "thinking" in model else None
        profiles.append(
            _profile(
                agent=AgentName.CLAUDE,
                model_id=model,
                display_name=model,
                effort=effort,
                version=version,
                supports_image_input=supports_image_input,
                supports_live_web=True,
            )
        )
    return tuple(profiles)


class ProfileCatalog:
    def __init__(self, profiles: Iterable[AgentModelProfile] = ()) -> None:
        self._profiles = {profile.profile_id: profile for profile in profiles}

    def profiles(self, agent: AgentName | None = None) -> tuple[AgentModelProfile, ...]:
        values = tuple(self._profiles.values())
        if agent is not None:
            values = tuple(profile for profile in values if profile.agent is agent)
        return tuple(sorted(values, key=lambda profile: profile.profile_id))

    def resolve(self, agent: AgentName, profile_id: str) -> ResolvedProfile:
        profile = self._profiles.get(profile_id)
        if profile is None or profile.agent is not agent:
            raise KeyError(profile_id)
        return ResolvedProfile(profile=profile, model_id=profile.model_id, effort=profile.effort)
