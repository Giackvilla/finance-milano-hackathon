"""Shared story validation and de-duplication helpers.

The pipeline receives the same MF article through more than one source (and
occasionally receives a second content id for a republished headline).  The
helpers in this module operate on article-like mappings and deliberately do
not know about cards, tape rows, or the dashboard schema.  Both the dashboard
export and the statistical pipeline can therefore use the same selection
rule.

``deduplicate_stories`` keeps the earliest publication for a company and
normalised headline within ``window``.  Exact content-id duplicates are
always one story, even if their timestamps are missing or disagree.  When a
merge callback is supplied it is called with the retained and dropped record;
this is useful for carrying a translated card or a chart onto the canonical
record without leaving a dangling detail file.
"""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:  # The matcher is added by the company-matching pipeline.
    from company_matching import instrument_matches, matching_instruments
except ImportError:  # pragma: no cover - only used while developing in isolation
    def instrument_matches(title: str, name: str, code: str = "") -> bool:
        hay = normalize_headline(title)
        needle = normalize_headline(name)
        return bool(needle and re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", hay))

    def matching_instruments(title: str, instruments: Sequence[Mapping[str, Any]]) -> List[dict]:
        return [dict(i) for i in instruments if instrument_matches(
            title, str(i.get("DES_AZIONE") or i.get("des_azione") or ""),
            str(i.get("COD_AZIONE") or i.get("cod_azione") or ""),
        )]


_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_headline(value: Any) -> str:
    """Normalise a headline for duplicate comparison.

    Case, accents, punctuation, quote styles, and whitespace are ignored.
    Digits remain significant, so ``target 10`` and ``target 20`` are not
    silently treated as the same story.
    """
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.casefold().replace("’", "'").replace("–", "-").replace("—", "-")
    text = _PUNCT_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", text).strip()


def parse_publication(value: Any) -> Optional[datetime]:
    """Parse the local publication timestamp used by cards and tape rows."""
    if value in (None, ""):
        return None
    text = str(value).strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:26], fmt)
        except ValueError:
            continue
    return None


