import re
from collections import Counter

STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "i",
    "we", "you", "he", "she", "they", "my", "our", "your", "their", "me",
    "us", "them", "who", "which", "will", "would", "can", "could", "should",
    "has", "have", "had", "do", "does", "did", "not", "no", "so", "if",
    "than", "then", "there", "here", "up", "out", "over", "into", "about",
    "seeking", "looking", "want", "need", "required", "must", "prefer",
    "ability", "work", "team", "company", "role", "position", "job",
}

_DASH_CLASS = "[\\-–—]"

# Genuine ranges that should read as "to". Phone numbers (e.g. 555-9876 or
# 555-123-4567) deliberately don't match any of these, so their dashes just
# become spaces instead of turning into "555 to 9876".
_YEAR_RANGE = re.compile(r"\b(\d{4})\s*" + _DASH_CLASS + r"\s*(\d{4})\b")
_YEAR_TO_PRESENT = re.compile(
    r"\b(\d{4})\s*" + _DASH_CLASS + r"\s*(present|current|now)\b", re.IGNORECASE)
_SMALL_RANGE = re.compile(r"\b(\d{1,2})\s*" + _DASH_CLASS + r"\s*(\d{1,2})\b")


def remove_dashes(text: str) -> str:
    text = _YEAR_RANGE.sub(r"\1 to \2", text)
    text = _YEAR_TO_PRESENT.sub(lambda m: f"{m.group(1)} to {m.group(2)}", text)
    text = _SMALL_RANGE.sub(r"\1 to \2", text)
    text = re.sub(_DASH_CLASS, " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def has_dashes(text: str) -> bool:
    return bool(re.search(_DASH_CLASS, text))


def find_repeated_words(text: str, protected: set[str], threshold: int = 4) -> list[str]:
    protected_lower = {w.lower() for w in protected}
    words = re.findall(r"[a-zA-Z]+", text.lower())
    counts = Counter(
        w for w in words
        if w not in STOPWORDS and w not in protected_lower and len(w) > 2
    )
    flagged = [w for w, c in counts.items() if c >= threshold]
    return sorted(flagged, key=lambda w: counts[w], reverse=True)
