"""Shared, conservative title-to-instrument matching rules.

The same small set of rules is used by the Python tools and mirrored in the
BigQuery queries.  A title is useful for tape attribution only when it leaves
one listed company after aliases and obvious person/analyst references have
been removed.  In particular, a bare ``Leonardo`` in a story about Leonardo
Maria Del Vecchio is not the aerospace company.

This module intentionally has no catalogue or network dependency.  Callers
provide the rows from ``instruments_info`` (``COD_AZIONE`` and
``DES_AZIONE``, optionally ``COD_ISIN``).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


# The aliases are deliberately short and curated.  Do not turn this into a
# general fuzzy matcher: a false company is more damaging than a missed title.
_ALIAS_GROUPS: Dict[str, Tuple[str, ...]] = {
    "telecom italia": ("telecom italia", "tim"),
    "leonardo": ("leonardo", "finmeccanica"),
    "intesa sanpaolo": ("intesa sanpaolo", "intesa san paolo", "intesa"),
}

_CODE_GROUPS = {
    "OLI": "telecom italia",
    "FINME": "leonardo",
    "AMBR": "intesa sanpaolo",
}

# These catalogue names are common words or first names.  Their appearance in
# a headline is not enough evidence for a listed-company attribution.
_GENERIC_NAMES = {
    "adventure",
    "circle",
    "energy",
    "friends",
    "impianti",
    "maps",
    "pattern",
    "plc",
    "predict",
    "reti",
    "simone",
    "tecno",
}

_ANALYST_VERBS = (
    "vede",
    "vedono",
    "alza",
    "alzano",
    "taglia",
    "tagliano",
    "conferma",
    "confermano",
    "aggiorna",
    "aggiornano",
    "stima",
    "stimano",
    "prevede",
    "prevedono",
    "promuove",
    "boccia",
    "raccomanda",
    "raccomandano",
    "fissa",
    "fissano",
)


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    return re.sub(r"\s+", " ", text).strip()


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalise(text)).strip()


def _canonical(name: str, code: str = "") -> Optional[str]:
    key = _key(name)
    for canonical, aliases in _ALIAS_GROUPS.items():
        if key in aliases:
            return canonical
    code_key = (code or "").strip().upper()
    return _CODE_GROUPS.get(code_key)


def _phrase_pattern(phrase: str) -> re.Pattern:
    """Compile a Unicode-safe whole-phrase pattern.

    Separators are allowed between words so ``Intesa-Sanpaolo`` and the
    newspaper spelling ``Intesa San Paolo`` can be handled by aliases.  The
    expression uses only constructs also available in RE2; the Python
    boundary lookarounds are replaced by explicit character classes in SQL.
    """

    words = re.findall(r"[\w]+", _normalise(phrase), flags=re.UNICODE)
    if not words:
        return re.compile(r"(?!x)x")
    # ``&`` joins real names such as ``B&C Speakers`` and ``Danieli & C``.
    middle = r"[\s\-_/.,'’&+]*".join(re.escape(word) for word in words)
    # Bare ``intesa`` is also the Italian noun for an agreement (``l'intesa``,
    # ``sull'intesa``).  The apostrophe stays attached to that noun so it does
    # not count as the bank.  The full ``Intesa Sanpaolo`` name is unchanged.
    left = r"[\w']" if words == ["intesa"] else r"[\w]"
    return re.compile(rf"(?<!{left}){middle}(?![\w])", re.IGNORECASE | re.UNICODE)


def _aliases(name: str, code: str = "") -> Tuple[str, Tuple[str, ...]]:
    canonical = _canonical(name, code)
    if canonical is not None:
        return canonical, _ALIAS_GROUPS[canonical]
    clean = _normalise(name)
    return clean, (clean,) if clean else ()


def _occurrences(text: str, name: str, code: str = "") -> List[Tuple[int, int, str, str]]:
    canonical, aliases = _aliases(name, code)
    found: List[Tuple[int, int, str, str]] = []
    for alias in sorted(aliases, key=len, reverse=True):
        for match in _phrase_pattern(alias).finditer(text or ""):
            found.append((match.start(), match.end(), alias, canonical))

    # ``Intesa`` is an alias of ``Intesa Sanpaolo``.  Keep only the longest
    # non-overlapping span so one company can never count twice.
    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    selected: List[Tuple[int, int, str, str]] = []
    for item in found:
        if any(item[0] < other[1] and other[0] < item[1] for other in selected):
            continue
        selected.append(item)
    return selected


def _homonym_or_other_company(text: str, start: int, end: int, canonical: str) -> bool:
    if canonical == "telecom italia":
        after_tim = _normalise((text or "")[end : end + 40])
        # Apple executive and the Brazilian carrier are frequent non-MF uses
        # of the short alias.  Keep ordinary Italian ``Tim`` headlines valid.
        return bool(re.match(r"^[\s,;:/()\-]*(?:cook\b|brasil\b)", after_tim))
    if canonical != "leonardo":
        return False
    # Leonardo Maria Del Vecchio, Leonardo jr, Leonardo da Vinci and Leonardo
    # Capital/LMDV are person or other-company names.  The bounded lookahead
    # keeps ``Leonardo, maxi-ordine ...`` a valid company mention.
    after = _normalise((text or "")[end : end + 70])
    if re.match(
        r"^[\s,;:/()\-]*(?:maria(?:\s+del\s+vecchio)?|del\s+vecchio|"
        r"jr\b|j\s*r\b|da\s+vinci\b|capital\b|lmdv\b|group\b|holding\b)",
        after,
    ):
        return True
    # The name generally starts the person span, but cover the inverted form
    # as well when punctuation separates the words.
    before = _normalise((text or "")[max(0, start - 45) : start])
    if re.search(r"(?:maria|del\s+vecchio)\s*[,:-]?\s*$", before):
        return True
    # "l'eredità di Leonardo" in a Del Vecchio story is the person, not the
    # aerospace company. "commessa di Leonardo" without that family name stays.
    return bool(
        re.search(r"\bdi\s*$", before)
        and re.search(r"del\s+vecchio", _normalise(text or ""))
    )


def _analyst_reference(text: str, start: int, end: int) -> bool:
    """Whether this occurrence names a broker/bank speaking about another stock."""

    # Slice first, then normalise.  NFKD can change the number of codepoints,
    # so offsets from a regex match must not be applied to normalised text.
    before = _normalise((text or "")[max(0, start - 100) : start])
    after = _normalise((text or "")[end : end + 100])

    # The firm is the source of the note.  ``rating di Unicredit`` and
    # ``target di Unicredit`` name the company being rated, so they stay.
    if re.search(r"(?:analist\w*|stime)\s+(?:di|da)\s*$", before):
        return True
    if re.search(r"secondo\s*$", before):
        return True

    # ``Intesa vede/alza il target`` — the verb's object is a market call.
    # ``sul titolo`` is ordinary stock wording.  ``target di riduzione`` is
    # an operating goal, not a price target.  The object must sit next to the
    # verb so ``Prysmian aggiorna il record ... Ubs alza il target`` stays.
    verb = "|".join(_ANALYST_VERBS)
    # Bare ``target`` is usually guidance ("alza il target sulle vendite",
    # "conferma i target 2021"). A market call says "target price" or
    # "target sul titolo".
    market = (
        r"(?:target\s+price|target\s+sul\s+titolo|rating|upside|stime|"
        r"valutazion\w*|giudizio|raccomand\w*)"
    )
    call = rf"^[\s,;:/()\-]*(?:{verb})\b(?:\s+\S+){{0,5}}\s+{market}\b"
    return re.match(call, after) is not None


def _valid_occurrences(text: str, name: str, code: str = "") -> List[Tuple[int, int, str, str]]:
    canonical, _ = _aliases(name, code)
    if not canonical or canonical in _GENERIC_NAMES:
        return []
    valid = []
    for occurrence in _occurrences(text, name, code):
        start, end, alias, _ = occurrence
        if _homonym_or_other_company(text, start, end, canonical):
            continue
        if _analyst_reference(text, start, end):
            continue
        valid.append(occurrence)
    return valid


def instrument_matches(title: str, name: str, code: str = "") -> bool:
    """Return whether *title* has a disambiguated mention of this company."""

    return bool(_valid_occurrences(title or "", name or "", code or ""))


def matching_instruments(title: str, instruments: Sequence[dict]) -> List[dict]:
    """Return the sole unambiguous title candidate, preserving its input row.

    Rows sharing a ``COD_AZIONE`` (for example one row per listing/ISIN) are
    deduplicated before the company count.  If two distinct listed companies
    are genuine title mentions, the title is intentionally rejected with an
    empty list; callers must not guess which tape to use.
    """

    candidates: List[dict] = []
    seen_codes = set()
    for instrument in instruments or ():
        name = str(instrument.get("DES_AZIONE") or "").strip()
        code = str(instrument.get("COD_AZIONE") or "").strip()
        if not name or (code and code in seen_codes):
            continue
        if instrument_matches(title or "", name, code):
            candidates.append(instrument)
            if code:
                seen_codes.add(code)
    return candidates if len(candidates) == 1 else []


__all__ = ["instrument_matches", "matching_instruments"]
