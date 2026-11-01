"""Text normalization shared by the seed (search column) and the search query."""

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, strip accents, collapse punctuation into single spaces."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    unaccented = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _NON_ALNUM.sub(" ", unaccented).strip()


def singularize(word: str) -> str:
    """Simple Portuguese plural: `oes` -> `ao`, otherwise drop a final `s`."""
    if word.endswith("oes"):
        return word[:-3] + "ao"
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    """Normalized, singularized words (search column and query use the same rule)."""
    return [singularize(word) for word in normalize(text).split()]
