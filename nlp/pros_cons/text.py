"""Text utilities: cleaning, sentence / clause splitting and tokenization."""

from __future__ import annotations

import re


_HTML_BREAK = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_READ_MORE = re.compile(r"\bread more\b\s*$", re.IGNORECASE)
_SPACES = re.compile(r"[ \t\r\f\v]+")

# Sentence boundary: ., ! or ? (possibly repeated) followed by space, or a line break.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Contrast markers start a new clause, because the sentiment usually flips:
# "Keeps water cold all day, but the lid leaks."
_CLAUSE_SPLIT = re.compile(
    r"\s*(?:;|,?\s+\bbut\b|,?\s+\bhowever\b|,?\s+\balthough\b|,?\s+\bthough\b"
    r"|,?\s+\bexcept\b|,?\s+\bwhereas\b|,?\s+\bunfortunately\b)\s*",
    re.IGNORECASE,
)

# A sentence that starts with a contrast word: drop the word itself.
# "However, once inflated they were easy to shape" -> "once inflated they were ..."
_LEADING_MARKER = re.compile(r"^(?:however|but|unfortunately|that said)\b,?\s*", re.IGNORECASE)

# Concessive opening: "While X, Y" / "Although X, Y" usually holds two opposite
# opinions, so X and Y become separate clauses.
_CONCESSIVE = re.compile(r"^(?:while|although|though|even though|even if)\s+([^,]+),\s*(.+)$", re.IGNORECASE)

_TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def clean_text(text: str) -> str:
    """Remove HTML remnants and scraping artifacts, normalize whitespace."""
    text = str(text)
    text = text.replace("’", "'").replace("‘", "'")
    text = _HTML_BREAK.sub("\n", text)
    text = _HTML_TAG.sub(" ", text)
    text = _READ_MORE.sub("", text.strip())
    text = _SPACES.sub(" ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    """Split cleaned text into non-empty sentences."""
    parts = _SENTENCE_SPLIT.split(clean_text(text))
    return [p.strip() for p in parts if p and p.strip()]


def split_clauses(sentence: str) -> list[str]:
    """Split one sentence at contrast markers; keeps clauses with real words."""
    sentence = sentence.strip()
    concessive = _CONCESSIVE.match(sentence)
    if concessive:
        return split_clauses(concessive.group(1)) + split_clauses(concessive.group(2))
    sentence = _LEADING_MARKER.sub("", sentence)
    parts = _CLAUSE_SPLIT.split(sentence)
    return [p.strip(" ,") for p in parts if p and re.search(r"[A-Za-z]", p)]


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens; keeps contractions such as "doesn't" as one token."""
    return _TOKEN.findall(text.lower())
