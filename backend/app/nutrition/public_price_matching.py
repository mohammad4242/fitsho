"""Deterministic conservative matching for public market products."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.nutrition.food_catalogue import normalize_food_alias
from app.nutrition.public_price_sources import PublicProductCandidate

_REJECT_TERMS = {
    "مکمل",
    "پروتئین وی",
    "رستوران",
    "پرس",
    "ساندویچ",
    "خوراک آماده",
    "خوراک",
    "غذای آماده",
    "سرخ شده",
    "کبابی",
    "کوکو",
    "شنیسل",
    "شینسل",
    "سوخاری",
    "پیاز داغ",
    "پاپ کرن",
    "مخصوص پاپ کردن",
    "پفیلا",
    "کچاپ",
    "بوداده",
    "نمک",
    "چاشنی",
    "بذر",
    "گیفت",
    "ماست ساز",
    "کنسرو",
    "پودر",
    "عصاره",
    "طعم",
    "بسته ترکیبی",
    "پک",
    "تخمه",
    "غذای گربه",
    "غذای سگ",
    "خوراک گربه",
    "خوراک سگ",
    "پوچ",
    "سرکه",
    "خشک",
    "چیپس",
    "شیره",
    "دسر",
    "سس",
    "اسنک",
    "ادویه",
    "تخم ",
    "پاستیل",
    "خورش",
    "قیمه",
    "خیارشور",
    "خیار شور",
    "مربا",
    "کمپوت",
    "نوشیدنی",
    "اسپری",
    "برنزه",
    "موسیر",
    "چکیده",
    "پوره کن",
    "خردکن",
    "پوست کن",
    "کره بدن",
    "بالم لب",
    "کرم",
    "لوسیون",
    "شامپو",
    "ماسک",
    "عطر",
    "گل اگزالیس",
    "کفیر",
    "میکروب",
    "گرده شبتاب",
}

_FOOD_SPECIFIC_REJECT_TERMS: dict[str, set[str]] = {
    "بادام": {"بادام هندی"},
    "کره": {"کره بادام", "کره فندق", "کره پسته"},
    "ماست ساده": {"ماست سبزیجات", "ماست میوه"},
}

_FOOD_SPECIFIC_REQUIRED_TERMS: dict[str, set[str]] = {
    "ران مرغ بدون پوست": {"بدون پوست"},
}


@dataclass(frozen=True)
class CanonicalFoodIdentity:
    slug: str
    name_fa: str
    category: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class CandidateMatch:
    accepted: bool
    confidence: Decimal
    matched_alias: str | None
    reason_code: str | None


def _tokens(value: str) -> set[str]:
    normalized = normalize_food_alias(value)
    return {token for token in re.split(r"\s+", normalized) if len(token) > 1}


def match_candidate(
    food: CanonicalFoodIdentity, candidate: PublicProductCandidate
) -> CandidateMatch:
    normalized_title = normalize_food_alias(candidate.title)
    normalized_food_names = " ".join(
        normalize_food_alias(value) for value in (food.name_fa, *food.aliases)
    )
    if any(
        term in normalized_title and term.strip() not in normalized_food_names
        for term in _REJECT_TERMS
    ):
        return CandidateMatch(False, Decimal("0"), None, "IRRELEVANT_PRODUCT")
    if any(
        term in normalized_title
        for term in _FOOD_SPECIFIC_REJECT_TERMS.get(normalize_food_alias(food.name_fa), set())
    ):
        return CandidateMatch(False, Decimal("0"), None, "IRRELEVANT_PRODUCT")
    required_terms = _FOOD_SPECIFIC_REQUIRED_TERMS.get(normalize_food_alias(food.name_fa), set())
    if required_terms and not all(term in normalized_title for term in required_terms):
        return CandidateMatch(False, Decimal("0"), None, "AMBIGUOUS_MATCH")
    aliases = tuple(dict.fromkeys((food.name_fa, *food.aliases)))
    scored: list[tuple[Decimal, str]] = []
    title_tokens = _tokens(normalized_title)
    for alias in aliases:
        normalized_alias = normalize_food_alias(alias)
        alias_tokens = _tokens(normalized_alias)
        if not alias_tokens:
            continue
        if normalized_alias == normalized_title:
            score = Decimal("1")
        elif alias_tokens.issubset(title_tokens):
            score = Decimal("0.92")
        else:
            overlap = Decimal(len(alias_tokens & title_tokens)) / Decimal(len(alias_tokens))
            score = overlap * Decimal("0.8")
        scored.append((score, alias))
    if not scored:
        return CandidateMatch(False, Decimal("0"), None, "NO_ALIAS_MATCH")
    score, alias = max(scored, key=lambda item: (item[0], len(item[1])))
    if score < Decimal("0.90"):
        return CandidateMatch(False, score, alias, "AMBIGUOUS_MATCH")
    return CandidateMatch(True, score, alias, None)
