#!/usr/bin/env python3
"""Pick one news type from the keyword classifier and the Gemini classifier.

Gemini proposes up to three topics, each with a verbatim quote. A topic counts
only when that quote matches the same rules the keyword classifier uses for
that type. The chosen type is the first Gemini topic that passes. If none
does, the keyword label is used when the title supports it, otherwise other.

Chart quotes ("situazione tecnica", "chiuso in ribasso") are accepted as
market_report even when they miss the narrower headline patterns.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from classify import _collect_hits, normalise

_CHART = re.compile(
    r"situazione tecnica|tendenza (?:ribassista|rialzista)|"
    r"(?:chiuso|chiude|chiusa) in (?:calo|rialzo|ribasso)|"
    r"resistenza a quota|il titolo prova|il trend rimane",
    re.I,
)


def evidence_supports(label: str, text: str) -> bool:
    if not label or label == "other" or not (text or "").strip():
        return False
    if any(hit[0] == label for hit in _collect_hits(normalise(text))):
        return True
    return label == "market_report" and bool(_CHART.search(normalise(text)))


def choose_news_type(
    keyword_type: str,
    topics: Optional[List[dict]],
    title: str,
) -> Tuple[str, str]:
    """Return (label, reason)."""
    topics = topics or []
    for item in topics:
        label = item.get("topic")
        if evidence_supports(label, item.get("evidence") or ""):
            return label, "gemini_quote"
    if evidence_supports(keyword_type, title):
        return keyword_type, "keyword_title"
    return "other", "unsupported"
