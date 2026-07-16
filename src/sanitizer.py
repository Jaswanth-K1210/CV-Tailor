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
}

_DASH_CLASS = "[\\-–—]"


def remove_dashes(text: str) -> str:
    text = re.sub(r"(\d)\s*" + _DASH_CLASS + r"\s*(\d)", r"\1 to \2", text)
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