def _get(item: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in item and item[name] not in (None, ""):
            return item[name]
    return None


def story_title(item: Mapping[str, Any]) -> str:
    article = item.get("article") if isinstance(item.get("article"), Mapping) else {}
    return str(_get(item, "titolo", "title") or _get(article, "titolo", "title") or "")


def story_publication(item: Mapping[str, Any]) -> Optional[datetime]:
    article = item.get("article") if isinstance(item.get("article"), Mapping) else {}
    return parse_publication(_get(item, "pub_local", "publication", "published_at")
                             or _get(article, "pub_local", "publication", "published_at"))


def story_id(item: Mapping[str, Any]) -> str:
    article = item.get("article") if isinstance(item.get("article"), Mapping) else {}
    return str(_get(item, "content_id", "id") or _get(article, "content_id", "id") or "")


def story_company_key(item: Mapping[str, Any]) -> str:
    """Return a stable company identity, preferring ticker and then ISIN."""
    instrument = item.get("instrument") if isinstance(item.get("instrument"), Mapping) else {}
    code = _get(item, "COD_AZIONE", "cod_azione", "code") or _get(instrument, "COD_AZIONE", "cod_azione", "code")
    isin = _get(item, "COD_ISIN", "isin") or _get(instrument, "COD_ISIN", "isin")
    name = _get(item, "DES_AZIONE", "des_azione", "company", "company_name") or _get(
        instrument, "DES_AZIONE", "des_azione", "company", "company_name"
    )
    if code:
        return "code:" + str(code).strip().casefold()
    if isin:
        return "isin:" + str(isin).strip().casefold()
    return "name:" + normalize_headline(name)


def _default_merge(retained: dict, duplicate: Mapping[str, Any]) -> dict:
    """Merge non-empty nested fields while keeping the canonical identity."""
    for key, value in duplicate.items():
        if key in ("content_id", "id"):
            continue
        if isinstance(value, Mapping) and isinstance(retained.get(key), Mapping):
            _default_merge(retained[key], value)
        elif key not in retained or retained[key] in (None, "", [], {}):
            retained[key] = value
    return retained


def deduplicate_stories(
    items: Iterable[Mapping[str, Any]],
    window: timedelta = timedelta(hours=24),
    merge: Optional[Callable[[dict, Mapping[str, Any]], Any]] = None,
) -> List[dict]:
    """Select canonical records before tape/statistical aggregation.

    Records are ordered by publication time and ``content_id``.  A later
    record is merged into the earliest record when company and normalised
    headline match and the distance from that earliest record is within the
    bounded window.  Missing timestamps only match an identical content id.
    The returned records are fresh dictionaries and deterministic.
    """
    prepared = [dict(x) for x in items]
    prepared.sort(key=lambda x: (story_publication(x) is None,
                                 story_publication(x) or datetime.max,
                                 story_id(x)))
    selected: List[dict] = []
    by_id: Dict[str, dict] = {}
    groups: Dict[Tuple[str, str], List[Tuple[Optional[datetime], dict]]] = {}
    merge_fn = merge or _default_merge

    for item in prepared:
        cid = story_id(item)
        if cid and cid in by_id:
            merge_fn(by_id[cid], item)
            continue
        key = (story_company_key(item), normalize_headline(story_title(item)))
        published = story_publication(item)
        canonical: Optional[dict] = None
        if key[1] and published is not None:
            for first_time, candidate in groups.get(key, []):
                if first_time is not None and published - first_time <= window:
                    canonical = candidate
                    break
        if canonical is None:
            canonical = item
            selected.append(canonical)
            groups.setdefault(key, []).append((published, canonical))
        else:
            merge_fn(canonical, item)
        if cid:
            by_id[cid] = canonical

    selected.sort(key=lambda x: (story_publication(x) is None,
                                 story_publication(x) or datetime.max,
                                 story_id(x)))
    return selected


def catalog_from_rows(rows: Iterable[Mapping[str, Any]]) -> List[dict]:
    """Build a de-duplicated matcher catalog from tape/query rows."""
    out: "OrderedDict[Tuple[str, str, str], dict]" = OrderedDict()
    for row in rows:
        code = str(_get(row, "COD_AZIONE", "cod_azione") or "").strip()
        name = str(_get(row, "DES_AZIONE", "des_azione") or "").strip()
        isin = str(_get(row, "COD_ISIN", "isin") or "").strip()
        if not (code or name or isin):
            continue
        key = (code.casefold(), name.casefold(), isin.casefold())
        out.setdefault(key, {"COD_AZIONE": code, "DES_AZIONE": name, "COD_ISIN": isin or None})
    return list(out.values())


def story_matches_catalog(item: Mapping[str, Any], catalog: Sequence[Mapping[str, Any]]) -> bool:
    """Return whether an already assigned story validly names its company.

    ``matching_instruments`` is the rule for an unassigned title: two real
    companies means no guess.  A cached row already has a company.  Keep it
    when that company is a real mention, even if a counterparty is also named.
    Drop it when the mention is a homonym or the company is only the analyst.
    """
    if not catalog:
        return True
    title = story_title(item)
    instrument = item.get("instrument") if isinstance(item.get("instrument"), Mapping) else {}
    code = str(_get(item, "COD_AZIONE", "cod_azione", "code") or _get(instrument, "COD_AZIONE", "cod_azione", "code") or "")
    name = str(_get(item, "DES_AZIONE", "des_azione", "company", "company_name") or _get(instrument, "DES_AZIONE", "des_azione", "company", "company_name") or "")
    if not name and not code:
        return False
    return instrument_matches(title, name, code)


def filter_valid_stories(items: Iterable[Mapping[str, Any]], catalog: Sequence[Mapping[str, Any]]) -> List[dict]:
    """Drop detail/history records whose title does not name their company."""
    return [dict(item) for item in items if story_matches_catalog(item, catalog)]


__all__ = [
    "catalog_from_rows", "deduplicate_stories", "filter_valid_stories",
    "normalize_headline", "parse_publication", "story_company_key",
    "story_matches_catalog", "story_id", "story_publication", "story_title",
]
